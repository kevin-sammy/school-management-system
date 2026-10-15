from tests.test_portals import app, client, login, post
from app import db
from app.demo import seed_demo_dataset
from app.sample_names import normalize_sample_accounts
from app.models import User, Parent, SampleAccount, StudentAccount, Staff, Attendance


def test_sample_rename_preserves_links_passwords_and_audit_names(app):
    with app.app_context():
        seed_demo_dataset('sample-password-123')
        teacher=User.query.filter_by(username='demo.teacher01').one()
        student=User.query.filter_by(username='demo.student001').one()
        teacher_id,student_id=teacher.id,student.id
        password_hash=teacher.password_hash
        student_profile_id=StudentAccount.query.filter_by(user_id=student.id).one().student_id
        collision=User(username='grace.kamau',email='collision@test.example',role='admin')
        collision.set_password('another-password-123')
        db.session.add(collision)
        db.session.commit()
        assert normalize_sample_accounts()==96
        assert teacher.id==teacher_id and teacher.password_hash==password_hash
        assert teacher.username=='grace.kamau2'
        assert student.id==student_id and not student.username.startswith('demo.')
        assert StudentAccount.query.filter_by(user_id=student_id).one().student_id==student_profile_id
        assert db.session.get(SampleAccount,'teacher01').user_id==teacher_id
        assert not Parent.query.filter(Parent.first_name.like('Demo Guardian%')).count()
        assert not Attendance.query.filter_by(recorded_by='demo.teacher01').count()
        assert User.query.filter_by(username='admin').one().email=='admin@test.example'
        assert normalize_sample_accounts()==0
        assert SampleAccount.query.count()==96
        assert teacher.check_password('sample-password-123')


def test_existing_dataset_normalized_on_next_cold_start(client,app):
    with app.app_context():
        seed_demo_dataset('sample-password-123')
    login(client,'admin')
    page=client.get('/portal/accounts')
    assert page.status_code==200 and b'grace.kamau' in page.data
    assert b'demo.student001' not in page.data
    with app.app_context():
        assert db.session.get(SampleAccount,'parent01').user.username=='joseph.kamau'
