"""
run.py — Start the SchoolMS application
Usage: python run.py
"""
from app import create_app, db
from app.models import User, Student, Staff, Parent, Grade, Attendance, FeeRecord, Notification, StudentAccount, TeachingClass, Assignment, Lesson, CourseMaterial, CoursePost


def seed_demo_data(app):
    """Seed the database with demo data for testing."""
    with app.app_context():
        db.create_all()

        if User.query.first():
            return  # Already seeded

        print("🌱 Seeding demo data...")

        # Admin user
        admin = User(username="admin", email="admin@school.ke", role="admin")
        admin.set_password("admin123")
        teacher = User(username="teacher", email="teacher@school.ke", role="teacher")
        teacher.set_password("teacher123")
        db.session.add_all([admin, teacher])
        db.session.flush()

        # Parents
        parents = [
            Parent(first_name="James", last_name="Kamau", phone="+254711000001", email="jkamau@gmail.com"),
            Parent(first_name="Mary", last_name="Wanjiku", phone="+254711000002", email="mwanjiku@gmail.com"),
            Parent(first_name="Peter", last_name="Odhiambo", phone="+254711000003"),
        ]
        db.session.add_all(parents)
        db.session.flush()

        # Students
        students = [
            Student(admission_no="KIS/2024/001", first_name="Brian", last_name="Kamau",
                    class_name="Grade 7", stream="East", gender="Male", year_enrolled=2024,
                    parent_id=parents[0].id),
            Student(admission_no="KIS/2024/002", first_name="Amina", last_name="Wanjiku",
                    class_name="Grade 7", stream="East", gender="Female", year_enrolled=2024,
                    parent_id=parents[1].id),
            Student(admission_no="KIS/2024/003", first_name="Collins", last_name="Odhiambo",
                    class_name="Grade 6", stream="West", gender="Male", year_enrolled=2023,
                    parent_id=parents[2].id),
            Student(admission_no="KIS/2024/004", first_name="Faith", last_name="Mutua",
                    class_name="Grade 6", stream="West", gender="Female", year_enrolled=2023),
            Student(admission_no="KIS/2024/005", first_name="Dennis", last_name="Cheruiyot",
                    class_name="Grade 8", stream="North", gender="Male", year_enrolled=2022),
        ]
        db.session.add_all(students)
        db.session.flush()

        # Staff
        staff = [
            Staff(staff_no="STF/001", first_name="Grace", last_name="Muthoni",
                  role="Teacher", department="Mathematics", phone="+254722000001"),
            Staff(staff_no="STF/002", first_name="John", last_name="Kipchoge",
                  role="Teacher", department="English", phone="+254722000002"),
            Staff(staff_no="STF/003", first_name="Kevin", last_name="Sammy",
                  role="IT", department="ICT", phone="+254726685096", email="kmwendwa@bu.edu"),
        ]
        db.session.add_all(staff)
        db.session.flush()

        # Linked demo portals (only created in an empty demo database).
        learner = User(username="student", email="student@school.ke", role="student")
        learner.set_password("student123")
        db.session.add(learner)
        db.session.flush()
        db.session.add(StudentAccount(user_id=learner.id, student_id=students[0].id))
        staff[0].user_id = teacher.id
        classroom = TeachingClass(teacher_id=teacher.id, class_name="Grade 7", stream="East", subject="Mathematics")
        db.session.add(classroom)
        db.session.flush()
        from datetime import date, timedelta
        db.session.add(Assignment(teaching_class_id=classroom.id, title="Fractions practice",
                                 instructions="Explain how to add 1/2 and 1/4. Show your working.",
                                 due_date=(date.today() + timedelta(days=7)).isoformat()))
        db.session.add(Lesson(teaching_class_id=classroom.id, day="Monday", start_time="09:00", end_time="09:40", room="Room 7E"))

        # Demonstration course spaces and materials.
        course_items = [classroom]
        for subject in ['English', 'Science']:
            course = TeachingClass(teacher_id=teacher.id, class_name="Grade 7", stream="East", subject=subject)
            db.session.add(course)
            course_items.append(course)
        db.session.flush()
        for i, course in enumerate(course_items):
            db.session.add(CourseMaterial(teaching_class_id=course.id, module="Unit 1 · Getting started",
                title=f"Welcome to {course.subject}", kind="page",
                content="Welcome to your course. Review the lesson notes, explore the learning resources, and take part in our class discussion. Your weekly tasks and feedback are available in this space."))
            db.session.add(CoursePost(teaching_class_id=course.id, author_id=teacher.id,
                kind="discussion", title="What are you curious about this term?",
                body="Share one topic you would like to explore and one question you have. Read your classmates’ ideas and build on them respectfully."))
            if i:
                db.session.add(Assignment(teaching_class_id=course.id, title="Reading reflection" if i == 1 else "Observe the world around you",
                    instructions="Write a short reflection and explain what you learned. Use examples to support your answer.",
                    due_date=(date.today() + timedelta(days=3+i)).isoformat()))
                db.session.add(Lesson(teaching_class_id=course.id, day="Tuesday" if i == 1 else "Wednesday",
                    start_time="10:00", end_time="10:40", room="Room 7E"))

        # Grades
        from datetime import date
        subjects = ["Mathematics", "English", "Science", "Kiswahili"]
        scores = [85, 72, 91, 68, 78, 55, 88, 74]
        for i, student in enumerate(students[:3]):
            for j, subject in enumerate(subjects):
                g = Grade(student_id=student.id, subject=subject,
                          term="Term 1", year=2026,
                          score=scores[(i + j) % len(scores)],
                          recorded_by="admin")
                db.session.add(g)

        # Attendance
        today = date.today().strftime("%Y-%m-%d")
        statuses = ["present", "present", "present", "absent", "late"]
        for i, student in enumerate(students):
            a = Attendance(student_id=student.id, date=today,
                           status=statuses[i], recorded_by="admin")
            db.session.add(a)

        # Fee records
        fee_data = [
            (students[0].id, "invoice", 15000, "Term 1 2026 Fees"),
            (students[0].id, "payment", 15000, "Term 1 payment", "mpesa", "QWE123456"),
            (students[1].id, "invoice", 15000, "Term 1 2026 Fees"),
            (students[1].id, "payment", 10000, "Partial payment", "cash"),
            (students[2].id, "invoice", 15000, "Term 1 2026 Fees"),
        ]
        for fd in fee_data:
            f = FeeRecord(student_id=fd[0], record_type=fd[1], amount=fd[2],
                          description=fd[3], term="Term 1", year=2026,
                          payment_method=fd[4] if len(fd) > 4 else None,
                          reference_no=fd[5] if len(fd) > 5 else None,
                          date=today, recorded_by="admin")
            db.session.add(f)

        # Notification
        n = Notification(title="Welcome to Term 1 2026",
                         message="Dear parents and staff, welcome back! Term 1 begins on 6th January 2026. Please ensure all fees are paid by end of week 1.",
                         target="all", sent_by="admin")
        db.session.add(n)

        db.session.commit()
        print("✅ Demo data seeded! Login: admin / admin123")


if __name__ == "__main__":
    app = create_app()
    seed_demo_data(app)
    print("\n🚀 Starting SchoolMS on http://127.0.0.1:5000")
    app.run(debug=False)
