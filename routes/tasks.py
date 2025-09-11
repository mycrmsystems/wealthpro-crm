# routes/tasks.py
from datetime import datetime, timedelta
from flask import Blueprint, render_template

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")

# Dummy tasks
_TASKS = [
    {"id": 101, "client_id": 1, "client_name": "Alice Brown", "title": "ISA top-up", "due_date": (datetime.utcnow()+timedelta(days=3)).date().isoformat(), "status": "ongoing"},
    {"id": 102, "client_id": 2, "client_name": "Bob Smith", "title": "Pension review", "due_date": (datetime.utcnow()+timedelta(days=10)).date().isoformat(), "status": "ongoing"},
]

@tasks_bp.route("", methods=["GET"])
def list_tasks():
    return render_template("simple_page.html",
                           title="Tasks",
                           subtitle="Ongoing & completed (next 30 days remain visible until completed)",
                           items=[f'#{t["id"]} • {t["title"]} • {t["client_name"]} • due {t["due_date"]} • {t["status"]}' for t in _TASKS])

@tasks_bp.route("/new", methods=["GET"])
def new_task():
    return render_template("simple_page.html",
                           title="New Task",
                           subtitle="(Form matches Communications styling per your request)",
                           items=["(Task creation form here)"])

@tasks_bp.route("/<int:task_id>", methods=["GET"])
def open_task(task_id):
    t = next((x for x in _TASKS if x["id"] == task_id), None)
    return render_template("simple_page.html",
                           title=f"Task #{task_id}",
                           subtitle="Open task",
                           items=[str(t)] if t else ["Task not found"])

@tasks_bp.route("/<int:task_id>/complete", methods=["GET"])
def complete_task(task_id):
    t = next((x for x in _TASKS if x["id"] == task_id), None)
    if t: t["status"] = "completed"
    return render_template("simple_page.html",
                           title=f"Task #{task_id} completed",
                           subtitle="Marked as completed",
                           items=[str(t)] if t else ["Task not found"])

@tasks_bp.route("/<int:task_id>/delete", methods=["GET"])
def delete_task(task_id):
    return render_template("simple_page.html",
                           title=f"Task #{task_id} deleted",
                           subtitle="Removed from list",
                           items=["(Implement deletion in DB)"])
routes/tasks.py → must export tasks_bp
