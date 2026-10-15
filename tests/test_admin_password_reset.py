from tests.test_portals import app,client,login,post
from app import db
from app.models import User, Staff, PortalPasswordChange


def linked_teacher(app):
    with app.app_context():
        user=User.query.filter_by(username='teacher').one()
        member=db.session.get(Staff,1)
        member.user_id=user.id
        db.session.commit()
        return user.id


def test_staff_edit_shows_reset_for_linked_teacher_and_preserves_password_when_blank(client,app):
    teacher_id=linked_teacher(app)
    login(client,'admin')
    page=client.get('/staff/1/edit')
    assert b'Set / reset password' in page.data
    assert b'name="initial_password"' in page.data and b'name="confirm_password"' in page.data
    data=dict(first_name='New',last_name='Teacher',role='Teacher',status='active')
    with app.app_context():
        original=db.session.get(User,teacher_id).password_hash
    assert post(client,'/staff/1/edit',data).status_code==302
    with app.app_context():
        assert db.session.get(User,teacher_id).password_hash==original
    assert post(client,'/staff/1/edit',{**data,'initial_password':'replacement-pass-123','confirm_password':'different-password'}).status_code==400
    assert post(client,'/staff/1/edit',{**data,'initial_password':'replacement-pass-123','confirm_password':'replacement-pass-123'}).status_code==302
    with app.app_context():
        user=db.session.get(User,teacher_id)
        assert user.username=='teacher' and user.role=='teacher'
        assert user.check_password('replacement-pass-123')
        assert not user.check_password('test-password-123')
        assert db.session.get(PortalPasswordChange,teacher_id)
    with client.session_transaction() as session:
        assert 'replacement-pass-123' not in str(dict(session))
    post(client,'/logout',{})
    assert post(client,'/login/teacher',dict(username='teacher',password='replacement-pass-123')).status_code==302
    assert client.get('/portal/').status_code==200
    assert client.get('/portal/accounts').status_code==403


def test_admin_reset_parent_invalidates_existing_and_legacy_sessions(client,app):
    modern=app.test_client()
    legacy=app.test_client()
    login(modern,'parent')
    login(legacy,'parent')
    with legacy.session_transaction() as session:
        session.pop('_credential_stamp',None)
    login(client,'admin')
    with app.app_context():
        parent_id=User.query.filter_by(username='parent').one().id
    path=f'/portal/accounts/{parent_id}/password'
    assert b'Set / reset password' in client.get(path).data
    assert client.post(path,data={'password':'replacement-pass-123'}).status_code==400
    assert post(client,path,dict(password='short',confirm_password='short')).status_code==400
    assert post(client,path,dict(password='replacement-pass-123',confirm_password='replacement-pass-123')).status_code==302
    assert modern.get('/family/').status_code==302
    assert legacy.get('/family/').status_code==302
    assert post(modern,'/login/parent',dict(username='parent',password='replacement-pass-123')).status_code==302
    assert modern.get('/family/').status_code==200


def test_non_admin_cannot_reset_other_account_and_admin_cannot_target_admin(client,app):
    with app.app_context():
        users={u.username:u.id for u in User.query.all()}
    for name in ['teacher','parent','student']:
        login(client,name)
        path=f'/portal/accounts/{users["teacher"]}/password'
        assert client.get(path).status_code==403
        assert post(client,path,dict(password='replacement-pass-123',confirm_password='replacement-pass-123')).status_code==403
        post(client,'/logout',{})
    login(client,'admin')
    assert client.get(f'/portal/accounts/{users["admin"]}/password').status_code==403


def test_own_password_change_keeps_current_session_and_expires_other_sessions(client,app):
    other=app.test_client()
    login(client,'parent')
    login(other,'parent')
    assert post(client,'/portal/password',dict(current_password='test-password-123',password='replacement-pass-123',confirm_password='replacement-pass-123')).status_code==302
    assert client.get('/family/').status_code==200
    assert other.get('/family/').status_code==302


def test_forgotten_password_requests_are_generic_deduplicated_and_admin_only(client,app):
    from app.models import PortalPasswordRequest
    assert b'Forgot password?' in client.get('/login/student').data
    assert client.get('/forgot-password').status_code==200
    assert client.post('/forgot-password',data={'identifier':'parent'}).status_code==400
    responses=[]
    for identifier in ['not-a-school-user','parent','parent']:
        visitor=app.test_client()
        response=post(visitor,'/forgot-password',{'identifier':identifier})
        assert response.status_code==302
        page=visitor.get(response.location)
        assert b'If these details match a school portal account' in page.data
        responses.append(page.data)
    with app.app_context():
        assert PortalPasswordRequest.query.count()==1
        request=PortalPasswordRequest.query.one()
        assert request.user.username=='parent' and request.status=='pending'
        user_id=request.user_id
    login(client,'parent')
    assert client.get('/portal/password-requests').status_code==403
    post(client,'/logout',{})
    login(client,'admin')
    assert b'parent@test.example' in client.get('/portal/password-requests').data
    assert post(client,f'/portal/accounts/{user_id}/password',dict(password='replacement-pass-123',confirm_password='replacement-pass-123')).status_code==302
    with app.app_context():
        assert db.session.get(PortalPasswordRequest,user_id).status=='resolved'
    assert b'No pending requests' in client.get('/portal/password-requests').data


def test_legacy_session_without_a_password_change_stays_logged_in(client):
    login(client,'student')
    with client.session_transaction() as session:
        session.pop('_credential_stamp',None)
    assert client.get('/portal/').status_code==200


def test_student_can_request_by_email_and_use_replacement_password(client,app):
    from app.models import PortalPasswordRequest
    visitor=app.test_client()
    assert post(visitor,'/forgot-password',{'identifier':'STUDENT@test.example'}).status_code==302
    admin_visitor=app.test_client()
    assert post(admin_visitor,'/forgot-password',{'identifier':'admin'}).status_code==302
    with app.app_context():
        assert PortalPasswordRequest.query.count()==1
        user_id=PortalPasswordRequest.query.one().user_id
        assert db.session.get(User,user_id).role=='student'
    login(client,'admin')
    assert post(client,f'/portal/accounts/{user_id}/password',dict(password='student-new-pass-123',confirm_password='student-new-pass-123')).status_code==302
    post(client,'/logout',{})
    assert post(client,'/login/student',dict(username='student',password='test-password-123')).status_code==200
    assert post(client,'/login/student',dict(username='student',password='student-new-pass-123')).status_code==302
    assert client.get('/portal/').status_code==200
    assert client.get('/students/').status_code==403
