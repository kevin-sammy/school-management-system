"""Initialize missing schema and explicitly requested demo/bootstrap data."""
import os
from threading import Lock
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app import db


def install_startup(app):
    ready = False
    lock = Lock()

    @app.before_request
    def prepare_database():
        nonlocal ready
        from flask import request
        if request.endpoint == 'static' or ready:
            return None
        with lock:
            if ready:
                return None
            # A serverless instance's local filesystem is not a persistent DB.
            if os.environ.get('VERCEL') and not os.environ.get('DATABASE_URL') and not app.testing:
                app.logger.error('Startup configuration: DATABASE_URL is missing on Vercel.')
                return unavailable('The hosted database is not configured. Set DATABASE_URL to a persistent PostgreSQL database in your hosting settings and redeploy.')
            if os.environ.get('VERCEL') and not os.environ.get('SECRET_KEY') and not app.testing:
                app.logger.error('Startup configuration: SECRET_KEY is missing on Vercel.')
                return unavailable('The login session key is not configured. Set a persistent SECRET_KEY in your hosting settings and redeploy.')
            try:
                # Serialize additive schema creation across PostgreSQL cold starts.
                # All schema/bootstrap operations share this transaction.
                if db.engine.dialect.name == 'postgresql':
                    db.session.execute(text('SELECT pg_advisory_xact_lock(73491026)'))
                db.metadata.create_all(bind=db.session.connection())
                bootstrap_admin()
                if os.environ.get('SEED_DEMO_DATA', '').lower() == 'true':
                    from app.demo import seed_demo_dataset
                    password = os.environ.get('DEMO_PASSWORD', '')
                    # An already imported dataset is a no-op and never resets passwords.
                    seed_demo_dataset(password)
                db.session.commit()
                ready = True
            except ValueError as error:
                db.session.rollback()
                app.logger.error('Startup configuration error: %s', error)
                return unavailable(str(error))
            except SQLAlchemyError as error:
                db.session.rollback()
                app.logger.error('Database startup failed (%s). Check database connectivity and schema permissions.', type(error).__name__)
                return unavailable('The database could not be prepared. Check DATABASE_URL, database availability, and permission to create the missing tables.')
        return None

    def unavailable(message):
        # Standalone template avoids querying current_user during a database failure.
        return app.jinja_env.get_template('service_unavailable.html').render(message=message), 503

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.error('Database request failed (%s). Check deployment runtime logs.', type(error).__name__)
        return unavailable('A database request failed. Check your deployment database connection and run the database initialization command if schema updates were disabled.')


def bootstrap_admin():
    """Create a first administrator only when explicitly configured; never reset one."""
    from app.models import User
    if User.query.filter_by(role='admin').first():
        return
    password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD', '')
    if not password:
        return
    if not 12 <= len(password) <= 128:
        raise ValueError('BOOTSTRAP_ADMIN_PASSWORD must contain 12 to 128 characters.')
    username = os.environ.get('BOOTSTRAP_ADMIN_USERNAME', 'admin').strip()
    email = os.environ.get('BOOTSTRAP_ADMIN_EMAIL', 'admin@schoolms.example.invalid').strip()
    if not username or len(username) > 80 or not email or len(email) > 120:
        raise ValueError('Use valid BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_EMAIL values.')
    if User.query.filter(db.or_(User.username == username, User.email == email)).first():
        raise ValueError('The bootstrap username or email is already linked to a non-administrator. Choose different bootstrap identifiers.')
    admin = User(username=username, email=email, role='admin')
    admin.set_password(password)
    db.session.add(admin)
    db.session.flush()
