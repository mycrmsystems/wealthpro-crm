"""
WealthPro CRM - Clients Routes
FULL FILE — drop in as routes/clients.py

This version keeps the clients list and simply adds:
- “Details” link next to each client → /clients/<client_id>/details
- “Portfolio” link → /clients/<client_id>/portfolio
- “Folder” link opens the Google Drive client folder in a new tab
"""

import logging
from flask import Blueprint, render_template_string, redirect, url_for, session
from google.oauth2.credentials import Credentials

from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)
clients_bp = Blueprint("clients", __name__)

@clients_bp.route("/clients")
def clients():
    if "credentials" not in session:
        return redirect(url_for("auth.authorize"))

    try:
        creds = Credentials(**session["credentials"])
        drive = SimpleGoogleDrive(creds)
        clients = drive.get_clients_enhanced()

        return render_template_string(
            """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Clients</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <nav class="bg-gradient-to-r from-slate-800 to-blue-600 text-white shadow">
        <div class="max-w-7xl mx-auto px-6">
            <div class="h-16 flex items-center justify-between">
                <h1 class="text-lg font-bold">WealthPro CRM</h1>
                <div class="flex gap-6">
                    <a href="/" class="hover:text-blue-200">Dashboard</a>
                    <a href="/clients" class="hover:text-blue-200 font-semibold">Clients</a>
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="flex items-center justify-between mb-6">
            <h2 class="text-2xl font-bold">Clients</h2>
            <div class="flex gap-3">
                <a href="/clients/create" class="px-4 py-2 rounded bg-green-600 text-white hover:bg-green-700">Add Client</a>
            </div>
        </div>

        <div class="bg-white shadow rounded-lg overflow-hidden">
            <div class="px-6 py-4 border-b">
                <h3 class="font-semibold">Active Clients</h3>
            </div>
            <div class="p-6">
                {% if clients %}
                <div class="overflow-x-auto">
                    <table class="min-w-full text-sm">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-3 py-2 text-left font-medium text-gray-600">Client</th>
                                <th class="px-3 py-2 text-left font-medium text-gray-600">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y">
                            {% for c in clients %}
                            <tr>
                                <td class="px-3 py-2">
                                    <div class="font-medium">{{ c.display_name }}</div>
                                </td>
                                <td class="px-3 py-2">
                                    <div class="flex flex-wrap gap-2">
                                        <a class="px-2 py-1 rounded bg-blue-100 text-blue-800 hover:bg-blue-200" href="/clients/{{ c.client_id }}/details">Details</a>
                                        <a class="px-2 py-1 rounded bg-purple-100 text-purple-800 hover:bg-purple-200" href="/clients/{{ c.client_id }}/portfolio">Portfolio</a>
                                        <a class="px-2 py-1 rounded bg-slate-100 text-slate-800 hover:bg-slate-200" href="https://drive.google.com/drive/folders/{{ c.client_id }}" target="_blank">Folder</a>
                                        <a class="px-2 py-1 rounded bg-gray-100 text-gray-800 hover:bg-gray-200" href="/clients/{{ c.client_id }}/tasks">Tasks</a>
                                        <a class="px-2 py-1 rounded bg-amber-100 text-amber-800 hover:bg-amber-200" href="/clients/{{ c.client_id }}/communications">Comms</a>
                                        <a class="px-2 py-1 rounded bg-green-100 text-green-800 hover:bg-green-200" href="/reviews/{{ c.client_id }}">Reviews</a>
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                {% else %}
                    <p class="text-gray-500">No clients found.</p>
                {% endif %}
            </div>
        </div>
    </main>
</body>
</html>
            """,
            clients=clients,
        )
    except Exception as e:
        logger.error(f"Clients list error: {e}")
        return f"Error: {e}", 500
