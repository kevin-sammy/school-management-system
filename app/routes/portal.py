"""Teacher and student self-service with server-side record scoping."""
from datetime import date, datetime
from functools import wraps
from math import isfinite
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import (User, Student, Staff, StudentAccount, TeachingClass,
                        Assignment, Submission, Lesson, Grade, Attendance, Notification, SubmissionAssessment, Parent)

portal_bp = Blueprint('portal', __name__)
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def roles(*allowed):
    def decorate(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in allowed:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorate


def text(name, limit=200, required=True):
    value = request.form.get(name, '').strip()
    if (required and not value) or len(value) > limit:
        abort(400, description=f'Invalid {name.replace("_", " ")}.')
    return value


def integer(name):
    try:
        return int(request.form.get(name, ''))
    except ValueError:
        abort(400, description=f'Invalid {name}.')


def valid_date(name):
    value = text(name, 10)
    try:
        value = date.fromisoformat(value).isoformat()
    except ValueError:
        abort(400, description='Use a valid date.')
    return value


def student_profile(user=None):
    user = user or current_user
    link = StudentAccount.query.filter_by(user_id=user.id).first()
    if not link or link.student.status != 'active':
        abort(403, description='Ask your school administrator to link an active student profile.')
    return link.student


def teaching_class(class_id):
    item = TeachingClass.query.get_or_404(class_id)
    if item.teacher_id != current_user.id:
        abort(403)
    return item


def class_students(item):
    return Student.query.filter_by(class_name=item.class_name, status='active').filter(
        db.func.coalesce(Student.stream, '') == item.stream
    ).order_by(Student.last_name).all()


def belongs(student, item):
    return student.class_name == item.class_name and (student.stream or '') == item.stream


def academic_classes(student):
    return TeachingClass.query.filter_by(class_name=student.class_name, stream=student.stream or '').all()


def save(message):
    db.session.commit()
    flash(message, 'success')
    return redirect(url_for('portal.home'))


@portal_bp.route('/')
@roles('teacher', 'student')
def home():
    from app.routes.learning import workspace_context
    return render_template('portal/home.html', **workspace_context())


@portal_bp.route('/class/<int:class_id>', methods=['GET', 'POST'])
@roles('teacher')
def classroom(class_id):
    item = teaching_class(class_id)
    students = class_students(item)
    if request.method == 'POST':
        kind = text('kind', 20)
        if kind not in {'attendance', 'grade'}:
            abort(400)
        student = Student.query.get_or_404(integer('student_id'))
        if student not in students:
            abort(403)
        if kind == 'attendance':
            day = valid_date('date')
            status = text('status', 20)
            if status not in {'present', 'absent', 'late'}:
                abort(400)
            record = Attendance.query.filter_by(student_id=student.id, date=day).first()
            if record is None:
                record = Attendance(student_id=student.id, date=day)
                db.session.add(record)
            record.status, record.notes = status, text('notes', 200, False)
            record.recorded_by = current_user.username
        else:
            try:
                score, maximum = float(request.form.get('score', '')), float(request.form.get('max_score', '100'))
            except ValueError:
                abort(400)
            if not all(isfinite(v) for v in [score, maximum]) or maximum <= 0 or not 0 <= score <= maximum:
                abort(400, description='Score must be between zero and a positive maximum.')
            year, term = integer('year'), text('term', 20)
            if term not in {'Term 1', 'Term 2', 'Term 3'} or not 2000 <= year <= 2100:
                abort(400)
            exam_type = text('exam_type', 40)
            record = Grade.query.filter_by(student_id=student.id, subject=item.subject, year=year, term=term, exam_type=exam_type).first()
            if record is None:
                record = Grade(student_id=student.id, subject=item.subject, year=year, term=term, exam_type=exam_type)
                db.session.add(record)
            record.score, record.max_score = score, maximum
            record.remarks = text('remarks', 200, False)
            record.recorded_by = current_user.username
        db.session.commit()
        flash('Record saved.', 'success')
        return redirect(url_for('portal.classroom', class_id=item.id))
    grades = Grade.query.filter(Grade.student_id.in_([s.id for s in students]), Grade.subject == item.subject).order_by(Grade.created_at.desc()).all()
    attendance = Attendance.query.filter(Attendance.student_id.in_([s.id for s in students])).order_by(Attendance.date.desc()).limit(100).all()
    return render_template('portal/classroom.html', item=item, students=students, grades=grades, attendance=attendance, today=date.today().isoformat(), year=date.today().year)


@portal_bp.route('/assignments/new', methods=['GET', 'POST'])
@roles('teacher')
def new_assignment():
    classes = TeachingClass.query.filter_by(teacher_id=current_user.id).all()
    if request.method == 'POST':
        item = teaching_class(integer('class_id'))
        db.session.add(Assignment(teaching_class_id=item.id, title=text('title', 120),
                                  instructions=text('instructions', 20000), due_date=valid_date('due_date')))
        return save('Assignment published to your class.')
    return render_template('portal/assignment_form.html', classes=classes)


@portal_bp.route('/assignments/<int:assignment_id>', methods=['GET', 'POST'])
@roles('teacher', 'student', 'admin')
def assignment(assignment_id):
    item = Assignment.query.get_or_404(assignment_id)
    student = student_profile() if current_user.role == 'student' else None
    if student:
        if not belongs(student, item.teaching_class):
            abort(403)
        submissions = Submission.query.filter_by(assignment_id=item.id, student_id=student.id).all()
    else:
        if current_user.role != 'admin':
            teaching_class(item.teaching_class_id)
        submissions = Submission.query.filter_by(assignment_id=item.id).all()
    if request.method == 'POST':
        if current_user.role == 'admin':
            abort(403)
        if student:
            if date.today().isoformat() > item.due_date:
                abort(400, description='The submission deadline has passed.')
            submission = submissions[0] if submissions else Submission(assignment_id=item.id, student_id=student.id)
            submission.answer = text('answer', 20000)
            submission.submitted_at = datetime.utcnow()
            # A revised answer needs a fresh review.
            submission.feedback = None
            assessment = SubmissionAssessment.query.filter_by(submission_id=submission.id).first() if submission.id else None
            if assessment:
                if assessment.grade:
                    db.session.delete(assessment.grade)
                db.session.delete(assessment)
            db.session.add(submission)
        else:
            submission = Submission.query.get_or_404(integer('submission_id'))
            if submission.assignment_id != item.id:
                abort(403)
            submission.feedback = text('feedback', 5000)
            assessment = SubmissionAssessment.query.filter_by(submission_id=submission.id).first()
            if assessment and assessment.grade:
                assessment.grade.remarks = submission.feedback[:200]
        db.session.commit()
        flash('Submission saved.' if student else 'Feedback saved.', 'success')
        return redirect(url_for('portal.assignment', assignment_id=item.id))
    assessments = {a.submission_id: a for a in SubmissionAssessment.query.filter(SubmissionAssessment.submission_id.in_([s.id for s in submissions])).all()}
    if student:
        assessments = {sid: a for sid, a in assessments.items() if a.grade_id}
    return render_template('portal/assignment.html', item=item, student=student, submissions=submissions, assessments=assessments, year=date.today().year, closed=date.today().isoformat() > item.due_date)


@portal_bp.route('/accounts', methods=['GET', 'POST'])
@roles('admin')
def accounts():
    if request.method == 'POST':
        kind = text('kind', 20)
        if kind == 'account':
            role = text('role', 20)
            if role not in {'student', 'teacher', 'parent'}:
                abort(400)
            password = request.form.get('password', '')
            if not 12 <= len(password) <= 128:
                abort(400, description='Use a password of 12 to 128 characters.')
            user = User(username=text('username', 80), email=text('email', 120), role=role)
            user.set_password(password)
            db.session.add(user)
            try:
                db.session.flush()
                if role == 'student':
                    student = Student.query.get_or_404(integer('profile_id'))
                    if student.status != 'active':
                        abort(400)
                    db.session.add(StudentAccount(user_id=user.id, student_id=student.id))
                elif role == 'parent':
                    guardian = Parent.query.filter_by(id=integer('profile_id')).with_for_update().first_or_404()
                    if guardian.user_id:
                        abort(400, description='This parent or guardian already has a login.')
                    guardian.user_id = user.id
                else:
                    staff = Staff.query.get_or_404(integer('profile_id'))
                    if staff.user_id or staff.status != 'active' or staff.role.lower() != 'teacher':
                        abort(400, description='Choose an active, unlinked teacher staff record.')
                    staff.user_id = user.id
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash('Username, email or student profile is already linked.', 'danger')
                return redirect(url_for('portal.accounts'))
        elif kind == 'class':
            teacher = User.query.get_or_404(integer('teacher_id'))
            if teacher.role != 'teacher':
                abort(400)
            name, stream = text('class_name', 20), text('stream', 10, False)
            if not Student.query.filter_by(class_name=name).filter(db.func.coalesce(Student.stream, '') == stream).first():
                abort(400, description='Choose an existing class and stream.')
            db.session.add(TeachingClass(teacher_id=teacher.id, class_name=name, stream=stream, subject=text('subject', 60)))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash('That teaching assignment already exists.', 'warning')
                return redirect(url_for('portal.accounts'))
        elif kind == 'lesson':
            item = TeachingClass.query.get_or_404(integer('class_id'))
            day, start, end = text('day', 12), text('start_time', 5), text('end_time', 5)
            try:
                start = datetime.strptime(start, '%H:%M').strftime('%H:%M')
                end = datetime.strptime(end, '%H:%M').strftime('%H:%M')
            except ValueError:
                abort(400)
            if day not in DAYS or start >= end:
                abort(400, description='Choose a valid day and time range.')
            for lesson in Lesson.query.filter_by(day=day).all():
                other = lesson.teaching_class
                if start < lesson.end_time and end > lesson.start_time and (other.teacher_id == item.teacher_id or (other.class_name, other.stream) == (item.class_name, item.stream)):
                    abort(400, description='This lesson overlaps an existing class or teacher lesson.')
            db.session.add(Lesson(teaching_class_id=item.id, day=day, start_time=start, end_time=end, room=text('room', 60)))
            db.session.commit()
        else:
            abort(400)
        flash('Saved successfully.', 'success')
        return redirect(url_for('portal.accounts'))
    return render_template('portal/accounts.html', students=Student.query.filter_by(status='active').all(),
                           staff=Staff.query.filter_by(status='active', user_id=None).all(),
                           parents=Parent.query.filter_by(user_id=None).all(),
                           teachers=User.query.filter_by(role='teacher').all(), classes=TeachingClass.query.all(),
                           users=User.query.order_by(User.role, User.username).all(), days=DAYS)


@portal_bp.route('/password', methods=['GET', 'POST'])
@login_required
def password():
    if request.method == 'POST':
        value = request.form.get('password', '')
        if not current_user.check_password(request.form.get('current_password', '')):
            flash('Current password is incorrect.', 'danger')
        elif not 12 <= len(value) <= 128 or value != request.form.get('confirm_password'):
            flash('Use 12–128 characters and matching confirmation.', 'danger')
        else:
            current_user.set_password(value)
            db.session.commit()
            flash('Password updated.', 'success')
            return redirect(url_for('dashboard.index'))
    return render_template('portal/password.html')


@portal_bp.route('/demo-data', methods=['GET', 'POST'])
@roles('admin')
def demo_data():
    from sqlalchemy import inspect
    from app.demo import DATASET_KEY, seed_demo_dataset, seed_demo_parent_accounts
    from app.models import DemoDataset
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirmation = request.form.get('confirm_password', '')
        if password != confirmation:
            flash('The demo password and confirmation must match.', 'danger')
            return redirect(url_for('portal.demo_data'))
        try:
            # Additive table creation also supports an existing deployment upgrade.
            db.create_all()
            kind = request.form.get('kind', 'school')
            if kind not in {'school','parents'}:
                abort(400)
            summary, created = seed_demo_parent_accounts(password) if kind == 'parents' else seed_demo_dataset(password)
        except ValueError as error:
            db.session.rollback()
            flash(str(error), 'danger')
            return redirect(url_for('portal.demo_data'))
        except IntegrityError:
            db.session.rollback()
            flash('The import conflicted with another request. Refresh to check whether the dataset was loaded.', 'warning')
            return redirect(url_for('portal.demo_data'))
        flash('Expanded demo data is ready.' if created else 'Demo data is already loaded. No duplicates were added.', 'success')
        return redirect(url_for('portal.demo_data'))
    ready = inspect(db.engine).has_table('demo_datasets')
    marker = db.session.get(DemoDataset, DATASET_KEY) if ready else None
    return render_template('portal/demo_data.html', summary=marker.summary if marker else None)
