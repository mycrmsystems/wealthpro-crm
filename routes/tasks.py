# routes/tasks.py
"""
WealthPro CRM — Tasks (Drive-only)

Shows:
  - Tasks due in the next 30 days (Pending only) via drive.get_upcoming_tasks(30)
  - Tasks due later (>30 days) or without a date (Pending only), built by scanning clients

Also provides:
  - /tasks/<task_id>/complete -> moves the Drive file to "Completed Tasks" and renames it
"""

import logging
from datetime import datetime, timedelta, date
from flask import Blueprint, render_template_string, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)
tasks_bp = Blueprint("tasks", __name__)


def _require_creds():
    if "credentials" not in session:
        return None
    return Credentials(**session["credentials"])


def _parse_date(d: str) -> date | None:
    """Try a few formats; return a date or None."""
    if not d:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(d.strip(), fmt).date()
        except Exception:
            continue
    return None


@tasks_bp.route("/tasks")
def tasks():
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)

        # For display names on the page
        clients = drive.get_clients_enhanced()
        client_lookup = {c["client_id"]: c.get("display_name", "Unknown") for c in clients}

        # Section 1: due in next 30 days — already filtered for Pending by the model
        within_30 = drive.get_upcoming_tasks(30)

        # Section 2: later (>30 days) or no due date — we build from each client's Pending tasks
        later = []
        today = datetime.today().date()
        cutoff = today + timedelta(days=30)

        for c in clients:
            cid = c["client_id"]
            for t in drive.get_client_tasks(cid):
                if (t.get("status") or "").lower() == "completed":
                    continue  # Completed stay in Drive but not shown here
                due = _parse_date(t.get("due_date", ""))
                # "later" bucket: no date OR due after cutoff
                if not due or due > cutoff:
                    t = dict(t)
                    t["client_id"] = cid
                    t["__due"] = due or date.max
                    later.append(t)

        # Sort consistently
        within_30_sorted = sorted(
            within_30,
            key=lambda x: _parse_date(x.get("due_date", "")) or date.max,
        )
        later_sorted = sorted(later, key=lambda x: x.get("__due", date.max))

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
                                <div class="pr-4">
                                    <h4 class="font-semibold text-gray-900">{{ task.title }}</h4>
                                    <p class="text-sm text-gray-600">
                                        Client: {{ client_lookup.get(task.client_id, 'Unknown') }}
                                    </p>
                                    <p class="text-sm text-gray-500">
                                        Due: {{ task.due_date or 'No date set' }} | Priority: {{ task.priority or 'Medium' }} | Type: {{ task.task_type or '' }}
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

        <!-- Section: Due later (>30 days) or no date -->
        <div class="bg-white rounded-lg shadow">
            <div class="p-6 border-b flex items-center justify-between">
                <h3 class="text-lg font-semibold">Due later (>30 days) or no date</h3>
                <span class="text-sm text-gray-600">Total: {{ later|length }}</span>
            </div>
            <div class="p-6">
                {% if later %}
                    <div class="space-y-4">
                        {% for task in later %}
                        <div class="border-l-4 border-blue-500 pl-4 py-3 bg-gray-50 rounded-r">
                            <div class="flex justify-between items-start">
                                <div class="pr-4">
                                    <h4 class="font-semibold text-gray-900">{{ task.title }}</h4>
                                    <p class="text-sm text-gray-600">
                                        Client: {{ client_lookup.get(task.client_id, 'Unknown') }}
                                    </p>
                                    <p class="text-sm text-gray-500">
                                        Due: {{ task.due_date or 'No date set' }} | Priority: {{ task.priority or 'Medium' }} | Type: {{ task.task_type or '' }}
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
                    <div class="text-center py-8 text-gray-500">No later-dated tasks.</div>
                {% endif %}
            </div>
        </div>
    </main>
</body>
</html>
            """,
            within_30=within_30_sorted,
            later=later_sorted,
            client_lookup=client_lookup,
        )

    except Exception as e:
        logger.exception("Tasks page error")
        return f"Error: {e}", 500


@tasks_bp.route("/tasks/<task_id>/complete")
def complete_task_route(task_id: str):
    """
    Mark a task as complete:
      - Moves the Drive file from Ongoing -> Completed
      - Prefixes filename with 'COMPLETED - ' (handled by model)
    """
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
