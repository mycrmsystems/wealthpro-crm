# routes/tasks.py
"""
WealthPro CRM — Task Management (Drive-only)
- Overview page:
    * Due in next 30 days (open tasks)
    * Due later (>30 days OR no date) (open tasks)
- Complete action moves Drive file Ongoing -> Completed and prefixes name.
- Client tasks page shows that client’s open + completed tasks.
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template_string, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)
tasks_bp = Blueprint("tasks", __name__)


# ------------------------------
# Helpers
# ------------------------------
def _require_creds():
    if "credentials" not in session:
        return None
    return Credentials(**session["credentials"])


def _parse_due_date(due_str):
    """Try common formats; return date or None."""
    if not due_str:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(due_str.strip(), fmt).date()
        except Exception:
            continue
    return None


# ------------------------------
# Routes
# ------------------------------
@tasks_bp.route("/tasks")
def tasks():
    """
    Tasks overview (open tasks only):
      - Section 1: due within 30 days
      - Section 2: due later than 30 days OR no due date
    """
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)

        # For name rendering
        clients = drive.get_clients_enhanced()
        client_lookup = {c["client_id"]: c["display_name"] for c in clients}

        # Within 30 days from convenience method
        within_30 = drive.get_upcoming_tasks(30)

        # Build "later" by scanning ongoing tasks per client and excluding those already in within_30
        horizon = datetime.today().date() + timedelta(days=30)
        within_ids = {t["task_id"] for t in within_30}

        later = []
        for c in clients:
            all_client_tasks = drive.get_client_tasks(c["client_id"])
            for t in all_client_tasks:
                if (t.get("status") or "").lower() == "completed":
                    continue
                if t.get("task_id") in within_ids:
                    continue
                due = _parse_due_date(t.get("due_date"))
                if (due and due > horizon) or (not due):
                    later.append(t)

        # Sort for nice display
        def _sort_key(x):
            d = _parse_due_date(x.get("due_date"))
            return d or datetime(9999, 12, 31).date()

        within_30.sort(key=_sort_key)
        later.sort(key=_sort_key)

        return render_template_string(
            """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Tasks & Reminders</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: "Inter", sans-serif; }
        .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); }
    </style>
</head>
<body class="bg-gray-50">
    <nav class="gradient-wealth text-white shadow-lg">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex justify-between items-center h-16">
                <h1 class="text-xl font-bold">WealthPro CRM</h1>
                <div class="flex items-center space-x-6">
                    <a href="/" class="hover:text-blue-200">Dashboard</a>
                    <a href="/clients" class="hover:text-blue-200">Clients</a>
                    <a href="/tasks" class="text-white font-semibold">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Tasks & Reminders</h1>
            <p class="text-gray-600 mt-2">Open tasks remain visible until you mark them Completed.</p>
        </div>

        <!-- Section: Due in next 30 days -->
        <div class="bg-white rounded-lg shadow mb-8">
            <div class="p-6 border-b flex items-center justify-between">
                <h3 class="text-lg font-semibold">Due in next 30 days</h3>
                <span class="text-sm text-gray-600">Total: {{ within_30|length }}</span>
            </div>
            <div class="p-6">
                {% if within_30 %}
                    <div class="space-y-4">
                        {% for task in within_30 %}
                        <div class="border-l-4
                            {% if task.priority == 'High' %}border-red-500
                            {% elif task.priority == 'Medium' %}border-yellow-500
                            {% else %}border-green-500{% endif %}
                            pl-4 py-3 bg-gray-50 rounded-r">
                            <div class="flex justify-between items-start">
                                <div>
                                    <h4 class="font-semibold text-gray-900">{{ task.title }}</h4>
                                    <p class="text-sm text-gray-600">
                                        Client: {{ client_lookup.get(task.client_id, 'Unknown') }}
                                    </p>
                                    <p class="text-sm text-gray-500">
                                        Due: {{ task.due_date or 'No date' }} | Priority: {{ task.priority }} | Type: {{ task.task_type or '—' }}
                                    </p>
                                    {% if task.description %}
                                    <p class="text-sm text-gray-700 mt-1">{{ task.description }}</p>
                                    {% endif %}
                                </div>
                                <div class="flex space-x-2">
                                    <a href="/tasks/{{ task.task_id }}/complete"
                                       class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded hover:bg-green-200">Mark Complete</a>
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                {% else %}
                    <div class="text-center py-8 text-gray-500">No tasks due in the next 30 days.</div>
                {% endif %}
            </div>
        </div>

        <!-- Section: Due later (>30 days or no date) -->
        <div class="bg-white rounded-lg shadow">
            <div class="p-6 border-b flex items-center justify-between">
                <h3 class="text-lg font-semibold">Due later (>30 days or no date)</h3>
                <span class="text-sm text-gray-600">Total: {{ later|length }}</span>
            </div>
            <div class="p-6">
                {% if later %}
                    <div class="space-y-4">
                        {% for task in later %}
                        <div class="border-l-4 border-blue-500 pl-4 py-3 bg-gray-50 rounded-r">
                            <div class="flex justify-between items-start">
                                <div>
                                    <h4 class="font-semibold text-gray-900">{{ task.title }}</h4>
                                    <p class="text-sm text-gray-600">
                                        Client: {{ client_lookup.get(task.client_id, 'Unknown') }}
                                    </p>
                                    <p class="text-sm text-gray-500">
                                        Due: {{ task.due_date or 'No date set' }} | Priority: {{ task.priority }} | Type: {{ task.task_type or '—' }}
                                    </p>
                                    {% if task.description %}
                                    <p class="text-sm text-gray-700 mt-1">{{ task.description }}</p>
                                    {% endif %}
                                </div>
                                <div class="flex space-x-2">
                                    <a href="/tasks/{{ task.task_id }}/complete"
                                       class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded hover:bg-green-200">Mark Complete</a>
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                {% else %}
                    <div class="text-center py-8 text-gray-500">No tasks due later.</div>
                {% endif %}
            </div>
        </div>
    </main>
