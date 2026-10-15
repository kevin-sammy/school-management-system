from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.models import Staff, TransportRoute, User
from sqlalchemy.exc import IntegrityError
from app.routes.portal import text
from app.account_provisioning import create_teacher_account

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
    return render_template("staff/index.html", staff=staff, search=search, users={u.id:u for u in User.query.all()})


@staff_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        member = Staff(
            first_name=text("first_name", 60),
            last_name=text("last_name", 60),
            role=text("role", 40),
            department=request.form.get("department"),
            phone=request.form.get("phone"),
            email=request.form.get("email"),
            date_joined=request.form.get("date_joined"),
        )
        db.session.add(member)
        teacher = None
        try:
            if member.role.lower() == 'teacher':
                teacher = create_teacher_account(member, request.form.get('initial_password', ''))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('The username or email was allocated by another request. Please retry.', 'warning')
            return redirect(url_for('staff.add'))
        if teacher:
            flash(f'Teacher login ready. Username: {teacher.username}. Login: {url_for("auth.login", role="teacher")}. Share the initial password you entered privately.', 'success')
        flash(f"{member.full_name} added to staff. ID: {member.staff_no}", "success")
        return redirect(url_for("staff.index"))
    return render_template("staff/form.html", member=None, action="Add")


@staff_bp.route("/<int:staff_id>/edit", methods=["GET", "POST"])
@login_required
def edit(staff_id):
    query = Staff.query.filter_by(id=staff_id)
    member = (query.with_for_update() if request.method == 'POST' else query).first_or_404()
    user = db.session.get(User, member.user_id) if member.user_id else None
    if request.method == "POST":
        if user and text('role', 40).lower() != 'teacher':
            abort(400, description='Keep linked teachers in the Teacher role; set their status to inactive to disable access.')
        member.first_name = text("first_name", 60)
        member.last_name = text("last_name", 60)
        member.role = text('role', 40)
        member.department = request.form.get("department")
        member.phone = request.form.get("phone")
        member.email = request.form.get("email")
        member.status = request.form.get("status", "active")
        if member.status not in ['active', 'inactive']:
            abort(400)
        try:
            if user and request.form.get('initial_password', ''):
                if user.role != 'teacher':
                    abort(403)
                user = User.query.filter_by(id=user.id).populate_existing().with_for_update().one()
                from app.account_passwords import reset_portal_password
                reset_portal_password(user, request.form['initial_password'], request.form.get('confirm_password', ''))
            if not user and member.role.lower() == 'teacher' and member.status == 'active':
                user = create_teacher_account(member, request.form.get('initial_password', ''))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('The username or email was allocated by another request. Please retry.', 'warning')
            return redirect(url_for('staff.edit', staff_id=member.id))
        if user:
            flash(f'Teacher username: {user.username}. Login: {url_for("auth.login", role="teacher")}.', 'success')
        flash("Staff record updated.", "success")
        return redirect(url_for("staff.index"))
    return render_template("staff/form.html", member=member, action="Edit", portal_user=user)


@staff_bp.route("/<int:staff_id>/delete", methods=["POST"])
@login_required
def delete(staff_id):
    member = Staff.query.get_or_404(staff_id)
    if member.user_id:
        abort(409, description='This teacher has a portal account. Set their status to inactive to preserve their account and class records.')
    if TransportRoute.query.filter_by(teacher_id=member.id).first():
        abort(409, description='Reassign transport routes before removing this teacher.')
    db.session.delete(member)
    db.session.commit()
    flash("Staff record removed.", "info")
    return redirect(url_for("staff.index"))
