from tests.test_portals import app, client, login, post
from app import db
from app.models import User, Staff, Parent, Student


def teacher_data(**changes):
    return dict(first_name='Grace',last_name='Kamau',role='Teacher',email='grace@school.example',
                initial_password='teacher-password-123',**changes)


def test_teacher_profile_save_creates_usable_non_admin_login(client,app):
    login(client,'admin')
    page=client.get('/staff/add')
    assert b'data-profile-account' in page.data and b'name="initial_password"' in page.data
    assert client.get('/portal/username-preview?first_name=Grace&last_name=Kamau').json['username']=='gkamau'
    data=teacher_data(username='admin',user_role='admin')
    response=post(client,'/staff/add',data)
    assert response.status_code==302
    with app.app_context():
        teacher=User.query.filter_by(username='gkamau').one()
        member=Staff.query.filter_by(user_id=teacher.id).one()
        assert teacher.role=='teacher' and member.first_name=='Grace'
        assert teacher.check_password('teacher-password-123')
        assert teacher.password_hash!='teacher-password-123'
        staff_id=member.id
    assert b'gkamau' in client.get('/staff/').data
    assert b'data-linked-username="gkamau"' in client.get(f'/staff/{staff_id}/edit').data
    assert post(client,f'/staff/{staff_id}/delete',{}).status_code==409
    with client.session_transaction() as session:
        assert 'teacher-password-123' not in str(dict(session))
    post(client,'/logout',{})
    assert post(client,'/login/teacher',dict(username='gkamau',password='teacher-password-123')).status_code==302
    assert client.get('/portal/').status_code==200
    assert client.get('/students/').status_code==403
    assert client.get('/portal/accounts').status_code==403


def test_guardian_creation_login_and_child_scope(client,app):
    login(client,'admin')
    assert b'data-account-kind="parent"' in client.get('/parents/add').data
    data=dict(first_name='Mary',last_name='Otieno',email='mary@example.test',phone='0700000000',
              relationship='guardian',initial_password='parent-password-123',role='admin',username='admin')
    assert post(client,'/parents/add',data).status_code==302
    with app.app_context():
        user=User.query.filter_by(username='motieno').one()
        parent=Parent.query.filter_by(user_id=user.id).one()
        assert user.role=='parent' and parent.relationship=='guardian'
        assert user.check_password('parent-password-123')
        db.session.get(Student,1).parent_id=parent.id
        db.session.commit()
    assert b'motieno' in client.get('/parents/').data
    post(client,'/logout',{})
    assert post(client,'/login/parent',dict(username='motieno',password='parent-password-123')).status_code==302
    assert b'Alice Learner' in client.get('/family/').data
    assert client.get('/family/?student_id=2').status_code==403
    assert client.get('/staff/').status_code==403
    assert client.get('/portal/accounts').status_code==403


def test_collision_preview_and_save_share_namespace_across_roles(client,app):
    with app.app_context():
        existing=User(username='GKAMAU',email='reserved@example.test',role='admin')
        existing.set_password('original-password-123')
        db.session.add(existing)
        db.session.commit()
    login(client,'admin')
    assert client.get('/portal/username-preview?first_name=Grace&last_name=Kamau').json['username']=='gkamau2'
    assert post(client,'/staff/add',teacher_data()).status_code==302
    assert post(client,'/parents/add',dict(first_name='George',last_name='Kamau',email='george@example.test',
        relationship='parent',initial_password='parent-password-123')).status_code==302
    with app.app_context():
        assert User.query.filter_by(username='gkamau2',role='teacher').one()
        assert User.query.filter_by(username='gkamau3',role='parent').one()
        assert User.query.filter_by(username='GKAMAU').one().check_password('original-password-123')
    assert client.get('/portal/username-preview?first_name=Élise&last_name=O%27Neill').json['username']=='eoneill'


def test_invalid_password_or_duplicate_email_does_not_leave_orphan_profiles(client,app):
    login(client,'admin')
    data=teacher_data()
    data['initial_password']='short'
    assert post(client,'/staff/add',data).status_code==400
    data['initial_password']='teacher-password-123'
    data['email']='ADMIN@test.example'
    assert post(client,'/staff/add',data).status_code==409
    assert post(client,'/parents/add',dict(first_name='Mary',last_name='Test',email='not-an-email',initial_password='parent-password-123')).status_code==400
    with app.app_context():
        assert Staff.query.filter_by(first_name='Grace').count()==0
        assert Parent.query.filter_by(first_name='Mary').count()==0
        assert User.query.filter_by(username='gkamau').count()==0


def test_existing_unlinked_profiles_use_auto_names_and_cannot_be_linked_twice(client,app):
    login(client,'admin')
    data=dict(kind='account',role='teacher',profile_id=1,username='admin',email='new@example.test',password='teacher-password-123')
    assert post(client,'/portal/accounts',data).status_code==302
    assert post(client,'/portal/accounts',data).status_code==400
    with app.app_context():
        assert User.query.filter_by(username='nteacher',role='teacher').one()
        assert User.query.filter_by(username='admin').one().role=='admin'


def test_name_edits_preserve_login_and_inactive_teachers_cannot_use_existing_session(client,app):
    login(client,'admin')
    assert post(client,'/staff/add',teacher_data()).status_code==302
    with app.app_context():
        member=Staff.query.filter_by(first_name='Grace').one()
        staff_id=member.id
        original=User.query.filter_by(username='gkamau').one().password_hash
    data=dict(first_name='New name',last_name='Different',role='Teacher',email='grace@school.example',status='active')
    assert post(client,f'/staff/{staff_id}/edit',data).status_code==302
    with app.app_context():
        assert User.query.filter_by(username='gkamau').one().password_hash==original
    post(client,'/logout',{})
    assert post(client,'/login/teacher',dict(username='gkamau',password='teacher-password-123')).status_code==302
    with app.app_context():
        db.session.get(Staff,staff_id).status='inactive'
        db.session.commit()
    assert client.get('/portal/').status_code==302
    assert post(client,'/login/teacher',dict(username='gkamau',password='teacher-password-123')).status_code==200
    with client.session_transaction() as session:
        assert '_user_id' not in session


def test_non_teacher_staff_do_not_get_accounts_and_preview_is_admin_only(client,app):
    login(client,'admin')
    assert post(client,'/staff/add',dict(first_name='Support',last_name='Person',role='Support')).status_code==302
    with app.app_context():
        assert Staff.query.filter_by(first_name='Support').one().user_id is None
    post(client,'/logout',{})
    login(client,'teacher')
    assert client.get('/portal/username-preview?first_name=Grace&last_name=Kamau').status_code==403
    assert post(client,'/staff/add',teacher_data()).status_code==403
    assert post(client,'/parents/add',dict(first_name='Mary',last_name='Test')).status_code==403
