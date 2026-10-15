from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.models import Staff, TransportRoute

staff_bp = Blueprint("staff", __name__)


@staff_bp.route("/")
@login_required
def index():
    search = request.args.get("search", "")
    query = Staff.query
    if search:
        query = query.filter(
            (Staff.first_name.ilike(f"%{search}%")) |
            (Staff.last_name.ilike(f"%{search}%")) |
            (Staff.staff_no.ilike(f"%{search}%"))
        )
    staff = query.order_by(Staff.last_name).all()
    return render_template("staff/index.html", staff=staff, search=search)


@staff_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        member = Staff(
            first_name=request.form["first_name"],
            last_name=request.form["last_name"],
            role=request.form["role"],
            department=request.form.get("department"),
            phone=request.form.get("phone"),
            email=request.form.get("email"),
            date_joined=request.form.get("date_joined"),
        )
        db.session.add(member)
        db.session.commit()
        flash(f"{member.full_name} added to staff. ID: {member.staff_no}", "success")
        return redirect(url_for("staff.index"))
    return render_template("staff/form.html", member=None, action="Add")


@staff_bp.route("/<int:staff_id>/edit", methods=["GET", "POST"])
@login_required
def edit(staff_id):
    member = Staff.query.get_or_404(staff_id)
    if request.method == "POST":
        member.first_name = request.form["first_name"]
        member.last_name = request.form["last_name"]
        member.role = request.form["role"]
        member.department = request.form.get("department")
        member.phone = request.form.get("phone")
        member.email = request.form.get("email")
        member.status = request.form.get("status", "active")
        db.session.commit()
        flash("Staff record updated.", "success")
        return redirect(url_for("staff.index"))
    return render_template("staff/form.html", member=member, action="Edit")


@staff_bp.route("/<int:staff_id>/delete", methods=["POST"])
@login_required
def delete(staff_id):
    member = Staff.query.get_or_404(staff_id)
    if TransportRoute.query.filter_by(teacher_id=member.id).first():
        abort(409, description='Reassign transport routes before removing this teacher.')
    db.session.delete(member)
    db.session.commit()
    flash("Staff record removed.", "info")
    return redirect(url_for("staff.index"))
