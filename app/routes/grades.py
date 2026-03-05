from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Grade, Student
from datetime import datetime

grades_bp = Blueprint("grades", __name__)

SUBJECTS = ["Mathematics", "English", "Kiswahili", "Science", "Social Studies",
            "CRE", "Art & Craft", "Music", "Physical Education", "Computer Studies"]


@grades_bp.route("/")
@login_required
def index():
    class_filter = request.args.get("class_name", "")
    term = request.args.get("term", "")
    year = request.args.get("year", str(datetime.utcnow().year))

    student_query = Student.query.filter_by(status="active")
    if class_filter:
        student_query = student_query.filter_by(class_name=class_filter)
    students = student_query.order_by(Student.class_name, Student.last_name).all()
    classes = db.session.query(Student.class_name).distinct().all()

    return render_template("grades/index.html", students=students, classes=classes,
                           class_filter=class_filter, term=term, year=year, subjects=SUBJECTS)


@grades_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    students = Student.query.filter_by(status="active").order_by(Student.last_name).all()
    if request.method == "POST":
        grade = Grade(
            student_id=int(request.form["student_id"]),
            subject=request.form["subject"],
            term=request.form["term"],
            year=int(request.form["year"]),
            score=float(request.form["score"]),
            max_score=float(request.form.get("max_score", 100)),
            exam_type=request.form.get("exam_type", "end_of_term"),
            remarks=request.form.get("remarks", ""),
            recorded_by=current_user.username
        )
        db.session.add(grade)
        db.session.commit()
        flash("Grade recorded successfully.", "success")
        return redirect(url_for("grades.index"))
    return render_template("grades/form.html", students=students, subjects=SUBJECTS,
                           grade=None, action="Add")


@grades_bp.route("/report/<int:student_id>")
@login_required
def report_card(student_id):
    student = Student.query.get_or_404(student_id)
    year = request.args.get("year", str(datetime.utcnow().year))
    term = request.args.get("term", "Term 1")
    grades = Grade.query.filter_by(student_id=student_id, year=int(year), term=term).all()
    average = round(sum(g.percentage for g in grades) / len(grades), 1) if grades else 0
    return render_template("grades/report_card.html", student=student,
                           grades=grades, year=year, term=term, average=average)


@grades_bp.route("/<int:grade_id>/delete", methods=["POST"])
@login_required
def delete(grade_id):
    grade = Grade.query.get_or_404(grade_id)
    db.session.delete(grade)
    db.session.commit()
    flash("Grade record deleted.", "info")
    return redirect(url_for("grades.index"))
