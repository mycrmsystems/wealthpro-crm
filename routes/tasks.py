# routes/tasks.py
from datetime import date, timedelta
from flask import Blueprint, render_template, url_for, request

bp = Blueprint("tasks", __name__, url_prefix="/tasks")

def _sample_tasks(client_id=None):
    base = date.today()
    tasks = [
        {"id": 101, "title": "Prepare suitability report", "due": base + timedelta(days=3), "status": "ongoing"},
        {"id": 102, "title": "Chase provider forms", "due": base + timedelta(days=10), "status": "ongoing"},
        {"id": 103, "title": "Close review case", "due": base - timedelta(days=2), "status": "overdue"},
    ]
    if client_id:
        for t in tasks:
            t["client_id"] = client_id
    return tasks

@bp.route("/", methods=["GET"])
@bp.route("/client/<int:client_id>", methods=["GET"])
def list_tasks(client_id=None):
    # Shows the next 30 days (placeholder dataset)
    tasks = _sample_tasks(client_id)
    return render_template(
        "simple_page.html",
        title="Tasks",
        heading="Tasks (next 30 days)",
        description="Tasks list (placeholder). Styling matches your ‘communications’ layout request.",
        back_url=url_for("auth.dashboard") if not client_id else url_for("clients.client_details", client_id=client_id),
        extra={"tasks": tasks, "client_id": client_id},
    )

@bp.route("/new", methods=["GET", "POST"])
@bp.route("/client/<int:client_id>/new", methods=["GET", "POST"])
def new_task(client_id=None):
    # Simple form placeholder; hook to Drive + status folders later
    return render_template(
        "simple_page.html",
        title="New Task",
        heading="Create a new task",
        description="This is the ‘create task’ screen (placeholder).",
        back_url=url_for("tasks.list_tasks", client_id=client_id) if client_id else url_for("tasks.list_tasks"),
    )

# === Alias expected by app.py ===
tasks_bp = bp
