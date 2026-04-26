from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'org' or 'amb'
    full_name = db.Column(db.String(120), nullable=False)
    college = db.Column(db.String(200), default='')
    phone = db.Column(db.String(20), default='')
    bio = db.Column(db.Text, default='')
    avatar_color = db.Column(db.String(20), default='#9FE1CB')
    avatar_text_color = db.Column(db.String(20), default='#085041')
    points = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    referral_code = db.Column(db.String(20), unique=True, index=True, nullable=True)
    referred_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    streak_count = db.Column(db.Integer, default=0)
    last_activity_date = db.Column(db.Date, nullable=True)
    org_name = db.Column(db.String(200), default='')
    org_description = db.Column(db.Text, default='')
    org_website = db.Column(db.String(300), default='')
    is_active = db.Column(db.Boolean, default=True)
    theme = db.Column(db.String(10), default='dark')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tasks_created = db.relationship('Task', backref='creator', lazy='dynamic', foreign_keys='Task.created_by')
    submissions = db.relationship('Submission', backref='ambassador', lazy='dynamic', foreign_keys='Submission.ambassador_id')
    badges = db.relationship('UserBadge', backref='user', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    messages_sent = db.relationship('Message', backref='sender', lazy='dynamic', foreign_keys='Message.sender_id')
    messages_received = db.relationship('Message', backref='recipient', lazy='dynamic', foreign_keys='Message.recipient_id')
    events_created = db.relationship('Event', backref='creator', lazy='dynamic')
    events_created = db.relationship('Event', backref='creator', lazy='dynamic')
    streak_entries = db.relationship('StreakEntry', backref='user', lazy='dynamic')
    referrals = db.relationship('User', backref=db.backref('referrer', remote_side=[id]), lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_initials(self):
        parts = self.full_name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.full_name[:2].upper()

    def calculate_level(self):
        thresholds = [0, 500, 1200, 2500, 5000, 10000, 20000, 50000]
        for i in range(len(thresholds) - 1, -1, -1):
            if self.points >= thresholds[i]:
                return i + 1
        return 1

    def get_tier(self):
        level = self.level
        if level >= 50: return {"name": "Diamond", "color": "#06b6d4"}
        if level >= 30: return {"name": "Platinum", "color": "#a855f7"}
        if level >= 15: return {"name": "Gold", "color": "#eab308"}
        if level >= 5: return {"name": "Silver", "color": "#94a3b8"}
        return {"name": "Bronze", "color": "#d97706"}

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'college': self.college,
            'points': self.points,
            'level': self.level,
            'streak_count': self.streak_count,
            'avatar_color': self.avatar_color,
            'initials': self.get_initials(),
            'org_name': self.org_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    points = db.Column(db.Integer, nullable=False, default=100)
    category = db.Column(db.String(50), nullable=False, default='General')
    difficulty = db.Column(db.String(20), default='Medium')  # Easy, Medium, Hard
    deadline = db.Column(db.DateTime, nullable=True)
    max_submissions = db.Column(db.Integer, default=0)  # 0 = unlimited
    is_active = db.Column(db.Boolean, default=True)
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence = db.Column(db.String(20), default='')  # daily, weekly, monthly
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    requirements = db.Column(db.Text, default='')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    submissions = db.relationship('Submission', backref='task', lazy='dynamic')

    def submission_count(self):
        return self.submissions.count()

    def approved_count(self):
        return self.submissions.filter_by(status='approved').count()

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'points': self.points,
            'category': self.category,
            'difficulty': self.difficulty,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'is_active': self.is_active,
            'priority': self.priority,
            'requirements': self.requirements,
            'submission_count': self.submission_count(),
            'approved_count': self.approved_count(),
            'creator': self.creator.org_name or self.creator.full_name if self.creator else 'Unknown',
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Submission(db.Model):
    __tablename__ = 'submissions'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    ambassador_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    proof_text = db.Column(db.Text, nullable=False)
    proof_link = db.Column(db.String(500), default='')
    proof_file = db.Column(db.String(300), default='')
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, revision
    ai_score = db.Column(db.Integer, nullable=True)
    ai_feedback = db.Column(db.Text, default='')
    reviewer_notes = db.Column(db.Text, default='')
    points_awarded = db.Column(db.Integer, default=0)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'task_title': self.task.title if self.task else 'Unknown',
            'ambassador_name': self.ambassador.full_name if self.ambassador else 'Unknown',
            'ambassador_id': self.ambassador_id,
            'proof_text': self.proof_text,
            'proof_link': self.proof_link,
            'status': self.status,
            'ai_score': self.ai_score,
            'ai_feedback': self.ai_feedback,
            'points_awarded': self.points_awarded,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Badge(db.Model):
    __tablename__ = 'badges'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(10), nullable=False)
    category = db.Column(db.String(50), default='achievement')
    requirement_type = db.Column(db.String(50), nullable=False)  # points, tasks, streak, referral, etc.
    requirement_value = db.Column(db.Integer, nullable=False)
    rarity = db.Column(db.String(20), default='common')  # common, rare, epic, legendary

    users = db.relationship('UserBadge', backref='badge', lazy='dynamic')


class UserBadge(db.Model):
    __tablename__ = 'user_badges'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('badges.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(30), default='info')  # info, success, warning, task, badge, points
    is_read = db.Column(db.Boolean, default=False)
    link = db.Column(db.String(300), default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(200), default='')
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    is_broadcast = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    event_type = db.Column(db.String(50), default='workshop')  # workshop, webinar, meetup, hackathon, contest
    location = db.Column(db.String(300), default='')
    is_virtual = db.Column(db.Boolean, default=False)
    meeting_link = db.Column(db.String(500), default='')
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=True)
    max_attendees = db.Column(db.Integer, default=0)
    points_reward = db.Column(db.Integer, default=50)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    attendees = db.relationship('EventAttendee', backref='event', lazy='dynamic')

    def attendee_count(self):
        return self.attendees.count()

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'event_type': self.event_type,
            'location': self.location,
            'is_virtual': self.is_virtual,
            'meeting_link': self.meeting_link,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'max_attendees': self.max_attendees,
            'points_reward': self.points_reward,
            'attendee_count': self.attendee_count(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class EventAttendee(db.Model):
    __tablename__ = 'event_attendees'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='registered')  # registered, attended, cancelled
    registered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class StreakEntry(db.Model):
    __tablename__ = 'streak_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    activity_count = db.Column(db.Integer, default=1)

    __table_args__ = (db.UniqueConstraint('user_id', 'date'),)


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, default='')
    points_change = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='activity_logs')
