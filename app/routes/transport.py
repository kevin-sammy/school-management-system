"""Private school transport management and family/student route details."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from app import db
from app.models import TransportRoute, TransportPassenger, Staff, Student, Parent
from app.routes.portal import roles, student_profile, text, integer

transport_bp=Blueprint('transport',__name__,url_prefix='/transport')


def passengers_for_user():
    query=TransportPassenger.query
    if current_user.role=='admin':
        return query
    if current_user.role=='teacher':
        staff_ids=[s.id for s in Staff.query.filter_by(user_id=current_user.id,status='active').all() if s.role.lower()=='teacher']
        return query.join(TransportRoute).filter(TransportRoute.teacher_id.in_(staff_ids))
    if current_user.role=='student':
        return query.filter_by(student_id=student_profile().id)
    if current_user.role=='parent':
        parent_ids=[p.id for p in Parent.query.filter_by(user_id=current_user.id).all()]
        return query.join(Student).filter(Student.parent_id.in_(parent_ids))
    abort(403)


def route_access(route_id):
    route=TransportRoute.query.get_or_404(route_id)
    if current_user.role=='admin':
        return route
    if current_user.role=='teacher' and route.teacher.user_id==current_user.id and route.teacher.status=='active' and route.teacher.role.lower()=='teacher':
        return route
    abort(403)


def clock(name):
    try:
        return datetime.strptime(text(name,5),'%H:%M').strftime('%H:%M')
    except ValueError:
        abort(400,description='Use a valid pickup/drop-off time.')


@transport_bp.route('/')
@roles('admin','teacher','parent','student')
def index():
    passengers=passengers_for_user().all()
    if current_user.role=='admin':
        routes=TransportRoute.query.order_by(TransportRoute.name).all()
    elif current_user.role=='teacher':
        routes=TransportRoute.query.join(Staff).filter(Staff.user_id==current_user.id,Staff.status=='active',db.func.lower(Staff.role)=='teacher').all()
    else:
        routes=[]
    return render_template('transport/index.html',routes=routes,passengers=passengers)


@transport_bp.route('/routes/new',methods=['GET','POST'])
@transport_bp.route('/routes/<int:route_id>/edit',methods=['GET','POST'])
@roles('admin')
def route_form(route_id=None):
    route=TransportRoute.query.get_or_404(route_id) if route_id else None
    teachers=[s for s in Staff.query.filter_by(status='active').all() if s.role.lower()=='teacher']
    if request.method=='POST':
        teacher=Staff.query.get_or_404(integer('teacher_id'))
        if teacher not in teachers:
            abort(400,description='Assign an active teacher to the route.')
        if route is None:
            route=TransportRoute()
            db.session.add(route)
        route.name=text('name',100)
        route.vehicle_registration=text('vehicle_registration',30)
        route.driver_name=text('driver_name',100)
        route.driver_phone=text('driver_phone',30,False)
        route.teacher_id=teacher.id
        route.notes=text('notes',500,False)
        route.status=text('status',20)
        if route.status not in ['active','inactive']:
            abort(400)
        db.session.commit()
        flash('Transport route saved.','success')
        return redirect(url_for('transport.detail',route_id=route.id))
    return render_template('transport/route_form.html',route=route,teachers=teachers)


@transport_bp.route('/routes/<int:route_id>',methods=['GET','POST'])
@roles('admin','teacher')
def detail(route_id):
    route=route_access(route_id)
    if request.method=='POST':
        if current_user.role!='admin':
            abort(403)
        student=Student.query.get_or_404(integer('student_id'))
        if student.status!='active' or route.status!='active':
            abort(400,description='Use an active student and route.')
        passenger=TransportPassenger.query.filter_by(student_id=student.id).first()
        if passenger is None:
            passenger=TransportPassenger(student_id=student.id)
            db.session.add(passenger)
        passenger.route_id=route.id
        passenger.home_area=text('home_area',100)
        passenger.pickup_point=text('pickup_point',200)
        passenger.pickup_time=clock('pickup_time')
        passenger.dropoff_time=clock('dropoff_time')
        db.session.commit()
        flash('Student transport assignment saved.','success')
        return redirect(url_for('transport.detail',route_id=route.id))
    passengers=TransportPassenger.query.filter_by(route_id=route.id).join(Student).order_by(TransportPassenger.pickup_time,Student.last_name).all()
    students=Student.query.filter_by(status='active').order_by(Student.first_name).all() if current_user.role=='admin' else []
    return render_template('transport/detail.html',route=route,passengers=passengers,students=students)


@transport_bp.route('/passengers/<int:passenger_id>/remove',methods=['POST'])
@roles('admin')
def remove(passenger_id):
    passenger=TransportPassenger.query.get_or_404(passenger_id)
    route_id=passenger.route_id
    db.session.delete(passenger)
    db.session.commit()
    flash('Student removed from the route.','success')
    return redirect(url_for('transport.detail',route_id=route_id))
