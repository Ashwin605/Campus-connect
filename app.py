import os
import random
import json
import string
from datetime import datetime, timezone, timedelta, date
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, abort)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename

from config import Config
from models import (db, User, Task, Submission, Badge, UserBadge,
                    Notification, Message, Event, EventAttendee,
                    StreakEntry, ActivityLog)

from flask_migrate import Migrate

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
csrf = CSRFProtect(app)
socketio = SocketIO(app, cors_allowed_origins="*")

app.jinja_env.filters['fromjson'] = json.loads


os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ─── Helpers ───
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator

def log_activity(user_id, action, details='', pts=0):
    db.session.add(ActivityLog(user_id=user_id, action=action, details=details, points_change=pts))
    db.session.commit()
    user = db.session.get(User, user_id)
    if user and action not in ['login', 'registered']:
        # Broadcast exciting events to everyone!
        socketio.emit('global_activity', {
            'user': user.full_name,
            'avatar': user.get_initials(),
            'color': user.avatar_color,
            'action': action,
            'details': details,
            'pts': pts
        })

def send_notification(user_id, title, message, ntype='info'):
    n = Notification(user_id=user_id, title=title, message=message, type=ntype)
    db.session.add(n)
    db.session.commit()
    socketio.emit('notification', {'title': title, 'message': message, 'type': ntype}, room=f'user_{user_id}')

def update_streak(user):
    today = date.today()
    existing = StreakEntry.query.filter_by(user_id=user.id, date=today).first()
    if not existing:
        db.session.add(StreakEntry(user_id=user.id, date=today))
        yesterday = today - timedelta(days=1)
        had_yesterday = StreakEntry.query.filter_by(user_id=user.id, date=yesterday).first()
        user.streak_count = (user.streak_count + 1) if had_yesterday else 1
        user.last_activity_date = today
        db.session.commit()

def check_badges(user):
    all_badges = Badge.query.all()
    earned_ids = {ub.badge_id for ub in UserBadge.query.filter_by(user_id=user.id).all()}
    for badge in all_badges:
        if badge.id in earned_ids:
            continue
        earned = False
        if badge.requirement_type == 'points' and user.points >= badge.requirement_value:
            earned = True
        elif badge.requirement_type == 'tasks':
            done = Submission.query.filter_by(ambassador_id=user.id, status='approved').count()
            if done >= badge.requirement_value:
                earned = True
        elif badge.requirement_type == 'streak' and user.streak_count >= badge.requirement_value:
            earned = True
        if earned:
            db.session.add(UserBadge(user_id=user.id, badge_id=badge.id))
            send_notification(user.id, 'Badge Earned!', f'You earned the {badge.icon} {badge.name} badge!', 'badge')
    db.session.commit()

