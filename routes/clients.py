# routes/clients.py

import logging
from typing import Optional
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)

clients_bp = Blueprint('clients', __name__)


# ------------------------------
# Drive helpers (route-local)
# ------------------------------
def _list_folders(drive_service, parent_id: str):
    folders = []
    page = None
    q = (
        f"'{parent_id}' in parents and "
        "mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    while True:
        resp = drive_service.files().list(
            q=q, fields="nextPageToken, files(id,name)", pageToken=page, pageSize=1000
        ).execute()
        folders.extend(resp.get("files", []))
        page = resp.get("nextPageToken")
        if not page:
            break
    return folders


def _get_letter_folders(drive_service, parent_id: str):
    out = []
    for f in _list_folders(drive_service, parent_id):
        nm = (f.get("name") or "").strip()
        if len(nm) == 1 and nm.isalpha() and nm.upper() == nm:
            out.append(f)
    return out


def _ensure_folder(drive_service, parent_id: str, name: str) -> str:
    safe = (name or "").replace("'", "’")
    q = (
        f"'{parent_id}' in parents and "
        "mimeType='application/vnd.google-apps.folder' and "
        f"name='{safe}' and trashed=false"
    )
    resp = drive_service.files().list(q=q, fields="files(id,name)", pageSize=1).execute()
    files = resp.get("files", [])
    if files:
        return files[0]["id"]
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
    created = drive_service.files().create(body=body, fields="id,name").execute()
    return created["id"]


def _get_parent(drive_service, file_id: str) -> Optional[str]:
    meta = drive_service.files().get(fileId=file_id, fields="id,parents").execute()
    parents = meta.get("parents") or []
    return parents[0] if parents else None


def _get_ancestor_names(drive_service, file_id: str, max_hops: int = 6):
    names = []
    current = _get_parent(drive_service, file_id)
    hops = 0
    while current and hops < max_hops:
        meta = drive_service.files().get(fileId=current, fields="id,name,parents").execute()
        names.append(meta.get("name") or "")
        parents = meta.get("parents") or []
        current = parents[0] if parents else None
        hops += 1
    return names  # from immediate parent upwards


def _is_archived(drive: SimpleGoogleDrive, client_folder_id: str) -> bool:
    # If any ancestor is named "Archived Clients", treat as archived
    names = _get_ancestor_names(drive.drive, client_folder_id)
    return any(n.strip().lower() == "archived clients" for n in names)


def _ensure_category_letter(drive: SimpleGoogleDrive, category_name: str, display_name: str) -> str:
    """
    Ensure a category, then its A–Z letter folder, and return the letter folder id.
    """
    root = drive.root_folder_id
    category_id = _ensure_folder(drive.drive, root, category_name)

    first = (display_name[:1] or "#").upper()
    letter = first if first.isalpha() else "#"
    letter_id = _ensure_folder(drive.drive, category_id, letter)
    return letter_id


def _active_letter_destination(drive: SimpleGoogleDrive, display_name: str) -> str:
    """
    Find where active clients live:
      - If letters directly under ROOT, use ROOT.
      - Else find first category with A–Z (not 'Archived Clients'), and use that.
      - Else fall back to ROOT.
    Then ensure the letter and return its id.
    """
    root = drive.root_folder_id
    # letters at root?
    letters = _get_letter_folders(drive.drive, root)
    if letters:
        first = (display_name[:1] or "#").upper()
        letter = first if first.isalpha() else "#"
        return _ensure_folder(drive.drive, root, letter)

    # otherwise, find first category that contains letters (not Archived Clients)
    for cat in _list_folders(drive.drive, root):
        nm = (cat.get("name") or "").strip()
        if nm.lower() == "archived clients":
            continue
        if _get_letter_folders(drive.drive, cat["id"]):
            first = (display_name[:1] or "#").upper()
            letter = first if first.isalpha() else "#"
            return _ensure_folder(drive.drive, cat["id"], letter)

    # fallback: root
    first = (display_name[:1] or "#").upper()
    letter = first if first.isalpha() else "#"
    return _ensure_folder(drive.drive, root, letter)


def _move_folder(drive_service, folder_id: str, new_parent_id: str):
    meta = drive_service.files().get(fileId=folder_id, fields="id,parents").execute()
    prev = ",".join(meta.get("parents", [])) if meta.get("parents") else ""
    drive_service.files().update(
        fileId=folder_id,
        addParents=new_parent_id,
        removeParents=prev,
        fields="id,parents"
    ).execute()


# ------------------------------
# Routes
# ------------------------------
@clients_bp.route('/clients')
def clients():
    """List clients with full action set on each row."""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        clients = drive.get_clients_enhanced()

        # add folder_url & archived flag
        for c in clients:
            fid = c.get('folder_id') or c.get('client_id')
            c['folder_url'] = f"https://drive.google.com/drive/folders/{fid}" if fid else None
            c['is_archived'] = _is_archived(drive, c['client_id'])

        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Clients</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: "Inter", sans-serif; }
        .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); }
        .chip { font-size: 12px; padding: 2px 8px; border-radius: 9999px; }
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
            <p class="text-gray-600">Active and archived clients. Use actions at right.</p>
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
                        <div class="flex items-center gap-3">
                            <div class="font-semibold text-gray-900">{{ c.display_name }}</div>
                            {% if c.is_archived %}
                                <span class="chip bg-yellow-100 text-yellow-800">Archived</span>
                            {% endif %}
                        </div>
                        <div class="text-sm text-gray-600 mt-1">
                            Folder:
                            <a href="{{ c.folder_url }}" class="text-blue-600 underline" target="_blank" rel="noopener">Open in Drive</a>
                        </div>
                        {% if c.portfolio_value is not none %}
                        <div class="text-sm text-gray-600">Portfolio: £{{ "%.2f"|format(c.portfolio_value) }}</div>
                        {% endif %}
                    </div>

                    <div class="flex flex-wrap items-center gap-2">
                        {% if c.folder_url %}
                        <a href="{{ c.folder_url }}" target="_blank" rel="noopener"
                           class="px-3 py-1 text-sm bg-white border border-blue-300 text-blue-700 rounded hover:bg-blue-50">📁 Folder</a>
                        {% endif %}
                        <a href="/clients/{{ c.client_id }}/profile" class="px-3 py-1 text-sm bg-blue-100 text-blue-800 rounded hover:bg-blue-200">Profile</a>
                        <a href="/clients/{{ c.client_id }}/refresh" class="px-3 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200">Refresh</a>
                        <a href="/clients/{{ c.client_id }}/add_task" class="px-3 py-1 text-sm bg-green-100 text-green-800 rounded hover:bg-green-200">Add Task</a>
                        <a href="/clients/{{ c.client_id }}/tasks" class="px-3 py-1 text-sm bg-green-50 text-green-700 rounded hover:bg-green-100">Tasks</a>
                        <a href="/clients/{{ c.client_id }}/communications" class="px-3 py-1 text-sm bg-purple-100 text-purple-800 rounded hover:bg-purple-200">Communications</a>
                        <a href="/clients/{{ c.client_id }}/review/create" class="px-3 py-1 text-sm bg-amber-100 text-amber-800 rounded hover:bg-amber-200">Create Review</a>
                        {% if c.is_archived %}
                            <a href="/clients/{{ c.client_id }}/restore" class="px-3 py-1 text-sm bg-teal-100 text-teal-800 rounded hover:bg-teal-200">Restore</a>
                        {% else %}
                            <a href="/clients/{{ c.client_id }}/archive" class="px-3 py-1 text-sm bg-red-100 text-red-800 rounded hover:bg-red-200">Archive</a>
                        {% endif %}
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
    """Create a new client – Drive subfolders handled by model."""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        if request.method == 'POST':
            display_name = request.form.get('display_name', '').strip()
            if not display_name:
                return "Client name required", 400

            drive.create_client_enhanced_folders(display_name)
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
    """Per-client CRM refresh (does NOT touch Drive contents)."""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))
    try:
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

        fid = client.get('folder_id') or client.get('client_id')
        client['folder_url'] = f"https://drive.google.com/drive/folders/{fid}" if fid else None
        client['is_archived'] = _is_archived(drive, client['client_id'])

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
            {% if client.is_archived %}
            <p class="text-yellow-700 mt-1">This client is archived.</p>
            {% endif %}
        </div>
        <div class="flex gap-2">
            {% if client.folder_url %}
            <a href="{{ client.folder_url }}" target="_blank" rel="noopener" class="px-4 py-2 bg-blue-100 text-blue-800 rounded hover:bg-blue-200">📁 Open Folder</a>
            {% endif %}
            <a href="/clients/{{ client.client_id }}/refresh" class="px-4 py-2 bg-gray-100 rounded hover:bg-gray-200">Refresh</a>
        </div>
    </div>

    <div class="bg-white rounded-lg shadow p-6">
        <div class="flex flex-wrap gap-2">
            <a href="/clients/{{ client.client_id }}/add_task" class="px-3 py-1 text-sm bg-green-100 text-green-800 rounded hover:bg-green-200">Add Task</a>
            <a href="/clients/{{ client.client_id }}/tasks" class="px-3 py-1 text-sm bg-green-50 text-green-700 rounded hover:bg-green-100">Tasks</a>
            <a href="/clients/{{ client.client_id }}/communications" class="px-3 py-1 text-sm bg-purple-100 text-purple-800 rounded hover:bg-purple-200">Communications</a>
            <a href="/clients/{{ client.client_id }}/review/create" class="px-3 py-1 text-sm bg-amber-100 text-amber-800 rounded hover:bg-amber-200">Create Review</a>
            {% if client.is_archived %}
                <a href="/clients/{{ client.client_id }}/restore" class="px-3 py-1 text-sm bg-teal-100 text-teal-800 rounded hover:bg-teal-200">Restore</a>
            {% else %}
                <a href="/clients/{{ client.client_id }}/archive" class="px-3 py-1 text-sm bg-red-100 text-red-800 rounded hover:bg-red-200">Archive</a>
            {% endif %}
        </div>
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


