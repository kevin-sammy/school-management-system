"""
app/models/__init__.py — All SQLAlchemy models
"""
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="teacher")  # admin, teacher, parent
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    admission_no = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    date_of_birth = db.Column(db.String(20))
    gender = db.Column(db.String(10))
    class_name = db.Column(db.String(20), nullable=False)
    stream = db.Column(db.String(10))
    year_enrolled = db.Column(db.Integer, default=datetime.utcnow().year)
    status = db.Column(db.String(20), default="active")  # active, inactive, graduated
    parent_id = db.Column(db.Integer, db.ForeignKey("parents.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attendances = db.relationship("Attendance", backref="student", lazy=True, cascade="all, delete")
    grades = db.relationship("Grade", backref="student", lazy=True, cascade="all, delete")
    fee_records = db.relationship("FeeRecord", backref="student", lazy=True, cascade="all, delete")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def attendance_rate(self):
        total = Attendance.query.filter_by(student_id=self.id).count()
        if total == 0:
            return 100.0
        present = Attendance.query.filter_by(student_id=self.id, status="present").count()
        return round((present / total) * 100, 1)

    @property
    def fee_balance(self):
        total_billed = sum(f.amount for f in self.fee_records if f.record_type == "invoice")
        total_paid = sum(f.amount for f in self.fee_records if f.record_type == "payment")
        return total_billed - total_paid


class Parent(db.Model):
    __tablename__ = "parents"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    relationship = db.Column(db.String(20), default="parent")  # parent, guardian
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    children = db.relationship("Student", backref="parent", lazy=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Staff(db.Model):
    __tablename__ = "staff"
    id = db.Column(db.Integer, primary_key=True)
    staff_no = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(40), nullable=False)  # teacher, admin, support
    department = db.Column(db.String(60))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    date_joined = db.Column(db.String(20))
    status = db.Column(db.String(20), default="active")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="present")  # present, absent, late
    notes = db.Column(db.String(200))
    recorded_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Grade(db.Model):
    __tablename__ = "grades"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    subject = db.Column(db.String(60), nullable=False)
    term = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Float, nullable=False)
    max_score = db.Column(db.Float, default=100.0)
    exam_type = db.Column(db.String(40), default="end_of_term")
    remarks = db.Column(db.String(200))
    recorded_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def percentage(self):
        return round((self.score / self.max_score) * 100, 1) if self.max_score else 0

    @property
    def letter_grade(self):
        pct = self.percentage
        if pct >= 80: return "A"
        if pct >= 70: return "B"
        if pct >= 60: return "C"
        if pct >= 50: return "D"
        return "E"


class FeeRecord(db.Model):
    __tablename__ = "fee_records"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    record_type = db.Column(db.String(20), nullable=False)  # invoice, payment
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    term = db.Column(db.String(20))
    year = db.Column(db.Integer)
    payment_method = db.Column(db.String(40))  # cash, mpesa, bank
    reference_no = db.Column(db.String(60))
    date = db.Column(db.String(20))
    recorded_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    target = db.Column(db.String(20), default="all")  # all, parents, staff
    sent_by = db.Column(db.String(80))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
