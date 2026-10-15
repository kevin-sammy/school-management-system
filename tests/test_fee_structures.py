import pytest
from tests.test_portals import app, client, login, post
from app import db
from app.models import FeeStructure, FeeStructureLine, FeeRecord, Student, Parent, User


def create_structure(client, app, class_name='Grade 7', term='Term 1'):
    response=post(client,'/fee-structures/new',dict(class_name=class_name,year=2026,term=term,
        due_date='2026-10-30',payment_instructions='School-approved payment reference',notes='Meals and transport are optional.'))
    assert response.status_code==302
    with app.app_context():
        return FeeStructure.query.filter_by(class_name=class_name,term=term).one().id


def add_line(client,item_id,amount='12000.50',optional=False,category='Tuition',label='Term tuition'):
    data=dict(action='add_line',category=category,label=label,amount=amount)
    if optional:
        data['optional']='yes'
    return post(client,f'/fee-structures/{item_id}',data)


def test_admin_create_publish_print_and_return_to_draft(client,app):
    login(client,'admin')
    with app.app_context():
        record_count=FeeRecord.query.count()
        balance=db.session.get(Student,1).fee_balance
    assert client.get('/fee-structures/').status_code==200
    assert client.get('/fee-structures/new').status_code==200
    item_id=create_structure(client,app)
    path=f'/fee-structures/{item_id}'
    assert client.get(path).status_code==200
    assert post(client,path,{'action':'publish'}).status_code==400
    assert add_line(client,item_id).status_code==302
    assert add_line(client,item_id,'1500.25',True,'Meals','School lunch').status_code==302
    page=client.get(path)
    assert page.status_code==200
    assert b'12,000.50' in page.data and b'1,500.25' in page.data
    assert b'Optional / if applicable' in page.data and b'data-print' in page.data
    assert post(client,path,{'action':'publish'}).status_code==302
    assert b'Published' in client.get(path).data
    assert add_line(client,item_id).status_code==409
    with app.app_context():
        assert db.session.get(FeeStructure,item_id).compulsory_total_cents==1200050
        assert FeeRecord.query.count()==record_count
        assert db.session.get(Student,1).fee_balance==balance
        line_id=FeeStructureLine.query.filter_by(structure_id=item_id,category='Meals').one().id
    assert post(client,path,{'action':'unpublish'}).status_code==302
    assert post(client,path,{'action':'remove_line','line_id':line_id}).status_code==302
    with app.app_context():
        assert len(db.session.get(FeeStructure,item_id).lines)==1


@pytest.mark.parametrize('amount',['-1','nan','NaN','inf','Infinity','1e7','1e-999999999','10000000.01','12.345','1,000','1_000',''])
def test_invalid_amounts_are_rejected(client,app,amount):
    login(client,'admin')
    item_id=create_structure(client,app)
    assert add_line(client,item_id,amount).status_code==400
    with app.app_context():
        assert FeeStructureLine.query.count()==0


def test_duplicate_structure_and_invalid_fields_are_handled(client,app):
    login(client,'admin')
    first=create_structure(client,app)
    data=dict(class_name='Grade 7',year=2026,term='Term 1')
    assert post(client,'/fee-structures/new',data).status_code==409
    assert post(client,'/fee-structures/new',{**data,'year':2200}).status_code==400
    assert post(client,'/fee-structures/new',{**data,'due_date':'2026-02-30'}).status_code==400
    assert add_line(client,first,'25','',category='Invented').status_code==400
    second=create_structure(client,app,term='Term 2')
    assert add_line(client,second,'0.10').status_code==302
    assert add_line(client,second,'0.20',label='Activity fee').status_code==302
    with app.app_context():
        structure=db.session.get(FeeStructure,second)
        assert structure.compulsory_total_cents==30
        line_id=structure.lines[0].id
    assert post(client,f'/fee-structures/{first}',{'action':'remove_line','line_id':line_id}).status_code==403
    assert post(client,f'/fee-structures/{second}',{**data,'action':'details'}).status_code==409
    assert client.get('/fee-structures/?year=bad').status_code==400


def test_published_structures_are_class_scoped_and_drafts_private(client,app):
    with app.app_context():
        parent_user=User.query.filter_by(username='parent').one()
        parent=Parent(first_name='Mary',last_name='Learner',user_id=parent_user.id)
        db.session.add(parent)
        db.session.flush()
        db.session.get(Student,1).parent_id=parent.id
        db.session.commit()
    login(client,'admin')
    own=create_structure(client,app)
    private=create_structure(client,app,'Grade 8')
    draft=create_structure(client,app,term='Term 3')
    for item_id in [own,private]:
        assert add_line(client,item_id,label='Visible charges' if item_id==own else 'Other class charges').status_code==302
        assert post(client,f'/fee-structures/{item_id}',{'action':'publish'}).status_code==302
    post(client,'/logout',{})
    for role in ['student','parent','teacher']:
        login(client,role)
        page=client.get('/fee-structures/')
        assert page.status_code==200 and b'Term 1' in page.data
        assert b'Grade 8' not in page.data and b'Term 3' not in page.data
        assert b'School-approved payment reference' in client.get(f'/fee-structures/{own}').data
        assert client.get(f'/fee-structures/{private}').status_code==403
        assert client.get(f'/fee-structures/{draft}').status_code==403
        assert client.get('/fee-structures/new').status_code==403
        assert post(client,f'/fee-structures/{own}',{'action':'unpublish'}).status_code==403
        assert post(client,'/fee-structures/new',{}).status_code==403
        post(client,'/logout',{})
    assert client.get('/fee-structures/').status_code==302
    login(client,'otherstudent')
    assert client.get(f'/fee-structures/{own}').status_code==403
    assert client.get(f'/fee-structures/{private}').status_code==200


def test_unlinked_parent_empty_state_and_csrf(client):
    login(client,'parent')
    page=client.get('/fee-structures/')
    assert page.status_code==200 and b'No fee structures available' in page.data
    post(client,'/logout',{})
    login(client,'admin')
    assert client.post('/fee-structures/new',data=dict(class_name='Grade 7',year=2026,term='Term 1')).status_code==400
