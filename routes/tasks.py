"""
WealthPro CRM - Task Management Routes
Adds:
- View/Edit a task (works for Ongoing & Completed)
- Delete a task
- Status badge (Ongoing/Completed)
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

# ------------------------------
# Routes
# ------------------------------

@tasks_bp.route('/tasks')
def tasks():
    """
    Overview:
    - Section 1: due within 30 days (open tasks)
    - Section 2: due later than 30 days (open tasks)
    Shows an "Open/Edit" link and an Ongoing status badge.
    """
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        # For name rendering
        clients = drive.get_clients_enhanced()
        client_lookup = {c['client_id']: c['display_name'] for c in clients}

        # Build list of ALL open tasks by scanning clients
        all_open = []
        for c in clients:
            for t in drive.get_client_tasks(c['client_id']):
                if (t['status'] or '').lower() != 'completed':
                    all_open.append(t)

        today = datetime.now().date()
        cutoff = today + timedelta(days=30)
        within_30, later = [], []

        for t in all_open:
            due = _parse_due_date(t.get('due_date'))
            # Always show as 'Ongoing' here
            t['status_label'] = 'Ongoing'
            if due and due <= cutoff:
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
                                        <span class="mr-2">Status:
                                            <span class="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-800">{{ task.status_label }}</span>
                                        </span>
                                        Due: {{ task.due_date or 'No date' }} | Priority: {{ task.priority }} | Type: {{ task.task_type }}
                                    </p>
                                    {% if task.description %}
                                    <p class="text-sm text-gray-700 mt-1">{{ task.description }}</p>
                                    {% endif %}
                                </div>
                                <div class="flex space-x-2">
                                    <a href="/tasks/{{ task.task_id }}" class="bg-indigo-100 text-indigo-800 text-xs px-2 py-1 rounded hover:bg-indigo-200">Open / Edit</a>
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
                                        <span class="mr-2">Status:
                                            <span class="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-800">{{ task.status_label }}</span>
                                        </span>
                                        Due: {{ task.due_date or 'No date set' }} | Priority: {{ task.priority }} | Type: {{ task.task_type }}
                                    </p>
                                    {% if task.description %}
                                    <p class="text-sm text-gray-700 mt-1">{{ task.description }}</p>
                                    {% endif %}
                                </div>
                                <div class="flex space-x-2">
                                    <a href="/tasks/{{ task.task_id }}" class="bg-indigo-100 text-indigo-800 text-xs px-2 py-1 rounded hover:bg-indigo-200">Open / Edit</a>
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


@tasks_bp.route('/tasks/<task_id>/complete')
def complete_task_route(task_id):
    """Mark a task complete (moves file to Completed and renames)."""
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


# -------- NEW: View/Edit a single task --------
@tasks_bp.route('/tasks/<task_id>', methods=['GET', 'POST'])
def view_edit_task(task_id):
    """
    View and edit a task. Works for tasks in Ongoing or Completed.
    Allows changing Type, Priority, Due Date, Title, Description, and Status.
    """
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        if request.method == 'POST':
            updates = {
                "title": (request.form.get('title') or '').strip(),
                "task_type": (request.form.get('task_type') or '').strip(),
                "priority": (request.form.get('priority') or 'Medium').strip(),
                "due_date": (request.form.get('due_date') or '').strip(),
                "status": (request.form.get('status') or 'Pending').strip(),
                "description": (request.form.get('description') or '').strip(),
            }
            ok = drive.update_task_enhanced(task_id, updates)
            if not ok:
                return "Error saving task", 500
            return redirect(url_for('tasks.view_edit_task', task_id=task_id))

        # GET
        task = drive.read_task_enhanced(task_id)
        if not task:
            return "Task not found", 404

        # Display label
        status_label = "Ongoing" if (task['status'] or "Pending") == "Pending" else "Completed"

        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Task</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style> body { font-family: "Inter", sans-serif; } </style>
</head>
<body class="bg-gray-50">
    <main class="max-w-3xl mx-auto px-6 py-8">
        <div class="flex items-center justify-between mb-6">
            <h1 class="text-2xl font-bold">Task</h1>
            <div class="flex items-center space-x-2">
                <span class="text-sm">Status:</span>
                {% if status_label == 'Completed' %}
                    <span class="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">Completed</span>
                {% else %}
                    <span class="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-800">Ongoing</span>
                {% endif %}
            </div>
        </div>

        <form method="POST" class="bg-white shadow rounded p-6 space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Task Title *</label>
                <input name="title" value="{{ task.title }}" required class="w-full px-3 py-2 border rounded">
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Type</label>
                    <select name="task_type" class="w-full px-3 py-2 border rounded">
                        {% set types = ['Review','Follow Up','Documentation','Meeting','Call','Research','Compliance','Portfolio Review','Other'] %}
                        {% for t in types %}
                            <option value="{{ t }}" {% if task.task_type==t %}selected{% endif %}>{{ t }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                    <select name="priority" class="w-full px-3 py-2 border rounded">
                        {% for p in ['Low','Medium','High'] %}
                            <option {% if task.priority==p %}selected{% endif %}>{{ p }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Due Date</label>
                    <input type="date" name="due_date" value="{{ task.due_date }}" class="w-full px-3 py-2 border rounded">
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Status</label>
                    <select name="status" class="w-full px-3 py-2 border rounded">
                        <option value="Pending" {% if task.status=='Pending' %}selected{% endif %}>Ongoing</option>
                        <option value="Completed" {% if task.status=='Completed' %}selected{% endif %}>Completed</option>
                    </select>
                </div>
                <div class="md:col-span-2 flex items-end">
                    {% if task.webViewLink %}
                        <a href="{{ task.webViewLink }}" target="_blank" class="ml-auto text-sm text-blue-700 hover:text-blue-900">Open in Google Drive ↗</a>
                    {% endif %}
                </div>
            </div>

            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea name="description" rows="6" class="w-full px-3 py-2 border rounded">{{ task.description }}</textarea>
            </div>

            <div class="flex justify-between pt-2">
                <a href="/tasks" class="px-6 py-2 border rounded text-gray-700 hover:bg-gray-50">Back</a>
                <div class="space-x-2">
                    <button class="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Save Changes</button>
                    <form method="POST" action="/tasks/{{ task.task_id }}/delete" style="display:inline" onsubmit="return confirm('Delete this task? This cannot be undone.');">
                        <button class="px-6 py-2 bg-red-600 text-white rounded hover:bg-red-700">Delete</button>
                    </form>
                </div>
            </div>
        </form>
    </main>
</body>
</html>
        ''', task=task, status_label=status_label)

    except Exception as e:
        logger.error(f"View/Edit task error: {e}")
        return f"Error: {e}", 500


# -------- NEW: Delete a task --------
@tasks_bp.route('/tasks/<task_id>/delete', methods=['POST'])
def delete_task(task_id):
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))
    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        ok = drive.delete_task(task_id)
        if not ok:
            return "Error deleting task", 500
        return redirect(url_for('tasks.tasks'))
    except Exception as e:
        logger.error(f"Delete task error: {e}")
        return f"Error: {e}", 500


# -------- Existing: Add task for a client (left unchanged) --------
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
                return redirect(url_for('clients.clients'))
            else:
                return "Error creating task", 500

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
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-4xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Add Task: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Creates a task file in Google Drive → Tasks → Ongoing Tasks</p>
        </div>

        <div class="bg-white rounded-lg shadow p-8">
            <form method="POST" class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Task Type *</label>
                        <select name="task_type" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            <option value="">Select Type...</option>
                            <option value="Review">Client Review</option>
                            <option value="Follow Up">Follow Up</option>
                            <option value="Documentation">Documentation</option>
                            <option value="Meeting">Meeting</option>
                            <option value="Call">Phone Call</option>
                            <option value="Research">Research</option>
                            <option value="Compliance">Compliance</option>
                            <option value="Portfolio Review">Portfolio Review</option>
                            <option value="Other">Other</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Priority</label>
                        <select name="priority" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            <option value="Low">Low</option>
                            <option value="Medium" selected>Medium</option>
                            <option value="High">High</option>
                        </select>
                    </div>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Task Title *</label>
                    <input type="text" name="title" required placeholder="e.g., Annual review meeting" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Description</label>
                    <textarea name="description" rows="4" placeholder="Add any additional details or notes..." class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Due Date *</label>
                        <input type="date" name="due_date" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Time to Allocate (optional)</label>
                        <input type="text" name="time_spent" placeholder="e.g., 30 minutes, 1 hour" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                    </div>
                </div>

                <div class="bg-blue-50 p-4 rounded-lg">
                    <h3 class="text-sm font-medium text-blue-800 mb-2">📁 Google Drive Integration</h3>
                    <p class="text-sm text-blue-700">This task is saved to: {{ client.display_name }} / Tasks / Ongoing Tasks</p>
                </div>

                <div class="flex justify-between">
                    <a href="/clients" class="px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">Cancel</a>
                    <button type="submit" class="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700">Create Task</button>
                </div>
            </form>
        </div>
    </main>
</body>
</html>
        ''', client=client)

    except Exception as e:
        logger.error(f"Add task error: {e}")
        return f"Error: {e}", 500


@tasks_bp.route('/clients/<client_id>/tasks')
def client_tasks(client_id):
    """View all tasks for a specific client (open and completed)."""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c['client_id'] == client_id), None)
        if not client:
            return "Client not found", 404

        client_tasks = drive.get_client_tasks(client_id)

        return render_template_string('''
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

        <div class="mb-6">
            <a href="/clients/{{ client.client_id }}/add_task" class="bg-green-600 text-white px-6 py-3 rounded-lg hover:bg-green-700">
                Add New Task
            </a>
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
                                        {{ task.task_type }} | Due: {{ task.due_date or 'No date' }} | Priority: {{ task.priority }}
                                    </p>
                                    <p class="text-sm text-gray-500">
                                        Status:
                                        {% if task.status == 'Completed' %}
                                            <span class="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-800">Completed</span>
                                        {% else %}
                                            <span class="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-800">Ongoing</span>
                                        {% endif %}
                                    </p>
                                    {% if task.description %}
                                    <p class="text-sm text-gray-700 mt-1">{{ task.description }}</p>
                                    {% endif %}
                                    <p class="text-xs text-gray-500 mt-1">Created: {{ task.created_date }}</p>
                                </div>
                                <div class="flex space-x-2">
                                    <a href="/tasks/{{ task.task_id }}" class="bg-indigo-100 text-indigo-800 text-xs px-2 py-1 rounded hover:bg-indigo-200">Open / Edit</a>
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
            <a href="/clients/{{ client.client_id }}/profile" class="bg-gray-600 text-white px-6 py-3 rounded-lg hover:bg-gray-700">
                Back to Profile
            </a>
        </div>
    </main>
</body>
</html>
        ''', client=client, client_tasks=client_tasks)

    except Exception as e:
        logger.error(f"Client tasks error: {e}")
        return f"Error: {e}", 500
