# SchoolMS · Kevin Brook International Schools

An independent Flask school management system with separate administrator, teacher
student and parent areas, inspired by common SIS/LMS workflows.

## What users can do

| Role | Functions |
|---|---|
| Administrator | Student/staff/guardian records, finance, attendance, reports, accounts, course allocations, timetables, notices and demo-data generation |
| Teacher | Allocated courses and class rosters, attendance, subject assessments, lesson modules/resources, announcements, discussions, assignments, feedback and gradebooks |
| Student | Own grades, attendance, fee statements, timetable, course materials, discussions, submissions and teacher feedback |
| Parent / Guardian | Linked children’s attendance, fee balances/statements, grades, timetable and school notices |

Assignments support written submissions. Teachers can save draft scores, publish
results into the SIS grade records, update a published result or return it to draft.
Resubmission clears previous assessment results for a fresh review. Numeric draft
scores are private; written feedback may be visible before score publication.
Gradebooks support CSV export. Student records support printing.

## Local setup and expanded demo

```bash
pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`. On an empty local database, `run.py` generates the
expanded demo and prints a randomly generated demo password in your terminal.
Set `DEMO_PASSWORD` beforehand if you prefer your own 12–128 character password.
Existing populated databases are not automatically changed by `run.py`.

| Login area | Demo username | Password |
|---|---|---|
| `/login/admin` | `demo.admin` on an empty demo database | Password printed locally or supplied through `DEMO_PASSWORD` |
| `/login/teacher` | `demo.teacher01` through `demo.teacher06` | Password supplied when the dataset was first loaded |
| `/login/student` | `demo.student001` through `demo.student060` | Password supplied when the dataset was first loaded |
| `/login/parent` | `demo.parent01` through `demo.parent30` | Demo password, or the password chosen when upgrading parent logins |

The old `admin/admin123` demo credentials are not created by the new local runner.
Existing accounts and passwords remain unchanged.

## Expanded fictional dataset

The generator is in `app/demo.py` and is called by `run.py`, the Flask command and
the administrator's **Demo data** page.

| Records | Entries |
|---|---:|
| Students | 60 |
| Guardian profiles | 30 |
| Teacher staff profiles and logins | 6 |
| Class/stream groups | 6: Grades 6–8, East and West |
| Subject courses | 36 |
| Weekly timetable lessons | 36 |
| Assignments | 108 |
| Learning materials | 108 |
| Course announcements/discussions | 72 |
| Discussion replies | 108 |
| Attendance records | 1,200: 20 school days per student |
| Fee invoices/payments | 105 |
| Baseline assessments | 360, plus published assignment grades |
| School notices | 6 |

Coursework includes pending, overdue/missing, submitted, draft and published
states. Fees include fully paid, partially paid and unpaid statements. Attendance
includes present, absent and late records. Assignment deadlines are relative to
the import date; reruns retain the original deadlines.

Demo students use `DEMO/` admission numbers; staff use `DEMO/` staff numbers.
Contacts use reserved `.invalid` email addresses and omit real phone numbers.
A completed import marker prevents duplicate records on repeat runs. Collisions
without that marker fail instead of changing existing records. All data inserts
commit together. Existing accounts/passwords are never overwritten. A `demo.admin`
account is added only if the database has no administrator.

### Add demo data to an existing school

Sign in as the existing administrator, select **Demo data**, choose a password for
the new demo accounts and click **Generate demo data**. The records are added to
the database configured for that deployment. Repeating the import adds nothing.

Or run the command against the same configured database:

```bash
python -m flask --app wsgi seed-demo
```

The command prompts for the demo password. Automated environments can supply
`DEMO_PASSWORD` instead. Do not put passwords in source control or shared logs.

## Hosted deployment and login setup

Hosted deployments use `wsgi.py`. Configure these environment variables before
redeploying. Keep secret values in the hosting provider's environment settings.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Persistent PostgreSQL connection string; use your database provider's connection/SSL settings |
| `SECRET_KEY` | Strong, persistent random session secret shared by all instances |
| `SESSION_COOKIE_SECURE=true` | Use secure session cookies when serving over HTTPS |
| `BOOTSTRAP_ADMIN_USERNAME` | Optional first administrator username; defaults to `admin` |
| `BOOTSTRAP_ADMIN_EMAIL` | Optional first administrator email |
| `BOOTSTRAP_ADMIN_PASSWORD` | Optional 12–128 character first administrator password; ignored if an admin already exists |
| `SEED_DEMO_DATA=true` | Optional: load the expanded demo on the first request, once per database |
| `DEMO_PASSWORD` | Required for a first automatic demo import; 12–128 characters |

For a new hosted demo, set the first administrator credentials and demo settings,
then redeploy and visit `/login/admin`. Log in using the configured bootstrap
username/password. Teacher/student demo accounts use `DEMO_PASSWORD`.

Remove bootstrap/demo secret settings after the initial import and redeploy if
those settings are no longer needed. Removing them does not delete accounts or
records. Changing the variables does not reset existing passwords; users change
passwords through **Account settings**.

On the first non-static request, the application creates missing tables before
login queries run. PostgreSQL initialization uses a transaction advisory lock to
serialize cold starts. Existing records are preserved. Pool pre-ping checks stale
connections. Unavailable databases and incomplete hosted configuration return an
explanatory 503 setup page rather than an unhandled database traceback.

You can also initialize tables explicitly:

