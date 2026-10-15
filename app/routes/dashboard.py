from flask import Blueprint, render_template, redirect, url_for, abort
from flask_login import login_required, current_user
from app.models import Student, Staff, Attendance, FeeRecord, Notification
from datetime import date

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def index():
    if current_user.role in {"teacher", "student"}:
        return redirect(url_for("portal.home"))
    if current_user.role != "admin":
        abort(403)
    today = date.today().strftime("%Y-%m-%d")
    stats = {
        "total_students": Student.query.filter_by(status="active").count(),
        "total_staff": Staff.query.filter_by(status="active").count(),
        "present_today": Attendance.query.filter_by(date=today, status="present").count(),
        "absent_today": Attendance.query.filter_by(date=today, status="absent").count(),
        "total_fees_collected": sum(
            f.amount for f in FeeRecord.query.filter_by(record_type="payment").all()
        ),
        "total_fees_outstanding": sum(
            s.fee_balance for s in Student.query.filter_by(status="active").all()
        ),
    }
    recent_notifications = Notification.query.order_by(
        Notification.created_at.desc()
    ).limit(5).all()

    return render_template("dashboard/index.html", stats=stats, notifications=recent_notifications)
