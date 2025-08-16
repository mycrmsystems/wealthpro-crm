"""
WealthPro CRM - Authentication & Dashboard Routes
FULL FILE — Step 3

What's in here:
- Google OAuth (unchanged flow; callback handled on '/')
- Dashboard with stats:
    * Prospects / Active / Former / Deceased counts
    * Active clients portfolio total
    * Tasks due in next 30 days (open only)
- A compact list of upcoming tasks (top 8, soonest first)

NOTE: The "due in next 30 days" count relies on SimpleGoogleDrive.get_upcoming_tasks(30),
which already excludes tasks with Status == 'Completed'.
"""

import os
import logging
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# ------------------------------
# OAuth configuration
# ------------------------------
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

# Render injects your public URL in this env var; we use it as our redirect.
# Callback is handled on '/', just like your previous working version.
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://wealthpro-crm.onrender.com')
REDIRECT_URI = RENDER_URL

CLIENT_CONFIG = {
    "web": {
        "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
        "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET'),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT_URI]
    }
}

# ------------------------------
# Routes
# ------------------------------
@auth_bp.route('/')
def index():
    """
    Dashboard.
    Also handles OAuth callback when Google returns to '/?state=...&code=...'
    """
    try:
        # If this is an OAuth return, handle it first.
        if request.args.get('state') and request.args.get('code'):
            return handle_oauth_callback()

        connected = 'credentials' in session
        success = session.pop('oauth_success', False)

        if not connected:
            # Not connected -> show connect CTA
            return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM</title>
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
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="gradient-wealth text-white rounded-lg p-8 text-center">
            <h1 class="text-4xl font-bold mb-4">Welcome to WealthPro CRM</h1>
            <p class="text-xl mb-8">Connect Google Drive to get started</p>
            <a href="/authorize" class="bg-white text-blue-600 px-8 py-4 rounded-lg font-semibold hover:bg-blue-50">
                Connect Google Drive
            </a>
        </div>
    </main>
