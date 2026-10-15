"""Timed course exams with browser event logs for teacher review, not identity proctoring."""
from datetime import datetime, timedelta
from math import isfinite
from sqlalchemy.exc import IntegrityError
from flask import Blueprint, render_template, request, redirect, url_for, abort, jsonify, flash
from flask_login import current_user
from app import db
from app.models import OnlineExam, ExamQuestion, ExamAttempt, ExamAnswer, ExamEvent
from app.routes.portal import roles, text, integer, student_profile
from app.routes.learning import course_access, visible_classes

exams_bp = Blueprint('exams', __name__, url_prefix='/exams')


def exam_access(exam_id, write=False):
    exam = OnlineExam.query.get_or_404(exam_id)
    course_access(exam.teaching_class_id, write=write)
    if current_user.role == 'student' and not exam.published:
        abort(404)
    return exam


def finalize(attempt):
    if attempt.submitted_at:
        return
    attempt.submitted_at = min(datetime.utcnow(), attempt.deadline_at)
    for answer in attempt.answers:
        question = answer.question
        if not answer.answer.strip():
            answer.score = 0
        elif question.kind == 'mcq':
            answer.score = question.points if answer.answer == str(question.correct_choice) else 0
    attempt.reviewed = all(a.score is not None for a in attempt.answers)


def own_attempt(attempt_id):
    # Lock on mutation prevents an autosave racing with final submission.
    query = ExamAttempt.query.filter_by(id=attempt_id)
    if request.method == 'POST':
        query = query.with_for_update()
    attempt = query.first_or_404()
    exam_access(attempt.exam_id)
    if current_user.role != 'student' or student_profile().id != attempt.student_id:
        abort(403)
    if not attempt.submitted_at and datetime.utcnow() >= attempt.deadline_at:
        finalize(attempt)
        db.session.commit()
    return attempt


@exams_bp.route('/', methods=['GET', 'POST'])
@roles('admin', 'teacher', 'student')
def index():
    courses = visible_classes()
    if request.method == 'POST':
        course = course_access(integer('class_id'), write=True)
        duration = integer('duration_minutes')
        if not 1 <= duration <= 240:
            abort(400, description='Duration must be between 1 and 240 minutes.')
        exam = OnlineExam(teaching_class_id=course.id, title=text('title', 120), duration_minutes=duration)
        db.session.add(exam)
        db.session.commit()
        return redirect(url_for('exams.manage', exam_id=exam.id))
    query = OnlineExam.query.filter(OnlineExam.teaching_class_id.in_([c.id for c in courses]))
    if current_user.role == 'student':
        query = query.filter_by(published=True)
    return render_template('exams/index.html', exams=query.order_by(OnlineExam.id.desc()).all(), courses=courses)


@exams_bp.route('/<int:exam_id>/manage', methods=['GET', 'POST'])
@roles('admin', 'teacher')
def manage(exam_id):
    exam = exam_access(exam_id, write=True)
    # Serialize question addition and publishing to keep the published question set immutable.
    if request.method == 'POST':
        exam = OnlineExam.query.filter_by(id=exam.id).populate_existing().with_for_update().one()
        action = text('action', 20)
        if action == 'release':
            if not exam.published:
                abort(400)
            exam.results_released = True
        elif exam.published:
            abort(409, description='Published exam questions are locked.')
        elif action == 'publish':
            if not exam.questions:
                abort(400, description='Add at least one question before publishing.')
            exam.published = True
        elif action == 'question':
            kind = text('kind', 20)
            points = integer('points')
            if kind not in ['mcq', 'written'] or not 1 <= points <= 100:
                abort(400)
            choices = []
            correct = None
            if kind == 'mcq':
                choices = [text(f'choice_{i}', 500) for i in range(4)]
                correct = integer('correct_choice')
                if correct not in range(4):
                    abort(400)
            db.session.add(ExamQuestion(exam_id=exam.id, prompt=text('prompt', 10000), kind=kind,
                choices=choices, correct_choice=correct, points=points))
        else:
            abort(400)
        db.session.commit()
        return redirect(url_for('exams.manage', exam_id=exam.id))
    # Expired attempts finalize using their last saved answers, including when no student returns.
    for attempt in exam.attempts:
        if not attempt.submitted_at and datetime.utcnow() >= attempt.deadline_at:
            finalize(attempt)
    db.session.commit()
    return render_template('exams/manage.html', exam=exam)


