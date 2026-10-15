import io
import json
from datetime import datetime, timedelta
from urllib.error import URLError
from tests.test_portals import app, client, login, post
from app import db
from app.models import ChatAllowance


def test_guided_chat_is_instant_and_role_scoped(client, monkeypatch):
    monkeypatch.delenv('AI_GATEWAY_MODEL',raising=False)
    login(client,'parent')
    assert client.get('/hub/help').status_code==200
    result=post(client,'/hub/help',{'message':'How do I see my child fee balance?'}).json
    assert result['mode']=='guided'
    assert result['replies'][0]['url']=='/family/'
    result=post(client,'/hub/help',{'message':'exam'}).json
    assert not result['replies']
    assert client.post('/hub/help',data={'message':'transport'}).status_code==400
    assert post(client,'/hub/help',{'message':'x'*501}).status_code==400
    post(client,'/logout',{})
    login(client,'student')
    result=post(client,'/hub/help',{'message':'Where are learning materials?'}).json
    assert result['replies'][0]['url']=='/hub/'
    assert all(r['url']!='/portal/accounts' for r in result['replies'])


def test_ai_chat_auth_grounding_failure_and_quota(client,app,monkeypatch):
    monkeypatch.setenv('AI_GATEWAY_MODEL','configured/model')
    monkeypatch.setenv('AI_GATEWAY_API_KEY','secret-for-test-only')
    calls=[]
    def gateway(request,timeout):
        calls.append(request)
        payload=json.loads(request.data)
        assert payload['model']=='configured/model'
        assert len(payload['messages'])==2
        assert 'current role is student' in payload['messages'][0]['content']
        assert 'Accounts and dashboard previews' not in payload['messages'][0]['content']
        assert 'Alice' not in payload['messages'][0]['content']
        assert timeout==15
        return io.BytesIO(json.dumps({'choices':[{'message':{'content':'Open Digital learning hub from the sidebar.'}}]}).encode())
    monkeypatch.setattr('app.chatbot.urlopen',gateway)
    login(client,'student')
    result=post(client,'/hub/help',{'message':'Where do I find course books?'}).json
    assert result['mode']=='ai' and 'Digital learning hub' in result['answer']
    assert post(client,'/hub/help',{'message':'Where are my lessons?'}).status_code==429
    assert len(calls)==1
    with app.app_context():
        allowance=ChatAllowance.query.one()
        allowance.next_request_at=datetime.utcnow()-timedelta(seconds=1)
        db.session.commit()
    def failure(*args,**kwargs):
        raise URLError('unavailable')
    monkeypatch.setattr('app.chatbot.urlopen',failure)
    response=post(client,'/hub/help',{'message':'transport'})
    assert response.status_code==200 and response.json['mode']=='guided'
    assert b'secret-for-test-only' not in response.data
    with app.app_context():
        allowance=ChatAllowance.query.one()
        allowance.count=100
        allowance.next_request_at=datetime.utcnow()-timedelta(seconds=1)
        db.session.commit()
    assert post(client,'/hub/help',{'message':'help'}).status_code==429
    with app.app_context():
        allowance=ChatAllowance.query.one()
        allowance.day='2000-01-01'
        db.session.commit()
    assert post(client,'/hub/help',{'message':'help'}).status_code==200


def test_public_welcome_help_never_calls_ai_or_exposes_workspace_links(client,app,monkeypatch):
    monkeypatch.setenv('AI_GATEWAY_MODEL','configured/model')
    monkeypatch.setenv('AI_GATEWAY_API_KEY','secret-for-test-only')
    def forbidden(*args,**kwargs):
        raise AssertionError('Visitor questions must not use the authenticated AI path')
    monkeypatch.setattr('app.chatbot.answer',forbidden)
    page=client.get('/login/student')
    assert page.status_code==200
    assert b'Thank you for visiting Kevin Brook International Schools. How may I help you?' in page.data
    assert b'data-assistant-widget' in page.data
    assert b'action="/hub/help"' in page.data
    assert b'data-chat-input' in page.data
    assert b'aria-expanded="false"' in page.data
    assert client.get('/hub/help').status_code==200
    result=post(client,'/hub/help',{'message':'I forgot my password'}).json
    assert result['mode']=='guided' and not result['answer']
    assert any('school administrator' in r['text'] for r in result['replies'])
    assert all(r['url'] in ['/login','/forgot-password'] for r in result['replies'])
    assert client.post('/hub/help',data={'message':'login'}).status_code==400
    with app.app_context():
        assert ChatAllowance.query.count()==0


def test_transport_navigation_group_and_popup_role_boundaries(client,app):
    for user,path in [('admin','/dashboard'),('teacher','/portal/'),('student','/portal/'),('parent','/family/')]:
        login(client,user)
        page=client.get(path)
        assert page.status_code==200
        sidebar=page.data.split(b'<nav class="sidebar"',1)[1].split(b'</nav>',1)[0]
        section=sidebar.index(b'Student information')
        transport=sidebar.index(b'href="/transport/"')
        assert transport>section
        assert sidebar.count(b'href="/transport/"')==1
        assert b'data-assistant-widget' in page.data
        assert page.data.count(b'id="popup-message"')==1
        if user=='parent':
            assert b'data-topic="materials"' not in page.data
            assert b'data-topic="family"' in page.data
        page=client.get('/hub/help')
        assert b'data-assistant-widget' not in page.data
        assert b'id="page-message"' in page.data
        post(client,'/logout',{})
    login(client,'admin')
    from app.models import User
    with app.app_context():
        teacher_id=User.query.filter_by(username='teacher').one().id
    page=client.get(f'/family/previews/{teacher_id}')
    assert b'data-assistant-widget' not in page.data