```bash
python -m flask --app wsgi init-db
```

This additive initializer creates missing tables; it is not a migration tool for
changing existing column definitions. Back up the database before deployment.
SQLite is supported for local development. Vercel deployments require a configured
persistent database and session secret; they do not fall back to a local SQLite
file. Local runs without `SECRET_KEY` use a random per-process key and sessions
expire across restarts.

### If login still fails

Check the actual production deployment URL and runtime logs. Confirm that
`DATABASE_URL` and `SECRET_KEY` are configured for Production and that the service
can reach the database. Existing administrators must use their existing passwords.
An invalid credential returns a login error; a setup/database failure returns 503.
Never paste database passwords or session secrets into public issues.

## Permissions and enrollment

All record scopes are enforced on the server. Students see their own records;
teachers manage only allocated classes/subjects. The original school-wide modules
require admin access. Create active student and teacher staff profiles first,
then link their portal accounts under **Accounts & scheduling**. A blank teaching
stream matches blank student streams, not every stream. Course enrollment uses
the student's current class and stream. Linked students are archived by changing
their status to inactive, preserving coursework history.

CSRF protection covers state-changing forms, including login and logout. Logout
uses POST. Passwords are hashed. Resource links require HTTPS, and CSV exports
escape spreadsheet formula prefixes. Core styling is served locally.

## Verification

```bash
pip install -r requirements.txt pytest
python -m pytest -q
```

GitHub Actions runs the integration suite. Tests cover role/record boundaries,
login, CSRF, provisioning, scores, submissions, grade publishing, discussions,
calendar filters, repeatable demo generation and fresh/failed database startup.

Not included: quizzes, file uploads, direct messaging, email-based password recovery, mobile apps or external PowerSchool synchronization. This is not a
PowerSchool product and does not claim commercial feature parity.

## Recover a forgotten administrator username or password

If an administrator already exists, `BOOTSTRAP_ADMIN_*` deliberately does not
change that account. Use the following **Production** environment variables for a
one-time recovery, then redeploy:

| Variable | Value |
|---|---|
| `ADMIN_RECOVERY_USERNAME` | Desired username, for example `admin` |
| `ADMIN_RECOVERY_PASSWORD` | Your new private password, 12–128 characters; store as Secret |
| `ADMIN_RECOVERY_ID` | A unique request name, for example `restore-admin-20261015-1` |

Visit `/login/admin` after deployment. The first request applies the recovery.
If there is exactly one administrator, it keeps that account's ID and email,
updates its username/password, and preserves school records. If no administrator
exists, it creates one. It never promotes a student/teacher account. If multiple
administrators exist, specify the exact existing administrator username.

After successful login, remove the three recovery variables and redeploy. A
consumed recovery ID does not run again, even if its environment settings remain,
so later password changes survive cold starts. For another intentional recovery,
choose a new request ID. Password values/fingerprints are not stored in the
recovery marker, and there is no public password-reset endpoint. Whoever controls
these settings already controls the deployment; do not share the password or
commit it to the repository.

## Automatic student and staff IDs

Student registration assigns an ID such as `STU-2026-00001`; adding staff assigns
`STF-2026-00001`. Each type has its own sequence for the current calendar year in
Africa/Nairobi. The final ID is allocated when the record is saved, displayed in
the confirmation and existing profile/list pages, and shown read-only when editing.
The registration forms do not require or accept manually supplied IDs.

Existing identifiers are unchanged, including `DEMO/` values. Trusted Python/ORM
imports can keep explicit IDs; missing IDs are automatically generated. Counters
start after existing IDs matching the format and skip later imported values.
Allocations are atomic PostgreSQL/SQLite upserts inside the record transaction:
concurrent saves receive different IDs, failed transactions roll back allocations,
and deleting a saved record does not rewind its counter. IDs stay unchanged when
you edit a profile or enter another calendar year. New annual sequences start at
one. Missing counter tables are created by the normal first-request initializer.

## Kevin Brook International Schools · family portal and previews

The school name is now **Kevin Brook International Schools**, shared across login,
portal navigation and printable reports through the `SCHOOL_NAME` application setting.
Existing admission/staff numbers and academic records are preserved.

Parents/guardians sign in at `/login/parent` and are redirected to `/family/`.
They can switch between linked children and view each child's attendance, fee
invoices/payments/balance, published grades, weekly timetable and parent/school
notices. This portal is read-only except for the account's own password change;
it does not process online fee payments or expose another child's records.

To issue a parent login, create the parent/guardian profile in **Parents & guardians**,
link that profile in each child's Student record, then open **Accounts & scheduling**
and create a **Parent / Guardian** account linked to that profile. Each guardian
profile can have one login; one login can view all children attached to its profile.
No linked children produces an explanatory empty state.

Administrators can select **Dashboard previews** to view teacher, student and parent
snapshots with the selected role's navigation. Preview links/actions are disabled,
and the real administrator session is unchanged. For interactive testing, open a
private/incognito window and use the respective role's issued credentials.

Fresh demo datasets now include 30 linked parent accounts, `demo.parent01` through
`demo.parent30`, using the supplied demo password. For demos loaded before this
feature, select **Demo data → Add parent demo logins**, choose a password, and click
**Add parent logins**. This adds missing demo guardian accounts once without resetting
existing accounts. Parents are linked to their two existing demo children. The
regular demo import retains its no-duplicates behavior.
