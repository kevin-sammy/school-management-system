"""
app/__init__.py — Flask application factory
"""
import os
import secrets
from flask import Flask, render_template
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", secrets.token_hex(32)
    )

    # Get database URL from environment (Neon/Vercel) and handle prefix fix for SQLAlchemy
    db_url = os.environ.get("DATABASE_URL")
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url or "sqlite:///school.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    if test_config:
        app.config.update(test_config)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

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
        (students_bp, "/students"),
        (staff_bp, "/staff"),
        (attendance_bp, "/attendance"),
        (grades_bp, "/grades"),
        (fees_bp, "/fees"),
        (parents_bp, "/parents"),
    ]:
        app.register_blueprint(bp, url_prefix=prefix)

    from app.routes.portal import portal_bp
    from app.security import install_security
    app.register_blueprint(portal_bp, url_prefix="/portal")
    from app.routes.learning import learning_bp
    app.register_blueprint(learning_bp)
    install_security(app)

    @app.cli.command("init-db")
    def init_db():
        """Create missing tables without modifying existing records."""
        db.create_all()
        print("Database tables ready.")

    for code, title in [(400, 'Check your request'), (403, 'This area is restricted'), (404, 'Page not found'), (409, 'This record is still linked')]:
        def handle_error(error, title=title):
            return render_template('error.html', code=error.code, title=title,
                                   description=error.description), error.code
        app.register_error_handler(code, handle_error)

    return app
