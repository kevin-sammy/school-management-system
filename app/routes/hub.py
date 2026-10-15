"""Course-scoped resource library, external collaboration links and navigation help."""
from urllib.parse import urlsplit
from flask import Blueprint, render_template, request, abort, redirect, url_for, jsonify
from flask_login import current_user
from app import db
from app.models import CourseMaterial, CollaborationRoom
from app.routes.learning import visible_classes, course_access
from app.routes.portal import roles, text, integer

hub_bp = Blueprint('hub', __name__, url_prefix='/hub')


@hub_bp.route('/')
@roles('admin', 'teacher', 'student')
def index():
    courses = visible_classes()
    ids = [c.id for c in courses]
    search = request.args.get('q', '').strip()[:120]
    materials = CourseMaterial.query.filter(CourseMaterial.teaching_class_id.in_(ids)).order_by(CourseMaterial.created_at.desc()).all()
    if search:
        materials = [m for m in materials if search.casefold() in f'{m.title} {m.module} {m.teaching_class.subject} {m.content}'.casefold()]
    return render_template('hub/index.html', materials=materials, search=search)


@hub_bp.route('/collaborate', methods=['GET', 'POST'])
@roles('admin', 'teacher', 'student')
def collaborate():
    courses = visible_classes()
    if request.method == 'POST':
        course = course_access(integer('class_id'), write=True)
        platform = text('platform', 30)
        allowed = {'Google Meet': ('meet.google.com',), 'Google Classroom': ('classroom.google.com',),
                   'Microsoft Teams': ('teams.microsoft.com', 'teams.live.com', 'teams.cloud.microsoft')}
        link = text('join_url', 2000)
        try:
            parsed = urlsplit(link)
            valid = (platform in allowed and parsed.scheme == 'https' and parsed.hostname in allowed[platform]
                     and not parsed.username and not parsed.password and not any(c.isspace() for c in link)
                     and parsed.port in (None, 443))
        except ValueError:
            valid = False
        if not valid:
            abort(400, description='Use an HTTPS meeting or classroom link from the selected platform.')
        db.session.add(CollaborationRoom(teaching_class_id=course.id, title=text('title', 120),
            platform=platform, join_url=link, schedule=text('schedule', 200, False)))
        db.session.commit()
        return redirect(url_for('hub.collaborate'))
    rooms = CollaborationRoom.query.filter(CollaborationRoom.teaching_class_id.in_([c.id for c in courses])).all()
    return render_template('hub/collaborate.html', courses=courses, rooms=rooms)


@hub_bp.route('/collaborate/<int:room_id>/delete', methods=['POST'])
@roles('admin', 'teacher')
def remove_room(room_id):
    room = CollaborationRoom.query.get_or_404(room_id)
    course_access(room.teaching_class_id, write=True)
    db.session.delete(room)
    db.session.commit()
    return redirect(url_for('hub.collaborate'))


HELP_TOPICS = [
    ('materials', 'Learning materials', ['material', 'resource', 'library', 'hub', 'book', 'learn'],
     'Open the digital hub to search course materials. Teachers add pages and HTTPS resources from their course page.', 'hub.index', {'admin','teacher','student'}),
    ('courses', 'Courses and discussions', ['course', 'discussion', 'subject', 'class'],
     'Open a course, then choose Materials, Updates, or Assignments. Open a discussion in Updates to join the conversation.', 'learning.courses', {'admin','teacher','student'}),
    ('assignments', 'Assignments', ['assignment', 'homework', 'submit'],
     'Open Assignments, select the task, and read its instructions. Students submit work there; teachers review submissions in their course.', 'learning.assignments', {'admin','teacher','student'}),
    ('exams', 'Online exams', ['exam', 'test', 'proctor', 'quiz'],
     'Open Online exams. Students can start one timed attempt after reading the monitoring notice. Teachers create questions, publish exams, review answers and release results.', 'exams.index', {'admin','teacher','student'}),
    ('collaboration', 'Online collaboration', ['meet', 'team', 'collaborat', 'video', 'classroom'],
     'Open Collaboration to find your course meeting and Classroom links. The meeting provider may require its own school account.', 'hub.collaborate', {'admin','teacher','student'}),
    ('messages', 'School inbox', ['mail', 'message', 'inbox', 'contact'],
     'Open School inbox and choose Compose message. Select an available school contact. Messages stay inside this system; external email delivery is not connected.', 'mail.index', {'admin','teacher','student','parent'}),
    ('transport', 'School transport', ['transport', 'bus', 'route', 'pickup'],
     'Open School transport for pickup details and the route teacher. Administrators create routes and assign students; teachers see their assigned rosters.', 'transport.index', {'admin','teacher','student','parent'}),
    ('family', 'Child attendance and fees', ['fee', 'balance', 'child', 'attendance'],
     'Open your family dashboard and select a linked child to see attendance, fee invoices, payments and balance. Ask the administrator if a child is missing.', 'family.home', {'parent'}),
    ('records', 'Grades and attendance', ['grade', 'result', 'attendance', 'fee', 'balance'],
     'Open Grades & records to see your school records. Online exam results appear in Online exams after the teacher releases them.', 'learning.records', {'student'}),
    ('accounts', 'Accounts and dashboard previews', ['account', 'preview', 'login', 'password', 'user'],
     'Open Accounts & scheduling to provision accounts. Dashboard previews show the teacher, student and parent experience without changing your administrator session.', 'portal.accounts', {'admin'}),
    ('settings', 'Change password', ['password', 'setting', 'login'],
     'Open Account settings to change your password. If you cannot sign in, ask your school administrator to reset your account password.', 'portal.password', {'admin','teacher','student','parent'}),
]


@hub_bp.route('/help', methods=['GET', 'POST'])
@roles('admin', 'teacher', 'student', 'parent')
def help_chat():
    topics = [t for t in HELP_TOPICS if current_user.role in t[5]]
    if request.method == 'POST':
        message = text('message', 500)
        query = message.casefold()
        from app.chatbot import enabled, reserve_request, answer
        ai_answer = None
        if enabled():
            if not reserve_request(current_user.id):
                return jsonify(error='Please wait a moment or use the topic links. The assistant allows 100 AI questions per day.'), 429
            ai_answer = answer(message, current_user.role, topics)
        matches = [t for t in topics if t[0] == query or any(word in query for word in t[2])][:3]
        return jsonify(answer=ai_answer, mode='ai' if ai_answer else 'guided', replies=[{'text': t[3], 'label': t[1], 'url': url_for(t[4])} for t in matches],
                       fallback='I can help you find portal features. Choose a topic below, or try “materials”, “messages”, or “transport”.' if not matches and not ai_answer else '')
    from app.chatbot import enabled
    return render_template('hub/help.html', topics=topics, ai_enabled=enabled())
