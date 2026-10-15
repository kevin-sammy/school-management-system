"""Real in-app school inbox. No external email is sent by this module."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, abort, flash
from flask_login import current_user
from app import db
from app.models import (User,Parent,Student,StudentAccount,TeachingClass,Staff,
    TransportRoute,TransportPassenger,SchoolConversation,MailParticipant,SchoolMessage)
from app.routes.portal import roles,student_profile,academic_classes,text,integer
from app.people import profile_names

mail_bp=Blueprint('mail',__name__,url_prefix='/mail')


def contacts():
    ids={u.id for u in User.query.filter_by(role='admin').all()}
    if current_user.role=='admin':
        return User.query.filter(User.id!=current_user.id).order_by(User.username).all()
    if current_user.role=='teacher':
        courses=TeachingClass.query.filter_by(teacher_id=current_user.id).all()
        conditions=[db.and_(Student.class_name==c.class_name,db.func.coalesce(Student.stream,'')==c.stream) for c in courses]
        students=Student.query.filter(db.or_(*conditions)).all() if conditions else []
        staff_ids=[s.id for s in Staff.query.filter_by(user_id=current_user.id,status='active').all()]
        route_children=Student.query.join(TransportPassenger).join(TransportRoute).filter(TransportRoute.teacher_id.in_(staff_ids)).all()
        student_ids={s.id for s in students+route_children}
        ids.update(a.user_id for a in StudentAccount.query.filter(StudentAccount.student_id.in_(student_ids)).all())
        parent_ids={s.parent_id for s in students+route_children if s.parent_id}
        ids.update(p.user_id for p in Parent.query.filter(Parent.id.in_(parent_ids),Parent.user_id.isnot(None)).all())
    else:
        if current_user.role=='student':
            students=[student_profile()]
        else:
            parents=Parent.query.filter_by(user_id=current_user.id).all()
            students=Student.query.filter(Student.parent_id.in_([p.id for p in parents])).all()
        for student in students:
            ids.update(c.teacher_id for c in academic_classes(student))
            passenger=TransportPassenger.query.filter_by(student_id=student.id).first()
            if passenger and passenger.route.teacher.user_id:
                ids.add(passenger.route.teacher.user_id)
    ids.discard(None)
    ids.discard(current_user.id)
    return User.query.filter(User.id.in_(ids)).order_by(User.username).all()


@mail_bp.route('/')
@roles('admin','teacher','student','parent')
def index():
    memberships=MailParticipant.query.filter_by(user_id=current_user.id).all()
    rows=[]
    users={current_user.id:current_user}
    for membership in memberships:
        conversation=membership.conversation
        latest=conversation.messages[-1] if conversation.messages else None
        if latest is None:
            continue
        people=[p.user for p in conversation.participants if p.user_id!=current_user.id]
        users.update({u.id:u for u in people})
        rows.append(dict(conversation=conversation,latest=latest,people=people,
            unread=membership.last_read_at is None or membership.last_read_at<latest.created_at))
    rows.sort(key=lambda row:row['latest'].created_at,reverse=True)
    return render_template('mail/index.html',rows=rows,names=profile_names(list(users.values())))


@mail_bp.route('/compose',methods=['GET','POST'])
@roles('admin','teacher','student','parent')
def compose():
    recipients=contacts()
    if request.method=='POST':
        subject,body=text('subject',150),text('body',20000)
        audience=request.form.get('audience','individual')
        if audience!='individual':
            if current_user.role!='admin' or audience not in ['teachers','students','parents','all']:
                abort(403)
            role={'teachers':'teacher','students':'student','parents':'parent'}.get(audience)
            selected=[u for u in recipients if role is None or u.role==role]
        else:
            recipient_id=integer('recipient_id')
            selected=[u for u in recipients if u.id==recipient_id]
            if not selected:
                abort(403)
        if not selected:
            flash('No accounts match this audience.','warning')
            return redirect(url_for('mail.compose'))
        # One private thread per recipient; group messages expose no other families.
        now=datetime.utcnow()
        for recipient in selected:
            conversation=SchoolConversation(subject=subject)
            db.session.add(conversation)
            db.session.flush()
            db.session.add_all([MailParticipant(conversation_id=conversation.id,user_id=current_user.id,last_read_at=now),
                MailParticipant(conversation_id=conversation.id,user_id=recipient.id),
                SchoolMessage(conversation_id=conversation.id,sender_id=current_user.id,body=body,created_at=now)])
        db.session.commit()
        flash(f'Message delivered to {len(selected)} school inbox(es).','success')
        return redirect(url_for('mail.index'))
    return render_template('mail/compose.html',recipients=recipients,names=profile_names(recipients))


@mail_bp.route('/<int:conversation_id>',methods=['GET','POST'])
@roles('admin','teacher','student','parent')
def thread(conversation_id):
    membership=MailParticipant.query.filter_by(conversation_id=conversation_id,user_id=current_user.id).first()
    if membership is None:
        abort(403)
    conversation=membership.conversation
    if request.method=='POST':
        db.session.add(SchoolMessage(conversation_id=conversation.id,sender_id=current_user.id,body=text('body',20000)))
        db.session.flush()
    membership.last_read_at=datetime.utcnow()
    db.session.commit()
    users=[p.user for p in conversation.participants]
    if request.method=='POST':
        return redirect(url_for('mail.thread',conversation_id=conversation.id))
    return render_template('mail/thread.html',conversation=conversation,names=profile_names(users))
