"""
WealthPro CRM - Task Management Routes
FILE 6 of 8 - Upload this as routes/tasks.py
"""

import logging
from datetime import datetime
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint for task routes
tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/tasks')
def tasks():
    """Main tasks overview page"""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        upcoming_tasks = drive.get_upcoming_tasks(30)  # Next 30 days
        clients = drive.get_clients_enhanced()
        
        # Create client lookup for task display
        client_lookup = {c['client_id']: c['display_name'] for c in clients}

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
                    <a href="/factfind" class="hover:text-blue-200">Fact Find</a>
                    <a href="/tasks" class="text-white font-semibold">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Tasks & Reminders</h1>
            <p class="text-gray-600 mt-2">Manage your client follow-ups and reviews</p>
        </div>

        <div class="bg-white rounded-lg shadow">
            <div class="p-6 border-b">
                <h3 class="text-lg font-semibold">Upcoming Tasks (Next 30 Days)</h3>
            </div>
            <div class="p-6">
                {% if upcoming_tasks %}
                    <div class="space-y-4">
                        {% for task in upcoming_tasks %}
                        <div class="border-l-4 {% if task.priority == 'High' %}border-red-500{% elif task.priority == 'Medium' %}border-yellow-500{% else %}border-green-500{% endif %} pl-4 py-3 bg-gray-50 rounded-r">
                            <div class="flex justify-between items-start">
                                <div>
                                    <h4 class="font-semibold text-gray-900">{{ task.title }}</h4>
                                    <p class="text-sm text-gray-600">Client: {{ client_lookup.get(task.client_id, 'Unknown') }}</p>
                                    <p class="text-sm text-gray-500">Due: {{ task.due_date }} | Priority: {{ task.priority }}</p>
                                    {% if task.description %}
                                    <p class="text-sm text-gray-700 mt-1">{{ task.description }}</p>
                                    {% endif %}
                                </div>
                                <div class="flex space-x-2">
                                    <span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">{{ task.task_type }}</span>
                                    {% if task.status != 'Completed' %}
                                    <a href="/tasks/{{ task.task_id }}/complete" class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded hover:bg-green-200">Mark Complete</a>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                {% else %}
                    <div class="text-center py-8">
                        <p class="text-gray-500 mb-4">No upcoming tasks.</p>
                        <a href="/clients" class="text-blue-600 hover:underline">Go to clients to add some tasks</a>
                    </div>
                {% endif %}
            </div>
        </div>
    </main>
</body>
</html>
        ''', upcoming_tasks=upcoming_tasks, client_lookup=client_lookup)

    except Exception as e:
        logger.error(f"Tasks error: {e}")
        return f"Error: {e}", 500

@tasks_bp.route('/tasks/<task_id>/complete')
def complete_task_route(task_id):
    """Complete a task"""
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

@tasks_bp.route('/clients/<client_id>/add_task', methods=['GET', 'POST'])
def add_client_task(client_id):
    """Add task for specific client"""
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
                    <a href="/factfind" class="hover:text-blue-200">Fact Find</a>
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-4xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Add Task: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Create a new task or reminder for this client</p>
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
                    <p class="text-sm text-blue-700">This task will be saved to: {{ client.display_name }}/Tasks/ folder</p>
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
    """View all tasks for a specific client"""
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
                    <a href="/factfind" class="hover:text-blue-200">Fact Find</a>
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-6xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Tasks: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">All tasks and reminders for this client</p>
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
                        <div class="border-l-4 {% if task.status == 'Completed' %}border-green-500{% elif task.priority == 'High' %}border-red-500{% elif task.priority == 'Medium' %}border-yellow-500{% else %}border-blue-500{% endif %} pl-4 py-3 bg-gray-50 rounded-r">
                            <div class="flex justify-between items-start">
                                <div class="flex-1">
                                    <h4 class="font-semibold text-gray-900 {% if task.status == 'Completed' %}line-through text-gray-600{% endif %}">{{ task.title }}</h4>
                                    <p class="text-sm text-gray-600">{{ task.task_type }} | Due: {{ task.due_date }} | Priority: {{ task.priority }}</p>
                                    {% if task.description %}
                                    <p class="text-sm text-gray-700 mt-1">{{ task.description }}</p>
                                    {% endif %}
                                    <p class="text-xs text-gray-500 mt-1">Created: {{ task.created_date }}</p>
                                </div>
                                <div class="flex space-x-2">
                                    <span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">{{ task.status }}</span>
                                    {% if task.status != 'Completed' %}
                                    <a href="/tasks/{{ task.task_id }}/complete" class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded hover:bg-green-200">Complete</a>
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
