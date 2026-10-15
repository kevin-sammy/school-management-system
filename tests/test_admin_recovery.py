import pytest
from app import create_app, db
from app.models import User, Student, AdminRecovery
from test_startup import empty_app, submit_login


def configure(monkeypatch, **overrides):
    values = {'ADMIN_RECOVERY_USERNAME': 'admin', 'ADMIN_RECOVERY_PASSWORD': 'restored-password-123', 'ADMIN_RECOVERY_ID': 'restore-admin-20261015-1'}
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def add_admin(app, username='forgotten-name'):
    with app.app_context():
        db.create_all()
        user = User(username=username, email=username+'@example.invalid', role='admin')
        user.set_password('forgotten-password-123')
        db.session.add(user)
        db.session.add(Student(admission_no='KEEP-1', first_name='Keep', last_name='Record', class_name='Grade 7'))
        db.session.commit()
        return user.id


def test_recover_forgotten_username_password_preserves_records(empty_app, monkeypatch):
    original_id = add_admin(empty_app)
    configure(monkeypatch)
    page = submit_login(empty_app.test_client(), 'admin', 'restored-password-123')
    assert page.status_code == 200 and b'A clear view of your school' in page.data
    with empty_app.app_context():
        assert User.query.filter_by(role='admin').count() == 1
        assert User.query.filter_by(username='admin').first().id == original_id
        assert Student.query.filter_by(admission_no='KEEP-1').count() == 1
        assert AdminRecovery.query.count() == 1


def test_consumed_request_does_not_reset_password_on_cold_start(empty_app, monkeypatch):
    add_admin(empty_app, username='admin')
    configure(monkeypatch)
    assert empty_app.test_client().get('/login/admin').status_code == 200
    with empty_app.app_context():
        user = User.query.filter_by(username='admin').first()
        user.set_password('changed-after-recovery-123')
        db.session.commit()
    restarted = create_app(dict(empty_app.config))
    page = submit_login(restarted.test_client(), 'admin', 'changed-after-recovery-123')
    assert page.status_code == 200 and b'A clear view of your school' in page.data
    with restarted.app_context():
        assert AdminRecovery.query.count() == 1
    monkeypatch.setenv('ADMIN_RECOVERY_ID', 'restore-admin-20261015-2')
    second_restart = create_app(dict(empty_app.config))
    page = submit_login(second_restart.test_client(), 'admin', 'restored-password-123')
    assert page.status_code == 200 and b'A clear view of your school' in page.data


def test_recovery_bootstraps_empty_database(empty_app, monkeypatch):
    configure(monkeypatch)
    page = submit_login(empty_app.test_client(), 'admin', 'restored-password-123')
    assert page.status_code == 200 and b'A clear view of your school' in page.data


@pytest.mark.parametrize('overrides', [
    {'ADMIN_RECOVERY_ID': ''}, {'ADMIN_RECOVERY_PASSWORD': 'short'}, {'ADMIN_RECOVERY_USERNAME': ' '}
])
def test_invalid_recovery_configuration_changes_nothing(empty_app, monkeypatch, overrides):
    user_id = add_admin(empty_app)
    configure(monkeypatch, **overrides)
    assert empty_app.test_client().get('/login/admin').status_code == 503
    with empty_app.app_context():
        user = db.session.get(User, user_id)
        assert user.username == 'forgotten-name'
        assert user.check_password('forgotten-password-123')
        assert AdminRecovery.query.count() == 0


def test_recovery_never_promotes_student_account(empty_app, monkeypatch):
    add_admin(empty_app)
    with empty_app.app_context():
        user = User(username='learner', email='learner@example.invalid', role='student')
        user.set_password('student-password-123')
        db.session.add(user)
        db.session.commit()
    configure(monkeypatch, ADMIN_RECOVERY_USERNAME='learner')
    assert empty_app.test_client().get('/login/admin').status_code == 503
    with empty_app.app_context():
        assert User.query.filter_by(username='learner').first().role == 'student'
        assert AdminRecovery.query.count() == 0


def test_multiple_admins_need_exact_username(empty_app, monkeypatch):
    add_admin(empty_app, 'first')
    with empty_app.app_context():
        user = User(username='second', email='second@example.invalid', role='admin')
        user.set_password('second-password-123')
        db.session.add(user)
        db.session.commit()
    configure(monkeypatch)
    assert empty_app.test_client().get('/login/admin').status_code == 503
    monkeypatch.setenv('ADMIN_RECOVERY_USERNAME', 'first')
    page = submit_login(empty_app.test_client(), 'first', 'restored-password-123')
    assert page.status_code == 200 and b'A clear view of your school' in page.data
    with empty_app.app_context():
        assert User.query.filter_by(username='second').first().check_password('second-password-123')
