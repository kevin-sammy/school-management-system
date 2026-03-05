from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Student, Parent, Grade, Attendance, FeeRecord

students_bp = Blueprint("students", __name__)


@students_bp.route("/")
@login_required
def index():
    search = request.args.get("search", "")
    class_filter = request.args.get("class_name", "")
    query = Student.query
    if search:
        query = query.filter(
            (Student.first_name.ilike(f"%{search}%")) |
            (Student.last_name.ilike(f"%{search}%")) |
            (Student.admission_no.ilike(f"%{search}%"))
        )
    if class_filter:
        query = query.filter_by(class_name=class_filter)
    students = query.order_by(Student.last_name).all()
    classes = db.session.query(Student.class_name).distinct().all()
    return render_template("students/index.html", students=students, classes=classes,
                           search=search, class_filter=class_filter)


@students_bp.route("/<int:student_id>")
@login_required
def view(student_id):
    student = Student.query.get_or_404(student_id)
    grades = Grade.query.filter_by(student_id=student_id).order_by(Grade.year.desc()).all()
    attendance = Attendance.query.filter_by(student_id=student_id).order_by(Attendance.date.desc()).limit(30).all()
    fee_records = FeeRecord.query.filter_by(student_id=student_id).order_by(FeeRecord.created_at.desc()).all()
    return render_template("students/view.html", student=student, grades=grades,
                           attendance=attendance, fee_records=fee_records)


@students_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    parents = Parent.query.order_by(Parent.last_name).all()
    if request.method == "POST":
        student = Student(
            admission_no=request.form["admission_no"],
            first_name=request.form["first_name"],
            last_name=request.form["last_name"],
            date_of_birth=request.form.get("date_of_birth"),
            gender=request.form.get("gender"),
            class_name=request.form["class_name"],
            stream=request.form.get("stream"),
            year_enrolled=request.form.get("year_enrolled", 2026),
            parent_id=request.form.get("parent_id") or None
        )
        db.session.add(student)
        db.session.commit()
        flash(f"Student {student.full_name} registered successfully!", "success")
        return redirect(url_for("students.view", student_id=student.id))
    return render_template("students/form.html", student=None, parents=parents, action="Add")


@students_bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
def edit(student_id):
    student = Student.query.get_or_404(student_id)
    parents = Parent.query.order_by(Parent.last_name).all()
    if request.method == "POST":
        student.first_name = request.form["first_name"]
        student.last_name = request.form["last_name"]
        student.date_of_birth = request.form.get("date_of_birth")
        student.gender = request.form.get("gender")
        student.class_name = request.form["class_name"]
        student.stream = request.form.get("stream")
        student.status = request.form.get("status", "active")
        student.parent_id = request.form.get("parent_id") or None
        db.session.commit()
        flash("Student record updated.", "success")
        return redirect(url_for("students.view", student_id=student.id))
    return render_template("students/form.html", student=student, parents=parents, action="Edit")


@students_bp.route("/<int:student_id>/delete", methods=["POST"])
@login_required
def delete(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash("Student record deleted.", "info")
    return redirect(url_for("students.index"))
