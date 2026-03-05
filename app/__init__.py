"""
app/__init__.py — Flask application factory
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///school.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.students import students_bp
    from app.routes.staff import staff_bp
    from app.routes.attendance import attendance_bp
    from app.routes.grades import grades_bp
    from app.routes.fees import fees_bp
    from app.routes.parents import parents_bp

    for bp in [auth_bp, dashboard_bp]:
        app.register_blueprint(bp)
    for bp, prefix in [
        (students_bp, "/students"), (staff_bp, "/staff"),
        (attendance_bp, "/attendance"), (grades_bp, "/grades"),
        (fees_bp, "/fees"), (parents_bp, "/parents")
    ]:
        app.register_blueprint(bp, url_prefix=prefix)

    return app
