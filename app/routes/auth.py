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
