from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app import create_app, db
from app.models import Student, Staff, IdentifierCounter
from test_portals import app, client, login, post


def student(**extra):
    return Student(first_name='New', last_name='Student', class_name='Grade 7', **extra)


def member(**extra):
    return Staff(first_name='New', last_name='Teacher', role='Teacher', **extra)


def test_students_and_staff_generated_on_save(app, monkeypatch):
    monkeypatch.setattr('app.identifiers.current_year', lambda: 2026)
    with app.app_context():
        a,b,c,d = student(), student(), member(), member()
        db.session.add_all([a,b,c,d])
        db.session.commit()
        assert [a.admission_no, b.admission_no] == ['STU-2026-00001','STU-2026-00002']
        assert [c.staff_no, d.staff_no] == ['STF-2026-00001','STF-2026-00002']
        db.session.delete(b)
        db.session.commit()
        new=student()
        db.session.add(new)
        db.session.commit()
        assert new.admission_no == 'STU-2026-00003'


def test_imports_existing_numbers_and_edit_preserve_ids(app, monkeypatch):
    monkeypatch.setattr('app.identifiers.current_year', lambda: 2026)
    with app.app_context():
        db.session.add_all([student(admission_no='STU-2026-00020'),member(staff_no='Legacy Staff ID')])
        db.session.commit()
        generated=student()
        db.session.add(generated)
        db.session.commit()
        assert generated.admission_no == 'STU-2026-00021'
        generated.first_name='Updated'
        db.session.commit()
        assert generated.admission_no == 'STU-2026-00021'
        # Imported explicit values can occupy a future sequence number.
        db.session.add(student(admission_no='STU-2026-00022'))
        db.session.commit()
        next_student=student()
        db.session.add(next_student)
        db.session.commit()
        assert next_student.admission_no == 'STU-2026-00023'


def test_pending_explicit_identifiers_and_new_year(app, monkeypatch):
    monkeypatch.setattr('app.identifiers.current_year', lambda: 2026)
    with app.app_context():
        automatic=student()
        explicit=student(admission_no='STU-2026-00001')
        db.session.add_all([automatic,explicit])
        db.session.commit()
        assert automatic.admission_no == 'STU-2026-00002'
        monkeypatch.setattr('app.identifiers.current_year', lambda: 2027)
        following=student()
        db.session.add(following)
        db.session.commit()
        assert following.admission_no == 'STU-2027-00001'
        assert automatic.admission_no == 'STU-2026-00002'


def test_failed_insert_rolls_back_number_allocation(app, monkeypatch):
    monkeypatch.setattr('app.identifiers.current_year', lambda: 2026)
    with app.app_context():
        broken=Student(first_name='Missing required class',last_name='Record')
        db.session.add(broken)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        assert IdentifierCounter.query.count()==0
        record=student()
        db.session.add(record)
        db.session.commit()
        assert record.admission_no=='STU-2026-00001'


def test_admin_forms_do_not_accept_supplied_identifiers(client, app, monkeypatch):
    monkeypatch.setattr('app.identifiers.current_year', lambda: 2026)
    login(client,'admin')
    assert b'name="admission_no"' not in client.get('/students/add').data
    assert b'name="staff_no"' not in client.get('/staff/add').data
    assert post(client,'/students/add',{'first_name':'Auto','last_name':'Student','class_name':'Grade 7','admission_no':'MANUAL-OVERRIDE'}).status_code==302
    assert post(client,'/staff/add',{'first_name':'Auto','last_name':'Teacher','role':'Teacher','staff_no':'MANUAL-OVERRIDE'}).status_code==302
    with app.app_context():
        learner=Student.query.filter_by(first_name='Auto').first()
        staff=Staff.query.filter_by(first_name='Auto').first()
        assert learner.admission_no=='STU-2026-00001'
        assert staff.staff_no=='STF-2026-00001'
        sid,tid=learner.id,staff.id
    assert post(client,f'/students/{sid}/edit',{'first_name':'Edited','last_name':'Student','class_name':'Grade 8','admission_no':'TAMPERED'}).status_code==302
    assert post(client,f'/staff/{tid}/edit',{'first_name':'Edited','last_name':'Teacher','role':'Teacher','staff_no':'TAMPERED'}).status_code==302
    with app.app_context():
        assert db.session.get(Student,sid).admission_no=='STU-2026-00001'
        assert db.session.get(Staff,tid).staff_no=='STF-2026-00001'


def test_concurrent_transactions_allocate_unique_ids(tmp_path,monkeypatch):
    monkeypatch.setattr('app.identifiers.current_year', lambda: 2026)
    application=create_app({'TESTING':True,'SECRET_KEY':'test','SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'concurrent.db'),'SQLALCHEMY_ENGINE_OPTIONS':{'connect_args':{'timeout':30}}})
    with application.app_context():
        db.create_all()
        engine=db.engine
    def save_one(i):
        with Session(engine) as session:
            record=Student(first_name=f'Student {i}',last_name='Concurrent',class_name='Grade 7')
            session.add(record)
            session.commit()
            return record.admission_no
    with ThreadPoolExecutor(max_workers=4) as executor:
        ids=list(executor.map(save_one,range(16)))
    assert len(set(ids))==16
    assert sorted(ids)==[f'STU-2026-{i:05d}' for i in range(1,17)]
    with application.app_context():
        db.session.remove()
        db.drop_all()
