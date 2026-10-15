"""A course-centered learning workspace using the same SIS records."""
import calendar as month_calendar
import csv
import io
from collections import defaultdict
from datetime import date
from math import isfinite
from urllib.parse import urlsplit
from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user
from app import db
from app.models import (TeachingClass, Student, Assignment, Submission, Lesson, Grade,
                        Notification, CourseMaterial, CoursePost, CourseReply, SubmissionAssessment)
from app.routes.portal import roles, student_profile, academic_classes, class_students, belongs, text, integer

learning_bp = Blueprint('learning', __name__, url_prefix='/learning')


def visible_classes():
    if current_user.role == 'admin':
        return TeachingClass.query.order_by(TeachingClass.class_name, TeachingClass.subject).all()
    if current_user.role == 'teacher':
        return TeachingClass.query.filter_by(teacher_id=current_user.id).order_by(TeachingClass.class_name, TeachingClass.subject).all()
    return academic_classes(student_profile())


def course_access(class_id, write=False):
    item = TeachingClass.query.get_or_404(class_id)
    if current_user.role == 'admin':
        return item
    if current_user.role == 'teacher' and item.teacher_id == current_user.id:
        return item
    if not write and current_user.role == 'student' and belongs(student_profile(), item):
        return item
    abort(403)


def workspace_context():
    classes = visible_classes()
    ids = [c.id for c in classes]
    student = student_profile() if current_user.role == 'student' else None
    assignments = Assignment.query.filter(Assignment.teaching_class_id.in_(ids)).order_by(Assignment.due_date).all()
    # Do not expose a student's submissions from a previous class after transfer.
    submissions = {s.assignment_id: s for s in Submission.query.filter(
        Submission.student_id == student.id, Submission.assignment_id.in_([a.id for a in assignments])
    ).all()} if student else {}
    assessments = {a.submission_id: a for a in SubmissionAssessment.query.filter(
        SubmissionAssessment.submission_id.in_([s.id for s in submissions.values()]),
        SubmissionAssessment.grade_id.isnot(None)).all()}
    lessons = Lesson.query.filter(Lesson.teaching_class_id.in_(ids)).all()
    days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    lessons.sort(key=lambda l: (days.index(l.day), l.start_time))
    targets = ['all', 'students'] if student else ['all', 'teachers', 'staff']
    notices = Notification.query.filter(Notification.target.in_(targets)).order_by(Notification.created_at.desc()).limit(8).all()
    posts = CoursePost.query.filter(CoursePost.teaching_class_id.in_(ids)).order_by(CoursePost.created_at.desc()).limit(8).all()
    pending = [a for a in assignments if a.id not in submissions] if student else assignments
    upcoming = [a for a in pending if a.due_date >= date.today().isoformat()]
    missing = [a for a in pending if a.due_date < date.today().isoformat()] if student else []
    grade_titles = {a.grade_id: a.submission.assignment.title for a in SubmissionAssessment.query.join(Submission).filter(Submission.student_id == student.id, SubmissionAssessment.grade_id.isnot(None)).all()} if student else {}
    return dict(grade_titles=grade_titles, classes=classes, student=student, assignments=assignments, lessons=lessons,
                notices=notices, submissions=submissions, assessments=assessments,
                posts=posts, upcoming=upcoming, missing=missing, today=date.today().isoformat())


@learning_bp.route('/courses')
@roles('teacher', 'student', 'admin')
def courses():
    context = workspace_context()
    search = request.args.get('q', '').strip()
    context['classes'] = [c for c in context['classes'] if search.lower() in f'{c.subject} {c.class_name} {c.stream}'.lower()]
    return render_template('learning/courses.html', **context, search=search)


