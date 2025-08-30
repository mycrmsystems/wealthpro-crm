"""
WealthPro CRM - Client Portfolio Routes
FULL FILE — drop in as routes/portfolio.py

- Per-client Portfolio page at: /clients/<client_id>/portfolio
- Add/Edit/Delete holdings in the CRM
- Data saved to Google Drive at: <Client>/Portfolio/holdings.json
"""

import io
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)
portfolio_bp = Blueprint("portfolio", __name__)

# ------------------------------
# Helpers
# ------------------------------
def _require_creds():
    if "credentials" not in session:
        return None
    return Credentials(**session["credentials"])

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

def _ensure_client_portfolio_folder(drive: SimpleGoogleDrive, client_id: str) -> str:
    service = drive.drive
    return _ensure_folder(service, client_id, "Portfolio")

def _get_or_create_holdings_file(drive: SimpleGoogleDrive, portfolio_folder_id: str) -> str:
    service = drive.drive
    q = (
        f"'{portfolio_folder_id}' in parents and "
        "mimeType!='application/vnd.google-apps.folder' and "
        "name='holdings.json' and trashed=false"
    )
    resp = service.files().list(q=q, fields="files(id,name)", pageSize=1).execute()
    files = resp.get("files", []) or []
    if files:
        return files[0]["id"]
    data = json.dumps([], ensure_ascii=False, indent=2).encode("utf-8")
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="application/json", resumable=False)
    meta = {"name": "holdings.json", "parents": [portfolio_folder_id]}
    created = service.files().create(body=meta, media_body=media, fields="id").execute()
    return created["id"]

def _load_holdings(drive: SimpleGoogleDrive, client_id: str) -> List[Dict]:
    try:
        service = drive.drive
        pfid = _ensure_client_portfolio_folder(drive, client_id)
        file_id = _get_or_create_holdings_file(drive, pfid)
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
        logger.error(f"Failed to load holdings for client {client_id}: {e}")
        return []

def _save_holdings(drive: SimpleGoogleDrive, client_id: str, holdings: List[Dict]) -> bool:
    try:
        service = drive.drive
        pfid = _ensure_client_portfolio_folder(drive, client_id)
        file_id = _get_or_create_holdings_file(drive, pfid)
        data = json.dumps(holdings, ensure_ascii=False, indent=2).encode("utf-8")
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype="application/json", resumable=False)
        service.files().update(fileId=file_id, media_body=media).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save holdings for client {client_id}: {e}")
        return False

def _find_client(drive: SimpleGoogleDrive, client_id: str) -> Optional[Dict]:
    clients = drive.get_clients_enhanced()
    return next((c for c in clients if c["client_id"] == client_id), None)

def _new_holding_id() -> str:
    return "H" + datetime.now().strftime("%Y%m%d%H%M%S%f")

