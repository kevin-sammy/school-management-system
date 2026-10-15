from datetime import datetime, timedelta
from tests.test_portals import app, client, login, post
from app import db
from app.models import OnlineExam, ExamQuestion, ExamAttempt, ExamAnswer, ExamEvent


def make_exam(client, app):
    login(client, 'teacher')
    assert client.get('/exams/').status_code == 200
    assert post(client, '/exams/',dict(class_id=2,title='Forbidden',duration_minutes=5)).status_code == 403
    assert post(client, '/exams/',dict(class_id=1,title='Math exam',duration_minutes=5)).status_code == 302
    with app.app_context():
        exam_id=OnlineExam.query.one().id
    assert client.get(f'/exams/{exam_id}/manage').status_code == 200
    assert post(client,f'/exams/{exam_id}/manage',{'action':'publish'}).status_code == 400
    mcq=dict(action='question',kind='mcq',prompt='Two plus two?',points=5,choice_0='1',choice_1='2',choice_2='3',choice_3='4',correct_choice=3)
    assert post(client,f'/exams/{exam_id}/manage',mcq).status_code == 302
    assert post(client,f'/exams/{exam_id}/manage',dict(action='question',kind='written',prompt='Explain fractions',points=10)).status_code == 302
    post(client,'/logout',{})
    login(client,'student')
    assert client.get(f'/exams/{exam_id}').status_code == 404
    post(client,'/logout',{})
    login(client,'teacher')
    assert post(client,f'/exams/{exam_id}/manage',{'action':'publish'}).status_code == 302
    assert post(client,f'/exams/{exam_id}/manage',mcq).status_code == 409
    post(client,'/logout',{})
    return exam_id


def start_exam(client, app, exam_id):
    login(client,'student')
    assert b'monitoring notice' in client.get(f'/exams/{exam_id}').data
    assert post(client,f'/exams/{exam_id}',{}).status_code == 400
    assert post(client,f'/exams/{exam_id}',{'acknowledge':'yes'}).status_code == 302
    assert post(client,f'/exams/{exam_id}',{'acknowledge':'yes'}).status_code == 302
    with app.app_context():
        assert ExamAttempt.query.count()==1
        attempt=ExamAttempt.query.one()
        return attempt.id, [q.id for q in attempt.exam.questions]


def test_exam_complete_review_release_flow(client, app):
    exam_id=make_exam(client,app)
    attempt_id,questions=start_exam(client,app,exam_id)
    path=f'/exams/attempts/{attempt_id}'
    page=client.get(path)
    assert page.status_code==200 and b'correct_choice' not in page.data
    answers={f'q_{questions[0]}':'3',f'q_{questions[1]}':'Equal parts'}
    assert post(client,path,{**answers,'action':'save'}).json['saved']
    assert post(client,path+'/events',{'kind':'visibility_hidden'}).status_code==200
    assert post(client,path+'/events',{'kind':'invented'}).status_code==400
    assert post(client,path,{**answers,'action':'submit'}).status_code==302
    assert b'teacher will review' in client.get(path).data
    assert post(client,path+'/events',{'kind':'paste_attempt'}).status_code==409
    post(client,'/logout',{})
    login(client,'otherteacher')
    assert client.get(path+'/review').status_code==403
    post(client,'/logout',{})
    login(client,'teacher')
    page=client.get(path+'/review')
    assert page.status_code==200 and b'Equal parts' in page.data and b'visibility hidden' in page.data
    with app.app_context():
        written=ExamAnswer.query.filter_by(attempt_id=attempt_id,question_id=questions[1]).one().id
        assert ExamAnswer.query.filter_by(question_id=questions[0]).one().score==5
    assert post(client,path+'/review',{f'score_{written}':'nan'}).status_code==400
    assert post(client,path+'/review',{f'score_{written}':'8'}).status_code==302
    assert post(client,f'/exams/{exam_id}/manage',{'action':'release'}).status_code==302
    post(client,'/logout',{})
    login(client,'student')
    assert b'Result: 13.0 / 15' in client.get(path).data
    post(client,'/logout',{})
    login(client,'otherstudent')
    assert client.get(path).status_code==403
    assert post(client,path,{'action':'submit'}).status_code==403
    assert client.get(f'/exams/{exam_id}').status_code==403


def test_exam_deadline_rejects_late_answers_and_preserves_saved_work(client,app):
    exam_id=make_exam(client,app)
    attempt_id,questions=start_exam(client,app,exam_id)
    path=f'/exams/attempts/{attempt_id}'
    assert post(client,path,{'action':'save',f'q_{questions[0]}':'3'}).status_code==200
    with app.app_context():
        attempt=db.session.get(ExamAttempt,attempt_id)
        attempt.deadline_at=datetime.utcnow()-timedelta(seconds=2)
        db.session.commit()
    assert post(client,path,{'action':'save',f'q_{questions[0]}':'0'}).status_code==409
    with app.app_context():
        attempt=db.session.get(ExamAttempt,attempt_id)
        assert attempt.submitted_at and attempt.reviewed
        assert ExamAnswer.query.filter_by(question_id=questions[0]).one().answer=='3'
        assert sum(a.score for a in attempt.answers)==5
    assert client.get(path).status_code==200


def test_active_exam_suppresses_chat_popup_but_closed_attempt_restores_it(client,app):
    exam_id=make_exam(client,app)
    attempt_id,questions=start_exam(client,app,exam_id)
    path=f'/exams/attempts/{attempt_id}'
    assert b'data-assistant-widget' not in client.get(path).data
    assert post(client,path,{'action':'submit'}).status_code==302
    assert b'data-assistant-widget' in client.get(path).data
