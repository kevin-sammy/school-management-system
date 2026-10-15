"""Published fee schedules with exact cents and class/family authorization."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
import re
from sqlalchemy.exc import IntegrityError
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from app import db
from app.models import FeeStructure, FeeStructureLine, Student, Parent
from app.routes.portal import roles, text, integer, valid_date, student_profile
from app.routes.learning import visible_classes

fee_structures_bp = Blueprint('fee_structures', __name__, url_prefix='/fee-structures')
CATEGORIES = ['Tuition', 'Admission', 'Meals', 'Transport', 'Boarding', 'Examinations', 'Activities', 'Other']


def visible_class_names():
    if current_user.role == 'admin':
        return None
    if current_user.role == 'student':
        return {student_profile().class_name}
    if current_user.role == 'parent':
        parents = [p.id for p in Parent.query.filter_by(user_id=current_user.id).all()]
        return {s.class_name for s in Student.query.filter(Student.parent_id.in_(parents)).all()}
    return {c.class_name for c in visible_classes()}


def structure_access(structure_id, write=False):
    item = FeeStructure.query.get_or_404(structure_id)
    if current_user.role == 'admin':
        return item
    if write or not item.published or item.class_name not in visible_class_names():
        abort(403)
    return item


def money_cents():
    value = text('amount', 20)
    try:
        if not re.fullmatch(r'\d+(?:\.\d{1,2})?', value):
            raise InvalidOperation
        amount = Decimal(value)
        if not amount.is_finite() or not 0 <= amount <= Decimal('10000000'):
            raise InvalidOperation
        cents = amount * 100
        if cents != cents.to_integral_value():
            raise InvalidOperation
        return int(cents)
    except (InvalidOperation, ValueError, OverflowError):
        abort(400, description='Enter a KES amount from 0 to 10,000,000 with at most two decimal places.')


def details(item):
    item.class_name = text('class_name', 20)
    item.year = integer('year')
    if not 2000 <= item.year <= 2100:
        abort(400, description='Choose an academic year between 2000 and 2100.')
    item.term = text('term', 20)
    item.due_date = valid_date('due_date') if request.form.get('due_date', '').strip() else None
    item.payment_instructions = text('payment_instructions', 3000, False)
    item.notes = text('notes', 3000, False)


def save():
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, description='A fee structure already exists for this class, term and year. Open the existing structure instead.')


@fee_structures_bp.route('/')
@roles('admin', 'teacher', 'student', 'parent')
def index():
    names = visible_class_names()
    query = FeeStructure.query
    if names is not None:
        query = query.filter(FeeStructure.published.is_(True), FeeStructure.class_name.in_(names))
    year = request.args.get('year', '').strip()
    if year:
        try:
            year_number = int(year)
        except ValueError:
            abort(400)
        if not 2000 <= year_number <= 2100:
            abort(400)
        query = query.filter_by(year=year_number)
    items = query.order_by(FeeStructure.year.desc(), FeeStructure.term, FeeStructure.class_name).all()
    return render_template('fee_structures/index.html', structures=items, year=year)


@fee_structures_bp.route('/new', methods=['GET', 'POST'])
@roles('admin')
def new():
    if request.method == 'POST':
        item = FeeStructure(created_by=current_user.id)
        details(item)
        db.session.add(item)
        save()
        flash('Draft fee structure created. Add the approved charges, then publish it.', 'success')
        return redirect(url_for('fee_structures.detail', structure_id=item.id))
    return render_template('fee_structures/new.html', classes=sorted({s.class_name for s in Student.query.all()}),
        year=datetime.now(ZoneInfo('Africa/Nairobi')).year)


@fee_structures_bp.route('/<int:structure_id>', methods=['GET', 'POST'])
@roles('admin', 'teacher', 'student', 'parent')
def detail(structure_id):
    item = structure_access(structure_id, write=request.method == 'POST')
    if request.method == 'POST':
        # Serialize publication and edits across application instances.
        item = FeeStructure.query.filter_by(id=item.id).populate_existing().with_for_update().one()
        action = text('action', 20)
        if action == 'unpublish':
            item.published = False
        elif item.published:
            abort(409, description='Return this structure to draft before changing charges or instructions.')
        elif action == 'publish':
            if not item.lines:
                abort(400, description='Add at least one approved fee item before publishing.')
            item.published = True
        elif action == 'details':
            details(item)
        elif action == 'add_line':
            category = text('category', 30)
            if category not in CATEGORIES:
                abort(400)
            if len(item.lines) >= 50:
                abort(400, description='A structure can have at most 50 fee items.')
            db.session.add(FeeStructureLine(structure_id=item.id, category=category, label=text('label', 120),
                amount_cents=money_cents(), optional=request.form.get('optional') == 'yes'))
        elif action == 'remove_line':
            line = FeeStructureLine.query.get_or_404(integer('line_id'))
            if line.structure_id != item.id:
                abort(403)
            db.session.delete(line)
        else:
            abort(400)
        item.updated_at = datetime.utcnow()
        save()
        flash('Fee structure saved.', 'success')
        return redirect(url_for('fee_structures.detail', structure_id=item.id))
    return render_template('fee_structures/detail.html', item=item, categories=CATEGORIES)
