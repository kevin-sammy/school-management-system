from flask import Blueprint, render_template, redirect, url_for, flash, request, session, abort
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User
from app.account_provisioning import inactive_teacher

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/", methods=["GET", "POST"])
@auth_bp.route("/login", methods=["GET", "POST"])
@auth_bp.route("/login/<role>", methods=["GET", "POST"])
def login(role=None):
    if role not in {None, "admin", "teacher", "student", "parent"}:
        abort(404)
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and not inactive_teacher(user) and user.check_password(password) and (role is None or user.role == role):
            session.clear()
            login_user(user)
            from app.account_passwords import stamp_login
            stamp_login()
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(url_for("dashboard.index"))
        flash("Invalid username or password.", "danger")
    return render_template("auth/login.html", role=role)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        import time
        from datetime import datetime, timedelta
        from app.models import PortalPasswordRequest
        identifier = request.form.get('identifier', '').strip().lower()
        if not identifier or len(identifier) > 120:
            abort(400, description='Enter your school username or account email.')
        # Unknown identifiers are not persisted, and pending requests are deduplicated.
        # A session cooldown also prevents accidental repeated submissions.
        now = time.time()
        if now >= session.get('_password_request_after', 0):
            session['_password_request_after'] = now + 30
            matches = User.query.filter(User.role.in_(['teacher', 'student', 'parent']),
                db.or_(db.func.lower(User.username) == identifier, db.func.lower(User.email) == identifier)).all()
            if len(matches) == 1:
                user = User.query.filter_by(id=matches[0].id).with_for_update().one()
                pending = db.session.get(PortalPasswordRequest, user.id)
                if pending is None:
                    db.session.add(PortalPasswordRequest(user_id=user.id))
                elif pending.status == 'resolved' and pending.requested_at < datetime.utcnow()-timedelta(minutes=30):
                    pending.status = 'pending'
                    pending.requested_at = datetime.utcnow()
                db.session.commit()
        flash('If these details match a school portal account, a request has been submitted to the administrator. Contact the school office to verify your identity and receive a new password. No email has been sent.', 'info')
        return redirect(url_for('auth.forgot_password'))
    return render_template('auth/forgot_password.html')
