"""Read-only family records and administrator dashboard previews."""
from flask import Blueprint, render_template, request, abort
from flask_login import current_user
from app import db
from app.models import User, Parent, Student, Attendance, FeeRecord, Grade, Notification, TeachingClass, Lesson, StudentAccount
from app.routes.portal import roles

family_bp = Blueprint('family', __name__, url_prefix='/family')


def family_context(viewer):
    guardians = Parent.query.filter_by(user_id=viewer.id).all()
    children = Student.query.filter(Student.parent_id.in_([p.id for p in guardians])).order_by(Student.first_name).all()
    selected = request.args.get('student_id')
    if selected is not None:
        try:
            student_id = int(selected)
        except ValueError:
            abort(400)
        child = next((s for s in children if s.id == student_id), None)
        if child is None:
            abort(403)
    else:
        child = children[0] if children else None
    attendance = Attendance.query.filter_by(student_id=child.id).order_by(Attendance.date.desc()).limit(60).all() if child else []
    fees = FeeRecord.query.filter_by(student_id=child.id).order_by(FeeRecord.date.desc(), FeeRecord.id.desc()).all() if child else []
    grades = Grade.query.filter_by(student_id=child.id).order_by(Grade.year.desc(), Grade.created_at.desc()).all() if child else []
    courses = TeachingClass.query.filter_by(class_name=child.class_name, stream=child.stream or '').all() if child else []
    lessons = Lesson.query.filter(Lesson.teaching_class_id.in_([c.id for c in courses])).all()
    days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    lessons.sort(key=lambda l:(days.index(l.day),l.start_time))
    notices = Notification.query.filter(Notification.target.in_(['all','parents'])).order_by(Notification.created_at.desc()).limit(12).all()
    billed = sum(f.amount for f in fees if f.record_type == 'invoice')
    paid = sum(f.amount for f in fees if f.record_type == 'payment')
    return dict(viewer=viewer,children=children,child=child,attendance=attendance,fees=fees,
        grades=grades,lessons=lessons,notices=notices,billed=billed,paid=paid)


@family_bp.route('/')
@roles('parent')
def home():
    return render_template('family/home.html', **family_context(current_user))


@family_bp.route('/previews')
@roles('admin')
def previews():
    users = User.query.filter(User.role.in_(['teacher','student','parent'])).order_by(User.role, User.username).all()
    linked_students = {a.user_id:a.student for a in StudentAccount.query.all()}
    linked_parents = {p.user_id:p for p in Parent.query.filter(Parent.user_id.isnot(None)).all()}
    return render_template('family/previews.html', users=users,linked_students=linked_students,linked_parents=linked_parents)


@family_bp.route('/previews/<int:user_id>')
@roles('admin')
def preview(user_id):
    viewer = User.query.get_or_404(user_id)
    if viewer.role == 'parent':
        return render_template('family/home.html', **family_context(viewer), preview_mode=True)
    if viewer.role not in {'teacher','student'}:
        abort(403)
    from app.routes.learning import workspace_context
    return render_template('portal/home.html', **workspace_context(viewer), preview_mode=True)