@learning_bp.route('/courses/<int:class_id>', methods=['GET', 'POST'])
@roles('teacher', 'student', 'admin')
def course(class_id):
    item = course_access(class_id, write=request.method == 'POST')
    if request.method == 'POST':
        kind = text('kind', 20)
        if kind == 'material':
            material_kind = text('material_kind', 20)
            if material_kind not in {'page', 'link'}:
                abort(400)
            content = text('content', 20000)
            if material_kind == 'link':
                try:
                    parsed = urlsplit(content)
                    hostname = parsed.hostname
                except ValueError:
                    abort(400, description='Use a valid HTTPS resource URL.')
                if not hostname or any(c.isspace() for c in content) or parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
                    abort(400, description='Resource links must be valid HTTPS URLs.')
            db.session.add(CourseMaterial(teaching_class_id=item.id, title=text('title', 120),
                module=text('module', 100), kind=material_kind, content=content))
        elif kind in {'announcement', 'discussion'}:
            db.session.add(CoursePost(teaching_class_id=item.id, author_id=current_user.id,
                kind=kind, title=text('title', 120), body=text('body', 20000)))
        else:
            abort(400)
        db.session.commit()
        flash('Published to this course.', 'success')
        return redirect(url_for('learning.course', class_id=item.id))
    if request.args.get('tab', 'materials') not in {'materials', 'updates', 'assignments'}:
        abort(400)
    materials = CourseMaterial.query.filter_by(teaching_class_id=item.id).order_by(CourseMaterial.created_at).all()
    modules = defaultdict(list)
    for material in materials:
        modules[material.module].append(material)
    assignments = Assignment.query.filter_by(teaching_class_id=item.id).order_by(Assignment.due_date).all()
    posts = CoursePost.query.filter_by(teaching_class_id=item.id).order_by(CoursePost.created_at.desc()).all()
    student = student_profile() if current_user.role == 'student' else None
    submissions = {s.assignment_id: s for s in Submission.query.filter(
        Submission.assignment_id.in_([a.id for a in assignments]), Submission.student_id == student.id).all()} if student else {}
    return render_template('learning/course.html', item=item, modules=modules,
        assignments=assignments, posts=posts, submissions=submissions, student=student,
        roster=class_students(item) if not student else [], tab=request.args.get('tab', 'materials'), today=date.today().isoformat())


@learning_bp.route('/materials/<int:material_id>/delete', methods=['POST'])
@roles('teacher', 'admin')
def delete_material(material_id):
    material = CourseMaterial.query.get_or_404(material_id)
    course_access(material.teaching_class_id, write=True)
    class_id = material.teaching_class_id
    db.session.delete(material)
    db.session.commit()
    flash('Material removed.', 'success')
    return redirect(url_for('learning.course', class_id=class_id))


@learning_bp.route('/discussions/<int:post_id>', methods=['GET', 'POST'])
@roles('teacher', 'student', 'admin')
def discussion(post_id):
    post = CoursePost.query.get_or_404(post_id)
    course_access(post.teaching_class_id)
    if request.method == 'POST':
        if post.kind != 'discussion':
            abort(400)
        db.session.add(CourseReply(post_id=post.id, author_id=current_user.id, body=text('body', 10000)))
        db.session.commit()
        return redirect(url_for('learning.discussion', post_id=post.id))
    return render_template('learning/discussion.html', post=post)


@learning_bp.route('/assignments')
@roles('teacher', 'student', 'admin')
def assignments():
    context = workspace_context()
    status = request.args.get('status', 'all')
    if status not in {'all', 'upcoming', 'missing', 'submitted'}:
        abort(400)
    if status == 'submitted':
        context['assignments'] = [a for a in context['assignments'] if a.id in context['submissions']]
    elif status in {'upcoming', 'missing'}:
        context['assignments'] = context[status]
    return render_template('learning/assignments.html', **context, status=status)


@learning_bp.route('/calendar')
@roles('teacher', 'student', 'admin')
def calendar():
    context = workspace_context()
    try:
        month, year = int(request.args.get('month', date.today().month)), int(request.args.get('year', date.today().year))
        if not 1 <= month <= 12 or not 2000 <= year <= 2100:
            raise ValueError
    except ValueError:
        abort(400)
    events = defaultdict(list)
    for assignment in context['assignments']:
        deadline = date.fromisoformat(assignment.due_date)
        if (deadline.year, deadline.month) == (year, month):
            events[deadline.day].append(assignment)
    previous = date(year-1, 12, 1) if month == 1 else date(year, month-1, 1)
    following = date(year+1, 1, 1) if month == 12 else date(year, month+1, 1)
    return render_template('learning/calendar.html', **context, events=events,
        weeks=month_calendar.monthcalendar(year, month), month_name=month_calendar.month_name[month],
        month=month, year=year, previous=previous, following=following)


