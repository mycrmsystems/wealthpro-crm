# routes/communications.py
"""
WealthPro CRM — Communications (Drive-only, graceful fallback)

Designed to work even if models/google_drive.SimpleGoogleDrive
does NOT yet define:
  - add_communication_enhanced(comm_data, client)
  - get_client_communications(client_id) -> List[Dict]

If those methods exist, this page will use them. If not, it will
render safely and show a gentle message after POST.
"""

import logging
from datetime import datetime
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)
communications_bp = Blueprint("communications", __name__)


def _require_creds():
    if "credentials" not in session:
        return None
    return Credentials(**session["credentials"])


@communications_bp.route("/clients/<client_id>/communications", methods=["GET", "POST"])
def client_communications(client_id):
    """Client communications page with safe fallbacks."""
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)
        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c["client_id"] == client_id), None)
        if not client:
            return "Client not found", 404

        msg = request.args.get("msg", "")

        if request.method == "POST":
            comm_data = {
                "communication_id": f"COM{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "client_id": client_id,
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

            # Only call if the model implements it
            if hasattr(drive, "add_communication_enhanced"):
                ok = False
                try:
                    ok = drive.add_communication_enhanced(comm_data, client)  # type: ignore[attr-defined]
                except Exception as ex:
                    logger.exception("add_communication_enhanced failed")
                    return f"Error saving communication: {ex}", 500

                return redirect(
                    url_for(
                        "communications.client_communications",
                        client_id=client_id,
                        msg="Communication saved." if ok else "Could not save communication.",
                    )
                )
            else:
                # Graceful message when feature not yet enabled in the Drive model
                return redirect(
                    url_for(
                        "communications.client_communications",
                        client_id=client_id,
                        msg="Communications saving is not enabled yet in the Drive model.",
                    )
                )

        # GET — list communications if model supports it
        communications = []
        if hasattr(drive, "get_client_communications"):
            try:
                communications = drive.get_client_communications(client_id)  # type: ignore[attr-defined]
            except Exception as ex:
                logger.exception("get_client_communications failed")
                communications = []

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

    <main class="max-w-6xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Communications: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Track interactions and follow-ups (saves to Google Drive if enabled)</p>
            {% if msg %}
            <div class="mt-4 p-3 bg-blue-50 border border-blue-200 text-blue-800 rounded">
                {{ msg }}
            </div>
            {% endif %}
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
                                <input type="date" name="date" value="{{ nowdate }}" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Time *</label>
                                <input type="time" name="time" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
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
                                <option>Letter</option>
                                <option>Text Message</option>
                                <option>Other</option>
                            </select>
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Duration *</label>
                            <input type="text" name="duration" placeholder="e.g., 15 minutes, 1 hour" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Subject</label>
                            <input type="text" name="subject" placeholder="Brief summary" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Details</label>
                            <textarea name="details" rows="4" placeholder="What was discussed?" class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Outcome</label>
                            <textarea name="outcome" rows="2" placeholder="What was the result?" class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
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
                            <p class="text-xs text-blue-700">
                                {% if comm_enabled %}
                                  💾 Will save to Google Drive (Communications) for this client.
                                {% else %}
                                  ℹ️ Saving to Drive is not enabled yet in the model.
                                {% endif %}
                            </p>
                        </div>

                        <button class="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Add Communication</button>
                    </form>
                </div>
            </div>

            <!-- Communications History -->
            <div class="lg:col-span-2">
                <div class="bg-white rounded-lg shadow">
                    <div class="p-6 border-b">
                        <h3 class="text-lg font-semibold">Communication History</h3>
                    </div>
                    <div class="p-6">
                        {% if communications %}
                            <div class="space-y-4">
                                {% for comm in communications %}
                                <div class="border-l-4
                                    {% if comm.type == 'Meeting' %}border-blue-500
                                    {% elif comm.type == 'Phone Call' %}border-green-500
                                    {% elif comm.type == 'Email' %}border-purple-500
                                    {% else %}border-gray-500{% endif %}
                                    pl-4 py-3 bg-gray-50 rounded-r">
                                    <div class="flex justify-between items-start">
                                        <div class="flex-1">
                                            <h4 class="font-semibold text-gray-900">{{ comm.subject or 'No Subject' }}</h4>
                                            <p class="text-sm text-gray-600">
                                                {{ comm.type or 'Communication' }} — {{ comm.date or '' }}{% if comm.time %} at {{ comm.time }}{% endif %}
                                            </p>
                                            {% if comm.duration %}
                                            <p class="text-xs text-gray-500">Duration: {{ comm.duration }}</p>
                                            {% endif %}
                                        </div>
                                        {% if comm.follow_up_required == 'Yes' %}
                                        <span class="bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded">
                                            Follow Up: {{ comm.follow_up_date or 'TBD' }}
                                        </span>
                                        {% endif %}
                                    </div>
                                    {% if comm.details %}
                                    <div class="mt-2 text-sm text-gray-700">
                                        <strong>Details:</strong> {{ comm.details }}
                                    </div>
                                    {% endif %}
                                    {% if comm.outcome %}
                                    <div class="mt-1 text-sm text-gray-600">
                                        <strong>Outcome:</strong> {{ comm.outcome }}
                                    </div>
                                    {% endif %}
                                </div>
                                {% endfor %}
                            </div>
                        {% else %}
                            <p class="text-gray-500 text-center py-8">No communications recorded yet.</p>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>

        <div class="mt-8">
            <a href="/clients" class="bg-gray-600 text-white px-6 py-3 rounded-lg hover:bg-gray-700">Back to Clients</a>
        </div>
    </main>
</body>
</html>
            """,
            client=client,
            communications=communications,
            comm_enabled=hasattr(drive, "add_communication_enhanced"),
            nowdate=datetime.now().strftime("%Y-%m-%d"),
            msg=msg,
        )
    except Exception as e:
        logger.exception("Client communications error")
        return f"Error: {e}", 500


@communications_bp.route("/communications/summary")
def communications_summary():
    """Overview of recent communications across all clients (safe fallback)."""
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)
        clients = drive.get_clients_enhanced()

        recent_communications = []
        if hasattr(drive, "get_client_communications"):
            for client in clients:
                try:
                    comms = drive.get_client_communications(client["client_id"])  # type: ignore[attr-defined]
                except Exception:
                    comms = []
                for comm in comms[:5]:  # last 5 per client
                    comm = dict(comm or {})
                    comm["client_name"] = client["display_name"]
                    # Normalize date string for sort
                    comm["__sort_date"] = comm.get("date") or ""
                    recent_communications.append(comm)

            # Sort descending by date string (if ISO YYYY-MM-DD this is fine)
            recent_communications.sort(key=lambda x: x.get("__sort_date", ""), reverse=True)
            # Keep top 20
            recent_communications = recent_communications[:20]

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
            <p class="text-gray-600 mt-2">
                Overview across clients{% if not enabled %} — saving/listing not enabled yet in the model{% endif %}.
            </p>
        </div>

        <div class="bg-white rounded-lg shadow">
            <div class="p-6 border-b">
                <h3 class="text-lg font-semibold">Latest 20 Communications</h3>
            </div>
            <div class="p-6">
                {% if items %}
                    <div class="space-y-4">
                        {% for comm in items %}
                        <div class="border-l-4
                            {% if comm.type == 'Meeting' %}border-blue-500
                            {% elif comm.type == 'Phone Call' %}border-green-500
                            {% elif comm.type == 'Email' %}border-purple-500
                            {% else %}border-gray-500{% endif %}
                            pl-4 py-3 bg-gray-50 rounded-r">
                            <div class="flex justify-between items-start">
                                <div class="flex-1">
                                    <h4 class="font-semibold text-gray-900">{{ comm.subject or 'No Subject' }}</h4>
                                    <p class="text-sm text-gray-600">{{ comm.client_name }} | {{ comm.type or 'Communication' }} — {{ comm.date or '' }}</p>
                                    {% if comm.details %}
                                    <p class="text-sm text-gray-700 mt-1">
                                        {{ comm.details[:120] }}{% if comm.details|length > 120 %}…{% endif %}
                                    </p>
                                    {% endif %}
                                </div>
                                {% if comm.follow_up_required == 'Yes' %}
                                <span class="bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded">Follow Up</span>
                                {% endif %}
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                {% else %}
                    <p class="text-gray-500 text-center py-8">No communications to display.</p>
                {% endif %}
            </div>
        </div>
    </main>
</body>
</html>
            """,
            items=recent_communications,
            enabled=hasattr(drive, "get_client_communications"),
        )
    except Exception as e:
        logger.exception("Communications summary error")
        return f"Error: {e}", 500