</body>
</html>
            ''')

        # Connected -> load stats and render dashboard
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        clients = drive.get_clients_enhanced()
        upcoming_tasks = drive.get_upcoming_tasks(30)  # open tasks in next 30 days

        stats = {
            'total_clients': len(clients),
            'prospects': len([c for c in clients if c.get('status') == 'prospect']),
            'active_clients': len([c for c in clients if c.get('status') == 'active']),
            'former_clients': len([c for c in clients if c.get('status') == 'no_longer_client']),
            'deceased': len([c for c in clients if c.get('status') == 'deceased']),
            'active_portfolio': sum(c.get('portfolio_value', 0) for c in clients if c.get('status') == 'active'),
            'upcoming_tasks_30': len(upcoming_tasks)
        }

        # For rendering the small list, map client_id -> name
        client_lookup = {c['client_id']: c['display_name'] for c in clients}
        top_upcoming = upcoming_tasks[:8]  # show a quick peek on dashboard

        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM</title>
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
                    <a href="/" class="text-white font-semibold">Dashboard</a>
                    <a href="/clients" class="hover:text-blue-200">Clients</a>
                    <a href="/factfind" class="hover:text-blue-200">Fact Find</a>
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                    <div class="bg-green-500 px-3 py-1 rounded text-sm">Connected</div>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="gradient-wealth text-white rounded-lg p-6 mb-8">
            <h1 class="text-3xl font-bold mb-2">Dashboard</h1>
            <p class="text-blue-100">A–Z filing (Surname first). Total clients: {{ stats.total_clients }}</p>
        </div>

        <!-- Stat cards -->
        <div class="grid grid-cols-1 md:grid-cols-5 gap-6 mb-8">
            <div class="bg-white rounded-lg p-6 shadow">
                <h3 class="text-lg font-semibold text-gray-900">Prospects</h3>
                <p class="text-3xl font-bold text-yellow-600">{{ stats.prospects }}</p>
            </div>
            <div class="bg-white rounded-lg p-6 shadow">
                <h3 class="text-lg font-semibold text-gray-900">Active Clients</h3>
                <p class="text-3xl font-bold text-green-600">{{ stats.active_clients }}</p>
            </div>
            <div class="bg-white rounded-lg p-6 shadow">
                <h3 class="text-lg font-semibold text-gray-900">Former Clients</h3>
                <p class="text-3xl font-bold text-orange-600">{{ stats.former_clients }}</p>
            </div>
            <div class="bg-white rounded-lg p-6 shadow">
                <h3 class="text-lg font-semibold text-gray-900">Deceased</h3>
                <p class="text-3xl font-bold text-gray-600">{{ stats.deceased }}</p>
            </div>
            <div class="bg-white rounded-lg p-6 shadow">
                <h3 class="text-lg font-semibold text-gray-900">Tasks (Next 30 Days)</h3>
                <p class="text-3xl font-bold text-red-600">{{ stats.upcoming_tasks_30 }}</p>
            </div>
        </div>

        <!-- Active portfolio -->
        <div class="bg-white rounded-lg p-6 shadow mb-8 text-center">
            <h3 class="text-lg font-semibold text-gray-900 mb-2">Active Clients Portfolio Value</h3>
            <p class="text-4xl font-bold text-purple-600">£{{ "{:,.0f}".format(stats.active_portfolio) }}</p>
            <p class="text-sm text-gray-500 mt-1">Total value of active client portfolios</p>
        </div>

        <!-- Quick actions -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <a href="/clients/add" class="bg-white rounded-lg p-6 shadow hover:shadow-lg transition block">
                <h3 class="text-lg font-semibold text-gray-900 mb-2">Add New Client</h3>
                <p class="text-gray-600">Creates client with A–Z folder structure (Surname, First Name)</p>
            </a>
            <a href="/clients" class="bg-white rounded-lg p-6 shadow hover:shadow-lg transition block">
                <h3 class="text-lg font-semibold text-gray-900 mb-2">Manage Clients</h3>
                <p class="text-gray-600">View and edit all clients</p>
            </a>
            <a href="/tasks" class="bg-white rounded-lg p-6 shadow hover:shadow-lg transition block">
                <h3 class="text-lg font-semibold text-gray-900 mb-2">Tasks & Reminders</h3>
                <p class="text-gray-600">Manage follow-ups and reviews</p>
            </a>
        </div>

        <!-- Mini list: tasks due in next 30 days -->
        <div class="bg-white rounded-lg p-6 shadow">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg font-semibold text-gray-900">Next 30 Days — Upcoming Tasks</h3>
                <a href="/tasks" class="text-blue-600 hover:text-blue-800 text-sm">View all</a>
            </div>
            {% if top_upcoming %}
            <div class="divide-y">
                {% for t in top_upcoming %}
                <div class="py-3 flex items-start justify-between">
                    <div class="pr-4">
                        <div class="font-medium text-gray-900">{{ t.title }}</div>
                        <div class="text-sm text-gray-600">
                            {{ client_lookup.get(t.client_id, 'Unknown') }} • {{ t.task_type }} • Due {{ t.due_date }}
                        </div>
                        {% if t.description %}
                        <div class="text-sm text-gray-500 mt-1">{{ t.description }}</div>
                        {% endif %}
                    </div>
                    <div>
                        <a href="/tasks/{{ t.task_id }}/complete"
                           class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded hover:bg-green-200">
                           Mark Complete
                        </a>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <p class="text-gray-500">No tasks due in the next 30 days.</p>
            {% endif %}
        </div>

        {% if success %}
        <div class="mt-4 p-4 bg-green-100 border border-green-400 text-green-700 rounded">
            Google Drive connected successfully!
        </div>
        {% endif %}
    </main>
</body>
</html>
        ''', stats=stats, top_upcoming=top_upcoming, client_lookup=client_lookup)

    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return f"Dashboard error: {e}", 500


def handle_oauth_callback():
    """
    Handle OAuth callback from Google (state + code are on '/').
    """
    try:
        if 'state' not in session:
            return redirect(url_for('auth.index'))

        if request.args.get('state') != session['state']:
            return redirect(url_for('auth.index'))

        if request.args.get('error'):
            return redirect(url_for('auth.index'))

        code = request.args.get('code')
        if not code:
            return redirect(url_for('auth.index'))

        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, state=session['state'])
        flow.redirect_uri = REDIRECT_URI
        flow.fetch_token(authorization_response=request.url)

        credentials = flow.credentials
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

        session.pop('state', None)
        session['oauth_success'] = True
        return redirect(url_for('auth.index'))

    except Exception as e:
        logger.error(f"OAuth error: {e}")
        return redirect(url_for('auth.index'))


@auth_bp.route('/authorize')
def authorize():
    """Start Google OAuth flow."""
    try:
        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
        flow.redirect_uri = REDIRECT_URI

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )

        session['state'] = state
        return redirect(authorization_url)

    except Exception as e:
        logger.error(f"Authorization error: {e}")
        return f"Authorization error: {e}", 500
