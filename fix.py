from app import create_app, db
from app.models import RoomProgress, TaskSolve

app = create_app()

with app.app_context():
    all_progress = RoomProgress.query.all()
    for rp in all_progress:
        actual = TaskSolve.query.filter_by(
            user_id=rp.user_id, room_id=rp.room_id
        ).count()
        rp.tasks_completed = actual
        if actual >= rp.total_tasks and rp.total_tasks > 0:
            rp.completed = True
        print(f"Room {rp.room_id}: {actual}/{rp.total_tasks} completed={rp.completed}")
    db.session.commit()
    print("Done!")