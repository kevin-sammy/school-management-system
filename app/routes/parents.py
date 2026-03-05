from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Parent, Notification, Student

parents_bp = Blueprint("parents", __name__)


@parents_bp.route("/")
@login_required
def index():
    search = request.args.get("search", "")
    query = Parent.query
    if search:
        query = query.filter(
            (Parent.first_name.ilike(f"%{search}%")) |
            (Parent.last_name.ilike(f"%{search}%"))
        )
    parents = query.order_by(Parent.last_name).all()
    return render_template("parents/index.html", parents=parents, search=search)


@parents_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        parent = Parent(
            first_name=request.form["first_name"],
            last_name=request.form["last_name"],
            phone=request.form.get("phone"),
            email=request.form.get("email"),
            relationship=request.form.get("relationship", "parent"),
        )
        db.session.add(parent)
        db.session.commit()
        flash(f"{parent.full_name} added successfully.", "success")
        return redirect(url_for("parents.index"))
    return render_template("parents/form.html", parent=None, action="Add")


@parents_bp.route("/notify", methods=["GET", "POST"])
@login_required
def notify():
    if request.method == "POST":
        notif = Notification(
            title=request.form["title"],
            message=request.form["message"],
            target=request.form.get("target", "all"),
            sent_by=current_user.username
        )
        db.session.add(notif)
        db.session.commit()
        flash("Notification sent successfully.", "success")
        return redirect(url_for("parents.index"))
    return render_template("parents/notify.html")


@parents_bp.route("/notifications")
@login_required
def notifications():
    notifs = Notification.query.order_by(Notification.created_at.desc()).all()
    return render_template("parents/notifications.html", notifications=notifs)
