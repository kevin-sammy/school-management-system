from datetime import datetime, timedelta
from tests.test_portals import app, client, login, post
from app import db
from app.models import (User, Staff, Parent, Student, TransportRoute, TransportPassenger,
    SchoolConversation, SchoolMessage, MailParticipant, CourseMaterial, CollaborationRoom)


def setup_transport(app):
    with app.app_context():
        teacher = User.query.filter_by(username='teacher').one()
        parent_user = User.query.filter_by(username='parent').one()
        staff = db.session.get(Staff, 1)
        staff.user_id = teacher.id
        parent = Parent(first_name='Mary', last_name='Learner', user_id=parent_user.id)
        db.session.add(parent)
        db.session.flush()
        db.session.get(Student, 1).parent_id = parent.id
        route = TransportRoute(name='South route', vehicle_registration='KXX 001', driver_name='John',
                               driver_phone='0700000000', teacher_id=staff.id, status='active')
        db.session.add(route)
        db.session.flush()
        db.session.add(TransportPassenger(route_id=route.id, student_id=1, home_area='Sample estate',
            pickup_point='Private pickup location', pickup_time='06:45', dropoff_time='16:30'))
        db.session.commit()
        return route.id


def test_transport_role_privacy_and_forms(client, app):
    route_id = setup_transport(app)
    for user in ['student', 'parent', 'teacher', 'admin']:
        login(client, user)
        response = client.get('/transport/')
        assert response.status_code == 200
        assert b'Private pickup location' in response.data
        if user in ['student', 'parent']:
            assert client.get(f'/transport/routes/{route_id}').status_code == 403
        else:
            assert client.get(f'/transport/routes/{route_id}').status_code == 200
        post(client, '/logout', {})
    login(client, 'otherstudent')
    assert b'Private pickup location' not in client.get('/transport/').data
    post(client, '/logout', {})
    login(client, 'otherteacher')
    assert client.get(f'/transport/routes/{route_id}').status_code == 403
    assert post(client, f'/transport/routes/{route_id}', {}).status_code == 403
    post(client, '/logout', {})
    login(client, 'admin')
    assert client.get('/transport/routes/new').status_code == 200
    assert client.get(f'/transport/routes/{route_id}/edit').status_code == 200
    assert post(client, '/staff/1/delete', {}).status_code == 409
    data = dict(student_id=2, home_area='Second estate', pickup_point='Second stop', pickup_time='07:10', dropoff_time='17:00')
    assert post(client, f'/transport/routes/{route_id}', {**data, 'pickup_time':'bad'}).status_code == 400
    assert post(client, f'/transport/routes/{route_id}', data).status_code == 302
    assert post(client, '/students/2/delete', {}).status_code == 409
    with app.app_context():
        passenger = TransportPassenger.query.filter_by(student_id=2).one()
        passenger_id = passenger.id
    assert post(client, f'/transport/passengers/{passenger_id}/remove', {}).status_code == 302


def test_private_inbox_contact_scope_reply_and_broadcast(client, app):
    setup_transport(app)
    login(client, 'student')
    assert client.get('/mail/compose').status_code == 200
    with app.app_context():
        teacher_id = User.query.filter_by(username='teacher').one().id
        unrelated_id = User.query.filter_by(username='otherstudent').one().id
    data = dict(subject='Homework question', body='<script>not executable</script>', recipient_id=teacher_id)
    assert post(client, '/mail/compose', {**data, 'recipient_id':unrelated_id}).status_code == 403
    assert post(client, '/mail/compose', {**data, 'audience':'all'}).status_code == 403
    assert post(client, '/mail/compose', data).status_code == 302
    with app.app_context():
        thread_id = SchoolConversation.query.one().id
    page = client.get(f'/mail/{thread_id}')
    assert page.status_code == 200 and b'&lt;script&gt;' in page.data
    post(client, '/logout', {})
    login(client, 'teacher')
    assert b'Unread' in client.get('/mail/').data
    assert post(client, f'/mail/{thread_id}', {'body':'See the course page.'}).status_code == 302
    post(client, '/logout', {})
    login(client, 'admin')
    # Even administrators cannot read someone else's private thread.
    assert client.get(f'/mail/{thread_id}').status_code == 403
    assert post(client, '/mail/compose', {'audience':'parents','subject':'School news','body':'Welcome'}).status_code == 302
    with app.app_context():
        assert SchoolConversation.query.count() == 2
        assert all(len(c.participants)==2 for c in SchoolConversation.query.all())


def test_hub_materials_and_collaboration_are_course_scoped(client, app):
    with app.app_context():
        db.session.add_all([CourseMaterial(teaching_class_id=1,title='Fraction guide',module='Numbers',kind='page',content='Halves and quarters'),
                           CourseMaterial(teaching_class_id=2,title='Secret resource',module='Private',kind='page',content='Hidden')])
        db.session.commit()
    login(client, 'teacher')
    data=dict(class_id=1,title='Math live lesson',platform='Google Meet',join_url='https://meet.google.com/abc-defg-hij',schedule='Monday 09:00 EAT')
    assert post(client, '/hub/collaborate', {**data,'class_id':2}).status_code == 403
    assert post(client, '/hub/collaborate', {**data,'join_url':'https://meet.google.com.evil.example/x'}).status_code == 400
    assert post(client, '/hub/collaborate', {**data,'join_url':'javascript:alert(1)'}).status_code == 400
    assert post(client, '/hub/collaborate', data).status_code == 302
    post(client, '/logout', {})
    login(client, 'student')
    page=client.get('/hub/?q=quarters')
    assert b'Fraction guide' in page.data and b'Secret resource' not in page.data
    assert b'Math live lesson' in client.get('/hub/collaborate').data
    assert post(client, '/hub/collaborate', data).status_code == 403
    post(client, '/logout', {})
    login(client, 'otherstudent')
    assert b'Math live lesson' not in client.get('/hub/collaborate').data
    post(client, '/logout', {})
    login(client, 'parent')
    assert client.get('/hub/').status_code == 403
