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
| 🔐 **Auth** | Role-based login (admin, teacher, parent) |

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
