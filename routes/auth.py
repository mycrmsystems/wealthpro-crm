"""
WealthPro CRM - Authentication Routes
FILE 4 of 8 - Upload this as routes/auth.py
"""

import os
import logging
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from models.google_drive import SimpleGoogleDrive

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint for auth routes
auth_bp = Blueprint('auth', __name__)

# Configuration
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]
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

@auth_bp.route('/')
def index():
    """Main dashboard route"""
    if request.args.get('state') and request.args.get('code'):
        return handle_oauth_callback()

    connected = 'credentials' in session
    success = session.pop('oauth_success', False)

    if connected:
        try:
            credentials = Credentials(**session['credentials'])
            drive = SimpleGoogleDrive(credentials)
            clients = drive.get_clients_enhanced()
            upcoming_tasks = drive.get_upcoming_tasks(7)  # Get tasks for next 7 days

            stats = {
                'total_clients': len(clients),
                'prospects': len([c for c in clients if c.get('status') == 'prospect']),
                'active_clients': len([c for c in clients if c.get('status') == 'active']),
                'former_clients': len([c for c in clients if c.get('status') == 'no_longer_client']),
                'deceased': len([c for c in clients if c.get('status') == 'deceased']),
                'active_portfolio': sum(c.get('portfolio_value', 0) for c in clients if c.get('status') == 'active'),
                'upcoming_tasks': len(upcoming_tasks)
            }

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
                    <a href="/" class="hover:text-blue-200">Dashboard</a>
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
            <h1 class="text-3xl font-bold mb-2">Enhanced Dashboard</h1>
            <p class="text-blue-100">Your CRM is ready with A-Z filing system (Surname first) - {{ stats.total_clients }} clients</p>
        </div>

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
                <h3 class="text-lg font-semibold text-gray-900">Upcoming Tasks</h3>
                <p class="text-3xl font-bold text-red-600">{{ stats.upcoming_tasks }}</p>
            </div>
        </div>

        <div class="bg-white rounded-lg p-6 shadow mb-8 text-center">
            <h3 class="text-lg font-semibold text-gray-900 mb-2">Active Clients Portfolio Value</h3>
            <p class="text-4xl font-bold text-purple-600">£{{ "{:,.0f}".format(stats.active_portfolio) }}</p>
            <p class="text-sm text-gray-500 mt-1">Total value of active client portfolios only</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <a href="/clients/add" class="bg-white rounded-lg p-6 shadow hover:shadow-lg transition block">
                <h3 class="text-lg font-semibold text-gray-900 mb-2">Add New Client</h3>
                <p class="text-gray-600">Create client with A-Z folder structure (Surname first)</p>
            </a>
            <a href="/clients" class="bg-white rounded-lg p-6 shadow hover:shadow-lg transition block">
                <h3 class="text-lg font-semibold text-gray-900 mb-2">Manage Clients</h3>
                <p class="text-gray-600">View and edit all clients (sorted by surname)</p>
            </a>
            <a href="/tasks" class="bg-white rounded-lg p-6 shadow hover:shadow-lg transition block">
                <h3 class="text-lg font-semibold text-gray-900 mb-2">Tasks & Reminders</h3>
                <p class="text-gray-600">Manage follow-ups and client reviews</p>
            </a>
        </div>

        {% if success %}
        <div class="mt-4 p-4 bg-green-100 border border-green-400 text-green-700 rounded">
            Google Drive connected successfully!
        </div>
        {% endif %}
    </main>
</body>
</html>
            ''', stats=stats, success=success)

        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            return f"Dashboard error: {e}", 500

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

def handle_oauth_callback():
    """Handle OAuth callback from Google"""
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
    """Start OAuth authorization flow"""
    try:
        flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
        flow.redirect_uri = REDIRECT_URI

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # <— ensures refresh_token is returned
        )

        session['state'] = state
        return redirect(authorization_url)

    except Exception as e:
        logger.error(f"Authorization error: {e}")
        return f"Authorization error: {e}", 500
