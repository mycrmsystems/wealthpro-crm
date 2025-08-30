# routes/portfolio.py
#
# Client Portfolio (Investments & Pensions) UI + persistence.
# Writes/reads JSON at: Client Folder / Client Data / profile.json on Google Drive.
# Self-contained (Tailwind via CDN). No other features changed.

import logging
from datetime import datetime
from typing import Dict, List

from flask import Blueprint, render_template_string, request, redirect, url_for, session, abort
from google.oauth2.credentials import Credentials

from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)
portfolio_bp = Blueprint("portfolio", __name__)

def _new_id(prefix: str) -> str:
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S%f')[-10:]}"

def _coerce_float(val):
    try:
        return float(val)
    except Exception:
        return 0.0

def _recompute_total(profile: Dict) -> float:
    total = 0.0
    for it in profile.get("investments", []):
        total += _coerce_float(it.get("value", 0))
    for it in profile.get("pensions", []):
        total += _coerce_float(it.get("value", 0))
    profile["computed_total"] = float(total)
    return profile["computed_total"]

def _find_client(clients: List[Dict], client_id: str):
    return next((c for c in clients if c.get("client_id") == client_id), None)


@portfolio_bp.route("/clients/<client_id>/portfolio", methods=["GET", "POST"])
def client_portfolio(client_id):
    """
    Portfolio page per client:
      - Show investments & pensions in tables (edit/delete inline)
      - Add new investment or pension
      - Update free-form notes
    All changes persist to Client Data/profile.json via SimpleGoogleDrive.
    """
    if "credentials" not in session:
        return redirect(url_for("auth.authorize"))

    try:
        credentials = Credentials(**session["credentials"])
        drive = SimpleGoogleDrive(credentials)

        clients = drive.get_clients_enhanced()
        client = _find_client(clients, client_id)
        if not client:
            abort(404, description="Client not found")

        # Load (or lazily init) profile.json
        profile = drive.read_profile(client_id)
        profile.setdefault("investments", [])
        profile.setdefault("pensions", [])
        profile.setdefault("notes", "")
        _recompute_total(profile)

        if request.method == "POST":
            action = request.form.get("action", "").strip()

            if action == "add_investment":
                item = {
                    "id": _new_id("INV"),
                    "name": request.form.get("name", "").strip(),
                    "provider": request.form.get("provider", "").strip(),
                    "account_number": request.form.get("account_number", "").strip(),
                    "value": _coerce_float(request.form.get("value", "")),
                    "currency": request.form.get("currency", "GBP").strip() or "GBP",
                    "as_of": request.form.get("as_of", datetime.now().strftime("%Y-%m-%d")),
                    "notes": request.form.get("item_notes", "").strip(),
                    "holdings": [],
                }
                profile["investments"].append(item)
                _recompute_total(profile)
                drive.write_profile(client_id, profile)
                return redirect(url_for("portfolio.client_portfolio", client_id=client_id))

            if action == "add_pension":
                item = {
                    "id": _new_id("PEN"),
                    "name": request.form.get("name", "").strip(),
                    "provider": request.form.get("provider", "").strip(),
                    "plan_number": request.form.get("plan_number", "").strip(),
                    "value": _coerce_float(request.form.get("value", "")),
                    "currency": request.form.get("currency", "GBP").strip() or "GBP",
                    "as_of": request.form.get("as_of", datetime.now().strftime("%Y-%m-%d")),
                    "notes": request.form.get("item_notes", "").strip(),
                }
                profile["pensions"].append(item)
                _recompute_total(profile)
                drive.write_profile(client_id, profile)
                return redirect(url_for("portfolio.client_portfolio", client_id=client_id))

            if action == "delete_item":
                item_id = request.form.get("item_id", "")
                group = request.form.get("group", "")
                if group in ("investments", "pensions"):
                    profile[group] = [x for x in profile.get(group, []) if x.get("id") != item_id]
                    _recompute_total(profile)
                    drive.write_profile(client_id, profile)
                return redirect(url_for("portfolio.client_portfolio", client_id=client_id))

            if action == "edit_item":
                item_id = request.form.get("item_id", "")
                group = request.form.get("group", "")
                if group in ("investments", "pensions"):
                    items = profile.get(group, [])
                    for x in items:
                        if x.get("id") == item_id:
                            x["name"] = request.form.get("name", x.get("name","")).strip()
                            x["provider"] = request.form.get("provider", x.get("provider","")).strip()
                            if group == "investments":
                                x["account_number"] = request.form.get("account_number", x.get("account_number","")).strip()
                            else:
                                x["plan_number"] = request.form.get("plan_number", x.get("plan_number","")).strip()
                            x["value"] = _coerce_float(request.form.get("value", x.get("value", 0)))
                            x["currency"] = request.form.get("currency", x.get("currency","GBP")).strip() or "GBP"
                            x["as_of"] = request.form.get("as_of", x.get("as_of", "")).strip() or datetime.now().strftime("%Y-%m-%d")
                            x["notes"] = request.form.get("item_notes", x.get("notes","")).strip()
                            break
                    _recompute_total(profile)
                    drive.write_profile(client_id, profile)
                return redirect(url_for("portfolio.client_portfolio", client_id=client_id))

            if action == "save_notes":
                profile["notes"] = request.form.get("notes", "").strip()
                _recompute_total(profile)
                drive.write_profile(client_id, profile)
                return redirect(url_for("portfolio.client_portfolio", client_id=client_id))

        return render_template_string(PORTFOLIO_HTML, client=client, profile=profile, datetime=datetime)

    except Exception as e:
        logger.exception("Portfolio page error")
        return f"Error: {e}", 500


