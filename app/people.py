from app.models import Staff, Parent, StudentAccount


def profile_names(users):
    names = {u.id:u.username for u in users}
    ids = list(names)
    for staff in Staff.query.filter(Staff.user_id.in_(ids)).all():
        names[staff.user_id] = staff.full_name
    for guardian in Parent.query.filter(Parent.user_id.in_(ids)).all():
        names[guardian.user_id] = guardian.full_name
    for link in StudentAccount.query.filter(StudentAccount.user_id.in_(ids)).all():
        names[link.user_id] = link.student.full_name
    return names
