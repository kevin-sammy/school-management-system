"""Start a local SchoolMS demo. Hosted deployments use wsgi.py instead."""
import os
import secrets
from app import create_app, db
from app.demo import seed_demo_dataset
from app.models import User


def seed_demo_data(app):
    """Initialize an empty local demo with the expanded fictional dataset.

    Existing databases are untouched. To add the dataset to an existing school,
    use the admin Demo data page or `python -m flask --app wsgi seed-demo`.
    """
    with app.app_context():
        db.create_all()
        if User.query.first():
            return
        password = os.environ.get('DEMO_PASSWORD') or secrets.token_urlsafe(18)
        try:
            summary, created = seed_demo_dataset(password)
            from app.sample_names import normalize_sample_accounts
            normalize_sample_accounts()
        except Exception:
            db.session.rollback()
            raise
        if created:
            print('Expanded demo ready: 60 students, 6 teachers, 36 courses.')
            print('Administrator: demo.admin')
            print('Teacher/student/parent usernames are listed under Accounts & scheduling.')
            print(f'Local demo password: {password}')


if __name__ == '__main__':
    app = create_app()
    seed_demo_data(app)
    print('Starting SchoolMS on http://127.0.0.1:5000')
    app.run(debug=False)
