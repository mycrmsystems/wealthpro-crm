# routes/clients.py

"""
WealthPro CRM - Client Management Routes
 - /clients list with Drive folder link + Archive button
 - /clients/archived list of archived clients
 - /clients/add (creates full subfolders at creation time)
 - /clients/<client_id>/archive (soft delete -> move to Archived Clients A–Z)
 - /clients/<client_id>/add_task
 - /clients/<client_id>/review
 - /clients/<client_id>/tasks
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)
clients_bp = Blueprint("clients", __name__)

def _require_creds():
    if "credentials" not in session:
        return None
    return Credentials(**session["credentials"])

@clients_bp.route("/clients")
def clients():
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)
        items = drive.get_clients_enhanced()

        # Decorate with folder links and safe defaults
        for c in items:
            c.setdefault("email", None)
            c.setdefault("phone", None)
            c.setdefault("status", "active")
            c["portfolio_value"] = float(c.get("portfolio_value") or 0)
            c["folder_url"] = f"https://drive.google.com/drive/folders/{c['folder_id']}" if c.get("folder_id") else None

        return render_template_string(
            """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Clients</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: "Inter", sans-serif; }
        .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); }
        .danger { color:#b91c1c }
    </style>
</head>
<body class="bg-gray-50">
    <nav class="gradient-wealth text-white shadow-lg">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex justify-between items-center h-16">
                <h1 class="text-xl font-bold">WealthPro CRM</h1>
                <div class="flex items-center space-x-6">
                    <a href="/" class="hover:text-blue-200">Dashboard</a>
                    <a href="/clients" class="text-white font-semibold">Clients</a>
                    <a href="/clients/archived" class="hover:text-blue-200">Archived</a>
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold">Clients</h1>
                <p class="text-gray-600 mt-1">Total clients: {{ clients|length }}</p>
            </div>
            <a href="/clients/add" class="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700">
                Add New Client
            </a>
        </div>

        {% if request.args.get('msg') %}
        <div class="mb-6 p-4 bg-green-100 border border-green-300 text-green-800 rounded">
            {{ request.args.get('msg') }}
        </div>
        {% endif %}

        <div class="bg-white rounded-lg shadow overflow-hidden">
            <table class="min-w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Client</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contact</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Portfolio</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {% for client in clients %}
                    <tr>
                        <td class="px-6 py-4">
                            <div class="font-medium text-gray-900">{{ client.display_name }}</div>
                            <div class="text-sm text-gray-500">ID: {{ client.client_id }}</div>
                        </td>
                        <td class="px-6 py-4">
                            <div class="text-sm text-gray-900">{{ client.email or 'N/A' }}</div>
                            <div class="text-sm text-gray-500">{{ client.phone or 'N/A' }}</div>
                        </td>
                        <td class="px-6 py-4">
                            <span class="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">
                                Active
                            </span>
                        </td>
                        <td class="px-6 py-4 text-sm">
                            £{{ "{:,.0f}".format(client.portfolio_value) }}
                        </td>
                        <td class="px-6 py-4">
                            <div class="flex gap-3 flex-wrap items-center">
                                {% if client.folder_url %}
                                    <a href="{{ client.folder_url }}" target="_blank" class="text-blue-600 hover:text-blue-800 text-sm">📁 Folder</a>
                                {% endif %}
                                <a href="/clients/{{ client.client_id }}/add_task" class="text-indigo-700 hover:text-indigo-900 text-sm">📝 Add Task</a>
                                <a href="/clients/{{ client.client_id }}/review" class="text-teal-700 hover:text-teal-900 text-sm font-semibold">🔄 Review</a>
                                <a href="/clients/{{ client.client_id }}/tasks" class="text-gray-700 hover:text-gray-900 text-sm">📋 Tasks</a>
                                <a href="/clients/{{ client.client_id }}/archive?name={{ client.display_name | urlencode }}"
                                   class="text-sm danger hover:underline"
                                   onclick="return confirm('Archive this client? This will move their folder to Archived Clients in Google Drive (nothing is deleted).');">
                                   🗑️ Archive
                                </a>
                            </div>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="5" class="px-6 py-4 text-center text-gray-500">
                            No clients found. <a href="/clients/add" class="text-blue-600">Add your first client</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>
</body>
</html>
            """,
            clients=items,
        )

    except Exception as e:
        logger.exception("Clients error")
        return f"Error: {e}", 500

@clients_bp.route("/clients/archived")
def clients_archived():
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))
    try:
        drive = SimpleGoogleDrive(creds)
        items = drive.get_archived_clients_enhanced()
        for c in items:
            c["folder_url"] = f"https://drive.google.com/drive/folders/{c['folder_id']}"
        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Archived Clients</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <nav class="gradient-wealth text-white shadow-lg" style="background:linear-gradient(135deg,#1a365d 0%,#2563eb 100%);">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex justify-between items-center h-16">
                <h1 class="text-xl font-bold">WealthPro CRM</h1>
                <div class="flex items-center space-x-6">
                    <a href="/" class="hover:text-blue-200">Dashboard</a>
                    <a href="/clients" class="hover:text-blue-200">Clients</a>
                    <a href="/clients/archived" class="text-white font-semibold">Archived</a>
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Archived Clients</h1>
            <p class="text-gray-600 mt-1">Clients moved into the Archived area of Google Drive.</p>
        </div>

        <div class="bg-white rounded-lg shadow overflow-hidden">
            <table class="min-w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Client</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Folder</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {% for client in clients %}
                    <tr>
                        <td class="px-6 py-4">
                            <div class="font-medium text-gray-900">{{ client.display_name }}</div>
                            <div class="text-sm text-gray-500">ID: {{ client.client_id }}</div>
                        </td>
                        <td class="px-6 py-4">
                            <span class="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-800">Archived</span>
                        </td>
                        <td class="px-6 py-4">
                            <a href="{{ client.folder_url }}" target="_blank" class="text-blue-600 hover:text-blue-800 text-sm">📁 Open Folder</a>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="3" class="px-6 py-4 text-center text-gray-500">
                            No archived clients yet.
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>
</body>
</html>
        """, clients=items)
    except Exception as e:
        logger.exception("Archived clients error")
        return f"Error: {e}", 500