@exams_bp.route('/<int:exam_id>', methods=['GET', 'POST'])
@roles('student')
def start(exam_id):
    exam = exam_access(exam_id)
    student = student_profile()
    attempt = ExamAttempt.query.filter_by(exam_id=exam.id, student_id=student.id).first()
    if request.method == 'POST':
        if not request.form.get('acknowledge'):
            abort(400, description='Read and acknowledge the monitoring notice first.')
        if attempt is None:
            now = datetime.utcnow()
            attempt = ExamAttempt(exam_id=exam.id, student_id=student.id, started_at=now,
                                  deadline_at=now+timedelta(minutes=exam.duration_minutes))
            db.session.add(attempt)
            try:
                db.session.flush()
                for question in exam.questions:
                    db.session.add(ExamAnswer(attempt_id=attempt.id, question_id=question.id, answer=''))
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                attempt = ExamAttempt.query.filter_by(exam_id=exam.id, student_id=student.id).one()
        return redirect(url_for('exams.attempt', attempt_id=attempt.id))
    return render_template('exams/start.html', exam=exam, attempt=attempt)


@exams_bp.route('/attempts/<int:attempt_id>', methods=['GET', 'POST'])
@roles('student')
def attempt(attempt_id):
    attempt = own_attempt(attempt_id)
    if request.method == 'POST':
        if attempt.submitted_at:
            if request.form.get('action') == 'save':
                return jsonify(saved=False, finished=True), 409
            return redirect(url_for('exams.attempt', attempt_id=attempt.id))
        for answer in attempt.answers:
            value = request.form.get(f'q_{answer.question_id}', '').strip()
            if len(value) > 20000 or (answer.question.kind == 'mcq' and value not in ['', '0', '1', '2', '3']):
                abort(400)
            answer.answer = value
        if request.form.get('action') == 'submit':
            finalize(attempt)
        elif request.form.get('action') != 'save':
            abort(400)
        db.session.commit()
        if request.form.get('action') == 'save':
            return jsonify(saved=True, finished=False)
        return redirect(url_for('exams.attempt', attempt_id=attempt.id))
    return render_template('exams/attempt.html', attempt=attempt,
        deadline=attempt.deadline_at.isoformat()+'Z', answers={a.question_id: a for a in attempt.answers})


@exams_bp.route('/attempts/<int:attempt_id>/events', methods=['POST'])
@roles('student')
def event(attempt_id):
    attempt = own_attempt(attempt_id)
    if attempt.submitted_at:
        return jsonify(recorded=False), 409
    kind = text('kind', 30)
    if kind not in {'visibility_hidden', 'fullscreen_exit', 'paste_attempt', 'focus_lost'}:
        abort(400)
    if ExamEvent.query.filter_by(attempt_id=attempt.id).count() >= 200:
        return jsonify(recorded=False), 429
    db.session.add(ExamEvent(attempt_id=attempt.id, kind=kind))
    db.session.commit()
    return jsonify(recorded=True)


@exams_bp.route('/attempts/<int:attempt_id>/review', methods=['GET', 'POST'])
@roles('admin', 'teacher')
def review(attempt_id):
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    exam_access(attempt.exam_id, write=True)
    if not attempt.submitted_at and datetime.utcnow() >= attempt.deadline_at:
        finalize(attempt)
        db.session.commit()
    if request.method == 'POST':
        attempt = ExamAttempt.query.filter_by(id=attempt.id).populate_existing().with_for_update().one()
        if not attempt.submitted_at:
            abort(409, description='This attempt is still in progress.')
        for answer in attempt.answers:
            if answer.question.kind != 'written':
                continue
            try:
                score = float(request.form.get(f'score_{answer.id}', ''))
            except ValueError:
                abort(400)
            if not isfinite(score) or not 0 <= score <= answer.question.points:
                abort(400)
            answer.score = score
        attempt.reviewed = True
        db.session.commit()
        flash('Exam review saved.', 'success')
        return redirect(url_for('exams.review', attempt_id=attempt.id))
    return render_template('exams/review.html', attempt=attempt)
