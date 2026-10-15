import pytest
from app import db
from app.models import User,Parent,Student,Attendance,FeeRecord,Grade,Notification,DemoDataset
from app.demo import seed_demo_dataset,seed_demo_parent_accounts,DATASET_KEY
from test_portals import app,client,login,post


@pytest.fixture
def family(app):
    with app.app_context():
        parent_user=User.query.filter_by(username='parent').first()
        guardian=Parent(first_name='Guardian',last_name='One',user_id=parent_user.id)
        db.session.add(guardian)
        db.session.flush()
        db.session.get(Student,1).parent_id=guardian.id
        sibling=Student(first_name='Sibling',last_name='One',class_name='Grade 7',parent_id=guardian.id)
        db.session.add(sibling)
        db.session.add(Attendance(student_id=1,date='2026-10-15',status='present',notes='Own attendance'))
        db.session.add(Attendance(student_id=2,date='2026-10-15',status='absent',notes='PRIVATE attendance'))
        db.session.add(FeeRecord(student_id=1,record_type='payment',amount=200,description='Own payment'))
        db.session.add(Notification(title='Guardian notice',message='Family update',target='parents'))
        db.session.add(Notification(title='PRIVATE staff notice',message='Staff',target='staff'))
        db.session.commit()
        return parent_user.id,sibling.id


def test_parent_login_and_own_child_fee_attendance_view(client,family):
    response=post(client,'/login/parent',{'username':'parent','password':'test-password-123'})
    assert response.status_code==302
    assert client.get('/dashboard').location.endswith('/family/')
    page=client.get('/family/')
    assert page.status_code==200
    for expected in [b'Alice Learner',b'Sibling One',b'Own attendance',b'Own payment',b'1,000.00',b'Guardian notice']:
        assert expected in page.data
    for forbidden in [b'PRIVATE attendance',b'Private grade',b'99,999',b'PRIVATE staff notice',b'Staff private notice']:
        assert forbidden not in page.data
    assert client.get('/family/?student_id=2').status_code==403
    assert client.get('/family/?student_id=bad').status_code==400
    assert client.get('/family/?student_id='+str(family[1])).status_code==200


@pytest.mark.parametrize('path',['/students/','/fees/','/attendance/','/grades/','/learning/courses','/learning/records','/family/previews'])
def test_parent_cannot_access_other_role_pages(client,family,path):
    login(client,'parent')
    assert client.get(path).status_code==403


def test_no_parent_profile_shows_helpful_empty_state(client):
    login(client,'parent')
    response=client.get('/family/')
    assert response.status_code==200
    assert b'link your parent profile' in response.data


def test_admin_creates_linked_parent_account(client,app):
    with app.app_context():
        guardian=Parent(first_name='New',last_name='Guardian')
        db.session.add(guardian)
        db.session.flush()
        db.session.get(Student,1).parent_id=guardian.id
        db.session.commit()
        profile_id=guardian.id
    login(client,'admin')
    data={'kind':'account','role':'parent','profile_id':profile_id,'username':'nguardian','email':'guardian@example.invalid','password':'guardian-password-123'}
    assert post(client,'/portal/accounts',data).status_code==302
    with app.app_context():
        assert db.session.get(Parent,profile_id).user_id==User.query.filter_by(username='nguardian').first().id
    post(client,'/logout',{})
    assert post(client,'/login/parent',{'username':'nguardian','password':'guardian-password-123'}).status_code==302
    assert b'Alice Learner' in client.get('/family/').data


def test_admin_previews_scoped_dashboards_without_impersonation(client,app,family):
    login(client,'admin')
    assert client.get('/family/previews').status_code==200
    with app.app_context():
        ids={u.username:u.id for u in User.query.all()}
    with client.session_transaction() as session:
        admin_id=session['_user_id']
    for name in ['teacher','student','parent']:
        response=client.get(f'/family/previews/{ids[name]}')
        assert response.status_code==200
        assert b'Read-only' in response.data and b'inert' in response.data
        assert b'Accounts &amp; scheduling' not in response.data and b'Accounts & scheduling' not in response.data
        if name=='student':
            assert b'Private homework' not in response.data
        if name=='parent':
            assert b'PRIVATE attendance' not in response.data
        with client.session_transaction() as session:
            assert session['_user_id']==admin_id
    assert client.post(f'/family/previews/{ids["teacher"]}').status_code in [400,405]
    post(client,'/logout',{})
    login(client,'student')
    assert client.get(f'/family/previews/{ids["teacher"]}').status_code==403


def test_demo_has_parent_accounts_and_old_demo_can_be_upgraded(app):
    with app.app_context():
        seed_demo_dataset('demo-password-123')
        parent=User.query.filter_by(username='demo.parent01').first()
        assert parent and parent.role=='parent'
        guardian=Parent.query.filter_by(user_id=parent.id).first()
        assert len(guardian.children)==2
        # Emulate a previous demo with no parent login accounts.
        for guardian in Parent.query.filter(Parent.email.like('demo.parent%@schoolms.example.invalid')).all():
            guardian.user_id=None
        db.session.flush()
        for user in User.query.filter(User.username.like('demo.parent%')).all():
            db.session.delete(user)
        db.session.commit()
        summary,created=seed_demo_parent_accounts('new-parent-password-123')
        assert created and summary['parent_logins']==30
        again,created=seed_demo_parent_accounts('different-password-123')
        assert not created
        assert User.query.filter_by(username='demo.parent01').first().check_password('new-parent-password-123')


def test_brand_name_on_login_and_reports(client):
    assert b'Kevin Brook International Schools' in client.get('/login/parent').data
    login(client,'admin')
    page=client.get('/grades/report/1')
    assert b'Kevin Brook International Schools' in page.data
    assert b'Kitengela' not in page.data
