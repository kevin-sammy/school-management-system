"""Allocate school IDs atomically for ORM inserts on SQLite and PostgreSQL."""
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.models import IdentifierCounter, Student, Staff


def current_year():
    return datetime.now(ZoneInfo('Africa/Nairobi')).year


def allocate_identifier(session, model, attribute, kind, year):
    """Reserve the next number inside the same transaction as the new record.

    Upsert locks the counter row, including the first concurrent allocation. The
    initial value follows existing identifiers in this format; later allocations
    skip existing/pending explicit imports. Failed saves roll the counter back.
    """
    prefix = f'{kind}-{year}-'
    namespace = f'{kind}:{year}'
    column = getattr(model, attribute)
    counters = IdentifierCounter.__table__
    known = session.execute(select(counters.c.last_value).where(counters.c.namespace == namespace)).scalar_one_or_none()
    highest = 0
    if known is None:
        for value in session.execute(select(column).where(column.like(prefix + '%'))).scalars():
            suffix = value[len(prefix):]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
    reserved = {getattr(item, attribute, None) for item in session.new if isinstance(item, model)}
    dialect = session.get_bind(mapper=model).dialect.name
    insert = {'postgresql': postgres_insert, 'sqlite': sqlite_insert}.get(dialect)
    if insert is None:
        raise RuntimeError('Automatic school IDs require PostgreSQL or SQLite.')
    while True:
        statement = insert(counters).values(namespace=namespace, last_value=highest + 1)
        statement = statement.on_conflict_do_update(index_elements=[counters.c.namespace],
            set_={'last_value': counters.c.last_value + 1}).returning(counters.c.last_value)
        number = session.execute(statement).scalar_one()
        candidate = f'{prefix}{number:05d}'
        if candidate in reserved:
            continue
        exists = session.execute(select(column).where(column == candidate).limit(1)).first()
        if exists is None:
            return candidate


@event.listens_for(Session, 'before_flush')
def generate_missing_identifiers(session, flush_context, instances):
    # Explicit identifiers from trusted imports/demo data are retained.
    for item in list(session.new):
        if isinstance(item, Student) and not (item.admission_no or '').strip():
            item.admission_no = allocate_identifier(session, Student, 'admission_no', 'STU', current_year())
        elif isinstance(item, Staff) and not (item.staff_no or '').strip():
            item.staff_no = allocate_identifier(session, Staff, 'staff_no', 'STF', current_year())
