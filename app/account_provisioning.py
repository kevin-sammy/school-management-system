"""Teacher and parent account creation and stable, collision-safe name-based usernames."""
import re
import unicodedata
from sqlalchemy import text as sql_text
from flask import abort
from app import db
from app.models import Staff, User


def name_part(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value).casefold() if c.isalnum())


def available_username(first_name, last_name, lock=False):
    first, last = name_part(first_name), name_part(last_name)
    if not first or not last:
        abort(400, description='Enter a first and last name containing letters or numbers.')
    if lock and db.engine.dialect.name == 'postgresql':
        db.session.execute(sql_text('SELECT pg_advisory_xact_lock(73491028)'))
    base = (first[0] + last)[:70]
    candidate, suffix = base, 1
    while User.query.filter(db.func.lower(User.username) == candidate).first():
        suffix += 1
        candidate = f'{base}{suffix}'
    return candidate


def create_profile_account(member, role, password, email=None):
    if role not in {'teacher', 'parent'} or member.user_id:
        abort(400, description='This profile already has a login or has an invalid role.')
    if role == 'teacher' and (member.status not in (None, 'active') or member.role.lower() != 'teacher'):
        abort(400, description='Choose an active teacher without a portal account.')
    if not 12 <= len(password) <= 128:
        abort(400, description='Set an initial password of 12 to 128 characters.')
    address = (email if email is not None else member.email or '').strip().lower()
    if len(address) > 120 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', address):
        abort(400, description='Enter a valid email address.')
    username = available_username(member.first_name, member.last_name, lock=True)
    if User.query.filter(db.func.lower(User.email) == address).first():
        abort(409, description='This email already belongs to a portal account. Use a different email or check Accounts & scheduling.')
    user = User(username=username, email=address, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    member.user_id = user.id
    member.email = address
    return user


def create_teacher_account(member, password, email=None):
    return create_profile_account(member, 'teacher', password, email)


def create_parent_account(member, password, email=None):
    return create_profile_account(member, 'parent', password, email)


def inactive_teacher(user):
    if user.role != 'teacher':
        return False
    member = Staff.query.filter_by(user_id=user.id).first()
    return bool(member and (member.status != 'active' or member.role.lower() != 'teacher'))
