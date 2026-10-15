import re
from datetime import date, timedelta
import pytest
from app import create_app, db
from app.models import (User, Student, Staff, StudentAccount, TeachingClass, Assignment,
                        Submission, Grade, Attendance, Notification, FeeRecord, Lesson)


@pytest.fixture
def app():
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret', 'SQLALCHEMY_DATABASE_URI': 'sqlite://'})
    with app.app_context():
        db.create_all()
        for name, role in [('admin', 'admin'), ('teacher', 'teacher'), ('otherteacher', 'teacher'), ('student', 'student'), ('otherstudent', 'student'), ('unlinked', 'student'), ('parent', 'parent')]:
            user = User(username=name, email=name+'@test.example', role=role)
            user.set_password('test-password-123')
            db.session.add(user)
        db.session.flush()
        db.session.add_all([Student(id=1, admission_no='S1', first_name='Alice', last_name='Learner', class_name='Grade 7', stream='East'), Student(id=2, admission_no='S2', first_name='Private', last_name='Learner', class_name='Grade 8', stream='West'), Staff(id=1, staff_no='T1', first_name='New', last_name='Teacher', role='Teacher')])
        db.session.flush()
        users = {u.username: u for u in User.query.all()}
        db.session.add_all([StudentAccount(user_id=users['student'].id, student_id=1), StudentAccount(user_id=users['otherstudent'].id, student_id=2), TeachingClass(id=1, teacher_id=users['teacher'].id, class_name='Grade 7', stream='East', subject='Math'), TeachingClass(id=2, teacher_id=users['otherteacher'].id, class_name='Grade 8', stream='West', subject='English')])
        db.session.flush()
        db.session.add_all([Assignment(id=1, teaching_class_id=1, title='Fractions', instructions='Show working', due_date=(date.today()+timedelta(days=2)).isoformat()), Assignment(id=2, teaching_class_id=2, title='Private homework', instructions='Private', due_date='2099-01-01'), Grade(student_id=2, subject='Private grade', term='Term 1', year=2026, score=50), Notification(title='Staff private notice', message='Private', target='staff'), Notification(title='Student notice', message='Welcome', target='students'), FeeRecord(student_id=1, record_type='invoice', amount=1200), FeeRecord(student_id=2, record_type='invoice', amount=99999)])
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def post(client, url, data):
    client.get('/login', follow_redirects=True)
    with client.session_transaction() as session:
        token = session['_csrf_token']
    return client.post(url, data={**data, 'csrf_token': token})


def login(client, name):
    response = post(client, '/login', {'username': name, 'password': 'test-password-123'})
    assert response.status_code == 302


def test_login_role_and_csrf(client):
    assert client.post('/login', data={'username': 'admin'}).status_code == 400
    assert post(client, '/login/student', {'username': 'teacher', 'password': 'test-password-123'}).status_code == 200
    with client.session_transaction() as session:
        assert '_user_id' not in session
    login(client, 'student')
    assert client.get('/dashboard').location.endswith('/portal/')
    assert client.get('/logout').status_code == 405
    assert post(client, '/logout', {}).status_code == 302
    assert client.get('/portal/').status_code == 302


@pytest.mark.parametrize('name', ['student', 'teacher', 'parent'])
@pytest.mark.parametrize('url', ['/students/', '/students/2', '/staff/', '/fees/', '/fees/student/2', '/grades/', '/grades/report/2', '/attendance/', '/parents/', '/portal/accounts'])
def test_admin_routes_deny_other_roles(client, name, url):
    login(client, name)
    assert client.get(url).status_code == 403


@pytest.mark.parametrize('url', ['/students/2/delete', '/staff/1/delete', '/grades/1/delete', '/attendance/save', '/fees/record', '/parents/notify', '/portal/accounts'])
def test_student_cannot_write_admin_routes(client, url):
    login(client, 'student')
    assert post(client, url, {}).status_code == 403


def test_student_dashboard_is_private(client):
    login(client, 'student')
    page = client.get('/portal/')
    assert page.status_code == 200
    for value in [b'Alice', b'Fractions', b'Student notice', b'1,200.00']:
        assert value in page.data
    for value in [b'Private homework', b'Private grade', b'Staff private notice', b'99,999']:
        assert value not in page.data
    assert client.get('/portal/assignments/2').status_code == 403
    assert client.get('/portal/class/1').status_code == 403


def test_unlinked_student_denied(client):
    login(client, 'unlinked')
    assert client.get('/portal/').status_code == 403


def test_teacher_scope_and_validation(client, app):
    login(client, 'teacher')
    assert client.get('/portal/class/1').status_code == 200
    assert client.get('/portal/class/2').status_code == 403
    assert client.get('/portal/assignments/2').status_code == 403
    assert post(client, '/portal/class/1', {'kind': 'attendance', 'student_id': 2}).status_code == 403
    attendance = {'kind': 'attendance', 'student_id': 1, 'date': '2026-10-15', 'status': 'present'}
    assert post(client, '/portal/class/1', attendance).status_code == 302
    assert post(client, '/portal/class/1', {**attendance, 'status': 'late'}).status_code == 302
    assert post(client, '/portal/class/1', {**attendance, 'status': 'fake'}).status_code == 400
    grade = {'kind': 'grade', 'student_id': 1, 'score': 80, 'max_score': 100, 'term': 'Term 1', 'year': 2026, 'exam_type': 'quiz'}
    for bad in ['nan', 'inf', '-1', '101']:
        assert post(client, '/portal/class/1', {**grade, 'score': bad}).status_code == 400
    assert post(client, '/portal/class/1', grade).status_code == 302
    assert post(client, '/portal/class/1', {**grade, 'score': 90}).status_code == 302
    with app.app_context():
        assert Attendance.query.count() == 1
        assert Attendance.query.first().status == 'late'
        assert Grade.query.filter_by(student_id=1).count() == 1
        assert Grade.query.filter_by(student_id=1).first().score == 90


