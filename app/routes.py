from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models import User, Room, Task, TaskSolve, TaskAttempt, RoomProgress, Badge, UserBadge
import os, requests as req_lib

main = Blueprint('main', __name__)

def get_solved_task_ids(user_id):
    rows = TaskSolve.query.filter_by(user_id=user_id).all()
    return {s.task_id for s in rows}

def check_and_award_badges(user):
    all_badges  = Badge.query.all()
    earned_ids  = {ub.badge_id for ub in UserBadge.query.filter_by(user_id=user.id).all()}
    solve_count = TaskSolve.query.filter_by(user_id=user.id).count()
    rooms_done  = RoomProgress.query.filter_by(user_id=user.id, completed=True).count()
    new_names   = []
    for b in all_badges:
        if b.id in earned_ids:
            continue
        earned = False
        if b.requirement_type == 'solves' and solve_count >= b.requirement_value:
            earned = True
        if b.requirement_type == 'points' and user.points >= b.requirement_value:
            earned = True
        if b.requirement_type == 'rooms'  and rooms_done  >= b.requirement_value:
            earned = True
        if earned:
            db.session.add(UserBadge(user_id=user.id, badge_id=b.id))
            new_names.append(f"{b.icon} {b.name}")
    db.session.commit()
    return new_names

def generate_hint(task):
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return task.hint or "Re-read the task content carefully!"
    try:
        r = req_lib.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 120,
                'messages': [{'role': 'user', 'content':
                    f"Cybersecurity task: {task.title}\nQuestion: {task.question}\n"
                    f"Give ONE short encouraging hint (2 sentences max). No direct answer."}]
            }
        )
        return r.json()['content'][0]['text']
    except:
        return task.hint or "Think carefully — the answer is in the reading!"

@main.route('/')
def home():
    rooms = Room.query.order_by(Room.order_index).all()
    return render_template('home.html', rooms=rooms)

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html')
        pw = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, password=pw)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please login.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('main.dashboard'))
        flash('Wrong email or password.', 'danger')
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.home'))

@main.route('/dashboard')
@login_required
def dashboard():
    rooms       = Room.query.order_by(Room.order_index).all()
    solved_ids  = get_solved_task_ids(current_user.id)
    progress    = {rp.room_id: rp for rp in RoomProgress.query.filter_by(user_id=current_user.id).all()}
    user_badges = UserBadge.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', rooms=rooms, solved_ids=solved_ids,
                           progress=progress, user=current_user, user_badges=user_badges)

@main.route('/room/<int:room_id>')
@login_required
def room(room_id):
    r          = Room.query.get_or_404(room_id)
    tasks      = Task.query.filter_by(room_id=room_id).order_by(Task.order_index).all()
    solved_ids = get_solved_task_ids(current_user.id)
    rp         = RoomProgress.query.filter_by(user_id=current_user.id, room_id=room_id).first()
    return render_template('room.html', room=r, tasks=tasks, solved_ids=solved_ids, progress=rp)

@main.route('/room/<int:room_id>/task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def task(room_id, task_id):
    r          = Room.query.get_or_404(room_id)
    t          = Task.query.get_or_404(task_id)
    tasks      = Task.query.filter_by(room_id=room_id).order_by(Task.order_index).all()
    solved_ids = get_solved_task_ids(current_user.id)
    already    = task_id in solved_ids
    attempts   = TaskAttempt.query.filter_by(
                     user_id=current_user.id, task_id=task_id
                 ).order_by(TaskAttempt.attempted_at.desc()).all()

    if request.method == 'POST':
        submitted = request.form.get('flag', '').strip()

        if already:
            flash('You already solved this!', 'info')

        elif submitted.lower() == t.flag.lower():
            db.session.add(TaskAttempt(
                user_id=current_user.id, task_id=task_id,
                submitted=submitted, is_correct=True
            ))
            db.session.add(TaskSolve(
                user_id=current_user.id, task_id=task_id,
                room_id=room_id, points_earned=t.points
            ))
            current_user.points += t.points

            rp = RoomProgress.query.filter_by(
                user_id=current_user.id, room_id=room_id
            ).first()
            if not rp:
                rp = RoomProgress(
                    user_id=current_user.id,
                    room_id=room_id,
                    total_tasks=len(tasks)
                )
                db.session.add(rp)

            db.session.commit()

            solved_count       = TaskSolve.query.filter_by(
                                     user_id=current_user.id, room_id=room_id
                                 ).count()
            rp.tasks_completed = solved_count
            rp.total_tasks     = len(tasks)

            if solved_count >= len(tasks):
                rp.completed = True
                from datetime import datetime
                rp.completed_at = datetime.utcnow()
                flash(f'🎉 Room "{r.title}" completed!', 'success')

            db.session.commit()

            new_badges = check_and_award_badges(current_user)
            for b in new_badges:
                flash(f'🏅 Badge unlocked: {b}!', 'warning')
            flash(f'✅ Correct! +{t.points} points', 'success')

            next_t = next((x for x in tasks if x.order_index > t.order_index), None)
            if next_t:
                return redirect(url_for('main.task', room_id=room_id, task_id=next_t.id))
            return redirect(url_for('main.room', room_id=room_id))

        else:
            db.session.add(TaskAttempt(
                user_id=current_user.id, task_id=task_id,
                submitted=submitted, is_correct=False
            ))
            db.session.commit()
            flash('❌ Wrong answer. Try again!', 'danger')

    task_list = list(tasks)
    idx       = next((i for i, x in enumerate(task_list) if x.id == task_id), 0)
    prev_task = task_list[idx - 1] if idx > 0 else None
    next_task = task_list[idx + 1] if idx < len(task_list) - 1 else None

    return render_template('task.html', room=r, task=t, tasks=tasks,
                           solved_ids=solved_ids, already_solved=already,
                           attempts=attempts, prev_task=prev_task, next_task=next_task)

@main.route('/hint/<int:task_id>')
@login_required
def hint(task_id):
    t = Task.query.get_or_404(task_id)
    return jsonify({'hint': generate_hint(t)})

@main.route('/leaderboard')
def leaderboard():
    users      = User.query.order_by(User.points.desc()).limit(20).all()
    rooms_done = {
        u.id: RoomProgress.query.filter_by(user_id=u.id, completed=True).count()
        for u in users
    }
    return render_template('leaderboard.html', users=users, rooms_done=rooms_done)

@main.route('/profile')
@login_required
def profile():
    solves      = TaskSolve.query.filter_by(user_id=current_user.id)\
                      .order_by(TaskSolve.solved_at.desc()).all()
    attempts    = TaskAttempt.query.filter_by(user_id=current_user.id).count()
    correct     = TaskAttempt.query.filter_by(user_id=current_user.id, is_correct=True).count()
    user_badges = UserBadge.query.filter_by(user_id=current_user.id).all()
    rooms_done  = RoomProgress.query.filter_by(user_id=current_user.id, completed=True).all()
    return render_template('profile.html', user=current_user, solves=solves,
                           attempts=attempts, correct=correct,
                           user_badges=user_badges, rooms_done=rooms_done)