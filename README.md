# 🏫 School Management System

> A full-stack web application for managing school operations — built with Python (Flask) and Bootstrap.

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://sqlite.org)
[![Bootstrap](https://img.shields.io/badge/UI-Bootstrap_5-7952B3?style=flat-square&logo=bootstrap&logoColor=white)](https://getbootstrap.com)

Built from real-world experience managing ICT systems at **Kitengela International Schools** — this system handles the core operational workflows of a busy multi-site school.

---

## ✨ Features

| Module | Functionality |
|---|---|
| 🎓 **Students** | Registration, profiles, search, class management |
| 👨‍🏫 **Staff** | Staff directory, roles, departments, contact info |
| ✅ **Attendance** | Daily class-by-class attendance with save & report |
| 📊 **Grades** | Subject grades, report cards, letter grades, averages |
| 💰 **Fees** | Invoices, M-Pesa/cash payments, per-student statements |
| 👪 **Parents** | Parent/guardian registry, linked to students |
| 🔔 **Notifications** | Broadcast messages to parents, staff, or all |
| 🔐 **Auth** | Separate admin, teacher and student logins |

---

## 🚀 Quick Start

```bash
# Clone the repo
git clone https://github.com/kevin-sammy/school-management-system.git
cd school-management-system

# Install dependencies
pip install -r requirements.txt

# Run (auto-seeds demo data on first launch)
python run.py
```

Open **http://127.0.0.1:5000** in your browser.

**Demo credentials:**
| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Admin |
| `teacher` | `teacher123` | Teacher |
| `student` | `student123` | Student |

---

## 🗂️ Project Structure

```
school-management-system/
├── run.py                    # App entry point + demo data seeder
├── requirements.txt
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── models/               # SQLAlchemy database models
│   │   └── __init__.py       # User, Student, Staff, Grade, Attendance, Fee, Parent
│   ├── routes/               # Blueprint route handlers
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── students.py
│   │   ├── staff.py
│   │   ├── attendance.py
│   │   ├── grades.py
│   │   ├── fees.py
│   │   └── parents.py
│   └── templates/            # Jinja2 HTML templates
│       ├── base.html         # Sidebar layout
│       ├── auth/
│       ├── dashboard/
│       ├── students/
│       ├── staff/
│       ├── attendance/
│       ├── grades/
│       ├── fees/
│       └── parents/
```

---

## 🛠️ Tech Stack

- **Backend:** Python 3.8+, Flask 3.0, Flask-SQLAlchemy, Flask-Login
- **Database:** SQLite (zero-config, file-based)
- **Frontend:** Jinja2 templates, Bootstrap 5, Bootstrap Icons
- **Auth:** Werkzeug password hashing, session-based login

---

## 📸 Screenshots

> Dashboard with live stats, attendance summary, fee tracking, and quick actions.

---

## 🔮 Roadmap

- [ ] PDF report card export
- [ ] SMS/email notification delivery (Africa's Talking API)
- [ ] Parent self-service portal (view child's grades & fees)
- [ ] REST API for mobile app integration
- [ ] PostgreSQL support for production deployment

---

## 👤 Author

**Kevin Sammy**
- 📧 kmwendwa@bu.edu
- 🎓 MS Software Engineering, Boston University
- 💼 4+ years managing ICT at Kitengela International Schools
- 🏅 CCNA | CompTIA Network+ | Azure AZ-900

---

## 📄 License

MIT License — free to use and adapt.

## Teacher and student portals

Separate entry points are available at `/login/teacher`, `/login/student`, and
`/login/admin`. Successful teacher/student logins open `/portal/` automatically.

| Role | Functions |
|---|---|
| Teacher | Assigned class rosters, daily attendance, subject grades, publish assignments, read submissions, give feedback, weekly timetable and staff notices |
| Student | Own grades, attendance, fee statement, class timetable, assignments, written submissions and teacher feedback, student notices |
| Admin | Existing school administration plus portal account creation, profile linking, teacher/class/stream/subject allocation, timetable lessons, targeted notices |

Every portal query is scoped on the server. Students cannot access other student
records; teachers cannot manage classes or subjects outside their allocation.
The original school-wide administration modules now require an admin account.
Parent self-service is still on the roadmap; parent accounts cannot enter these
administration or teacher/student portals.

### Existing database setup

Back up your existing database, set `SECRET_KEY` to a unique random value and
`DATABASE_URL` to your database connection string, then run:

```bash
python -m flask --app wsgi init-db
```

This creates the five new portal tables without changing or reseeding existing
records. No columns are added to existing tables. Restart the application after
installing the code. Use HTTPS in production and configure
`SESSION_COOKIE_SECURE=true` in your deployment environment. Without a configured
`SECRET_KEY`, a random per-process key is generated for local use, so sessions do
not persist across restarts and cannot be shared between workers.

Sign in as admin, open **Portal accounts & classes**, and:

1. Create each student's account linked to their existing active student profile,
   or each teacher's account linked to an active Teacher staff profile.
2. Assign each teacher a class, exact stream and subject. A blank stream means
   students whose stream is blank, not all streams. Multiple allocations are supported.
3. Add weekly timetable lessons. Overlapping teacher or class lessons are rejected.
4. Share credentials privately. Users can select **Change password** after login.
5. Publish notices using **Parents → Send Notification** and choose the audience.

For an existing teacher login created before these changes, allocate that user
under **Assign teacher to class**; no new login is needed. Existing student logins
were not supported before this change; create them with the linked account form.

### Local demo

`python run.py` seeds demonstration data only if there are no users in the database.
On a fresh database, use `teacher / teacher123`, `student / student123`, or
`admin / admin123`. These are demonstration credentials only. The student is linked
to Brian Kamau and the teacher is allocated Grade 7 East Mathematics. Demo seeding
does not upgrade accounts in an already populated database.

Assignments accept written text, can be updated until the due date (inclusive,
server date), and expose feedback only to their owner. Resubmitting clears previous
feedback for a fresh review. File uploads, password recovery/email delivery, online
fee payments, and PDF exports are not included in this version. Timetables and
account creation are administered through the portal; existing account editing,
password resets by administrators and timetable editing are future improvements.

All state-changing forms, including login and logout, require a CSRF token. Logout
now uses POST. Passwords are hashed; newly issued passwords must be 12–128 characters.

### Tests

```bash
pip install -r requirements.txt pytest
python -m pytest -q
```

Tests cover role/record isolation, login and CSRF, roster scope, attendance updates,
finite score validation and grade updates, assignment submission and feedback,
deadlines, account provisioning, lesson conflicts, password changes, and existing
admin-page rendering. GitHub Actions runs these tests on pushes and pull requests.

## Connected SIS + learning workspace

This version adds a course-centered learning experience inspired by the common
SIS/LMS workflows in PowerSchool SIS and Schoology, with original SchoolMS branding.
It is an independent Flask application, not a PowerSchool product or integration.

- **Overview:** role-specific metrics, course cards, school/course activity, upcoming
  work and a weekly schedule.
- **Courses:** search by subject/class, open course modules, read lesson pages and
  HTTPS resource links, and participate in teacher-created class discussions.
- **Teachers:** publish course announcements, discussions and learning materials;
  remove materials; create assignments; review student work in a class gradebook.
- **Grade publishing:** save draft scores privately, publish grades to the existing
  SIS `Grade` records, update a published grade without creating another record,
  or return a published result to draft. Publishing includes term/year/feedback.
  A student resubmission clears its assessment and published grade for fresh review.
  Written feedback may be visible before a numeric score is published.
- **Calendar:** monthly assignment deadlines and the weekly timetable with previous,
  current and next-month navigation.
- **Students:** upcoming/missing/submitted assignment views, published results,
  printable academic/attendance/fee records and course conversations.
- **Administrators:** redesigned SIS overview, course oversight and gradebook CSV
  exports, alongside enrollment, staff, finance, notices, accounts and scheduling.
- **Accessibility:** labeled forms, keyboard focus, a skip link, responsive navigation
  and semantic headings. Core styling is served locally without a runtime CDN.

New routes are under `/learning`. Course access follows teacher allocation and
student class/stream membership; students never receive a class roster or another
student's submissions. CSV gradebook exports are limited to authorized staff and
escape spreadsheet formula prefixes in user-supplied cells. Linked students are
archived by setting their status inactive rather than deleting academic history.

Run `python -m flask --app wsgi init-db` after updating to create the four additional
learning tables (`course_materials`, `course_posts`, `course_replies`,
`submission_assessments`). This is additive and preserves existing records.
Fresh demonstration databases include Mathematics, English and Science course
spaces; existing databases are not reseeded.

This release does not include quizzes, file uploads, direct messaging, a parent
self-service portal, a mobile app or external SIS synchronization. It does not
claim feature parity with commercial platforms. Course and attendance allocations
continue to use each student's current class/stream rather than historical course
enrollment snapshots.