@clients_bp.route("/clients/<client_id>/archive")
def archive_client(client_id):
    """
    Soft delete: move the client's Drive folder into 'Archived Clients' A–Z
    and remove them from the active list (they will appear on /clients/archived).
    """
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    name = request.args.get("name", "").strip()  # display_name passed from link
    if not name:
        # As a fallback, try to look up the name
        try:
            drive = SimpleGoogleDrive(creds)
            clients = drive.get_clients_enhanced()
            c = next((x for x in clients if x["client_id"] == client_id), None)
            if c:
                name = c["display_name"]
        except Exception:
            name = ""

    try:
        drive = SimpleGoogleDrive(creds)
        ok = drive.archive_client(client_id, name or "Client")
        if ok:
            return redirect(url_for("clients.clients", msg="Client archived."))
        else:
            return "Error archiving client", 500
    except Exception as e:
        logger.exception("Archive client error")
        return f"Error: {e}", 500

# ---------- Add Client ----------
@clients_bp.route("/clients/add", methods=["GET", "POST"])
def add_client():
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    if request.method == "POST":
        try:
            drive = SimpleGoogleDrive(creds)

            first_name = (request.form.get("first_name") or "").strip()
            surname = (request.form.get("surname") or "").strip()
            if not first_name or not surname:
                raise ValueError("First name and surname are required")

            display_name = f"{surname}, {first_name}"

            # Create Drive structure (A–Z + client + Tasks/Reviews/Communications)
            drive.create_client_enhanced_folders(display_name)

            return redirect(url_for("clients.clients", msg="Client created successfully"))

        except Exception as e:
            logger.exception("Add client error")
            return f"Error adding client: {e}", 500

    # GET form
    return render_template_string(
        """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Add Client</title>
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
            <h1 class="text-3xl font-bold">Add New Client</h1>
            <p class="text-gray-600 mt-2">Client will be filed as "Surname, First Name" in the A–Z folder system.</p>
        </div>

        <div class="bg-white rounded-lg shadow p-8">
            <form method="POST" class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">First Name *</label>
                        <input type="text" name="first_name" required class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Surname *</label>
                        <input type="text" name="surname" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        <p class="text-xs text-gray-500 mt-1">Will display as "Surname, First Name"</p>
                    </div>
                </div>

                <div class="flex justify-between">
                    <a href="/clients" class="px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">Cancel</a>
                    <button type="submit" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Create Client</button>
                </div>
            </form>
        </div>
    </main>
</body>
</html>
        """
    )