def test_assignment_submission_feedback_flow(client, app):
    login(client, 'teacher')
    assert post(client, '/portal/assignments/new', {'class_id': 2, 'title': 'Bad', 'instructions': 'Bad', 'due_date': '2099-01-01'}).status_code == 403
    assert post(client, '/portal/assignments/new', {'class_id': 1, 'title': 'New work', 'instructions': 'Explain', 'due_date': '2099-01-01'}).status_code == 302
    post(client, '/logout', {})
    login(client, 'student')
    assert post(client, '/portal/assignments/1', {'answer': 'Three quarters'}).status_code == 302
    assert post(client, '/portal/assignments/1', {'answer': '3/4'}).status_code == 302
    with app.app_context():
        assert Submission.query.count() == 1
        sid = Submission.query.first().id
    post(client, '/logout', {})
    login(client, 'otherteacher')
    assert post(client, '/portal/assignments/1', {'submission_id': sid, 'feedback': 'Bad'}).status_code == 403
    post(client, '/logout', {})
    login(client, 'teacher')
    assert post(client, '/portal/assignments/1', {'submission_id': sid, 'feedback': 'Well done'}).status_code == 302
    post(client, '/logout', {})
    login(client, 'student')
    assert b'Well done' in client.get('/portal/assignments/1').data
    with app.app_context():
        db.session.get(Assignment, 1).due_date = '2000-01-01'
        db.session.commit()
    assert post(client, '/portal/assignments/1', {'answer': 'Late'}).status_code == 400


def test_admin_account_classes_timetable_and_password(client, app):
    login(client, 'admin')
    assert client.get('/portal/accounts').status_code == 200
    account = {'kind': 'account', 'role': 'teacher', 'profile_id': 1, 'username': 'newteacher', 'email': 'new@example.test', 'password': 'strong-password-123'}
    assert post(client, '/portal/accounts', account).status_code == 302
    with app.app_context():
        teacher_id = User.query.filter_by(username='newteacher').first().id
        assert db.session.get(Staff, 1).user_id == teacher_id
    assert post(client, '/portal/accounts', {'kind': 'class', 'teacher_id': teacher_id, 'class_name': 'Grade 7', 'stream': 'East', 'subject': 'Science'}).status_code == 302
    lesson = {'kind': 'lesson', 'class_id': 1, 'day': 'Monday', 'start_time': '09:00', 'end_time': '10:00', 'room': 'A'}
    assert post(client, '/portal/accounts', lesson).status_code == 302
    assert post(client, '/portal/accounts', lesson).status_code == 400
    assert post(client, '/portal/password', {'current_password': 'test-password-123', 'password': 'updated-password-123', 'confirm_password': 'updated-password-123'}).status_code == 302
    with app.app_context():
        assert User.query.filter_by(username='admin').first().check_password('updated-password-123')


def test_admin_legacy_pages_and_forms_render(client):
    login(client, 'admin')
    for url in ['/dashboard', '/students/', '/students/1', '/students/add', '/students/1/edit', '/staff/', '/staff/add', '/attendance/', '/attendance/report', '/grades/', '/grades/add', '/grades/report/1', '/fees/', '/fees/record', '/fees/student/1', '/parents/', '/parents/add', '/parents/notify', '/parents/notifications', '/portal/password']:
        page = client.get(url)
        assert page.status_code == 200, url
        for form in re.findall(rb'<form\b.*?</form>', page.data, re.S):
            if b'post' in form.lower():
                assert b'name="csrf_token"' in form, url


def test_student_account_provisioning_and_duplicate_rejection(client, app):
    login(client, 'admin')
    with app.app_context():
        db.session.add(Student(id=3, admission_no='S3', first_name='New', last_name='Learner', class_name='Grade 7', stream='East'))
        db.session.commit()
    data = {'kind': 'account', 'role': 'student', 'profile_id': 3, 'username': 'newstudent', 'email': 'newstudent@example.test', 'password': 'strong-password-123'}
    assert post(client, '/portal/accounts', data).status_code == 302
    assert post(client, '/portal/accounts', {**data, 'username': 'duplicate', 'email': 'duplicate@example.test'}).status_code == 302
    with app.app_context():
        assert StudentAccount.query.filter_by(student_id=3).count() == 1
        assert User.query.filter_by(username='duplicate').count() == 0
    post(client, '/logout', {})
    assert post(client, '/login/student', {'username': 'newstudent', 'password': 'strong-password-123'}).status_code == 302
    assert b'New Learner' in client.get('/portal/').data


def test_malformed_csrf_and_database_upgrade(client, app):
    client.get('/login')
    assert client.post('/login', data={'csrf_token': 'invalid-\u2603'}).status_code == 400
    with app.app_context():
        original_count = User.query.count()
        # Emulate the original schema by dropping only the newly added tables.
        for model in [Submission, Lesson, Assignment, TeachingClass, StudentAccount]:
            model.__table__.drop(db.engine)
        assert app.test_cli_runner().invoke(args=['init-db']).exit_code == 0
        assert app.test_cli_runner().invoke(args=['init-db']).exit_code == 0
        assert User.query.count() == original_count
        assert TeachingClass.query.count() == 0