PORTFOLIO_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>WealthPro CRM - {{ client.display_name }} Portfolio</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>body { font-family: Inter, ui-sans-serif, system-ui, -apple-system; }</style>
</head>
<body class="bg-gray-50">
  <nav class="bg-blue-900 text-white">
    <div class="max-w-7xl mx-auto px-6">
      <div class="h-14 flex items-center justify-between">
        <div class="font-semibold">WealthPro CRM</div>
        <div class="space-x-6 text-sm">
          <a href="/" class="hover:text-blue-200">Dashboard</a>
          <a href="/clients" class="hover:text-blue-200">Clients</a>
          <a href="/tasks" class="hover:text-blue-200">Tasks</a>
        </div>
      </div>
    </div>
  </nav>

  <main class="max-w-7xl mx-auto px-6 py-8">
    <div class="mb-6">
      <h1 class="text-2xl font-bold">Portfolio: {{ client.display_name }}</h1>
      <p class="text-gray-600">Track investments & pensions. Saved to Google Drive → Client Data/profile.json</p>
      <div class="mt-3 inline-flex items-center gap-3 p-3 bg-white rounded shadow">
        <div class="text-sm text-gray-600">Total portfolio value</div>
        <div class="text-xl font-semibold">£{{ '%.2f'|format(profile.computed_total|float) }}</div>
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <section class="xl:col-span-2 bg-white rounded-lg shadow">
        <div class="p-5 border-b">
          <h2 class="text-lg font-semibold">Investments</h2>
        </div>
        <div class="p-5 overflow-x-auto">
          {% if profile.investments %}
            <table class="min-w-full text-sm">
              <thead class="text-left text-gray-600">
                <tr>
                  <th class="py-2 pr-4">Name</th>
                  <th class="py-2 pr-4">Provider</th>
                  <th class="py-2 pr-4">Account #</th>
                  <th class="py-2 pr-4">As of</th>
                  <th class="py-2 pr-4">Value</th>
                  <th class="py-2 pr-4">Currency</th>
                  <th class="py-2">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y">
                {% for it in profile.investments %}
                <tr>
                  <td class="py-2 pr-4 font-medium">{{ it.name }}</td>
                  <td class="py-2 pr-4">{{ it.provider }}</td>
                  <td class="py-2 pr-4">{{ it.account_number }}</td>
                  <td class="py-2 pr-4">{{ it.as_of }}</td>
                  <td class="py-2 pr-4">£{{ '%.2f'|format(it.value|float) }}</td>
                  <td class="py-2 pr-4">{{ it.currency or 'GBP' }}</td>
                  <td class="py-2">
                    <details>
                      <summary class="cursor-pointer text-blue-700 hover:underline text-sm">Edit / Delete</summary>
                      <div class="mt-3 p-3 bg-gray-50 rounded">
                        <form method="POST" class="space-y-2">
                          <input type="hidden" name="action" value="edit_item">
                          <input type="hidden" name="group" value="investments">
                          <input type="hidden" name="item_id" value="{{ it.id }}">
                          <div class="grid grid-cols-2 gap-3">
                            <div>
                              <label class="block text-xs text-gray-600">Name</label>
                              <input name="name" value="{{ it.name }}" class="w-full px-3 py-2 border rounded">
                            </div>
                            <div>
                              <label class="block text-xs text-gray-600">Provider</label>
                              <input name="provider" value="{{ it.provider }}" class="w-full px-3 py-2 border rounded">
                            </div>
                            <div>
                              <label class="block text-xs text-gray-600">Account #</label>
                              <input name="account_number" value="{{ it.account_number }}" class="w-full px-3 py-2 border rounded">
                            </div>
                            <div>
                              <label class="block text-xs text-gray-600">As of</label>
                              <input type="date" name="as_of" value="{{ it.as_of }}" class="w-full px-3 py-2 border rounded">
                            </div>
                            <div>
                              <label class="block text-xs text-gray-600">Value (£)</label>
                              <input name="value" value="{{ it.value }}" class="w-full px-3 py-2 border rounded">
                            </div>
                            <div>
                              <label class="block text-xs text-gray-600">Currency</label>
                              <input name="currency" value="{{ it.currency or 'GBP' }}" class="w-full px-3 py-2 border rounded">
                            </div>
                            <div class="col-span-2">
                              <label class="block text-xs text-gray-600">Notes</label>
                              <textarea name="item_notes" rows="2" class="w-full px-3 py-2 border rounded">{{ it.notes }}</textarea>
                            </div>
                          </div>
                          <div class="mt-2 flex items-center gap-2">
                            <button class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Save</button>
                            </form>
                            <form method="POST" onsubmit="return confirm('Delete this investment?');">
                              <input type="hidden" name="action" value="delete_item">
                              <input type="hidden" name="group" value="investments">
                              <input type="hidden" name="item_id" value="{{ it.id }}">
                              <button class="bg-red-600 text-white px-3 py-2 rounded hover:bg-red-700">Delete</button>
                            </form>
                          </div>
                      </div>
                    </details>
                  </td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          {% else %}
            <p class="text-gray-500">No investments yet.</p>
          {% endif %}
        </div>

        <div class="p-5 border-t">
          <h3 class="font-semibold mb-3">Add Investment</h3>
          <form method="POST" class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input type="hidden" name="action" value="add_investment">
            <input name="name" placeholder="Name" class="px-3 py-2 border rounded">
            <input name="provider" placeholder="Provider" class="px-3 py-2 border rounded">
            <input name="account_number" placeholder="Account #" class="px-3 py-2 border rounded">
            <input type="date" name="as_of" value="{{ datetime.now().strftime('%Y-%m-%d') }}" class="px-3 py-2 border rounded">
            <input name="value" placeholder="Value (£)" class="px-3 py-2 border rounded">
            <input name="currency" placeholder="Currency (GBP)" value="GBP" class="px-3 py-2 border rounded">
            <textarea name="item_notes" rows="2" placeholder="Notes" class="md:col-span-3 px-3 py-2 border rounded"></textarea>
            <div class="md:col-span-3">
              <button class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Add Investment</button>
            </div>
          </form>
        </div>
      </section>

      <section class="space-y-6">
        <div class="bg-white rounded-lg shadow">
          <div class="p-5 border-b">
            <h2 class="text-lg font-semibold">Pensions</h2>
          </div>
          <div class="p-5 overflow-x-auto">
            {% if profile.pensions %}
              <table class="min-w-full text-sm">
                <thead class="text-left text-gray-600">
                  <tr>
                    <th class="py-2 pr-4">Name</th>
                    <th class="py-2 pr-4">Provider</th>
                    <th class="py-2 pr-4">Plan #</th>
                    <th class="py-2 pr-4">As of</th>
                    <th class="py-2 pr-4">Value</th>
                    <th class="py-2 pr-4">Currency</th>
                    <th class="py-2">Actions</th>
                  </tr>
                </thead>
                <tbody class="divide-y">
                  {% for it in profile.pensions %}
                  <tr>
                    <td class="py-2 pr-4 font-medium">{{ it.name }}</td>
                    <td class="py-2 pr-4">{{ it.provider }}</td>
                    <td class="py-2 pr-4">{{ it.plan_number }}</td>
                    <td class="py-2 pr-4">{{ it.as_of }}</td>
                    <td class="py-2 pr-4">£{{ '%.2f'|format(it.value|float) }}</td>
                    <td class="py-2 pr-4">{{ it.currency or 'GBP' }}</td>
                    <td class="py-2">
                      <details>
                        <summary class="cursor-pointer text-blue-700 hover:underline text-sm">Edit / Delete</summary>
                        <div class="mt-3 p-3 bg-gray-50 rounded">
                          <form method="POST" class="space-y-2">
                            <input type="hidden" name="action" value="edit_item">
                            <input type="hidden" name="group" value="pensions">
                            <input type="hidden" name="item_id" value="{{ it.id }}">
                            <div class="grid grid-cols-2 gap-3">
                              <div>
                                <label class="block text-xs text-gray-600">Name</label>
                                <input name="name" value="{{ it.name }}" class="w-full px-3 py-2 border rounded">
                              </div>
                              <div>
                                <label class="block text-xs text-gray-600">Provider</label>
                                <input name="provider" value="{{ it.provider }}" class="w-full px-3 py-2 border rounded">
                              </div>
                              <div>
                                <label class="block text-xs text-gray-600">Plan #</label>
                                <input name="plan_number" value="{{ it.plan_number }}" class="w-full px-3 py-2 border rounded">
                              </div>
                              <div>
                                <label class="block text-xs text-gray-600">As of</label>
                                <input type="date" name="as_of" value="{{ it.as_of }}" class="w-full px-3 py-2 border rounded">
                              </div>
                              <div>
                                <label class="block text-xs text-gray-600">Value (£)</label>
                                <input name="value" value="{{ it.value }}" class="w-full px-3 py-2 border rounded">
                              </div>
                              <div>
                                <label class="block text-xs text-gray-600">Currency</label>
                                <input name="currency" value="{{ it.currency or 'GBP' }}" class="w-full px-3 py-2 border rounded">
                              </div>
                              <div class="col-span-2">
                                <label class="block text-xs text-gray-600">Notes</label>
                                <textarea name="item_notes" rows="2" class="w-full px-3 py-2 border rounded">{{ it.notes }}</textarea>
                              </div>
                            </div>
                            <div class="mt-2 flex items-center gap-2">
                              <button class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Save</button>
                              </form>
                              <form method="POST" onsubmit="return confirm('Delete this pension?');">
                                <input type="hidden" name="action" value="delete_item">
                                <input type="hidden" name="group" value="pensions">
                                <input type="hidden" name="item_id" value="{{ it.id }}">
                                <button class="bg-red-600 text-white px-3 py-2 rounded hover:bg-red-700">Delete</button>
                              </form>
                            </div>
                        </div>
                      </details>
                    </td>
                  </tr>
                  {% endfor %}
                </tbody>
              </table>
            {% else %}
              <p class="text-gray-500">No pensions yet.</p>
            {% endif %}
          </div>

          <div class="p-5 border-t">
            <h3 class="font-semibold mb-3">Add Pension</h3>
            <form method="POST" class="grid grid-cols-1 md:grid-cols-3 gap-3">
              <input type="hidden" name="action" value="add_pension">
              <input name="name" placeholder="Name" class="px-3 py-2 border rounded">
              <input name="provider" placeholder="Provider" class="px-3 py-2 border rounded">
              <input name="plan_number" placeholder="Plan #" class="px-3 py-2 border rounded">
              <input type="date" name="as_of" value="{{ datetime.now().strftime('%Y-%m-%d') }}" class="px-3 py-2 border rounded">
              <input name="value" placeholder="Value (£)" class="px-3 py-2 border rounded">
              <input name="currency" placeholder="Currency (GBP)" value="GBP" class="px-3 py-2 border rounded">
              <textarea name="item_notes" rows="2" placeholder="Notes" class="md:col-span-3 px-3 py-2 border rounded"></textarea>
              <div class="md:col-span-3">
                <button class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Add Pension</button>
              </div>
            </form>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow">
          <div class="p-5 border-b">
            <h2 class="text-lg font-semibold">Client Notes</h2>
          </div>
          <div class="p-5">
            <form method="POST" class="space-y-3">
              <input type="hidden" name="action" value="save_notes">
              <textarea name="notes" rows="8" class="w-full px-3 py-2 border rounded" placeholder="Key notes…">{{ profile.notes }}</textarea>
              <div>
                <button class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Save Notes</button>
              </div>
            </form>
          </div>
        </div>
      </section>
    </div>

    <div class="mt-8 flex gap-3">
      <a href="/clients/{{ client.client_id }}/portfolio" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Refresh Portfolio</a>
      <a href="/clients/{{ client.client_id }}/profile" class="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700">Back to Profile</a>
      <a href="/clients" class="bg-white text-gray-700 px-4 py-2 rounded border hover:bg-gray-50">All Clients</a>
    </div>
  </main>
</body>
</html>
"""
