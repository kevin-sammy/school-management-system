from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import FeeRecord, Student
from datetime import date, datetime

fees_bp = Blueprint("fees", __name__)


@fees_bp.route("/")
@login_required
def index():
    search = request.args.get("search", "")
    students = Student.query.filter_by(status="active")
    if search:
        students = students.filter(
            (Student.first_name.ilike(f"%{search}%")) |
            (Student.last_name.ilike(f"%{search}%")) |
            (Student.admission_no.ilike(f"%{search}%"))
        )
    students = students.order_by(Student.last_name).all()
    total_collected = sum(f.amount for f in FeeRecord.query.filter_by(record_type="payment").all())
    total_outstanding = sum(s.fee_balance for s in Student.query.filter_by(status="active").all())
    return render_template("fees/index.html", students=students, search=search,
                           total_collected=total_collected, total_outstanding=total_outstanding)


@fees_bp.route("/record", methods=["GET", "POST"])
@login_required
def record():
    students = Student.query.filter_by(status="active").order_by(Student.last_name).all()
    if request.method == "POST":
        record = FeeRecord(
            student_id=int(request.form["student_id"]),
            record_type=request.form["record_type"],
            amount=float(request.form["amount"]),
            description=request.form.get("description", ""),
            term=request.form.get("term"),
            year=int(request.form.get("year", datetime.utcnow().year)),
            payment_method=request.form.get("payment_method"),
            reference_no=request.form.get("reference_no", ""),
            date=request.form.get("date", date.today().strftime("%Y-%m-%d")),
            recorded_by=current_user.username
        )
        db.session.add(record)
        db.session.commit()
        flash("Fee record saved successfully.", "success")
        return redirect(url_for("fees.index"))
    return render_template("fees/form.html", students=students)


@fees_bp.route("/student/<int:student_id>")
@login_required
def student_fees(student_id):
    student = Student.query.get_or_404(student_id)
    records = FeeRecord.query.filter_by(student_id=student_id).order_by(FeeRecord.created_at.desc()).all()
    return render_template("fees/student.html", student=student, records=records)