def ai_score_submission(proof_text, task_title):
    """Simulated Advanced AI scoring engine"""
    score = random.randint(55, 98)
    length_bonus = min(len(proof_text) // 50, 15)
    has_link = 1 if ('http' in proof_text or 'www.' in proof_text) else 0
    score = min(score + length_bonus + (has_link * 5), 100)
    
    grammar = random.randint(70, 100)
    brand_alignment = random.randint(60, 100)
    creativity = random.randint(65, 100)

    feedbacks = [
        f"Great work on the {task_title}! Your submission shows genuine effort and creativity.",
        f"Solid submission! The detail in your proof demonstrates real commitment to the task.",
        f"Well done! Your {task_title} contribution is impressive and will make a real impact.",
        f"Excellent execution! You've gone above and beyond with this {task_title} submission.",
        f"Nice job! Your submission for {task_title} meets all the key requirements effectively.",
    ]
    summary = random.choice(feedbacks)
    detailed_feedback = json.dumps({
        "grammar": grammar,
        "brand_alignment": brand_alignment,
        "creativity": creativity,
        "summary": summary
    })
    return score, detailed_feedback

# ─── Auth Routes ───
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('org_dashboard' if current_user.role == 'org' else 'amb_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            update_streak(user)
            flash('Welcome back!', 'success')
            return redirect(url_for('index'))
        flash('Invalid email or password.', 'error')
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'amb')
        college = request.form.get('college', '').strip()
        org_name = request.form.get('org_name', '').strip()

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('auth/register.html')
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return render_template('auth/register.html')
            
        referral_input = request.form.get('referral_code', '').strip().upper()

        colors = ['#9FE1CB','#AFA9EC','#F5C4B3','#B5D4F4','#C0DD97','#FAC775','#F4C0D1','#D3D1C7']
        tcolors = ['#085041','#26215C','#4A1B0C','#042C53','#173404','#412402','#4B1528','#2C2C2A']
        ci = random.randint(0, len(colors)-1)

        base_code = username[:4].upper()
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        my_ref_code = f"{base_code}-{suffix}"

        user = User(full_name=full_name, username=username, email=email, role=role,
                     college=college, org_name=org_name, avatar_color=colors[ci],
                     avatar_text_color=tcolors[ci], referral_code=my_ref_code)
        user.set_password(password)

        db.session.add(user)
        db.session.flush() # flush to get user.id before commit
        
        if referral_input:
            referrer = User.query.filter_by(referral_code=referral_input).first()
            if referrer:
                user.referred_by_id = referrer.id
                user.points += 500
                referrer.points += 500
                user.level = user.calculate_level()
                referrer.level = referrer.calculate_level()
                log_activity(referrer.id, 'referral_success', f'Referred {username}')
                send_notification(referrer.id, 'Referral Success!', f'{username} joined using your code! +500 pts', 'success')

        db.session.commit()
        login_user(user, remember=True)
        log_activity(user.id, 'registered', f'{role} account created')
        send_notification(user.id, 'Welcome!', 'Welcome to CampusConnect! Start exploring.', 'success')
        flash('Account created successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('auth/register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

# ─── Organization Routes ───
@app.route('/org/dashboard')
@login_required
@role_required('org')
def org_dashboard():
    tasks = Task.query.filter_by(created_by=current_user.id).order_by(Task.created_at.desc()).all()
    pending = Submission.query.join(Task).filter(Task.created_by == current_user.id, Submission.status == 'pending').order_by(Submission.created_at.desc()).all()
    ambassadors = User.query.filter_by(role='amb').order_by(User.points.desc()).all()
    events = Event.query.filter_by(created_by=current_user.id).order_by(Event.start_date.desc()).all()
    total_submissions = Submission.query.join(Task).filter(Task.created_by == current_user.id).count()
    approved_submissions = Submission.query.join(Task).filter(Task.created_by == current_user.id, Submission.status == 'approved').count()
    recent_logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(20).all()

    # Chart data
    cats = db.session.query(Task.category, db.func.count(Task.id)).filter_by(created_by=current_user.id).group_by(Task.category).all()
    chart_categories = {c[0]: c[1] for c in cats}
    weekly = []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        count = Submission.query.join(Task).filter(Task.created_by == current_user.id, db.func.date(Submission.created_at) == d).count()
        weekly.append({'date': d.strftime('%a'), 'count': count})

    return render_template('org/dashboard.html', tasks=tasks, pending=pending,
                           ambassadors=ambassadors, events=events,
                           total_submissions=total_submissions,
                           approved_submissions=approved_submissions,
                           chart_categories=json.dumps(chart_categories),
                           weekly_data=json.dumps(weekly),
                           recent_logs=recent_logs)

@app.route('/org/task/create', methods=['POST'])
@login_required
@role_required('org')
def create_task():
    task = Task(
        title=request.form['title'],
        description=request.form['description'],
        points=int(request.form.get('points', 100)),
        category=request.form.get('category', 'General'),
        difficulty=request.form.get('difficulty', 'Medium'),
        priority=request.form.get('priority', 'normal'),
        requirements=request.form.get('requirements', ''),
        created_by=current_user.id
    )
    deadline = request.form.get('deadline')
    if deadline:
        task.deadline = datetime.fromisoformat(deadline)
    db.session.add(task)
    db.session.commit()
    log_activity(current_user.id, 'task_created', task.title)
    # Notify all ambassadors
    for amb in User.query.filter_by(role='amb').all():
        send_notification(amb.id, 'New Task!', f'"{task.title}" is now available for +{task.points} pts', 'task')
    flash('Task created!', 'success')
    return redirect(url_for('org_dashboard'))

@app.route('/org/submission/<int:sid>/review', methods=['POST'])
@login_required
@role_required('org')
def review_submission(sid):
    sub = Submission.query.get_or_404(sid)
    action = request.form.get('action')
    if action == 'approve':
        sub.status = 'approved'
        sub.points_awarded = sub.task.points
        sub.reviewed_at = datetime.now(timezone.utc)
        sub.reviewer_notes = request.form.get('notes', '')
        amb = sub.ambassador
        amb.points += sub.points_awarded
        amb.level = amb.calculate_level()
        db.session.commit()
        check_badges(amb)
        send_notification(amb.id, 'Submission Approved!', f'Your "{sub.task.title}" was approved! +{sub.points_awarded} pts', 'success')
        log_activity(amb.id, 'submission_approved', sub.task.title, sub.points_awarded)
    elif action == 'reject':
        sub.status = 'rejected'
        sub.reviewed_at = datetime.now(timezone.utc)
        sub.reviewer_notes = request.form.get('notes', '')
        db.session.commit()
        send_notification(sub.ambassador_id, 'Submission Rejected', f'Your "{sub.task.title}" needs improvement.', 'warning')
    flash(f'Submission {action}ed.', 'success')
    return redirect(url_for('org_dashboard'))

@app.route('/org/event/create', methods=['POST'])
@login_required
@role_required('org')
def create_event():
    event = Event(
        title=request.form['title'],
        description=request.form['description'],
        event_type=request.form.get('event_type', 'workshop'),
        location=request.form.get('location', ''),
        is_virtual='is_virtual' in request.form,
        meeting_link=request.form.get('meeting_link', ''),
        start_date=datetime.fromisoformat(request.form['start_date']),
        points_reward=int(request.form.get('points_reward', 50)),
        created_by=current_user.id
    )
    if request.form.get('end_date'):
        event.end_date = datetime.fromisoformat(request.form['end_date'])
    db.session.add(event)
    db.session.commit()
    for amb in User.query.filter_by(role='amb').all():
        send_notification(amb.id, 'New Event!', f'"{event.title}" — Register now!', 'info')
    flash('Event created!', 'success')
    return redirect(url_for('org_dashboard'))

@app.route('/org/message/broadcast', methods=['POST'])
@login_required
@role_required('org')
def broadcast_message():
    subject = request.form.get('subject', '')
    body = request.form.get('body', '')
    for amb in User.query.filter_by(role='amb').all():
        msg = Message(sender_id=current_user.id, recipient_id=amb.id, subject=subject, body=body, is_broadcast=True)
        db.session.add(msg)
        send_notification(amb.id, 'New Message', f'From {current_user.org_name or current_user.full_name}: {subject}', 'info')
    db.session.commit()
    flash('Broadcast sent!', 'success')
    return redirect(url_for('org_dashboard'))

# ─── Ambassador Routes ───
@app.route('/amb/dashboard')
@login_required
@role_required('amb')
def amb_dashboard():
    tasks = Task.query.filter_by(is_active=True).order_by(Task.created_at.desc()).all()
    my_submissions = Submission.query.filter_by(ambassador_id=current_user.id).order_by(Submission.created_at.desc()).all()
    submitted_task_ids = {s.task_id for s in my_submissions}
    leaderboard = User.query.filter_by(role='amb').order_by(User.points.desc()).limit(20).all()
    all_badges = Badge.query.all()
    earned_ids = {ub.badge_id for ub in UserBadge.query.filter_by(user_id=current_user.id).all()}
    events = Event.query.filter_by(is_active=True).order_by(Event.start_date).all()
    my_event_ids = {ea.event_id for ea in EventAttendee.query.filter_by(user_id=current_user.id).all()}
    messages = Message.query.filter_by(recipient_id=current_user.id).order_by(Message.created_at.desc()).limit(20).all()
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(15).all()
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    # Streak data
    streak_days = []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        active = StreakEntry.query.filter_by(user_id=current_user.id, date=d).first() is not None
        streak_days.append({'day': d.strftime('%a')[0], 'active': active, 'date': d.isoformat()})
    # Rank
    rank = 1
    for u in User.query.filter_by(role='amb').order_by(User.points.desc()).all():
        if u.id == current_user.id:
            break
        rank += 1

    return render_template('amb/dashboard.html', tasks=tasks, my_submissions=my_submissions,
                           submitted_task_ids=submitted_task_ids, leaderboard=leaderboard,
                           all_badges=all_badges, earned_ids=earned_ids, events=events,
                           my_event_ids=my_event_ids, messages=messages,
                           notifications=notifications, unread_count=unread_count,
                           streak_days=streak_days, rank=rank)

@app.route('/amb/submit/<int:task_id>', methods=['POST'])
@login_required
@role_required('amb')
def submit_task(task_id):
    task = Task.query.get_or_404(task_id)
    existing = Submission.query.filter_by(task_id=task_id, ambassador_id=current_user.id).first()
    if existing and existing.status != 'rejected':
        flash('Already submitted.', 'warning')
        return redirect(url_for('amb_dashboard'))

    proof_text = request.form.get('proof_text', '')
    proof_link = request.form.get('proof_link', '')
    score, feedback = ai_score_submission(proof_text, task.title)

    sub = Submission(task_id=task_id, ambassador_id=current_user.id,
                     proof_text=proof_text, proof_link=proof_link,
                     ai_score=score, ai_feedback=feedback)
    db.session.add(sub)
    update_streak(current_user)
    db.session.commit()
    log_activity(current_user.id, 'task_submitted', task.title)
    send_notification(task.created_by, 'New Submission', f'{current_user.full_name} submitted "{task.title}" (AI: {score}/100)', 'task')
    flash(f'Submitted! AI Score: {score}/100 — {feedback}', 'success')
    return redirect(url_for('amb_dashboard'))

@app.route('/amb/event/<int:eid>/register', methods=['POST'])
@login_required
@role_required('amb')
def register_event(eid):
    event = Event.query.get_or_404(eid)
    existing = EventAttendee.query.filter_by(event_id=eid, user_id=current_user.id).first()
    if not existing:
        db.session.add(EventAttendee(event_id=eid, user_id=current_user.id))
        db.session.commit()
        flash(f'Registered for {event.title}!', 'success')
    return redirect(url_for('amb_dashboard'))

# ─── API Endpoints ───
@app.route('/api/notifications/read', methods=['POST'])
@login_required
def mark_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/ai-score', methods=['POST'])
@login_required
def api_ai_score():
    data = request.get_json()
    score, feedback = ai_score_submission(data.get('proof', ''), data.get('task', ''))
    return jsonify({'score': score, 'feedback': feedback})

@app.route('/api/stats')
@login_required
def api_stats():
    if current_user.role == 'org':
        return jsonify({
            'ambassadors': User.query.filter_by(role='amb').count(),
            'tasks': Task.query.filter_by(created_by=current_user.id, is_active=True).count(),
            'submissions': Submission.query.join(Task).filter(Task.created_by == current_user.id).count(),
            'pending': Submission.query.join(Task).filter(Task.created_by == current_user.id, Submission.status == 'pending').count(),
        })
    return jsonify({'points': current_user.points, 'level': current_user.level, 'streak': current_user.streak_count})

@app.route('/api/leaderboard')
@login_required
def api_leaderboard():
    users = User.query.filter_by(role='amb').order_by(User.points.desc()).limit(50).all()
    return jsonify([u.to_dict() for u in users])

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name', current_user.full_name)
        current_user.college = request.form.get('college', current_user.college)
        current_user.bio = request.form.get('bio', current_user.bio)
        current_user.phone = request.form.get('phone', current_user.phone)
        current_user.theme = request.form.get('theme', current_user.theme)
        if current_user.role == 'org':
            current_user.org_name = request.form.get('org_name', current_user.org_name)
            current_user.org_description = request.form.get('org_description', current_user.org_description)
            current_user.org_website = request.form.get('org_website', current_user.org_website)
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html')

# ─── SocketIO ───
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room(f'user_{current_user.id}')

# ─── Seed Data ───
def seed_db():
    if User.query.first():
        return
    # Badges
    badges_data = [
        ('Rocket Start', 'Complete your first task', '🚀', 'tasks', 1, 'common'),
        ('On Fire', '5-day streak', '🔥', 'streak', 5, 'common'),
        ('Task Master', 'Complete 10 tasks', '🎯', 'tasks', 10, 'rare'),
        ('Star Performer', 'Earn 500 points', '⭐', 'points', 500, 'common'),
        ('Content King', 'Complete 20 tasks', '✍️', 'tasks', 20, 'epic'),
        ('Social Buzz', 'Earn 1000 points', '📱', 'points', 1000, 'rare'),
        ('Top Ambassador', 'Earn 2000 points', '🏅', 'points', 2000, 'epic'),
        ('Diamond Elite', 'Earn 5000 points', '💎', 'points', 5000, 'legendary'),
        ('Streak Legend', '30-day streak', '⚡', 'streak', 30, 'legendary'),
        ('Rising Star', 'Earn 200 points', '🌟', 'points', 200, 'common'),
    ]
    for name, desc, icon, rtype, rval, rarity in badges_data:
        db.session.add(Badge(name=name, description=desc, icon=icon, requirement_type=rtype, requirement_value=rval, rarity=rarity))

    # Demo org
    org = User(full_name='TechCorp Admin', username='techcorp', email='org@demo.com', role='org',
               org_name='TechCorp', org_description='Leading tech education platform',
               avatar_color='#9FE1CB', avatar_text_color='#085041')
    org.set_password('demo123')
    db.session.add(org)
    db.session.flush()

    # Demo ambassadors
    amb_data = [
        ('Arjun Mehta', 'arjun', 'arjun@demo.com', 'IIT Delhi', 2100, '#9FE1CB', '#085041'),
        ('Sneha Patel', 'sneha', 'sneha@demo.com', 'NIT Surat', 1850, '#AFA9EC', '#26215C'),
        ('Priya Sharma', 'priya', 'priya@demo.com', 'BITS Pilani', 1240, '#F5C4B3', '#4A1B0C'),
        ('Rahul Verma', 'rahul', 'rahul@demo.com', 'VIT Vellore', 980, '#B5D4F4', '#042C53'),
        ('Ananya Roy', 'ananya', 'ananya@demo.com', 'Jadavpur Univ', 760, '#C0DD97', '#173404'),
        ('Dev Singh', 'dev', 'dev@demo.com', 'DTU Delhi', 640, '#FAC775', '#412402'),
    ]
    for fname, uname, email, college, pts, ac, atc in amb_data:
        u = User(full_name=fname, username=uname, email=email, role='amb', college=college,
                 points=pts, avatar_color=ac, avatar_text_color=atc)
        u.set_password('demo123')
        u.level = u.calculate_level()
        db.session.add(u)
    db.session.flush()

    # Demo tasks
    tasks_data = [
        ('Instagram Story Post', 'Post a story mentioning our brand with the official hashtag #CampusConnect. Screenshot required as proof.', 150, 'Social Media', 'Easy'),
        ('Refer 3 Students', 'Refer 3 students from your college. Share their email addresses as proof.', 200, 'Referral', 'Medium'),
        ('LinkedIn Article', 'Write a 300+ word article about our platform on LinkedIn.', 100, 'Content Creation', 'Medium'),
        ('Campus Event Promotion', 'Promote our upcoming webinar on your campus. Distribute at least 20 flyers.', 250, 'Event Promotion', 'Hard'),
        ('Twitter Thread', 'Create a 5+ tweet thread about campus ambassador programs.', 120, 'Social Media', 'Medium'),
        ('YouTube Short', 'Create a 60-second video about CampusConnect and post on YouTube Shorts.', 300, 'Content Creation', 'Hard'),
    ]
    for title, desc, pts, cat, diff in tasks_data:
        db.session.add(Task(title=title, description=desc, points=pts, category=cat, difficulty=diff, created_by=org.id))
    db.session.flush()

    # Demo submissions
    tasks = Task.query.all()
    ambs = User.query.filter_by(role='amb').all()
    for i, amb in enumerate(ambs[:3]):
        for j, task in enumerate(tasks[:2]):
            status = 'approved' if j == 0 else 'pending'
            sub = Submission(task_id=task.id, ambassador_id=amb.id,
                             proof_text=f'Completed {task.title}. Here is my proof with screenshots and links.',
                             proof_link='https://example.com/proof', status=status,
                             ai_score=random.randint(70, 95), ai_feedback='Great submission!',
                             points_awarded=task.points if status == 'approved' else 0)
            db.session.add(sub)

    db.session.commit()
    print("✅ Database seeded with demo data!")

# ─── Init ───
with app.app_context():
    # In production, use 'flask db upgrade' instead of create_all()
    if os.environ.get('FLASK_ENV') != 'production':
        db.create_all()
        seed_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    socketio.run(app, host='0.0.0.0', port=port, debug=debug_mode)