# ---------- Add Task ----------
@clients_bp.route("/clients/<client_id>/add_task", methods=["GET", "POST"])
def add_task(client_id):
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)
        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c["client_id"] == client_id), None)
        if not client:
            return "Client not found", 404

        if request.method == "POST":
            title = (request.form.get("title") or "").strip()
            task_type = (request.form.get("task_type") or "").strip()
            priority = (request.form.get("priority") or "Medium").strip()
            due_date = (request.form.get("due_date") or "").strip()
            description = (request.form.get("description") or "").strip()

            if not title:
                return "Title is required", 400

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
            return redirect(url_for("clients.clients", msg="Task created"))

        return render_template_string(
            """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Add Task</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <main class="max-w-3xl mx-auto px-6 py-8">
        <h1 class="text-2xl font-bold mb-6">Add Task for {{ client.display_name }}</h1>
        <form method="POST" class="bg-white shadow rounded p-6 space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Title *</label>
                <input name="title" class="w-full px-3 py-2 border rounded" required>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Type</label>
                    <select name="task_type" class="w-full px-3 py-2 border rounded">
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
                    <select name="priority" class="w-full px-3 py-2 border rounded">
                        <option>High</option>
                        <option selected>Medium</option>
                        <option>Low</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Due Date</label>
                    <input type="date" name="due_date" class="w-full px-3 py-2 border rounded">
                </div>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea name="description" rows="4" class="w-full px-3 py-2 border rounded"></textarea>
            </div>
            <div class="bg-blue-50 p-3 rounded">
                <p class="text-xs text-blue-700">💾 Saves to Google Drive → {{ client.display_name }} / Tasks / Ongoing Tasks</p>
            </div>
            <div class="flex justify-between pt-2">
                <a href="/clients" class="px-6 py-2 border rounded text-gray-700 hover:bg-gray-50">Cancel</a>
                <button class="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Create Task</button>
            </div>
        </form>
    </main>
</body>
</html>
            """,
            client=client,
        )

    except Exception as e:
        logger.exception("Add task error")
        return f"Error: {e}", 500

# ---------- Create Review Pack (+ task) ----------
@clients_bp.route("/clients/<client_id>/review")
def create_review(client_id):
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)
        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c["client_id"] == client_id), None)
        if not client:
            return "Client not found", 404

        drive.create_review_pack_for_client(client)

        # Add a Review task due in 14 days
        due_date = (datetime.today() + timedelta(days=14)).strftime("%Y-%m-%d")
        review_task = {
            "task_id": f"TSK{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "title": "Annual Client Review",
            "task_type": "Review",
            "priority": "High",
            "due_date": due_date,
            "status": "Pending",
            "description": "Prepare and complete the annual client review.",
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "completed_date": "",
            "time_spent": "",
        }
        drive.add_task_enhanced(review_task, client)

        return redirect(url_for("clients.clients", msg="Review pack created and task added."))

    except Exception as e:
        logger.exception("Create review error")
        return f"Error: {e}", 500

# ---------- Per-client task history ----------
@clients_bp.route('/clients/<client_id>/tasks')
def client_tasks(client_id):
    creds = _require_creds()
    if not creds:
        return redirect(url_for('auth.authorize'))

    try:
        drive = SimpleGoogleDrive(creds)

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
                                        {{ task.task_type }} | Due: {{ task.due_date }} | Priority: {{ task.priority }}
                                    </p>
                                    {% if task.description %}
                                    <p class="text-sm text-gray-700 mt-1">{{ task.description }}</p>
                                    {% endif %}
                                    <p class="text-xs text-gray-500 mt-1">Created: {{ task.created_date }}</p>
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
        ''', client=client, client_tasks=client_tasks)

    except Exception as e:
        logger.error(f"Client tasks error: {e}")
        return f"Error: {e}", 500
