import re
import pytest
from app import create_app, db
from app.models import User, Student, DemoDataset


@pytest.fixture
def empty_app(tmp_path, monkeypatch):
    for name in ['VERCEL', 'SEED_DEMO_DATA', 'DEMO_PASSWORD', 'BOOTSTRAP_ADMIN_PASSWORD', 'BOOTSTRAP_ADMIN_USERNAME', 'BOOTSTRAP_ADMIN_EMAIL']:
        monkeypatch.delenv(name, raising=False)
    app = create_app({'TESTING': True, 'SECRET_KEY': 'stable-test-secret', 'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(tmp_path/'school.db')})
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def submit_login(client, username, password):
    response = client.get('/login/admin')
    assert response.status_code == 200
    token = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()
    return client.post('/login/admin', data={'username': username, 'password': password, 'csrf_token': token}, follow_redirects=True)


def test_first_login_initializes_missing_tables(empty_app):
    client = empty_app.test_client()
    assert submit_login(client, 'not-created', 'password').status_code == 200
    with empty_app.app_context():
        assert User.query.count() == 0
        assert DemoDataset.query.count() == 0


def test_bootstrap_admin_and_hosted_demo_flow(empty_app, monkeypatch):
    monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'school-admin-password-123')
    monkeypatch.setenv('SEED_DEMO_DATA', 'true')
    monkeypatch.setenv('DEMO_PASSWORD', 'school-demo-password-123')
    response = submit_login(empty_app.test_client(), 'admin', 'school-admin-password-123')
    assert response.status_code == 200
    assert b'A clear view of your school' in response.data
    with empty_app.app_context():
        assert Student.query.count() == 60
        assert User.query.filter_by(role='admin').count() == 1
        assert User.query.filter_by(username='demo.admin').first() is None
        assert User.query.filter_by(username='demo.student001').first().check_password('school-demo-password-123')


def test_bootstrap_never_resets_existing_admin(empty_app, monkeypatch):
    with empty_app.app_context():
        db.create_all()
        user = User(username='admin', email='admin@school.test', role='admin')
        user.set_password('original-password-123')
        db.session.add(user)
        db.session.commit()
    monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'different-password-123')
    response = submit_login(empty_app.test_client(), 'admin', 'original-password-123')
    assert response.status_code == 200 and b'A clear view of your school' in response.data
    with empty_app.app_context():
        assert User.query.filter_by(username='admin').first().check_password('original-password-123')


def test_bad_demo_password_returns_actionable_setup_error(empty_app, monkeypatch):
    monkeypatch.setenv('SEED_DEMO_DATA', 'true')
    response = empty_app.test_client().get('/login/admin')
    assert response.status_code == 503
    assert b'12 to 128 characters' in response.data
    monkeypatch.setenv('DEMO_PASSWORD', 'school-demo-password-123')
    assert empty_app.test_client().get('/login/admin').status_code == 200


def test_database_unavailable_returns_friendly_error(monkeypatch, tmp_path):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('SEED_DEMO_DATA', raising=False)
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(tmp_path/'missing-folder'/'school.db')})
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = '999'
    response = client.get('/login/admin')
    assert response.status_code == 503
    assert b'database could not be prepared' in response.data
    assert b'Traceback' not in response.data


def test_local_python_runner_generates_expanded_demo(empty_app, monkeypatch):
    from run import seed_demo_data
    monkeypatch.setenv('DEMO_PASSWORD', 'local-demo-password-123')
    seed_demo_data(empty_app)
    seed_demo_data(empty_app)
    with empty_app.app_context():
        assert Student.query.count() == 60
        assert User.query.filter_by(username='demo.admin').first().check_password('local-demo-password-123')


@pytest.mark.parametrize('missing', ['DATABASE_URL', 'SECRET_KEY'])
def test_hosted_configuration_requires_database_and_stable_secret(empty_app, monkeypatch, missing):
    empty_app.testing = False
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('DATABASE_URL', 'configured-only-for-validation')
    monkeypatch.setenv('SECRET_KEY', 'stable-test-secret')
    monkeypatch.delenv(missing)
    response = empty_app.test_client().get('/login/admin')
    assert response.status_code == 503
    assert missing.encode() in response.data
    assert empty_app.test_client().get('/static/css/workspace.css').status_code == 200
