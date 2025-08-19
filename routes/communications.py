# routes/communications.py
"""
WealthPro CRM — Communications (Drive-only)

- GET/POST /clients/<client_id>/communications
    * Ensures a 'Communications' folder under the client folder
    * POST creates a .txt note file with structured content
    * GET lists existing communication files (newest first)

- GET /communications/summary
    * Scans each client's 'Communications' folder
    * Shows the most recent notes across clients (top 20)

This uses only the Google Drive service exposed by SimpleGoogleDrive and its
private helpers (_ensure_folder, _upload_bytes). No changes to the model are required.
"""

import io
import logging
from datetime import datetime
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaIoBaseUpload
from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)
communications_bp = Blueprint("communications", __name__)


def _require_creds():
    if "credentials" not in session:
        return None
    return Credentials(**session["credentials"])


def _ensure_comm_folder(drive: SimpleGoogleDrive, client_folder_id: str) -> str:
    """Ensure the Communications folder exists under the client folder and return its id."""
    return drive._ensure_folder(client_folder_id, "Communications")  # noqa: SLF001 (accessing private helper by design)


def _list_comm_files(drive: SimpleGoogleDrive, comm_folder_id: str):
    """List non-folder files (notes) in the Communications folder, newest first."""
    files = []
    page = None
    service = drive.drive  # googleapiclient service
    while True:
        resp = service.files().list(
            q=f"'{comm_folder_id}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false",
            fields="nextPageToken, files(id,name,modifiedTime,createdTime,webViewLink,size,mimeType)",
            orderBy="modifiedTime desc",
            pageToken=page,
            pageSize=100,
        ).execute()
        files.extend(resp.get("files", []))
        page = resp.get("nextPageToken")
        if not page:
            break
    return files


def _create_comm_note(drive: SimpleGoogleDrive, comm_folder_id: str, payload: dict) -> str:
    """
    Create a .txt communication note in the Communications folder.
    Filename example: '2025-08-17 14-30 - Phone Call - Subject [COM20250817143055].txt'
    """
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    date = (payload.get("date") or datetime.now().strftime("%Y-%m-%d")).strip()
    time_ = (payload.get("time") or "").replace(":", "-").strip()
    ctype = (payload.get("type") or "Note").strip()
    subj = (payload.get("subject") or "No Subject").strip()

    base = f"{date}"
    if time_:
        base += f" {time_}"
    filename = f"{base} - {ctype} - {subj} [COM{ts}].txt"

    lines = [
        f"Communication ID: COM{ts}",
        f"Date: {payload.get('date', '')}",
        f"Time: {payload.get('time', '')}",
        f"Type: {ctype}",
        f"Subject: {subj}",
        f"Duration: {payload.get('duration','')}",
        f"Outcome: {payload.get('outcome','')}",
        f"Follow Up Required: {payload.get('follow_up_required','No')}",
        f"Follow Up Date: {payload.get('follow_up_date','')}",
        f"Created By: {payload.get('created_by','')}",
        "",
        "Details:",
        (payload.get("details") or "").strip(),
    ]
    data = ("\n".join(lines)).encode("utf-8")
    return drive._upload_bytes(comm_folder_id, filename, data, "text/plain")  # noqa: SLF001


