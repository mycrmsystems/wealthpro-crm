# routes/clients.py

import logging
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive
from datetime import datetime

logger = logging.getLogger(__name__)
clients_bp = Blueprint("clients", __name__)

@clients_bp.route("/clients", methods=["GET", "POST"])
def clients():
    if "credentials" not in session:
        return redirect(url_for("auth.authorize"))

    try:
        credentials = Credentials(**session["credentials"])
        drive = SimpleGoogleDrive(credentials)

        all_clients = drive.get_clients_enhanced()
        show_archived = request.args.get("archived") == "1"

        if not show_archived:
            clients = [c for c in all_clients if (c.get("status") or "active") != "archived"]
        else:
            clients = all_clients

        total_active_value = sum(
            float(c.get("portfolio_value") or 0.0)
            for c in all_clients
            if (c.get("status") or "active") != "archived"
        )

        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
  <title>WealthPro CRM - Clients</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style> body { font-family: "Inter", sans-serif; } .gradient-wealth{background:linear-gradient(135deg,#1a365d 0%,#2563eb 100%);} </style>
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
        <p class="text-gray-600">Total Active Portfolio Value: £{{ "{:,.2f}".format(total_active_value) }}</p>
      </div>
      <div class="space-x-2">
        {% if show_archived %}
          <a href="/clients" class="px-4 py-2 border rounded">Hide archived</a>
        {% else %}
          <a href="/clients?archived=1" class="px-4 py-2 border rounded">Show archived</a>
        {% endif %}
        <a href="/clients/new" class="px-4 py-2 bg-green-600 text-white rounded">New Client</a>
      </div>
    </div>

    <div class="bg-white rounded shadow">
      <div class="divide-y">
        {% for c in clients %}
          <div class="p-4 flex items-center justify-between">
            <div>
              <div class="font-semibold">
                <a href="/clients/{{ c.client_id }}/profile" class="text-blue-700 hover:text-blue-900">{{ c.display_name }}</a>
                {% if c.status == 'archived' %}
                  <span class="ml-2 text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-700">Archived</span>
                {% endif %}
              </div>
              <div class="text-sm text-gray-600">
                Portfolio: £{{ "{:,.2f}".format(c.portfolio_value or 0) }} · {{ c.email or 'no email' }} · {{ c.phone or 'no phone' }}
              </div>
            </div>
            <div class="space-x-2">
              <a href="/clients/{{ c.client_id }}/profile" class="text-sm px-3 py-1 border rounded">Profile</a>
              {% if c.status != 'archived' %}
              <form method="POST" action="/clients/{{ c.client_id }}/delete" style="display:inline" onsubmit="return confirm('Archive this client in CRM (folders remain on Drive)?');">
                <button class="text-sm px-3 py-1 bg-red-600 text-white rounded">Delete (CRM only)</button>
              </form>
              {% endif %}
            </div>
          </div>
        {% endfor %}
        {% if not clients %}
          <div class="p-8 text-center text-gray-500">No clients found.</div>
        {% endif %}
      </div>
    </div>
  </main>
</body>
</html>
        """, clients=clients, total_active_value=total_active_value, show_archived=show_archived)

    except Exception as e:
        logger.error(f"clients list error: {e}")
        return f"Error: {e}", 500


@clients_bp.route("/clients/new", methods=["GET", "POST"])
def new_client():
    if "credentials" not in session:
        return redirect(url_for("auth.authorize"))
    try:
        credentials = Credentials(**session["credentials"])
        drive = SimpleGoogleDrive(credentials)

        if request.method == "POST":
            display_name = (request.form.get("display_name") or "").strip()
            email = (request.form.get("email") or "").strip()
            phone = (request.form.get("phone") or "").strip()
            portfolio_value = (request.form.get("portfolio_value") or "").strip()

            # Create full folder structure immediately + save meta
            client_id = drive.create_client_enhanced_folders(
                display_name,
                meta={
                    "status": "active",
                    "email": email,
                    "phone": phone,
                    "portfolio_value": portfolio_value,
                },
            )
            return redirect(url_for("clients.client_profile", client_id=client_id))

        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
  <title>New Client</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style> body{font-family:"Inter",sans-serif} </style>
</head>
<body class="bg-gray-50">
  <main class="max-w-xl mx-auto px-6 py-10">
    <h1 class="text-2xl font-bold mb-6">Create Client</h1>
    <form method="POST" class="bg-white rounded shadow p-6 space-y-4">
      <div>
        <label class="block text-sm font-medium">Display Name *</label>
        <input name="display_name" required class="w-full border rounded px-3 py-2">
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium">Email</label>
          <input name="email" class="w-full border rounded px-3 py-2">
        </div>
        <div>
          <label class="block text-sm font-medium">Phone</label>
          <input name="phone" class="w-full border rounded px-3 py-2">
        </div>
      </div>
      <div>
        <label class="block text-sm font-medium">Portfolio Value (£)</label>
        <input name="portfolio_value" placeholder="e.g., 125000" class="w-full border rounded px-3 py-2">
      </div>
      <div class="flex justify-end">
        <a href="/clients" class="px-4 py-2 border rounded mr-2">Cancel</a>
        <button class="px-4 py-2 bg-green-600 text-white rounded">Create</button>
      </div>
    </form>
  </main>
</body>
</html>
        """)

    except Exception as e:
        logger.error(f"new_client error: {e}")
        return f"Error: {e}", 500


@clients_bp.route("/clients/<client_id>/profile")
def client_profile(client_id):
    if "credentials" not in session:
        return redirect(url_for("auth.authorize"))
    try:
        credentials = Credentials(**session["credentials"])
        drive = SimpleGoogleDrive(credentials)

        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c["client_id"] == client_id), None)
        if not client:
            return "Client not found", 404

        # A quick deep link to the client folder in Drive (existing behavior preserved)
        drive_link = f"https://drive.google.com/drive/folders/{client_id}"

        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
  <title>Client Profile</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style> body{font-family:"Inter",sans-serif} </style>