@clients_bp.route('/clients/<client_id>/archive')
def archive_client(client_id):
    """Move the client folder to 'Archived Clients' A–Z. Data is NOT deleted."""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        # fetch client name
        all_clients = drive.get_clients_enhanced()
        client = next((c for c in all_clients if c['client_id'] == client_id), None)
        if not client:
            return "Client not found", 404

        # Ensure category + letter
        letter_parent = _ensure_category_letter(drive, "Archived Clients", client['display_name'])
        _move_folder(drive.drive, client_id, letter_parent)

        return redirect(url_for('clients.clients'))
    except Exception as e:
        logger.error(f"Archive client error: {e}")
        return f"Error: {e}", 500


@clients_bp.route('/clients/<client_id>/restore')
def restore_client(client_id):
    """Restore the client folder back to the active A–Z structure."""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        # fetch client name
        all_clients = drive.get_clients_enhanced()
        client = next((c for c in all_clients if c['client_id'] == client_id), None)
        if not client:
            return "Client not found", 404

        letter_parent = _active_letter_destination(drive, client['display_name'])
        _move_folder(drive.drive, client_id, letter_parent)

        return redirect(url_for('clients.clients'))
    except Exception as e:
        logger.error(f"Restore client error: {e}")
        return f"Error: {e}", 500


@clients_bp.route('/clients/<client_id>/review/create')
def create_review(client_id):
    """Create current year review pack and docs for this client."""
    if 'credentials' not in session:
        return redirect(url_for('auth.authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c['client_id'] == client_id), None)
        if not client:
            return "Client not found", 404

        drive.create_review_pack_for_client(client)
        return redirect(url_for('clients.client_profile', client_id=client_id))
    except Exception as e:
        logger.error(f"Create review error: {e}")
        return f"Error: {e}", 500
