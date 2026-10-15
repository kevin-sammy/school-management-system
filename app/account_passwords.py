"""Password changes invalidate older sessions without persisting plaintext secrets."""
from datetime import datetime
import hashlib
import hmac
from flask import abort, session, current_app
from flask_login import current_user
from app import db
from app.models import PortalPasswordChange, PortalPasswordRequest


def mark_password_changed(user):
    marker = db.session.get(PortalPasswordChange, user.id)
    if marker is None:
        marker = PortalPasswordChange(user_id=user.id)
        db.session.add(marker)
    marker.changed_at = datetime.utcnow()
    pending = db.session.get(PortalPasswordRequest, user.id)
    if pending:
        pending.status = 'resolved'
    return marker.changed_at


def reset_portal_password(user, password, confirmation):
    if user.role not in {'teacher', 'parent', 'student'}:
        abort(403, description='Use your own Account settings to change an administrator password.')
    if not 12 <= len(password) <= 128 or password != confirmation:
        abort(400, description='Use a password of 12–128 characters and a matching confirmation.')
    user.set_password(password)
    mark_password_changed(user)


def credential_stamp(user):
    secret = current_app.secret_key
    if isinstance(secret, str):
        secret = secret.encode()
    value = f'{user.id}:{user.password_hash}'.encode()
    return hmac.new(secret, value, hashlib.sha256).hexdigest()


def session_needs_reauthentication(user):
    issued = session.get('_credential_stamp')
    if isinstance(issued, str):
        return not hmac.compare_digest(issued, credential_stamp(user))
    # Existing sessions from before this feature stay usable until their password
    # is changed. A reset marker then also revokes these legacy sessions.
    return db.session.get(PortalPasswordChange, user.id) is not None


def stamp_login():
    session['_credential_stamp'] = credential_stamp(current_user)
