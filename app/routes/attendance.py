from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Attendance, Student
from datetime import date

attendance_bp = Blueprint("attendance", __name__)


@attendance_bp.route("/")
@login_required
def index():
    today = date.today().strftime("%Y-%m-%d")
    selected_date = request.args.get("date", today)
    class_filter = request.args.get("class_name", "")

    student_query = Student.query.filter_by(status="active")
    if class_filter:
        student_query = student_query.filter_by(class_name=class_filter)
    students = student_query.order_by(Student.class_name, Student.last_name).all()

    existing = {a.student_id: a for a in Attendance.query.filter_by(date=selected_date).all()}
    classes = db.session.query(Student.class_name).distinct().all()

    return render_template("attendance/index.html", students=students,
                           existing=existing, selected_date=selected_date,
                           classes=classes, class_filter=class_filter)


@attendance_bp.route("/save", methods=["POST"])
@login_required
def save():
    selected_date = request.form.get("date")
    student_ids = request.form.getlist("student_ids")

    for sid in student_ids:
        sid = int(sid)
        status = request.form.get(f"status_{sid}", "absent")
        notes = request.form.get(f"notes_{sid}", "")

        existing = Attendance.query.filter_by(student_id=sid, date=selected_date).first()
        if existing:
            existing.status = status
            existing.notes = notes
            existing.recorded_by = current_user.username
        else:
            record = Attendance(
                student_id=sid, date=selected_date,
                status=status, notes=notes,
                recorded_by=current_user.username
            )
            db.session.add(record)

    db.session.commit()
    flash(f"Attendance saved for {selected_date}.", "success")
    return redirect(url_for("attendance.index", date=selected_date))


@attendance_bp.route("/report")
@login_required
def report():
    students = Student.query.filter_by(status="active").order_by(Student.class_name, Student.last_name).all()
    return render_template("attendance/report.html", students=students)
