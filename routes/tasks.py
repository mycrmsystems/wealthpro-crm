# routes/tasks.py

import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)
tasks_bp = Blueprint("tasks", __name__)


def _require_creds():
    if "credentials" not in session:
        return None
    return Credentials(**session["credentials"])


def _parse_due_date(due_str):
    if not due_str:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(due_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


@tasks_bp.route("/tasks", methods=["GET", "POST"])
def tasks():
    """Styled Tasks: add/edit/delete; show due within 30 and later."""
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)

        # For client lookups
        clients = drive.get_clients_enhanced()
        client_lookup = {c["client_id"]: c["display_name"] for c in clients}

        # Create / edit a task
        if request.method == "POST":
            mode = (request.form.get("mode") or "add").lower()
            client_id = request.form.get("client_id", "")
            title = (request.form.get("title") or "").strip()
            task_type = (request.form.get("task_type") or "").strip()
            priority = (request.form.get("priority") or "Medium").strip()
            due_date = (request.form.get("due_date") or "").strip()
            description = (request.form.get("description") or "").strip()
            if not client_id or not title:
                return "Client and Title are required", 400

            # Find client
            client = next((c for c in clients if c["client_id"] == client_id), None)
            if not client:
                return "Client not found", 404

            if mode == "add":
                task = {
                    "task_id": f"TSK{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "title": title,
                    "task_type": task_type,
                    "priority": priority,
                    "due_date": due_date,
                    "status": "Pending",
                    "description": description,
                    "created_date": datetime.now().strftime("%Y-%m-%d"),
                    "completed_date": "",
                    "time_spent": "",
                }
                drive.add_task_enhanced(task, client)
            else:
                # Editing an existing task: we get current id and (re)create with new filename then delete old
                old_task_id = request.form.get("task_id", "")
                # build new record
                task = {
                    "task_id": f"TSK{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "title": title,
                    "task_type": task_type,
                    "priority": priority,
                    "due_date": due_date,
                    "status": "Pending",
                    "description": description,
                    "created_date": datetime.now().strftime("%Y-%m-%d"),
                    "completed_date": "",
                    "time_spent": "",
                }
                drive.add_task_enhanced(task, client)
                if old_task_id:
                    drive.delete_task(old_task_id)

            return redirect(url_for("tasks.tasks"))

        # Build lists
        all_tasks = []
        for c in clients:
            all_tasks.extend(drive.get_client_tasks(c["client_id"]))

        today = datetime.now().date()
        cutoff = today + timedelta(days=30)
        within_30, later = [], []
        for t in all_tasks:
            if (t["status"] or "").lower() == "completed":
                continue
            due = _parse_due_date(t["due_date"])
            holder = within_30 if (due and due <= cutoff) else later
            holder.append({**t, "due_date_obj": due})

        within_30.sort(key=lambda x: x.get("due_date_obj") or datetime(9999, 12, 31).date())
        later.sort(key=lambda x: x.get("due_date_obj") or datetime(9999, 12, 31).date())

        # For form selects
        types = ["Review", "Follow Up", "Documentation", "Meeting", "Call", "Research", "Compliance", "Portfolio Review", "Other"]
        priorities = ["Low", "Medium", "High"]

        return render_template_string(
            """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Tasks</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: "Inter", sans-serif; }
        .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); }
        .card { @apply bg-white rounded-lg shadow; }
        .label { @apply block text-sm font-medium text-gray-700 mb-1; }
        .input { @apply w-full px-3 py-2 border border-gray-300 rounded-md; }
        .select { @apply w-full px-3 py-2 border border-gray-300 rounded-md; }
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
            <p class="text-gray-600 mt-2">Open tasks remain listed until completed.</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Add / Edit Task Form -->
            <div class="lg:col-span-1">
                <div class="card p-6">
                    <h3 class="text-lg font-semibold mb-4">Add / Edit Task</h3>
                    <form method="POST" class="space-y-4">
                        <input type="hidden" name="mode" id="modeField" value="add">
                        <input type="hidden" name="task_id" id="taskIdField" value="">

                        <div>
                            <label class="label">Client *</label>
                            <select name="client_id" class="select" required>
                                <option value="">Select client</option>
                                {% for cid, name in client_lookup.items() %}
                                <option value="{{ cid }}">{{ name }}</option>
                                {% endfor %}
                            </select>
                        </div>

                        <div>
                            <label class="label">Title *</label>
                            <input name="title" class="input" required placeholder="e.g., Annual review meeting">
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div>
                                <label class="label">Type</label>
                                <select name="task_type" class="select">
                                    <option value="">Select…</option>
                                    {% for t in types %}
                                    <option value="{{ t }}">{{ t }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div>
                                <label class="label">Priority</label>
                                <select name="priority" class="select">
                                    {% for p in priorities %}
                                    <option value="{{ p }}" {% if p=='Medium' %}selected{% endif %}>{{ p }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div>
                                <label class="label">Due Date</label>
                                <input type="date" name="due_date" class="input">
                            </div>
                        </div>

                        <div>
                            <label class="label">Description</label>
                            <textarea name="description" rows="4" class="input"></textarea>
                        </div>

                        <button class="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                            Save Task
                        </button>
                    </form>
                </div>
            </div>

            <!-- Lists -->
            <div class="lg:col-span-2 space-y-8">
                <!-- Due in next 30 days -->
                <div class="card">
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
                                                Client: {{ client_lookup.get(task.client_id, 'Unknown') }} •
                                                Status: {{ task.status }}
                                            </p>
                                            <p class="text-sm text-gray-500">
                                                Due: {{ task.due_date }} | Priority: {{ task.priority }} | Type: {{ task.task_type }}
                                            </p>
                                        </div>
                                        <div class="flex space-x-2">
                                            <a href="/tasks/{{ task.task_id }}/complete"
                                               class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded hover:bg-green-200">Complete</a>
                                            <a href="/tasks/{{ task.task_id }}/delete"
                                               class="bg-red-100 text-red-800 text-xs px-2 py-1 rounded hover:bg-red-200">Delete</a>
                                            <button onclick="editFromRow('{{ task.task_id }}','{{ task.client_id }}','{{ task.title|e }}','{{ task.task_type|e }}','{{ task.priority|e }}','{{ task.due_date|e }}')" class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded hover:bg-blue-200">Edit</button>
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

                <!-- Due later -->
                <div class="card">
                    <div class="p-6 border-b flex items-center justify-between">
                        <h3 class="text-lg font-semibold">Due later (>30 days)</h3>
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
                                                Client: {{ client_lookup.get(task.client_id, 'Unknown') }} •
                                                Status: {{ task.status }}
                                            </p>
                                            <p class="text-sm text-gray-500">
                                                Due: {{ task.due_date or 'No date set' }} | Priority: {{ task.priority }} | Type: {{ task.task_type }}
                                            </p>
                                        </div>
                                        <div class="flex space-x-2">
                                            <a href="/tasks/{{ task.task_id }}/complete"
                                               class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded hover:bg-green-200">Complete</a>
                                            <a href="/tasks/{{ task.task_id }}/delete"
                                               class="bg-red-100 text-red-800 text-xs px-2 py-1 rounded hover:bg-red-200">Delete</a>
                                            <button onclick="editFromRow('{{ task.task_id }}','{{ task.client_id }}','{{ task.title|e }}','{{ task.task_type|e }}','{{ task.priority|e }}','{{ task.due_date|e }}')" class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded hover:bg-blue-200">Edit</button>
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
            </div>
        </div>
    </main>

    <script>
    function editFromRow(taskId, clientId, title, type, priority, due) {
        document.getElementById('modeField').value = 'edit';
        document.getElementById('taskIdField').value = taskId;
        const form = document.forms[0];
        form.client_id.value = clientId;
        form.title.value = title;
        form.task_type.value = type;
        form.priority.value = priority || 'Medium';
        form.due_date.value = (due || '').substring(0,10);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    </script>
</body>
</html>
            """,
            within_30=within_30,
            later=later,
            client_lookup=client_lookup,
            types=types,
            priorities=priorities,
        )

    except Exception as e:
        logger.exception("Tasks error")
        return f"Error: {e}", 500


@tasks_bp.route("/tasks/<task_id>/complete")
def complete_task(task_id):
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))
    try:
        drive = SimpleGoogleDrive(creds)
        ok = drive.complete_task(task_id)
        return redirect(url_for("tasks.tasks")) if ok else ("Error completing task", 500)
    except Exception as e:
        logger.exception("Complete task error")
        return f"Error: {e}", 500


@tasks_bp.route("/tasks/<task_id>/delete")
def delete_task(task_id):
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))
    try:
        drive = SimpleGoogleDrive(creds)
        ok = drive.delete_task(task_id)
        return redirect(url_for("tasks.tasks")) if ok else ("Error deleting task", 500)
    except Exception as e:
        logger.exception("Delete task error")
        return f"Error: {e}", 500