</body>
</html>
            """,
            within_30=within_30,
            later=later,
            client_lookup=client_lookup,
        )

    except Exception as e:
        logger.exception("Tasks overview error")
        return f"Error: {e}", 500


@tasks_bp.route("/tasks/<task_id>/complete")
def complete_task_route(task_id):
    """Mark a task complete (moves Drive file & renames)."""
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)
        ok = drive.complete_task(task_id)
        if not ok:
            return "Error completing task", 500
        return redirect(url_for("tasks.tasks"))
    except Exception as e:
        logger.exception("Complete task error")
        return f"Error: {e}", 500


@tasks_bp.route("/clients/<client_id>/tasks")
def client_tasks(client_id):
    """Task history for a specific client (open + completed)."""
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)
        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c["client_id"] == client_id), None)
        if not client:
            return "Client not found", 404

        client_tasks = drive.get_client_tasks(client_id)

        return render_template_string(
            """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Client Tasks</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: "Inter", sans-serif; }
        .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); }
    </style>
</head>
<body class="bg-gray-50">
    <nav class="gradient-wealth text-white shadow-lg">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex justify-between items-center h-16">
                <h1 class="text-xl font-bold">WealthPro CRM</h1>
                <div class="flex items-center space-x-6">
                    <a href="/" class="hover:text-blue-200">Dashboard</a>
                    <a href="/clients" class="hover:text-blue-200">Clients</a>
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-6xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Tasks: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Open tasks remain visible until completed.</p>
        </div>

        <div class="bg-white rounded-lg shadow">
            <div class="p-6 border-b">
                <h3 class="text-lg font-semibold">Task History</h3>
            </div>
            <div class="p-6">
                {% if client_tasks %}
                    <div class="space-y-4">
                        {% for task in client_tasks %}
                        <div class="border-l-4
                            {% if task.status == 'Completed' %}border-green-500
                            {% elif task.priority == 'High' %}border-red-500
                            {% elif task.priority == 'Medium' %}border-yellow-500
                            {% else %}border-blue-500{% endif %}
                            pl-4 py-3 bg-gray-50 rounded-r">
                            <div class="flex justify-between items-start">
                                <div class="flex-1">
                                    <h4 class="font-semibold text-gray-900 {% if task.status == 'Completed' %}line-through text-gray-600{% endif %}">
                                        {{ task.title }}
                                    </h4>
                                    <p class="text-sm text-gray-600">
                                        {{ task.task_type or '—' }} | Due: {{ task.due_date or 'No date' }} | Priority: {{ task.priority }}
                                    </p>
                                    {% if task.description %}
                                    <p class="text-sm text-gray-700 mt-1">{{ task.description }}</p>
                                    {% endif %}
                                    <p class="text-xs text-gray-500 mt-1">Created: {{ task.created_date }}</p>
                                    {% if task.completed_date %}
                                    <p class="text-xs text-gray-500">Completed: {{ task.completed_date }}</p>
                                    {% endif %}
                                </div>
                                <div class="flex space-x-2">
                                    <span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">{{ task.status }}</span>
                                    {% if task.status != 'Completed' %}
                                    <a href="/tasks/{{ task.task_id }}/complete"
                                       class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded hover:bg-green-200">Complete</a>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                {% else %}
                    <div class="text-center py-8">
                        <p class="text-gray-500 mb-4">No tasks found for this client.</p>
                        <a href="/clients/{{ client.client_id }}/add_task" class="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700">
                            Add First Task
                        </a>
                    </div>
                {% endif %}
            </div>
        </div>

        <div class="mt-8">
            <a href="/clients" class="bg-gray-600 text-white px-6 py-3 rounded-lg hover:bg-gray-700">
                Back to Clients
            </a>
        </div>
    </main>
</body>
</html>
            """,
            client=client,
            client_tasks=client_tasks,
        )

    except Exception as e:
        logger.exception("Client tasks error")
        return f"Error: {e}", 500
