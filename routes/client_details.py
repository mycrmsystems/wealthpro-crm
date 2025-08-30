"""
WealthPro CRM - Client Details (Summary) Page
FULL FILE — drop in as routes/client_details.py

- Details page at: /clients/<client_id>/details
- Shows quick links to key areas and a read-only snapshot of portfolio holdings
"""

import io
import json
import logging
from typing import Dict, List, Optional

from flask import Blueprint, render_template_string, redirect, url_for, session
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaIoBaseDownload

from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)
client_details_bp = Blueprint("client_details", __name__)

def _require_creds():
    if "credentials" not in session:
        return None
    return Credentials(**session["credentials"])

# Helpers copied (read-only) to fetch holdings.json
def _find_child_folder(drive_service, parent_id: str, name: str) -> Optional[str]:
    safe = (name or "").replace("'", "’")
    q = (
        f"'{parent_id}' in parents and "
        "mimeType='application/vnd.google-apps.folder' and "
        f"name='{safe}' and trashed=false"
    )
    resp = drive_service.files().list(q=q, fields="files(id,name)", pageSize=1).execute()
    files = resp.get("files", []) or []
    return files[0]["id"] if files else None

def _ensure_folder(drive_service, parent_id: str, name: str) -> str:
    fid = _find_child_folder(drive_service, parent_id, name)
    if fid:
        return fid
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
    created = drive_service.files().create(body=meta, fields="id").execute()
    return created["id"]

def _load_holdings(drive: SimpleGoogleDrive, client_id: str) -> List[Dict]:
    """Read holdings if present; return [] if missing."""
    try:
        service = drive.drive
        portfolio_id = _ensure_folder(service, client_id, "Portfolio")
        q = (
            f"'{portfolio_id}' in parents and "
            "mimeType!='application/vnd.google-apps.folder' and "
            "name='holdings.json' and trashed=false"
        )
        resp = service.files().list(q=q, fields="files(id,name)", pageSize=1).execute()
        files = resp.get("files", []) or []
        if not files:
            return []
        file_id = files[0]["id"]
        req = service.files().get_media(fileId=file_id)
        stream = io.BytesIO()
        downloader = MediaIoBaseDownload(stream, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        stream.seek(0)
        content = stream.read().decode("utf-8")
        data = json.loads(content)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Details: failed to load holdings for {client_id}: {e}")
        return []

@client_details_bp.route("/clients/<client_id>/details")
def client_details(client_id):
    """
    Summary page for a single client:
    - Header + quick links (Profile, Tasks, Communications, Reviews, Portfolio, Google Folder)
    - Read-only snapshot of holdings with button to edit in Portfolio
    """
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)
        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c["client_id"] == client_id), None)
        if not client:
            return "Client not found", 404

        holdings = _load_holdings(drive, client_id)

        # Build Google Drive link for convenience (web view of client folder)
        drive_link = f"https://drive.google.com/drive/folders/{client_id}"

        return render_template_string(
            """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - {{ client.display_name }} Details</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <nav class="bg-gradient-to-r from-slate-800 to-blue-600 text-white shadow">
        <div class="max-w-7xl mx-auto px-6">
            <div class="h-16 flex items-center justify-between">
                <h1 class="text-lg font-bold">WealthPro CRM</h1>
                <div class="flex gap-6">
                    <a href="/" class="hover:text-blue-200">Dashboard</a>
                    <a href="/clients" class="hover:text-blue-200">Clients</a>
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="flex items-center justify-between mb-6">
            <div>
                <h2 class="text-2xl font-bold">{{ client.display_name }}</h2>
                <p class="text-gray-600 text-sm mt-1">Client Details & Overview</p>
            </div>
            <a href="/clients" class="px-4 py-2 rounded bg-gray-700 text-white hover:bg-gray-800">Back to Clients</a>
        </div>

        <!-- Quick Actions -->
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
            <a href="/clients/{{ client.client_id }}/profile" class="block text-center px-3 py-2 bg-white shadow rounded hover:bg-gray-50">Profile</a>
            <a href="/clients/{{ client.client_id }}/tasks" class="block text-center px-3 py-2 bg-white shadow rounded hover:bg-gray-50">Tasks</a>
            <a href="/clients/{{ client.client_id }}/communications" class="block text-center px-3 py-2 bg-white shadow rounded hover:bg-gray-50">Comms</a>
            <a href="/reviews/{{ client.client_id }}" class="block text-center px-3 py-2 bg-white shadow rounded hover:bg-gray-50">Reviews</a>
            <a href="/clients/{{ client.client_id }}/portfolio" class="block text-center px-3 py-2 bg-white shadow rounded hover:bg-gray-50">Portfolio</a>
            <a href="{{ drive_link }}" target="_blank" class="block text-center px-3 py-2 bg-white shadow rounded hover:bg-gray-50">Google Folder</a>
        </div>

        <!-- Portfolio Snapshot -->
        <div class="bg-white shadow rounded-lg overflow-hidden">
            <div class="px-6 py-4 border-b flex items-center justify-between">
                <h3 class="font-semibold">Portfolio Snapshot</h3>
                <a href="/clients/{{ client.client_id }}/portfolio" class="text-blue-600 hover:underline">Edit in Portfolio</a>
            </div>
            <div class="p-6">
                {% if holdings %}
                <div class="overflow-x-auto">
                    <table class="min-w-full text-sm">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-3 py-2 text-left font-medium text-gray-600">Type</th>
                                <th class="px-3 py-2 text-left font-medium text-gray-600">Provider</th>
                                <th class="px-3 py-2 text-left font-medium text-gray-600">Account</th>
                                <th class="px-3 py-2 text-left font-medium text-gray-600">Value</th>
                                <th class="px-3 py-2 text-left font-medium text-gray-600">Currency</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y">
                            {% for h in holdings %}
                            <tr>
                                <td class="px-3 py-2">{{ h.product_type or '' }}</td>
                                <td class="px-3 py-2">{{ h.provider or '' }}</td>
                                <td class="px-3 py-2">
                                    <div class="font-medium">{{ h.account_name or '' }}</div>
                                    <div class="text-gray-500">{{ h.account_number or '' }}</div>
                                </td>
                                <td class="px-3 py-2">
                                    {% set v = (h.value or 0) | float %}
                                    £{{ '{:,.2f}'.format(v) if (h.currency in ['', None, 'GBP']) else '{:,.2f}'.format(v) }}
                                </td>
                                <td class="px-3 py-2">{{ h.currency or 'GBP' }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                {% else %}
                    <p class="text-gray-500">No holdings recorded yet. Click “Edit in Portfolio” to add them.</p>
                {% endif %}
            </div>
        </div>
    </main>
</body>
</html>
            """,
            client=client,
            holdings=holdings,
            drive_link=drive_link,
        )
    except Exception as e:
        logger.exception("Client details error")
        return f"Error: {e}", 500