# ------------------------------
# Routes
# ------------------------------
@portfolio_bp.route("/clients/<client_id>/portfolio", methods=["GET"])
def portfolio_home(client_id):
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))
    try:
        drive = SimpleGoogleDrive(creds)
        client = _find_client(drive, client_id)
        if not client:
            return "Client not found", 404
        holdings = _load_holdings(drive, client_id)

        return render_template_string(
            """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - {{ client.display_name }} Portfolio</title>
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
                <h2 class="text-2xl font-bold">{{ client.display_name }} — Portfolio</h2>
                <p class="text-gray-600 text-sm mt-1">Saved in Google Drive → {{ client.display_name }} / Portfolio / holdings.json</p>
            </div>
            <a href="/clients/{{ client.client_id }}/profile" class="px-4 py-2 rounded bg-gray-700 text-white hover:bg-gray-800">Back to Profile</a>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div class="lg:col-span-2">
                <div class="bg-white shadow rounded-lg overflow-hidden">
                    <div class="px-6 py-4 border-b">
                        <h3 class="font-semibold">Holdings</h3>
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
                                        <th class="px-3 py-2 text-left font-medium text-gray-600">Actions</th>
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
                                        <td class="px-3 py-2">
                                            <div class="flex gap-2">
                                                <button onclick="openEdit('{{ h.id }}')" class="px-2 py-1 text-xs rounded bg-blue-100 text-blue-800 hover:bg-blue-200">Edit</button>
                                                <form method="POST" action="/clients/{{ client.client_id }}/portfolio/{{ h.id }}/delete" onsubmit="return confirm('Delete this holding?');">
                                                    <button class="px-2 py-1 text-xs rounded bg-red-100 text-red-800 hover:bg-red-200">Delete</button>
                                                </form>
                                            </div>
                                            <div id="edit-{{ h.id }}" class="hidden mt-3">
                                                <form method="POST" action="/clients/{{ client.client_id }}/portfolio/{{ h.id }}/edit" class="space-y-2 bg-gray-50 p-3 rounded">
                                                    <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
                                                        <input type="text" name="product_type" value="{{ h.product_type or '' }}" placeholder="Type" class="px-2 py-1 border rounded">
                                                        <input type="text" name="provider" value="{{ h.provider or '' }}" placeholder="Provider" class="px-2 py-1 border rounded">
                                                        <input type="text" name="account_name" value="{{ h.account_name or '' }}" placeholder="Account Name" class="px-2 py-1 border rounded">
                                                    </div>
                                                    <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
                                                        <input type="text" name="account_number" value="{{ h.account_number or '' }}" placeholder="Account Number/Ref" class="px-2 py-1 border rounded">
                                                        <input type="number" step="0.01" name="value" value="{{ h.value or '' }}" placeholder="Value" class="px-2 py-1 border rounded">
                                                        <input type="text" name="currency" value="{{ h.currency or 'GBP' }}" placeholder="Currency" class="px-2 py-1 border rounded">
                                                    </div>
                                                    <div>
                                                        <textarea name="underlying" rows="2" placeholder="Underlying investments" class="w-full px-2 py-1 border rounded">{{ h.underlying or '' }}</textarea>
                                                    </div>
                                                    <div>
                                                        <textarea name="notes" rows="2" placeholder="Notes" class="w-full px-2 py-1 border rounded">{{ h.notes or '' }}</textarea>
                                                    </div>
                                                    <div class="text-right">
                                                        <button class="px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 text-sm">Save Changes</button>
                                                    </div>
                                                </form>
                                            </div>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                        {% else %}
                        <div class="text-gray-500">No holdings yet.</div>
                        {% endif %}
                    </div>
                </div>
            </div>

            <div>
                <div class="bg-white shadow rounded-lg p-6">
                    <h3 class="font-semibold mb-4">Add Holding</h3>
                    <form method="POST" action="/clients/{{ client.client_id }}/portfolio/add" class="space-y-3">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div>
                                <label class="block text-sm text-gray-700 mb-1">Type *</label>
                                <input name="product_type" required placeholder="Investment or Pension" class="w-full px-3 py-2 border rounded">
                            </div>
                            <div>
                                <label class="block text-sm text-gray-700 mb-1">Provider *</label>
                                <input name="provider" required placeholder="e.g., Fidelity, Aviva" class="w-full px-3 py-2 border rounded">
                            </div>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div>
                                <label class="block text-sm text-gray-700 mb-1">Account Name *</label>
                                <input name="account_name" required placeholder="e.g., SIPP, GIA" class="w-full px-3 py-2 border rounded">
                            </div>
                            <div>
                                <label class="block text-sm text-gray-700 mb-1">Account No./Ref</label>
                                <input name="account_number" placeholder="Reference/Policy" class="w-full px-3 py-2 border rounded">
                            </div>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div>
                                <label class="block text-sm text-gray-700 mb-1">Value *</label>
                                <input type="number" step="0.01" name="value" required placeholder="0.00" class="w-full px-3 py-2 border rounded">
                            </div>
                            <div>
                                <label class="block text-sm text-gray-700 mb-1">Currency</label>
                                <input name="currency" value="GBP" class="w-full px-3 py-2 border rounded">
                            </div>
                        </div>
                        <div>
                            <label class="block text-sm text-gray-700 mb-1">Underlying investments</label>
                            <textarea name="underlying" rows="3" placeholder="e.g., Fund A 40%, Fund B 60%" class="w-full px-3 py-2 border rounded"></textarea>
                        </div>
                        <div>
                            <label class="block text-sm text-gray-700 mb-1">Notes</label>
                            <textarea name="notes" rows="2" placeholder="Any relevant notes" class="w-full px-3 py-2 border rounded"></textarea>
                        </div>
                        <div class="text-right">
                            <button class="px-4 py-2 rounded bg-green-600 text-white hover:bg-green-700">Add Holding</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </main>

    <script>
    function openEdit(id) {
        const el = document.getElementById('edit-' + id);
        if (el) el.classList.toggle('hidden');
    }
    </script>
</body>
</html>
            """,
            client=client,
            holdings=holdings,
        )
    except Exception as e:
        logger.exception("Portfolio page error")
        return f"Error: {e}", 500

