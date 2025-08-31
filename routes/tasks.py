"""
WealthPro CRM - Task Management Routes
- Tasks page shows two sections:
  1) Due in next 30 days (open tasks)
  2) Due later (>30 days) (open tasks)
- "Mark Complete" moves Drive file Ongoing -> Completed and renames to "(COMPLETED - ...)"
- Add Task form restyled to match the communications layout you liked.
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)

tasks_bp = Blueprint('tasks', __name__)

# ------------------------------
# Helpers (route-local)
# ------------------------------
def _parse_due_date(due_str):
    """Try multiple formats; return date or None."""
    if not due_str:
        return None
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(due_str.strip(), fmt).date()
        except ValueError:
            continue
    return None

def _load_all_tasks(drive: SimpleGoogleDrive):
    """
    Load all tasks by scanning ongoing & completed task files per client.
    This version uses Drive folders (no Sheets).
    """
    tasks = []
    for c in drive.get_clients_enhanced():
        client_id = c["client_id"]
        client_tasks = drive.get_client_tasks(client_id)
        tasks.extend(client_tasks)
    return tasks

# ------------------------------
# Routes
# ------------------------------
@tasks_bp.route('/tasks')
def tasks():
    """
    Tasks overview:
    - Section 1: due within 30 days (status != Completed)
    - Section 2: due later than 30 days (status != Completed)
    """
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        # For name rendering
        clients = drive.get_clients_enhanced()
        client_lookup = {c['client_id']: c['display_name'] for c in clients}

        # Load & split tasks
        all_tasks = _load_all_tasks(drive)
        today = datetime.now().date()
        cutoff = today + timedelta(days=30)

        within_30 = []
        later = []

        for t in all_tasks:
            if (t['status'] or '').lower() == 'completed':
                continue

            due = _parse_due_date(t['due_date'])
            if not due:
                later.append(t)
                continue

            if due <= cutoff:
                within_30.append({**t, 'due_date_obj': due})
            else:
                later.append({**t, 'due_date_obj': due})

        within_30.sort(key=lambda x: x.get('due_date_obj') or datetime(9999, 12, 31).date())
        later.sort(key=lambda x: x.get('due_date_obj') or datetime(9999, 12, 31).date())

        return render_template_string('''
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
                    <a href="/products/options" class="hover:text-blue-200">Products</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Tasks & Reminders</h1>
            <p class="text-gray-600 mt-2">Open tasks are listed until you mark them Completed.</p>
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
                                        Due: {{ task.due_date }} | Priority: {{ task.priority }} | Type: {{ task.task_type }}
                                    </p>
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

        <!-- Section: Due later (>30 days) -->
        <div class="bg-white rounded-lg shadow">
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
                                        Client: {{ client_lookup.get(task.client_id, 'Unknown') }}
                                    </p>
                                    <p class="text-sm text-gray-500">
                                        Due: {{ task.due_date or 'No date set' }} | Priority: {{ task.priority }} | Type: {{ task.task_type }}
                                    </p>
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
        ''', within_30=within_30, later=later, client_lookup=client_lookup)

    except Exception as e:
        logger.error(f"Tasks error: {e}")
        return f"Error: {e}", 500


@tasks_bp.route('/clients/<client_id>/add_task', methods=['GET', 'POST'])
def add_client_task(client_id):
    """Add a new task for a specific client (creates Drive file in Ongoing Tasks)."""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c['client_id'] == client_id), None)
        if not client:
            return "Client not found", 404

        if request.method == 'POST':
            task_data = {
                'task_id': f"TSK{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'client_id': client_id,
                'task_type': request.form.get('task_type', ''),
                'title': request.form.get('title', ''),
                'description': request.form.get('description', ''),
                'due_date': request.form.get('due_date', ''),
                'priority': request.form.get('priority', 'Medium'),
                'status': 'Pending',
                'created_date': datetime.now().strftime('%Y-%m-%d'),
                'completed_date': '',
                'time_spent': request.form.get('time_spent', '')
            }

            success = drive.add_task_enhanced(task_data, client)
            if success:
                return redirect(url_for('tasks.tasks'))
            else:
                return "Error creating task", 500

        # Restyled form (communications-style)
        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Add Task</title>
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

    <main class="max-w-6xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Add Task: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Creates a task file in Google Drive → Tasks → Ongoing Tasks</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Add Task Form -->
            <div class="lg:col-span-1">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold mb-4">New Task</h3>
                    <form method="POST" class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Task Title *</label>
                            <input type="text" name="title" required placeholder="e.g., Annual review meeting" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Type</label>
                                <select name="task_type" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                    <option value="">Select...</option>
                                    <option>Review</option>
                                    <option>Follow Up</option>
                                    <option>Documentation</option>
                                    <option>Meeting</option>
                                    <option>Call</option>
                                    <option>Research</option>
                                    <option>Compliance</option>
                                    <option>Portfolio Review</option>
                                    <option>Other</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                                <select name="priority" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                    <option>Low</option>
                                    <option selected>Medium</option>
                                    <option>High</option>
                                </select>
                            </div>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Due Date *</label>
                            <input type="date" name="due_date" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Time to Allocate (optional)</label>
                            <input type="text" name="time_spent" placeholder="e.g., 30 minutes, 1 hour" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
                            <textarea name="description" rows="4" placeholder="Add any additional details or notes..." class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
                        </div>

                        <div class="bg-blue-50 p-3 rounded">
                            <p class="text-xs text-blue-700">💾 Saves to Google Drive: {{ client.display_name }} / Tasks / Ongoing Tasks</p>
                        </div>

                        <button type="submit" class="w-full bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700">
                            Create Task
                        </button>
                    </form>
                </div>
            </div>

            <!-- Context panel -->
            <div class="lg:col-span-2">
                <div class="bg-white rounded-lg shadow">
                    <div class="p-6 border-b">
                        <h3 class="text-lg font-semibold">Tips</h3>
                    </div>
                    <div class="p-6 text-sm text-gray-700">
                        <ul class="list-disc pl-6 space-y-1">
                            <li>Tasks appear on the Tasks page; those due within 30 days are highlighted.</li>
                            <li>Mark Complete moves the task to the client's <em>Completed Tasks</em> folder.</li>
                            <li>Tasks persist until you complete them—no auto-removal.</li>
                        </ul>
                    </div>
                </div>
                <div class="mt-6">
                    <a href="/tasks" class="inline-block px-6 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700">Back to Tasks</a>
                </div>
            </div>
        </div>
    </main>
</body>
</html>
        ''', client=client)

    except Exception as e:
        logger.error(f"Add task error: {e}")
        return f"Error: {e}", 500


@tasks_bp.route('/tasks/<task_id>/complete')
def complete_task_route(task_id):
    """Mark a task complete (updates Drive and renames the file)."""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))
    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        success = drive.complete_task(task_id)
        if success:
            return redirect(url_for('tasks.tasks'))
        else:
            return "Error completing task", 500
    except Exception as e:
        logger.error(f"Complete task error: {e}")
        return f"Error: {e}", 500