@communications_bp.route("/clients/<client_id>/communications", methods=["GET", "POST"])
def client_communications(client_id):
    """Per-client communications page (Drive-only)."""
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)

        # Find the client folder first
        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c["client_id"] == client_id), None)
        if not client:
            return "Client not found", 404

        client_folder_id = client.get("folder_id") or client.get("client_id")
        comm_folder_id = _ensure_comm_folder(drive, client_folder_id)

        if request.method == "POST":
            comm_data = {
                "date": request.form.get("date", datetime.now().strftime("%Y-%m-%d")),
                "time": request.form.get("time", ""),
                "type": request.form.get("type", ""),
                "subject": request.form.get("subject", ""),
                "details": request.form.get("details", ""),
                "outcome": request.form.get("outcome", ""),
                "duration": request.form.get("duration", ""),
                "follow_up_required": request.form.get("follow_up_required", "No"),
                "follow_up_date": request.form.get("follow_up_date", ""),
                "created_by": "System User",
            }
            _ = _create_comm_note(drive, comm_folder_id, comm_data)
            return redirect(url_for("communications.client_communications", client_id=client_id))

        # GET: list recent communications (files in Communications/)
        notes = _list_comm_files(drive, comm_folder_id)

        return render_template_string(
            """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Communications</title>
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

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Communications: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Notes are stored in Google Drive → Communications</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Add Communication -->
            <div class="lg:col-span-1">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold mb-4">Add Communication</h3>
                    <form method="POST" class="space-y-4">
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Date *</label>
                                <input type="date" name="date" value="{{ now_date }}" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Time</label>
                                <input type="time" name="time" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Type *</label>
                            <select name="type" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                <option value="">Select...</option>
                                <option>Phone Call</option>
                                <option>Email</option>
                                <option>Meeting</option>
                                <option>Video Call</option>
                                <option>Text Message</option>
                                <option>Letter</option>
                                <option>Other</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Duration</label>
                            <input type="text" name="duration" placeholder="e.g., 15 minutes, 1 hour" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Subject</label>
                            <input type="text" name="subject" placeholder="Brief subject" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Details</label>
                            <textarea name="details" rows="4" placeholder="What was discussed?" class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Outcome</label>
                            <textarea name="outcome" rows="2" placeholder="Result / next steps" class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Follow Up?</label>
                                <select name="follow_up_required" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                    <option>No</option>
                                    <option>Yes</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Follow Up Date</label>
                                <input type="date" name="follow_up_date" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                        </div>

                        <div class="bg-blue-50 p-3 rounded">
                            <p class="text-xs text-blue-700">💾 Saves in: Communications/</p>
                        </div>

                        <button class="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                            Add Communication
                        </button>
                    </form>
                </div>
            </div>

            <!-- Communications list -->
            <div class="lg:col-span-2">
                <div class="bg-white rounded-lg shadow">
                    <div class="p-6 border-b">
                        <h3 class="text-lg font-semibold">Recent Communications</h3>
                    </div>
                    <div class="p-6">
                        {% if notes %}
                            <div class="space-y-4">
                                {% for f in notes %}
                                <div class="border-l-4 border-gray-500 pl-4 py-3 bg-gray-50 rounded-r">
                                    <div class="flex justify-between items-start">
                                        <div class="flex-1">
                                            <h4 class="font-semibold text-gray-900">{{ f.name }}</h4>
                                            <p class="text-sm text-gray-600">Modified: {{ f.modifiedTime[:10] }} • Created: {{ f.createdTime[:10] }}</p>
                                        </div>
                                        <a href="https://drive.google.com/file/d/{{ f.id }}/view"
                                           target="_blank"
                                           class="text-blue-600 hover:text-blue-800 text-sm">Open</a>
                                    </div>
                                </div>
                                {% endfor %}
                            </div>
                        {% else %}
                            <p class="text-gray-500 text-center py-8">No communications recorded yet.</p>
                        {% endif %}
                    </div>
                </div>

                <div class="mt-6">
                    <a href="/clients" class="bg-gray-600 text-white px-6 py-3 rounded-lg hover:bg-gray-700">Back to Clients</a>
                </div>
            </div>
        </div>
    </main>
</body>
</html>
            """,
            client=client,
            notes=notes,
            now_date=datetime.now().strftime("%Y-%m-%d"),
        )
    except Exception as e:
        logger.exception("Client communications error")
        return f"Error: {e}", 500


@communications_bp.route("/communications/summary")
def communications_summary():
    """Overview of the most recent communications across all clients (Drive-only)."""
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)
        clients = drive.get_clients_enhanced()

        recent = []
        for c in clients:
            client_folder_id = c.get("folder_id") or c.get("client_id")
            comm_folder_id = drive._ensure_folder(client_folder_id, "Communications")  # noqa: SLF001
            files = _list_comm_files(drive, comm_folder_id)
            for f in files[:5]:  # only the latest 5 per client
                recent.append({
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "modifiedTime": f.get("modifiedTime"),
                    "client_name": c.get("display_name"),
                })

        # Sort by modifiedTime desc
        recent.sort(key=lambda x: x.get("modifiedTime", ""), reverse=True)
        recent = recent[:20]  # top 20 overall

        return render_template_string(
            """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Communications Summary</title>
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

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Recent Communications</h1>
            <p class="text-gray-600 mt-2">Across all clients (latest 20)</p>
        </div>

        <div class="bg-white rounded-lg shadow">
            <div class="p-6 border-b">
                <h3 class="text-lg font-semibold">Latest Notes</h3>
            </div>
            <div class="p-6">
                {% if recent %}
                    <div class="space-y-4">
                        {% for r in recent %}
                        <div class="border-l-4 border-gray-500 pl-4 py-3 bg-gray-50 rounded-r">
                            <div class="flex justify-between items-start">
                                <div class="flex-1">
                                    <h4 class="font-semibold text-gray-900">{{ r.name }}</h4>
                                    <p class="text-sm text-gray-600">{{ r.client_name }} • Modified: {{ r.modifiedTime[:10] }}</p>
                                </div>
                                <a href="https://drive.google.com/file/d/{{ r.id }}/view"
                                   target="_blank"
                                   class="text-blue-600 hover:text-blue-800 text-sm">Open</a>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                {% else %}
                    <p class="text-gray-500 text-center py-8">No communications found.</p>
                {% endif %}
            </div>
        </div>
    </main>
</body>
</html>
            """,
            recent=recent,
        )
    except Exception as e:
        logger.exception("Communications summary error")
        return f"Error: {e}", 500
