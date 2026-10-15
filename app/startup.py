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
                recover_admin()
                bootstrap_admin()
                if os.environ.get('SEED_DEMO_DATA', '').lower() == 'true':
                    from app.demo import seed_demo_dataset
                    password = os.environ.get('DEMO_PASSWORD', '')
                    # An already imported dataset is a no-op and never resets passwords.
                    seed_demo_dataset(password)
                from app.sample_names import normalize_sample_accounts
                normalize_sample_accounts()
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



def recover_admin():
    """Apply an owner-configured recovery once, before ordinary bootstrap.

    Only the hosting environment can request this operation. No public reset API
    or default recovery password is introduced. PostgreSQL startup already holds
    the transaction lock; the request primary key also rejects concurrent reuse.
    """
    from app.models import User, AdminRecovery
    password = os.environ.get('ADMIN_RECOVERY_PASSWORD', '')
    if not password:
        return
    request_id = os.environ.get('ADMIN_RECOVERY_ID', '').strip()
    username = os.environ.get('ADMIN_RECOVERY_USERNAME', 'admin').strip()
    if not 8 <= len(request_id) <= 80:
        raise ValueError('Set ADMIN_RECOVERY_ID to a unique request name of 8 to 80 characters, for example restore-admin-20261015-1.')
    # A previously consumed request must not overwrite a later password change.
    if db.session.get(AdminRecovery, request_id):
        return
    if not 12 <= len(password) <= 128:
        raise ValueError('ADMIN_RECOVERY_PASSWORD must contain 12 to 128 characters.')
    if not username or len(username) > 80:
        raise ValueError('ADMIN_RECOVERY_USERNAME must contain 1 to 80 characters.')
    target = User.query.filter_by(username=username).first()
    if target is not None and target.role != 'admin':
        raise ValueError('The requested recovery username belongs to a non-administrator. Choose a different ADMIN_RECOVERY_USERNAME.')
    if target is None:
        admins = User.query.filter_by(role='admin').all()
        if len(admins) > 1:
            raise ValueError('Multiple administrators exist. Set ADMIN_RECOVERY_USERNAME to the exact username of the administrator to recover.')
        if admins:
            target = admins[0]
            target.username = username
        else:
            email = f'recovery-{request_id}@schoolms.example.invalid'
            if User.query.filter_by(email=email).first():
                raise ValueError('The recovery account email already exists. Choose another ADMIN_RECOVERY_ID.')
            target = User(username=username, email=email, role='admin')
            db.session.add(target)
    target.set_password(password)
    db.session.flush()
    db.session.add(AdminRecovery(request_id=request_id, user_id=target.id))
