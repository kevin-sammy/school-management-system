"""Shared authorization and CSRF protection for all application routes."""
import hmac
import secrets
from flask import abort, request, session, redirect, url_for
from flask_login import current_user, logout_user


def csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_urlsafe(32)
    return session['_csrf_token']


def install_security(app):
    app.jinja_env.globals['csrf_token'] = csrf_token

    @app.before_request
    def protect_request():
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            expected = session.get('_csrf_token', '')
            provided = request.form.get('csrf_token', '')
            if not expected or not hmac.compare_digest(expected.encode(), provided.encode()):
                abort(400, description='Your form expired. Refresh the page and try again.')
        if current_user.is_authenticated:
            from app.account_provisioning import inactive_teacher
            from app.account_passwords import session_needs_reauthentication
            if inactive_teacher(current_user) or session_needs_reauthentication(current_user):
                logout_user()
                session.clear()
                return redirect(url_for('auth.login'))
        # The original modules expose school-wide records and are admin-only.
        if current_user.is_authenticated and request.blueprint in {
            'students', 'staff', 'attendance', 'grades', 'fees', 'parents'
        } and current_user.role != 'admin':
            abort(403)