@portfolio_bp.route("/clients/<client_id>/portfolio/add", methods=["POST"])
def portfolio_add(client_id):
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))
    try:
        drive = SimpleGoogleDrive(creds)
        client = _find_client(drive, client_id)
        if not client:
            return "Client not found", 404

        holdings = _load_holdings(drive, client_id)
        holding = {
            "id": _new_holding_id(),
            "product_type": (request.form.get("product_type") or "").strip(),
            "provider": (request.form.get("provider") or "").strip(),
            "account_name": (request.form.get("account_name") or "").strip(),
            "account_number": (request.form.get("account_number") or "").strip(),
            "value": float(request.form.get("value") or 0),
            "currency": (request.form.get("currency") or "GBP").strip(),
            "underlying": (request.form.get("underlying") or "").strip(),
            "notes": (request.form.get("notes") or "").strip(),
            "updated": datetime.utcnow().isoformat() + "Z",
        }
        holdings.append(holding)
        _save_holdings(drive, client_id, holdings)
        return redirect(url_for("portfolio.portfolio_home", client_id=client_id))
    except Exception as e:
        logger.exception("Portfolio add error")
        return f"Error: {e}", 500

@portfolio_bp.route("/clients/<client_id>/portfolio/<holding_id>/edit", methods=["POST"])
def portfolio_edit(client_id, holding_id):
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))
    try:
        drive = SimpleGoogleDrive(creds)
        client = _find_client(drive, client_id)
        if not client:
            return "Client not found", 404
        holdings = _load_holdings(drive, client_id)
        idx = next((i for i, h in enumerate(holdings) if h.get("id") == holding_id), None)
        if idx is None:
            return "Holding not found", 404
        h = holdings[idx]
        h["product_type"] = (request.form.get("product_type") or h.get("product_type") or "").strip()
        h["provider"] = (request.form.get("provider") or h.get("provider") or "").strip()
        h["account_name"] = (request.form.get("account_name") or h.get("account_name") or "").strip()
        h["account_number"] = (request.form.get("account_number") or h.get("account_number") or "").strip()
        h["value"] = float(request.form.get("value") or h.get("value") or 0)
        h["currency"] = (request.form.get("currency") or h.get("currency") or "GBP").strip()
        h["underlying"] = (request.form.get("underlying") or h.get("underlying") or "").strip()
        h["notes"] = (request.form.get("notes") or h.get("notes") or "").strip()
        h["updated"] = datetime.utcnow().isoformat() + "Z"
        holdings[idx] = h
        _save_holdings(drive, client_id, holdings)
        return redirect(url_for("portfolio.portfolio_home", client_id=client_id))
    except Exception as e:
        logger.exception("Portfolio edit error")
        return f"Error: {e}", 500

@portfolio_bp.route("/clients/<client_id>/portfolio/<holding_id>/delete", methods=["POST"])
def portfolio_delete(client_id, holding_id):
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))
    try:
        drive = SimpleGoogleDrive(creds)
        client = _find_client(drive, client_id)
        if not client:
            return "Client not found", 404
        holdings = _load_holdings(drive, client_id)
        new_holdings = [h for h in holdings if h.get("id") != holding_id]
        _save_holdings(drive, client_id, new_holdings)
        return redirect(url_for("portfolio.portfolio_home", client_id=client_id))
    except Exception as e:
        logger.exception("Portfolio delete error")
        return f"Error: {e}", 500
