# routes/clients.py

import logging
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)

clients_bp = Blueprint('clients', __name__)


@clients_bp.route('/clients')
def clients():
    """List clients with Drive folder link and per-client Refresh button."""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        clients = drive.get_clients_enhanced()

        return render_template_string("""
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
    <div class="flex items-center justify-between mb-6">
        <div>
            <h1 class="text-3xl font-bold">Clients</h1>
            <p class="text-gray-600">Active client list.</p>
        </div>
        <a href="/clients/new" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Add Client</a>
    </div>

    <div class="bg-white rounded-lg shadow">
        <div class="p-6 border-b flex justify-between items-center">
            <h3 class="text-lg font-semibold">All Clients</h3>
            <span class="text-sm text-gray-600">Total: {{ clients|length }}</span>
        </div>
        <div class="p-6">
            {% if clients %}
            <div class="divide-y">
                {% for c in clients %}
                <div class="py-4 flex items-center justify-between">
                    <div>
                        <div class="font-semibold text-gray-900">{{ c.display_name }}</div>
                        <div class="text-sm text-gray-600">Folder:
                            <a href="{{ c.folder_url }}" class="text-blue-600 underline" target="_blank" rel="noopener">Open in Drive</a>
                        </div>
                        {% if c.portfolio_value is not none %}
                        <div class="text-sm text-gray-600">Portfolio: £{{ "%.2f"|format(c.portfolio_value) }}</div>
                        {% endif %}
                    </div>
                    <div class="flex items-center gap-2">
                        <a href="/clients/{{ c.client_id }}/refresh" class="px-3 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200">Refresh</a>
                        <a href="/clients/{{ c.client_id }}/profile" class="px-3 py-1 text-sm bg-blue-100 text-blue-800 rounded hover:bg-blue-200">Profile</a>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="text-gray-500 text-center py-8">No clients yet.</div>
            {% endif %}
        </div>
    </div>
</main>
</body>
</html>
        """, clients=clients)

    except Exception as e:
        logger.error(f"Clients error: {e}")
        return f"Error: {e}", 500


@clients_bp.route('/clients/new', methods=['GET', 'POST'])
def new_client():
    """Create a new client – ensures main subfolders are created in Drive."""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        if request.method == 'POST':
            display_name = request.form.get('display_name', '').strip()
            if not display_name:
                return "Client name required", 400

            client_folder_id = drive.create_client_enhanced_folders(display_name)
            return redirect(url_for('clients.clients'))

        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - New Client</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style> body { font-family: "Inter", sans-serif; } .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); } </style>
</head>
<body class="bg-gray-50">
<nav class="gradient-wealth text-white shadow-lg">
    <div class="max-w-7xl mx-auto px-6">
        <div class="flex justify-between items-center h-16">
            <h1 class="text-xl font-bold">WealthPro CRM</h1>
            <div class="flex items-center space-x-6">
                <a href="/" class="hover:text-blue-200">Dashboard</a>
                <a href="/clients" class="text-white font-semibold">Clients</a>
            </div>
        </div>
    </div>
</nav>

<main class="max-w-xl mx-auto px-6 py-8">
    <h1 class="text-2xl font-bold mb-4">Add Client</h1>
    <form method="POST" class="space-y-4 bg-white p-6 rounded-lg shadow">
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Client Name *</label>
            <input type="text" name="display_name" required class="w-full px-3 py-2 border rounded-md" placeholder="e.g., Alice Smith">
        </div>
        <div class="flex justify-between">
            <a href="/clients" class="px-4 py-2 border rounded">Cancel</a>
            <button type="submit" class="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">Create</button>
        </div>
    </form>
</main>
</body>
</html>
        """)

    except Exception as e:
        logger.error(f"New client error: {e}")
        return f"Error: {e}", 500


@clients_bp.route('/clients/<client_id>/refresh')
def refresh_client(client_id):
    """
    Per-client CRM refresh.
    Does NOT touch Google folders; simply re-reads live data and reloads profile/list.
    """
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        # No cache to clear; reload by redirecting to profile (or list if you prefer)
        return redirect(url_for('clients.clients'))
    except Exception as e:
        logger.error(f"Refresh client error: {e}")
        return f"Error: {e}", 500


@clients_bp.route('/clients/<client_id>/profile')
def client_profile(client_id):
    """Minimal profile with quick links."""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c['client_id'] == client_id), None)
        if not client:
            return "Client not found", 404

        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Client Profile</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style> body { font-family: "Inter", sans-serif; } .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); } </style>
</head>
<body class="bg-gray-50">
<nav class="gradient-wealth text-white shadow-lg">
    <div class="max-w-7xl mx-auto px-6">
        <div class="flex justify-between items-center h-16">
            <h1 class="text-xl font-bold">WealthPro CRM</h1>
            <div class="flex items-center space-x-6">
                <a href="/" class="hover:text-blue-200">Dashboard</a>
                <a href="/clients" class="text-white font-semibold">Clients</a>
            </div>
        </div>
    </div>
</nav>

<main class="max-w-5xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
        <div>
            <h1 class="text-3xl font-bold">{{ client.display_name }}</h1>
            <p class="text-gray-600">Portfolio: £{{ "%.2f"|format(client.portfolio_value or 0) }}</p>
        </div>
        <div class="flex gap-2">
            <a href="{{ client.folder_url }}" target="_blank" rel="noopener" class="px-4 py-2 bg-blue-100 text-blue-800 rounded hover:bg-blue-200">Open Folder</a>
            <a href="/clients/{{ client.client_id }}/refresh" class="px-4 py-2 bg-gray-100 rounded hover:bg-gray-200">Refresh</a>
        </div>
    </div>

    <div class="bg-white rounded-lg shadow p-6">
        <p class="text-gray-600">Quick actions and summaries can appear here.</p>
    </div>

    <div class="mt-8">
        <a href="/clients" class="px-4 py-2 border rounded">Back to Clients</a>
    </div>
</main>
</body>
</html>
        """, client=client)

    except Exception as e:
        logger.error(f"Client profile error: {e}")
        return f"Error: {e}", 500
