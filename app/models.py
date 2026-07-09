from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ─── USER ───────────────────────────────────────────
class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(50),  unique=True, nullable=False)
    email         = db.Column(db.String(100), unique=True, nullable=False)
    password      = db.Column(db.String(200), nullable=False)
    points        = db.Column(db.Integer, default=0)
    is_admin      = db.Column(db.Boolean, default=False)
    joined_at     = db.Column(db.DateTime, default=datetime.utcnow)

    solves        = db.relationship('TaskSolve',  backref='user', lazy=True)
    attempts      = db.relationship('TaskAttempt',backref='user', lazy=True)
    user_badges   = db.relationship('UserBadge',  backref='user', lazy=True)
    room_progress = db.relationship('RoomProgress',backref='user',lazy=True)

    def is_authenticated(self): return True
    def is_active(self):        return True
    def is_anonymous(self):     return False
    def get_id(self):           return str(self.id)

# ─── ROOM (module) ──────────────────────────────────
class Room(db.Model):
    __tablename__ = 'rooms'
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text,        nullable=False)
    category    = db.Column(db.String(50),  default='General')
    difficulty  = db.Column(db.String(20),  default='Beginner')
    icon        = db.Column(db.String(10),  default='🔐')
    order_index = db.Column(db.Integer,     default=0)

    tasks       = db.relationship('Task', backref='room', lazy=True,
                                  order_by='Task.order_index')
    progress    = db.relationship('RoomProgress', backref='room', lazy=True)

# ─── TASK (question inside a room) ──────────────────
class Task(db.Model):
    __tablename__ = 'tasks'
    id           = db.Column(db.Integer, primary_key=True)
    room_id      = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    order_index  = db.Column(db.Integer, default=0)
    title        = db.Column(db.String(150), nullable=False)
    content      = db.Column(db.Text,        nullable=False)   # theory/explanation
    question     = db.Column(db.String(300), nullable=False)
    flag         = db.Column(db.String(150), nullable=False)
    hint         = db.Column(db.Text,        nullable=True)
    points       = db.Column(db.Integer,     default=10)
    task_type    = db.Column(db.String(30),  default='flag')   # flag / text / multiple

    solves       = db.relationship('TaskSolve',   backref='task', lazy=True)
    attempts     = db.relationship('TaskAttempt', backref='task', lazy=True)

# ─── TASK SOLVE (correct answer record) ─────────────
class TaskSolve(db.Model):
    __tablename__ = 'task_solves'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'),    nullable=False)
    task_id      = db.Column(db.Integer, db.ForeignKey('tasks.id'),    nullable=False)
    room_id      = db.Column(db.Integer, db.ForeignKey('rooms.id'),    nullable=False)
    solved_at    = db.Column(db.DateTime, default=datetime.utcnow)
    points_earned= db.Column(db.Integer, default=0)

# ─── TASK ATTEMPT (every try, right or wrong) ───────
class TaskAttempt(db.Model):
    __tablename__ = 'task_attempts'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'),    nullable=False)
    task_id      = db.Column(db.Integer, db.ForeignKey('tasks.id'),    nullable=False)
    submitted    = db.Column(db.String(200), nullable=False)
    is_correct   = db.Column(db.Boolean, default=False)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)

# ─── ROOM PROGRESS (tracks % completion per user) ───
class RoomProgress(db.Model):
    __tablename__ = 'room_progress'
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'),  nullable=False)
    room_id         = db.Column(db.Integer, db.ForeignKey('rooms.id'),  nullable=False)
    tasks_completed = db.Column(db.Integer, default=0)
    total_tasks     = db.Column(db.Integer, default=0)
    completed       = db.Column(db.Boolean, default=False)
    started_at      = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at    = db.Column(db.DateTime, nullable=True)

# ─── BADGE ──────────────────────────────────────────
class Badge(db.Model):
    __tablename__ = 'badges'
    id                = db.Column(db.Integer, primary_key=True)
    name              = db.Column(db.String(50),  nullable=False)
    description       = db.Column(db.String(200))
    icon              = db.Column(db.String(10),  default='🏅')
    requirement_type  = db.Column(db.String(30))   # solves / points / rooms
    requirement_value = db.Column(db.Integer)
    user_badges       = db.relationship('UserBadge', backref='badge', lazy=True)

# ─── USER BADGE ─────────────────────────────────────
class UserBadge(db.Model):
    __tablename__ = 'user_badges'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'),   nullable=False)
    badge_id   = db.Column(db.Integer, db.ForeignKey('badges.id'),  nullable=False)
    earned_at  = db.Column(db.DateTime, default=datetime.utcnow)