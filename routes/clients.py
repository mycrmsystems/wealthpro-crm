# routes/clients.py

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

        # Decorate with folder links and safe defaults for template
        for c in items:
            c.setdefault("email", None)
            c.setdefault("phone", None)
            c.setdefault("status", "active")  # lowercase to match label logic
            c["portfolio_value"] = float(c.get("portfolio_value") or 0)
            if c.get("folder_id"):
                c["folder_url"] = f"https://drive.google.com/drive/folders/{c['folder_id']}"
            else:
                c["folder_url"] = None

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
                            <span class="px-2 py-1 text-xs rounded-full
                                {% if client.status == 'active' %}bg-green-100 text-green-800
                                {% elif client.status == 'deceased' %}bg-gray-100 text-gray-800
                                {% elif client.status == 'no_longer_client' %}bg-red-100 text-red-800
                                {% else %}bg-yellow-100 text-yellow-800{% endif %}">
                                {{ (client.status or 'active').replace('_', ' ').title() }}
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

                                {% if client.status == 'archived' %}
                                    <a href="/clients/{{ client.client_id }}/restore" class="text-green-700 hover:text-green-900 text-sm font-semibold">♻️ Restore</a>
                                {% else %}
                                    <a href="/clients/{{ client.client_id }}/archive" class="text-red-700 hover:text-red-900 text-sm">🗑️ Archive</a>
                                {% endif %}
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
            email = (request.form.get("email") or "").strip()
            phone = (request.form.get("phone") or "").strip()
            status = (request.form.get("status") or "active").strip().lower()
            portfolio_value = request.form.get("portfolio_value", "0").strip()
            _ = request.form.get("notes", "").strip()  # not persisted (no DB)

            if not first_name or not surname:
                raise ValueError("First name and surname are required")

            display_name = f"{surname}, {first_name}"

            # Create Drive structure (A–Z + client + Tasks/Reviews/Comms) under Active Clients if present
            client_folder_id = drive.create_client_enhanced_folders(display_name)

            # Success -> redirect; list pulls directly from Drive
            return redirect(url_for("clients.clients", msg="Client created successfully"))

        except Exception as e:
            logger.exception("Add client error")
            return f"Error adding client: {e}", 500

    # GET form (kept as-is, full form)
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
            <p class="text-gray-600 mt-2">Client will be filed as "Surname, First Name" in the A–Z system.</p>
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
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Email</label>
                        <input type="email" name="email" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Phone</label>
                        <input type="tel" name="phone" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Status</label>
                        <select name="status" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            <option value="active" selected>Active</option>
                            <option value="prospect">Prospect</option>
                            <option value="no_longer_client">No Longer Client</option>
                            <option value="deceased">Deceased</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Portfolio Value (£)</label>
                        <input type="number" name="portfolio_value" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                    </div>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Notes</label>
                    <textarea name="notes" rows="4" class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
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

# ---------- Review Pack (unchanged behavior; uses templates if found) ----------
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

        # Also add a Review task due in 14 days (kept from your build)
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

        return redirect(url_for("clients.clients", msg="Review pack created (agenda/valuation added)."))

    except Exception as e:
        logger.exception("Create review error")
        return f"Error: {e}", 500

# ---------- Archive / Restore (Drive only) ----------
@clients_bp.route("/clients/<client_id>/archive")
def archive_client(client_id):
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))
    try:
        drive = SimpleGoogleDrive(creds)
        ok = drive.archive_client(client_id)
        msg = "Client archived" if ok else "Archive failed"
        return redirect(url_for("clients.clients", msg=msg))
    except Exception as e:
        logger.exception("Archive client error")
        return f"Error: {e}", 500

@clients_bp.route("/clients/<client_id>/restore")
def restore_client(client_id):
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))
    try:
        drive = SimpleGoogleDrive(creds)
        ok = drive.restore_client(client_id)
        msg = "Client restored" if ok else "Restore failed"
        return redirect(url_for("clients.clients", msg=msg))
    except Exception as e:
        logger.exception("Restore client error")
        return f"Error: {e}", 500
