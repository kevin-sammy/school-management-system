"""Generate fictional, linked SIS and LMS data without replacing existing records."""
from datetime import date, timedelta
from app import db
from app.models import (User, Student, Staff, Parent, StudentAccount, TeachingClass,
                        Assignment, Submission, SubmissionAssessment, Lesson, Grade,
                        Attendance, FeeRecord, Notification, CourseMaterial, CoursePost,
                        CourseReply, DemoDataset)

DATASET_KEY = 'schoolms-expanded-demo-v1'
PASSWORD_MIN = 12
SUBJECTS = ['Mathematics', 'English', 'Science', 'Kiswahili', 'Social Studies', 'Computer Studies']
FIRST_NAMES = ['Amina', 'Brian', 'Faith', 'Collins', 'Grace', 'Dennis', 'Leah', 'David', 'Zawadi', 'Daniel',
               'Nia', 'Ethan', 'Imani', 'Noah', 'Esther', 'Samuel', 'Joy', 'Isaac', 'Neema', 'Joshua']
LAST_NAMES = ['Kamau', 'Otieno', 'Wanjiku', 'Mutua', 'Kiptoo', 'Achieng', 'Mwangi', 'Njeri', 'Omondi', 'Wambui']


def school_days(today, count=20):
    days = []
    cursor = today
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return sorted(days)


