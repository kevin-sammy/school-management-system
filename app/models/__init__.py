"""
app/models/__init__.py — All SQLAlchemy models
"""
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="teacher")  # admin, teacher, student, parent
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


class StudentAccount(db.Model):
    """Separate table keeps existing student databases compatible."""
    __tablename__ = 'student_accounts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), unique=True, nullable=False)
    student = db.relationship('Student')
    user = db.relationship('User')


class TeachingClass(db.Model):
    __tablename__ = 'teaching_classes'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    class_name = db.Column(db.String(20), nullable=False)
    stream = db.Column(db.String(10), nullable=False, default='')
    subject = db.Column(db.String(60), nullable=False)
    __table_args__ = (db.UniqueConstraint('teacher_id', 'class_name', 'stream', 'subject'),)


class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    teaching_class_id = db.Column(db.Integer, db.ForeignKey('teaching_classes.id'), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.String(20), nullable=False)
    teaching_class = db.relationship('TeachingClass')


class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    feedback = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    student = db.relationship('Student')
    assignment = db.relationship('Assignment')
    __table_args__ = (db.UniqueConstraint('assignment_id', 'student_id'),)


class Lesson(db.Model):
    __tablename__ = 'lessons'
    id = db.Column(db.Integer, primary_key=True)
    teaching_class_id = db.Column(db.Integer, db.ForeignKey('teaching_classes.id'), nullable=False)
    day = db.Column(db.String(12), nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    room = db.Column(db.String(60), nullable=False)
    teaching_class = db.relationship('TeachingClass')


class CourseMaterial(db.Model):
    __tablename__ = 'course_materials'
    id = db.Column(db.Integer, primary_key=True)
    teaching_class_id = db.Column(db.Integer, db.ForeignKey('teaching_classes.id'), nullable=False)
    module = db.Column(db.String(100), nullable=False, default='General')
    title = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default='page')
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    teaching_class = db.relationship('TeachingClass')


class CoursePost(db.Model):
    __tablename__ = 'course_posts'
    id = db.Column(db.Integer, primary_key=True)
    teaching_class_id = db.Column(db.Integer, db.ForeignKey('teaching_classes.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    author = db.relationship('User')
    teaching_class = db.relationship('TeachingClass')


class CourseReply(db.Model):
    __tablename__ = 'course_replies'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('course_posts.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    author = db.relationship('User')
    post = db.relationship('CoursePost', backref=db.backref('replies', order_by='CourseReply.created_at'))


class SubmissionAssessment(db.Model):
    __tablename__ = 'submission_assessments'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), unique=True, nullable=False)
    points = db.Column(db.Float, nullable=False)
    max_points = db.Column(db.Float, nullable=False, default=100)
    term = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey('grades.id'), unique=True)
    submission = db.relationship('Submission')
    grade = db.relationship('Grade')


class DemoDataset(db.Model):
    """Transaction marker and summary for a repeatable demo-data import."""
    __tablename__ = 'demo_datasets'
    key = db.Column(db.String(80), primary_key=True)
    summary = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class AdminRecovery(db.Model):
    """Consumed owner-configured recovery requests; no password fingerprints."""
    __tablename__ = 'admin_recoveries'
    request_id = db.Column(db.String(80), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class IdentifierCounter(db.Model):
    """Transactional counters for student and staff public identifiers."""
    __tablename__ = 'identifier_counters'
    namespace = db.Column(db.String(40), primary_key=True)
    last_value = db.Column(db.Integer, nullable=False)
