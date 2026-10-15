from datetime import date
import pytest
from app import db
from app.models import CourseMaterial, CoursePost, CourseReply, Submission, SubmissionAssessment, Grade
from test_portals import app, client, login, post


def publish_material(client, class_id=1, **extra):
    return post(client, f'/learning/courses/{class_id}', {'kind': 'material', 'material_kind': 'page', 'module': 'Unit 1', 'title': 'Introduction', 'content': 'Lesson content', **extra})


@pytest.mark.parametrize('name', ['student', 'teacher', 'admin'])
def test_workspace_pages_render(client, name):
    login(client, name)
    for url in ['/learning/courses', '/learning/assignments', '/learning/calendar', '/learning/courses/1', '/learning/courses/1?tab=updates', '/learning/courses/1?tab=assignments']:
        assert client.get(url).status_code == 200, url
    assert client.get('/learning/courses/1?tab=invalid').status_code == 400
    if name == 'student':
        assert client.get('/learning/records').status_code == 200
        assert client.get('/learning/gradebook/1').status_code == 403
    else:
        assert client.get('/learning/gradebook/1').status_code == 200
        assert client.get('/learning/gradebook/1?export=csv').status_code == 200


def test_material_access_protocol_validation_and_delete(client, app):
    login(client, 'teacher')
    assert publish_material(client).status_code == 302
    for link in ['javascript:alert(1)', 'http://example.com', 'https://user:pass@example.com', 'https:///missing-host', 'https://[bad-host', 'https://example.com/bad path']:
        assert publish_material(client, material_kind='link', content=link).status_code == 400
    assert publish_material(client, material_kind='link', content='https://example.com/resources').status_code == 302
    assert publish_material(client, class_id=2).status_code == 403
    with app.app_context():
        material_id = CourseMaterial.query.first().id
    post(client, '/logout', {})
    login(client, 'student')
    page = client.get('/learning/courses/1')
    assert b'Introduction' in page.data and b'Lesson content' in page.data
    assert publish_material(client).status_code == 403
    assert client.get('/learning/courses/2').status_code == 403
    assert post(client, f'/learning/materials/{material_id}/delete', {}).status_code == 403
    post(client, '/logout', {})
    login(client, 'otherteacher')
    assert post(client, f'/learning/materials/{material_id}/delete', {}).status_code == 403
    post(client, '/logout', {})
    login(client, 'teacher')
    assert post(client, f'/learning/materials/{material_id}/delete', {}).status_code == 302


def test_discussions_are_course_scoped_and_escaped(client, app):
    login(client, 'teacher')
    assert post(client, '/learning/courses/1', {'kind': 'discussion', 'title': 'Think together', 'body': '<script>alert(1)</script>'}).status_code == 302
    with app.app_context():
        discussion_id = CoursePost.query.first().id
    post(client, '/logout', {})
    login(client, 'student')
    assert post(client, f'/learning/discussions/{discussion_id}', {'body': 'My response'}).status_code == 302
    page = client.get(f'/learning/discussions/{discussion_id}')
    assert b'My response' in page.data
    assert b'&lt;script&gt;' in page.data
    assert b'<script>alert(1)</script>' not in page.data
    post(client, '/logout', {})
    login(client, 'otherstudent')
    assert client.get(f'/learning/discussions/{discussion_id}').status_code == 403
    assert post(client, f'/learning/discussions/{discussion_id}', {'body': 'Wrong class'}).status_code == 403
    with app.app_context():
        assert CourseReply.query.count() == 1


def test_draft_publish_update_unpublish_and_resubmit(client, app):
    login(client, 'student')
    assert post(client, '/portal/assignments/1', {'answer': '1/2 + 1/4 = 3/4'}).status_code == 302
    with app.app_context():
        sid = Submission.query.first().id
    assert post(client, f'/learning/submissions/{sid}/assess', {}).status_code == 403
    post(client, '/logout', {})
    login(client, 'teacher')
    data = {'points': 83, 'max_points': 100, 'term': 'Term 1', 'year': 2026, 'feedback': 'Good reasoning', 'action': 'draft'}
    for invalid in ['nan', 'inf', '-1', '101']:
        assert post(client, f'/learning/submissions/{sid}/assess', {**data, 'points': invalid}).status_code == 400
    assert post(client, f'/learning/submissions/{sid}/assess', data).status_code == 302
    with app.app_context():
        assert Grade.query.filter_by(student_id=1).count() == 0
        assert SubmissionAssessment.query.first().grade_id is None
    post(client, '/logout', {})
    login(client, 'student')
    assert b'83.0/100.0' not in client.get('/portal/assignments/1').data
    post(client, '/logout', {})
    login(client, 'otherteacher')
    assert post(client, f'/learning/submissions/{sid}/assess', data).status_code == 403
    post(client, '/logout', {})
    login(client, 'teacher')
    assert post(client, f'/learning/submissions/{sid}/assess', {**data, 'action': 'publish'}).status_code == 302
    assert post(client, f'/learning/submissions/{sid}/assess', {**data, 'points': 90, 'action': 'publish'}).status_code == 302
    with app.app_context():
        assert Grade.query.filter_by(student_id=1).count() == 1
        assert Grade.query.filter_by(student_id=1).first().score == 90
    assert b'90.0/100.0' in client.get('/learning/gradebook/1?export=csv').data
    post(client, '/logout', {})
    login(client, 'student')
    assert b'90.0/100.0' in client.get('/portal/assignments/1').data
    assert b'90.0' in client.get('/learning/records').data
    post(client, '/logout', {})
    login(client, 'teacher')
    assert post(client, f'/learning/submissions/{sid}/assess', data).status_code == 302
    with app.app_context():
        assert Grade.query.filter_by(student_id=1).count() == 0
    assert post(client, f'/learning/submissions/{sid}/assess', {**data, 'action': 'publish'}).status_code == 302
    post(client, '/logout', {})
    login(client, 'student')
    assert post(client, '/portal/assignments/1', {'answer': 'Updated answer'}).status_code == 302
    with app.app_context():
        assert SubmissionAssessment.query.count() == 0
        assert Grade.query.filter_by(student_id=1).count() == 0
        assert Submission.query.first().feedback is None


def test_calendar_filters_and_gradebook_privacy(client):
    login(client, 'student')
    page = client.get('/learning/calendar?month=10&year=2026')
    assert page.status_code == 200
    assert b'Private homework' not in page.data
    for query in ['month=0', 'month=13', 'year=oops', 'year=1999']:
        assert client.get('/learning/calendar?' + query).status_code == 400
    assert client.get('/learning/assignments?status=invalid').status_code == 400
    assert b'Private homework' not in client.get('/learning/assignments').data
    post(client, '/logout', {})
    login(client, 'teacher')
    assert client.get('/learning/gradebook/2?export=csv').status_code == 403
    assert b'Private' not in client.get('/learning/gradebook/1?export=csv').data


def test_local_assets_available(client):
    for path in ['/static/css/workspace.css', '/static/vendor/bootstrap.min.css']:
        response = client.get(path)
        assert response.status_code == 200
        assert len(response.data) > 1000