</head>
<body class="bg-gray-50">
  <main class="max-w-3xl mx-auto px-6 py-10">
    <div class="flex items-start justify-between">
      <div>
        <h1 class="text-2xl font-bold">{{ client.display_name }}</h1>
        <p class="text-gray-600">Portfolio: £{{ "{:,.2f}".format(client.portfolio_value or 0) }}</p>
        {% if client.status == 'archived' %}
          <p class="text-xs px-2 py-0.5 rounded bg-gray-100 inline-block mt-1">Archived (CRM)</p>
        {% endif %}
      </div>
      <div class="space-x-2">
        <a href="{{ drive_link }}" target="_blank" class="px-3 py-2 border rounded">Open Folder ↗</a>
        {% if client.status != 'archived' %}
        <form method="POST" action="/clients/{{ client.client_id }}/delete" style="display:inline" onsubmit="return confirm('Archive this client in CRM (folders remain on Drive)?');">
          <button class="px-3 py-2 bg-red-600 text-white rounded">Delete (CRM only)</button>
        </form>
        {% endif %}
      </div>
    </div>

    <div class="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
      <a href="/clients/{{ client.client_id }}/tasks" class="block p-4 bg-white rounded shadow hover:shadow-md">
        <div class="font-semibold mb-1">Tasks</div>
        <div class="text-sm text-gray-600">View tasks for this client</div>
      </a>
      <a href="/clients/{{ client.client_id }}/communications" class="block p-4 bg-white rounded shadow hover:shadow-md">
        <div class="font-semibold mb-1">Communications</div>
        <div class="text-sm text-gray-600">Log & review interactions</div>
      </a>
      <a href="/clients/{{ client.client_id }}/review-pack" class="block p-4 bg-white rounded shadow hover:shadow-md">
        <div class="font-semibold mb-1">Review Pack</div>
        <div class="text-sm text-gray-600">Create the annual review pack</div>
      </a>
    </div>
  </main>
</body>
</html>
        """, client=client, drive_link=drive_link)

    except Exception as e:
        logger.error(f"client_profile error: {e}")
        return f"Error: {e}", 500


@clients_bp.route("/clients/<client_id>/delete", methods=["POST"])
def delete_client_crm_only(client_id):
    """
    Soft-delete a client: mark as archived in CRM only. Google Drive folders remain intact.
    """
    if "credentials" not in session:
        return redirect(url_for("auth.authorize"))
    try:
        credentials = Credentials(**session["credentials"])
        drive = SimpleGoogleDrive(credentials)
        ok = drive.archive_client(client_id)
        if not ok:
            return "Error archiving client", 500
        return redirect(url_for("clients.clients"))
    except Exception as e:
        logger.error(f"delete_client_crm_only error: {e}")
        return f"Error: {e}", 500
