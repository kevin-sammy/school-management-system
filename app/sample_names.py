"""Replace legacy sample login labels with natural names; preserve identity/passwords."""
import re
import unicodedata
from sqlalchemy import text
from app import db
from app.models import User, Staff, Parent, StudentAccount, DemoDataset, SampleAccount, Grade, Attendance, FeeRecord, Notification

PARENT_NAMES = ['Joseph','Mary','Peter','Sarah','James','Anne','David','Elizabeth','Samuel','Rose',
                'Daniel','Esther','Michael','Jane','Paul','Ruth','John','Lucy','Stephen','Margaret',
                'Isaac','Naomi','Simon','Grace','Philip','Agnes','George','Lydia','Anthony','Judith']


def normalize_sample_accounts():
    from app.demo import DATASET_KEY
    if db.session.get(DemoDataset, DATASET_KEY) is None:
        return 0
    if db.engine.dialect.name == 'postgresql':
        db.session.execute(text('SELECT pg_advisory_xact_lock(73491027)'))
    # Rename recognized unlinked guardian profiles too; their reserved email still
    # lets the optional parent-account upgrade identify them later.
    for parent in Parent.query.filter(Parent.first_name.like('Demo Guardian %'),
                                      Parent.email.like('demo.parent%@schoolms.example.invalid')).all():
        match = re.fullmatch(r'demo\.parent(\d{2})@schoolms\.example\.invalid', parent.email or '')
        if match and parent.children and all(s.admission_no.startswith('DEMO/') for s in parent.children):
            parent.first_name = PARENT_NAMES[(int(match.group(1))-1) % len(PARENT_NAMES)]
    changed = 0
    for user in User.query.filter(User.username.like('demo.%')).order_by(User.id).all():
        match = re.fullmatch(r'demo\.(teacher\d{2}|student\d{3}|parent\d{2})',user.username)
        if not match:
            continue
        key = match.group(1)
        profile = None
        if key.startswith('teacher') and user.role == 'teacher':
            profile = Staff.query.filter_by(user_id=user.id).first()
            if not profile or not profile.staff_no.startswith('DEMO/'):
                continue
        elif key.startswith('student') and user.role == 'student':
            link = StudentAccount.query.filter_by(user_id=user.id).first()
            profile = link.student if link else None
            if not profile or not profile.admission_no.startswith('DEMO/'):
                continue
        elif key.startswith('parent') and user.role == 'parent':
            profile = Parent.query.filter_by(user_id=user.id).first()
            if not profile or not (profile.email or '').endswith('@schoolms.example.invalid'):
                continue
            if profile.first_name.startswith('Demo Guardian '):
                profile.first_name = PARENT_NAMES[(int(key[-2:])-1) % len(PARENT_NAMES)]
        if profile is None:
            continue
        old_name, old_email = user.username, user.email
        slug = unicodedata.normalize('NFKD',profile.first_name+'.'+profile.last_name).encode('ascii','ignore').decode().lower()
        slug = re.sub(r'[^a-z0-9.]+','',slug).strip('.')[:65] or 'school.user'
        candidate, suffix = slug, 1
        while User.query.filter(User.id != user.id, db.or_(User.username == candidate, User.email == f'{candidate}@schoolms.example.invalid')).first():
            suffix += 1
            candidate = f'{slug}{suffix}'
        user.username = candidate
        if old_email.endswith('@schoolms.example.invalid'):
            user.email = f'{candidate}@schoolms.example.invalid'
        if hasattr(profile,'email') and profile.email == old_email:
            profile.email = user.email
        if db.session.get(SampleAccount,key) is None:
            db.session.add(SampleAccount(sample_key=key,user_id=user.id))
        for model, attribute in [(Grade,'recorded_by'),(Attendance,'recorded_by'),(FeeRecord,'recorded_by'),(Notification,'sent_by')]:
            model.query.filter(getattr(model,attribute)==old_name).update({attribute:candidate},synchronize_session=False)
        changed += 1
        db.session.flush()
    db.session.commit()
    return changed
