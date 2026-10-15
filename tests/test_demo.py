from datetime import date
import pytest
from app import db
from app.demo import seed_demo_dataset
from app.models import (User, Student, Parent, Staff, TeachingClass, Assignment, Submission,
    SubmissionAssessment, Grade, Attendance, FeeRecord, CourseMaterial, CoursePost, CourseReply, Lesson, DemoDataset)
from test_portals import app, client, login, post


def test_expanded_demo_counts_links_and_repeatability(app):
    with app.app_context():
        original_students = Student.query.count()
        original_admin = User.query.filter_by(username='admin').first().password_hash
        summary, created = seed_demo_dataset('demo-password-123', today=date(2026, 10, 15))
        assert created
        assert summary['students'] == 60
        assert summary['parents'] == 30
        assert summary['staff'] == 6
        assert summary['teaching_classes'] == 36
        assert summary['assignments'] == 108
        assert summary['attendance'] == 1200
        assert summary['course_materials'] == 108
        assert summary['course_posts'] == 72
        assert summary['course_replies'] == 108
        assert summary['lessons'] == 36
        assert summary['fee_records'] == 105
        assert summary['users'] == 66  # Existing admin is kept; no extra demo admin.
        assert Student.query.count() == original_students + 60
        assert User.query.filter_by(username='admin').first().password_hash == original_admin
        assert User.query.filter_by(username='demo.admin').first() is None
        second, new = seed_demo_dataset('another-password-123', today=date(2027, 1, 1))
        assert not new and second == summary
        assert Student.query.count() == original_students + 60
        assert User.query.filter_by(username='demo.student001').first().check_password('demo-password-123')
        assert not User.query.filter_by(username='demo.student001').first().check_password('another-password-123')
        for s in Submission.query.all():
            assert s.student.class_name == s.assignment.teaching_class.class_name
            assert (s.student.stream or '') == s.assignment.teaching_class.stream
        for a in SubmissionAssessment.query.all():
            if a.grade:
                assert a.grade.student_id == a.submission.student_id
                assert a.grade.score == a.points
        lessons = Lesson.query.join(TeachingClass).filter(TeachingClass.teacher_id.in_(
            [u.id for u in User.query.filter(User.username.like('demo.teacher%')).all()])).all()
        for i, first in enumerate(lessons):
            for second in lessons[i+1:]:
                if first.day == second.day and first.start_time < second.end_time and first.end_time > second.start_time:
                    assert first.teaching_class.teacher_id != second.teaching_class.teacher_id
                    assert (first.teaching_class.class_name, first.teaching_class.stream) != (second.teaching_class.class_name, second.teaching_class.stream)


def test_collision_and_bad_password_do_not_change_existing_data(app):
    with app.app_context():
        for password in ['', 'short']:
            with pytest.raises(ValueError):
                seed_demo_dataset(password)
        db.session.add(Student(admission_no='DEMO/001', first_name='Existing', last_name='Person', class_name='Grade 7'))
        db.session.commit()
        original = User.query.count(), Student.query.count()
        with pytest.raises(ValueError):
            seed_demo_dataset('demo-password-123')
        assert (User.query.count(), Student.query.count()) == original
        assert DemoDataset.query.count() == 0


@pytest.mark.parametrize('role', ['student', 'teacher', 'parent'])
def test_demo_admin_only(client, role):
    login(client, role)
    assert client.get('/portal/demo-data').status_code == 403
    assert post(client, '/portal/demo-data', {'password': 'demo-password-123', 'confirm_password': 'demo-password-123'}).status_code == 403


def test_demo_admin_form_and_new_role_logins(client, app):
    login(client, 'admin')
    assert client.get('/portal/demo-data').status_code == 200
    assert client.post('/portal/demo-data', data={}).status_code == 400
    assert post(client, '/portal/demo-data', {'password': 'demo-password-123', 'confirm_password': 'mismatch'}).status_code == 302
    with app.app_context():
        assert DemoDataset.query.count() == 0
    data = {'password': 'demo-password-123', 'confirm_password': 'demo-password-123'}
    assert post(client, '/portal/demo-data', data).status_code == 302
    assert b'Your demo dataset is loaded' in client.get('/portal/demo-data').data
    assert post(client, '/portal/demo-data', data).status_code == 302
    post(client, '/logout', {})
    for name in ['demo.teacher01', 'demo.student001', 'demo.student060']:
        assert post(client, '/login', {'username': name, 'password': 'demo-password-123'}).status_code == 302
        for path in ['/portal/', '/learning/courses', '/learning/assignments', '/learning/calendar']:
            assert client.get(path).status_code == 200, (name, path)
        post(client, '/logout', {})


def test_demo_cli_initializes_empty_database_and_creates_first_admin(app):
    with app.app_context():
        db.drop_all()
        result = app.test_cli_runner().invoke(args=['seed-demo'], env={'DEMO_PASSWORD': 'demo-password-123'})
        assert result.exit_code == 0, result.output
        assert User.query.filter_by(username='demo.admin').first().check_password('demo-password-123')
        assert Student.query.count() == 60
        second = app.test_cli_runner().invoke(args=['seed-demo'], env={'DEMO_PASSWORD': 'unused-password-123'})
        assert second.exit_code == 0
        assert 'no duplicates' in second.output
        assert Student.query.count() == 60