def seed_demo_dataset(password, today=None):
    """Insert one complete dataset atomically. Call inside an application context.

    Existing demo imports are a no-op. Collisions abort instead of modifying an
    existing record. The caller must create tables first and handle failures.
    """
    existing = db.session.get(DemoDataset, DATASET_KEY)
    if existing:
        return dict(existing.summary), False
    if not PASSWORD_MIN <= len(password) <= 128:
        raise ValueError('Use a demo password of 12 to 128 characters.')
    today = today or date.today()
    admin_needed = User.query.filter_by(role='admin').first() is None
    usernames = [f'demo.teacher{i:02d}' for i in range(1, 7)] + [f'demo.student{i:03d}' for i in range(1, 61)]
    if admin_needed:
        usernames.append('demo.admin')
    emails = [f'{username}@schoolms.example.invalid' for username in usernames]
    if (User.query.filter(db.or_(User.username.in_(usernames), User.email.in_(emails))).first()
            or Student.query.filter(Student.admission_no.like('DEMO/%')).first()
            or Staff.query.filter(Staff.staff_no.like('DEMO/%')).first()
            or Parent.query.filter(Parent.email.like('demo.parent%@schoolms.example.invalid')).first()):
        raise ValueError('Demo identifiers already exist without a completed import marker. No existing records were changed.')

    summary = {}

    def add(model, **values):
        item = model(**values)
        db.session.add(item)
        summary[model.__tablename__] = summary.get(model.__tablename__, 0) + 1
        return item

    # One hash is reused only for these deliberately shared demo credentials.
    # Distinct accounts still have separate roles and profile links.
    credential = User(username='unused', email='unused@example.invalid', role='student')
    credential.set_password(password)

    def account(username, role):
        return add(User, username=username, email=f'{username}@schoolms.example.invalid',
                   role=role, password_hash=credential.password_hash)

    if admin_needed:
        account('demo.admin', 'admin')
    teachers = []
    for i, subject in enumerate(SUBJECTS):
        teacher = account(f'demo.teacher{i+1:02d}', 'teacher')
        teachers.append(teacher)
    parents = [add(Parent, first_name=f'Demo Guardian {i+1}', last_name=LAST_NAMES[i % 10],
                   email=f'demo.parent{i+1:02d}@schoolms.example.invalid', relationship='guardian')
               for i in range(30)]
    db.session.flush()
    for i, guardian in enumerate(parents):
        parent_user = account(f'demo.parent{i+1:02d}', 'parent')
        db.session.flush()
        guardian.user_id = parent_user.id
    for i, teacher in enumerate(teachers):
        add(Staff, staff_no=f'DEMO/T{i+1:02d}', first_name=['Grace', 'John', 'Mary', 'Peter', 'Sarah', 'James'][i],
            last_name=LAST_NAMES[i], role='Teacher', department=SUBJECTS[i], email=teacher.email,
            user_id=teacher.id, date_joined=f'{today.year}-01-05')

    sections = [(f'Grade {grade}', stream) for grade in [6, 7, 8] for stream in ['East', 'West']]
    students = []
    days = school_days(today)
    for i in range(60):
        class_name, stream = sections[i // 10]
        student = add(Student, admission_no=f'DEMO/{i+1:03d}', first_name=FIRST_NAMES[i % 20],
            last_name=LAST_NAMES[(i // 6 + i) % 10], class_name=class_name, stream=stream,
            date_of_birth=f'{today.year-int(class_name[-1])-6}-05-{i % 28 + 1:02d}',
            gender='Female' if i % 2 == 0 else 'Male', year_enrolled=today.year,
            parent_id=parents[i // 2].id)
        user = account(f'demo.student{i+1:03d}', 'student')
        db.session.flush()
        add(StudentAccount, user_id=user.id, student_id=student.id)
        students.append((student, user))
        for offset, day in enumerate(days):
            status = 'absent' if (i + offset) % 13 == 0 else 'late' if (i + offset) % 11 == 0 else 'present'
            add(Attendance, student_id=student.id, date=day.isoformat(), status=status,
                notes='Fictional demo attendance', recorded_by=teachers[0].username)
        billed = 18000 + (i // 20) * 1500
        add(FeeRecord, student_id=student.id, record_type='invoice', amount=billed,
            description='DEMO · Current term tuition', term='Term 1', year=today.year,
            date=days[0].isoformat(), recorded_by='demo.generator', reference_no=f'DEMO-INV-{i+1:03d}')
        if i % 4 != 3:
            add(FeeRecord, student_id=student.id, record_type='payment', amount=billed if i % 4 == 0 else billed * .5,
                description='DEMO · Tuition payment', term='Term 1', year=today.year,
                payment_method=['mpesa', 'bank', 'cash'][i % 3], reference_no=f'DEMO-PAY-{i+1:03d}',
                date=days[-1].isoformat(), recorded_by='demo.generator')
        for j, subject in enumerate(SUBJECTS):
            add(Grade, student_id=student.id, subject=subject, term='Term 1', year=today.year,
                score=45 + (i * 7 + j * 11) % 54, max_score=100, exam_type='Demo baseline assessment',
                remarks='Fictional baseline result for demonstration.', recorded_by=teachers[j].username)

    slots = ['08:00', '08:50', '09:40', '10:50', '11:40', '12:30']
    ends = ['08:40', '09:30', '10:20', '11:30', '12:20', '13:10']
    for section_index, (class_name, stream) in enumerate(sections):
        roster = students[section_index * 10:(section_index + 1) * 10]
        for subject_index, subject in enumerate(SUBJECTS):
            teacher = teachers[subject_index]
            course = add(TeachingClass, teacher_id=teacher.id, class_name=class_name, stream=stream, subject=subject)
            db.session.flush()
            slot = (section_index + subject_index) % 6
            add(Lesson, teaching_class_id=course.id, day='Monday', start_time=slots[slot], end_time=ends[slot],
                room=f'Demo room {section_index+1}')
            for module in [1, 2]:
                add(CourseMaterial, teaching_class_id=course.id, module=f'Unit {module} · {subject}',
                    title=f'{subject}: lesson {module}', kind='page',
                    content=f'DEMO LESSON\nExplore the key ideas in {subject}. Explain one concept in your own words, work through an example, and compare your approach with a classmate.')
            add(CourseMaterial, teaching_class_id=course.id, module='Learning resources',
                title='Open educational resources', kind='link', content='https://www.khanacademy.org/')
            add(CoursePost, teaching_class_id=course.id, author_id=teacher.id, kind='announcement',
                title=f'Welcome to {subject}', body='This is a fictional demo course. Read Unit 1, check your timetable and complete the upcoming coursework.')
            discussion = add(CoursePost, teaching_class_id=course.id, author_id=teacher.id, kind='discussion',
                title='Share your learning goal', body='What would you like to learn this term? Explain your goal and ask one question.')
            db.session.flush()
            for student, user in roster[:3]:
                add(CourseReply, post_id=discussion.id, author_id=user.id,
                    body=f'I would like to improve my understanding of {subject} and explain my reasoning more clearly.')
            for assignment_index, (name, delta) in enumerate([('Practice and reflection', -5), ('Apply your learning', 3), ('Unit project', 10)]):
                assignment = add(Assignment, teaching_class_id=course.id, title=f'{subject} · {name}',
                    instructions='Fictional demo task: explain the main idea, give an example, and describe how you checked your answer.',
                    due_date=(today + timedelta(days=delta)).isoformat())
                db.session.flush()
                for roster_index, (student, user) in enumerate(roster):
                    state = (roster_index + assignment_index) % 4
                    if state == 0:
                        continue  # missing or pending work
                    submission = add(Submission, assignment_id=assignment.id, student_id=student.id,
                        answer=f'DEMO SUBMISSION\nMy example explains a key idea in {subject}. I checked each step and reviewed the result.',
                        feedback='Clear explanation. Include another example next time.' if state >= 2 else None)
                    db.session.flush()
                    if state >= 2:
                        points = 55 + (roster_index * 5 + subject_index * 3) % 44
                        assessment = add(SubmissionAssessment, submission_id=submission.id, points=points,
                            max_points=100, term='Term 1', year=today.year)
                        if state == 3:
                            grade = add(Grade, student_id=student.id, subject=subject, term='Term 1', year=today.year,
                                score=points, max_score=100, exam_type=f'assignment:{assignment.id}',
                                remarks=submission.feedback, recorded_by=teacher.username)
                            assessment.grade = grade
    for target, title in [('all', 'Demo school welcome'), ('students', 'Student study week'),
                          ('teachers', 'Teacher planning meeting'), ('staff', 'Staff development day'),
                          ('parents', 'Guardian information evening'), ('all', 'Library reading challenge')]:
        add(Notification, target=target, title=f'DEMO · {title}',
            message='Fictional demonstration notice. Explore your courses, academic records and school calendar.',
            sent_by='demo.generator')
    db.session.add(DemoDataset(key=DATASET_KEY, summary=summary))
    db.session.commit()
    return summary, True



def seed_demo_parent_accounts(password):
    """Add parent logins to an already loaded pre-parent demo, once."""
    import re
    key = 'schoolms-demo-parent-accounts-v1'
    marker = db.session.get(DemoDataset, key)
    if marker:
        return dict(marker.summary), False
    if not 12 <= len(password) <= 128:
        raise ValueError('Use a demo password of 12 to 128 characters.')
    guardians = Parent.query.filter(Parent.email.like('demo.parent%@schoolms.example.invalid')).all()
    if not guardians:
        raise ValueError('Load the expanded school demo dataset first.')
    pending = []
    for guardian in guardians:
        match = re.fullmatch(r'demo\.parent(\d{2})@schoolms\.example\.invalid', guardian.email or '')
        if not match or guardian.user_id:
            continue
        username = f'demo.parent{match.group(1)}'
        if User.query.filter(db.or_(User.username == username, User.email == guardian.email)).first():
            raise ValueError('A demo parent username or email is already in use. Existing accounts were preserved.')
        pending.append((guardian, username))
    credential = User(username='unused',email='unused@example.invalid',role='parent')
    credential.set_password(password)
    for guardian, username in pending:
        user = User(username=username,email=guardian.email,role='parent',password_hash=credential.password_hash)
        db.session.add(user)
        db.session.flush()
        guardian.user_id = user.id
    summary = {'parent_logins':len(pending)}
    db.session.add(DemoDataset(key=key,summary=summary))
    db.session.commit()
    return summary, True