@learning_bp.route('/records')
@roles('student')
def records():
    return render_template('learning/records.html', **workspace_context())


@learning_bp.route('/gradebook/<int:class_id>')
@roles('teacher', 'admin')
def gradebook(class_id):
    item = course_access(class_id, write=True)
    students = class_students(item)
    assignments = Assignment.query.filter_by(teaching_class_id=item.id).order_by(Assignment.due_date).all()
    submissions = {(s.student_id, s.assignment_id): s for s in Submission.query.filter(
        Submission.assignment_id.in_([a.id for a in assignments]), Submission.student_id.in_([s.id for s in students])).all()}
    assessments = {a.submission_id: a for a in SubmissionAssessment.query.filter(
        SubmissionAssessment.submission_id.in_([s.id for s in submissions.values()])).all()}
    if request.args.get('export') == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        def safe(value):
            value = str(value)
            return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
        writer.writerow(['Admission number', 'Student'] + [safe(a.title) for a in assignments])
        for student in students:
            cells = []
            for assignment in assignments:
                submission = submissions.get((student.id, assignment.id))
                assessment = assessments.get(submission.id) if submission else None
                cells.append(f'{assessment.points}/{assessment.max_points}' if assessment and assessment.grade_id else 'Draft' if assessment else 'Submitted' if submission else 'Missing' if assignment.due_date < date.today().isoformat() else 'Pending')
            writer.writerow([safe(student.admission_no), safe(student.full_name)] + cells)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=course-{item.id}-gradebook.csv'
        return response
    return render_template('learning/gradebook.html', item=item, students=students,
        assignments=assignments, submissions=submissions, assessments=assessments, today=date.today().isoformat())


@learning_bp.route('/submissions/<int:submission_id>/assess', methods=['POST'])
@roles('teacher')
def assess(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    item = course_access(submission.assignment.teaching_class_id, write=True)
    if not belongs(submission.student, item) or submission.student.status != 'active':
        abort(403)
    try:
        points, maximum = float(request.form.get('points', '')), float(request.form.get('max_points', '100'))
        if not all(isfinite(v) for v in (points, maximum)) or not 0 <= points <= maximum or maximum <= 0:
            raise ValueError
    except ValueError:
        abort(400, description='Enter a valid score within the maximum points.')
    term, year = text('term', 20), integer('year')
    if term not in {'Term 1', 'Term 2', 'Term 3'} or not 2000 <= year <= 2100:
        abort(400)
    action = text('action', 20)
    if action not in {'draft', 'publish'}:
        abort(400)
    assessment = SubmissionAssessment.query.filter_by(submission_id=submission.id).first()
    if assessment is None:
        assessment = SubmissionAssessment(submission_id=submission.id)
        db.session.add(assessment)
    assessment.points, assessment.max_points, assessment.term, assessment.year = points, maximum, term, year
    submission.feedback = text('feedback', 5000, False)
    if action == 'publish':
        grade = assessment.grade
        if grade is None:
            grade = Grade(student_id=submission.student_id, subject=item.subject, term=term, year=year,
                          score=points, max_score=maximum, exam_type=f'assignment:{submission.assignment_id}')
            db.session.add(grade)
        grade.score, grade.max_score, grade.term, grade.year = points, maximum, term, year
        grade.remarks, grade.recorded_by = submission.feedback[:200], current_user.username
        assessment.grade = grade
    elif assessment.grade is not None:
        old_grade = assessment.grade
        assessment.grade = None
        db.session.delete(old_grade)
    db.session.commit()
    flash('Grade published to student records.' if action == 'publish' else 'Draft saved; the score is hidden from the student.', 'success')
    return redirect(url_for('portal.assignment', assignment_id=submission.assignment_id))
