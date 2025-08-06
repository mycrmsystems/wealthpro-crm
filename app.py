"""
WealthPro CRM - Working Version
"""

import os
import json
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Configuration
PORT = int(os.environ.get('PORT', 10000))
HOST = '0.0.0.0'
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

# Global variable to store spreadsheet ID
SPREADSHEET_ID = None

class SimpleGoogleDrive:
    def __init__(self, credentials):
        global SPREADSHEET_ID
        self.service = build('drive', 'v3', credentials=credentials)
        self.sheets_service = build('sheets', 'v4', credentials=credentials)
        self.main_folder_id = None
        self.client_files_folder_id = None
        self.spreadsheet_id = SPREADSHEET_ID
        self.setup()

    def setup(self):
        global SPREADSHEET_ID
        try:
            self.main_folder_id = self.create_folder('WealthPro CRM - Client Files', None)
            self.client_files_folder_id = self.create_folder('Client Files', self.main_folder_id)
            
            for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                self.create_folder(letter, self.client_files_folder_id)

            if not self.spreadsheet_id:
                self.find_or_create_spreadsheet()
            SPREADSHEET_ID = self.spreadsheet_id
            
            logger.info(f"Setup complete - spreadsheet: {self.spreadsheet_id}")
        except Exception as e:
            logger.error(f"Setup error: {e}")

    def create_folder(self, name, parent_id):
        try:
            if parent_id:
                query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
            else:
                query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            
            results = self.service.files().list(q=query, fields="files(id)").execute()
            folders = results.get('files', [])
            
            if folders:
                return folders[0]['id']

            folder_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                folder_metadata['parents'] = [parent_id]

            folder = self.service.files().create(body=folder_metadata, fields='id').execute()
            return folder.get('id')
        except Exception as e:
            logger.error(f"Error creating folder {name}: {e}")
            return None

    def find_or_create_spreadsheet(self):
        try:
            query = "name='WealthPro CRM - Clients Data' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            spreadsheets = results.get('files', [])

            if spreadsheets:
                self.spreadsheet_id = spreadsheets[0]['id']
                logger.info(f"Found existing spreadsheet: {self.spreadsheet_id}")
            else:
                self.create_new_spreadsheet()
        except Exception as e:
            logger.error(f"Error finding spreadsheet: {e}")
            self.create_new_spreadsheet()

    def create_new_spreadsheet(self):
        try:
            spreadsheet = {
                'properties': {'title': 'WealthPro CRM - Clients Data'}
            }
            result = self.sheets_service.spreadsheets().create(body=spreadsheet).execute()
            self.spreadsheet_id = result['spreadsheetId']

            headers = [
                'Client ID', 'Display Name', 'First Name', 'Surname', 'Email', 'Phone', 'Status',
                'Date Added', 'Folder ID', 'Portfolio Value', 'Notes'
            ]
            
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A1:K1',
                valueInputOption='RAW',
                body={'values': [headers]}
            ).execute()

            logger.info(f"Created new spreadsheet: {self.spreadsheet_id}")
        except Exception as e:
            logger.error(f"Error creating spreadsheet: {e}")

    def create_client_folder(self, first_name, surname):
        try:
            letter = surname[0].upper() if surname else 'Z'
            letter_folder_id = self.create_folder(letter, self.client_files_folder_id)
            
            # Create display name: "Surname, First Name"
            display_name = f"{surname}, {first_name}"
            client_folder_id = self.create_folder(f"Client - {display_name}", letter_folder_id)
            
            reviews_folder_id = self.create_folder("Reviews", client_folder_id)
            
            # Fixed: Changed "LOA's" to "LOAs" to avoid apostrophe issue
            document_folders = [
                "ID&V", "FF & ATR", "Research", "LOAs", "Suitability Letter",
                "Meeting Notes", "Terms of Business", "Policy Information", "Valuation"
            ]

            sub_folder_ids = {'Reviews': reviews_folder_id}
            
            for doc_type in document_folders:
                folder_id = self.create_folder(doc_type, client_folder_id)
                sub_folder_ids[doc_type] = folder_id

            logger.info(f"Created client folder for {display_name} in {letter} folder with all sub-folders")
            
            return {
                'client_folder_id': client_folder_id,
                'sub_folders': sub_folder_ids
            }
        except Exception as e:
            logger.error(f"Error creating client folder: {e}")
            return None

    def add_client(self, client_data):
        try:
            values = [list(client_data.values())]
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A:K',
                valueInputOption='RAW',
                body={'values': values}
            ).execute()
            logger.info(f"Added client to spreadsheet: {client_data.get('display_name')}")
            return True
        except Exception as e:
            logger.error(f"Error adding client: {e}")
            return False

    def get_clients(self):
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A2:K'
            ).execute()
            
            values = result.get('values', [])
            clients = []
            
            for row in values:
                if len(row) >= 9:
                    while len(row) < 11:
                        row.append('')
                    
                    # Fixed: Safe portfolio value conversion to handle corrupt data
                    try:
                        portfolio_value = float(row[9]) if row[9] and str(row[9]).replace('.', '').replace('-', '').isdigit() else 0.0
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid portfolio value '{row[9]}', using 0.0")
                        portfolio_value = 0.0
                    
                    clients.append({
                        'client_id': row[0],
                        'display_name': row[1],  # "Surname, First Name"
                        'first_name': row[2],
                        'surname': row[3],
                        'email': row[4],
                        'phone': row[5],
                        'status': row[6],
                        'date_added': row[7],
                        'folder_id': row[8],
                        'portfolio_value': portfolio_value,
                        'notes': row[10]
                    })
            
            return sorted(clients, key=lambda x: x['display_name'])
        except Exception as e:
            logger.error(f"Error getting clients: {e}")
            return []

    def get_folder_url(self, folder_id):
        return f"https://drive.google.com/drive/folders/{folder_id}"

# Routes
@app.route('/')
def index():
    if request.args.get('state') and request.args.get('code'):
        return handle_oauth_callback()

    connected = 'credentials' in session
    success = session.pop('oauth_success', False)
    
    if connected:
        try:
            credentials = Credentials(**session['credentials'])
            drive = SimpleGoogleDrive(credentials)
            clients = drive.get_clients()
            
            stats = {
                'total_clients': len(clients),
                'active_clients': len([c for c in clients if c.get('status') == 'active']),
                'total_portfolio': sum(c.get('portfolio_value', 0) for c in clients)
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
                    <div class="bg-green-500 px-3 py-1 rounded text-sm">Connected</div>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="gradient-wealth text-white rounded-lg p-6 mb-8">
            <h1 class="text-3xl font-bold mb-2">Dashboard</h1>
            <p class="text-blue-100">Your CRM is ready with A-Z filing system (Surname first) - {{ stats.total_clients }} clients</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="bg-white rounded-lg p-6 shadow">
                <h3 class="text-lg font-semibold text-gray-900">Total Clients</h3>
                <p class="text-3xl font-bold text-blue-600">{{ stats.total_clients }}</p>
            </div>
            <div class="bg-white rounded-lg p-6 shadow">
                <h3 class="text-lg font-semibold text-gray-900">Active Clients</h3>
                <p class="text-3xl font-bold text-green-600">{{ stats.active_clients }}</p>
            </div>
            <div class="bg-white rounded-lg p-6 shadow">
                <h3 class="text-lg font-semibold text-gray-900">Total Portfolio</h3>
                <p class="text-3xl font-bold text-purple-600">£{{ "{:,.0f}".format(stats.total_portfolio) }}</p>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <a href="/clients/add" class="bg-white rounded-lg p-6 shadow hover:shadow-lg transition block">
                <h3 class="text-lg font-semibold text-gray-900 mb-2">Add New Client</h3>
                <p class="text-gray-600">Create client with A-Z folder structure (Surname first)</p>
            </a>
            <a href="/clients" class="bg-white rounded-lg p-6 shadow hover:shadow-lg transition block">
                <h3 class="text-lg font-semibold text-gray-900 mb-2">Manage Clients</h3>
                <p class="text-gray-600">View and edit all clients (sorted by surname)</p>
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
    try:
        if 'state' not in session:
            return redirect(url_for('index'))
        if request.args.get('state') != session['state']:
            return redirect(url_for('index'))
        if request.args.get('error'):
            return redirect(url_for('index'))

        code = request.args.get('code')
        if not code:
            return redirect(url_for('index'))

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
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"OAuth error: {e}")
        return redirect(url_for('index'))

@app.route('/authorize')
def authorize():
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

@app.route('/clients')
def clients():
    if 'credentials' not in session:
        return redirect(url_for('authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        clients = drive.get_clients()
        
        folder_urls = {}
        for client in clients:
            if client.get('folder_id'):
                folder_urls[client['folder_id']] = drive.get_folder_url(client['folder_id'])

        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Clients</title>
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
                    <a href="/clients" class="text-white font-semibold">Clients</a>
                    <a href="/factfind" class="hover:text-blue-200">Fact Find</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold">Clients (Sorted by Surname)</h1>
                <p class="text-gray-600 mt-1">Total clients: {{ clients|length }}</p>
            </div>
            <a href="/clients/add" class="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700">
                Add New Client
            </a>
        </div>

        <div class="bg-white rounded-lg shadow overflow-hidden">
            <table class="min-w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Client Name</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contact</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Portfolio</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {% for client in clients %}
                    <tr>
                        <td class="px-6 py-4">
                            <div class="font-medium text-gray-900">{{ client.display_name }}</div>
                            <div class="text-sm text-gray-500">ID: {{ client.client_id }}</div>
                        </td>
                        <td class="px-6 py-4">
                            <div class="text-sm text-gray-900">{{ client.email or 'N/A' }}</div>
                            <div class="text-sm text-gray-500">{{ client.phone or 'N/A' }}</div>
                        </td>
                        <td class="px-6 py-4">
                            <span class="px-2 py-1 text-xs rounded-full {% if client.status == 'active' %}bg-green-100 text-green-800{% else %}bg-yellow-100 text-yellow-800{% endif %}">
                                {{ client.status.title() }}
                            </span>
                        </td>
                        <td class="px-6 py-4 text-sm">£{{ "{:,.0f}".format(client.portfolio_value) }}</td>
                        <td class="px-6 py-4">
                            <div class="flex space-x-2">
                                {% if client.folder_id %}
                                <a href="{{ folder_urls[client.folder_id] }}" target="_blank" class="text-blue-600 hover:text-blue-800 text-sm">📁 Folder</a>
                                {% endif %}
                                <a href="/factfind/{{ client.client_id }}" class="text-green-600 hover:text-green-800 text-sm">📋 Fact Find</a>
                            </div>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="5" class="px-6 py-4 text-center text-gray-500">
                            No clients found. <a href="/clients/add" class="text-blue-600">Add your first client</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>
</body>
</html>
        ''', clients=clients, folder_urls=folder_urls)
    except Exception as e:
        logger.error(f"Clients error: {e}")
        return f"Error: {e}", 500

@app.route('/clients/add', methods=['GET', 'POST'])
def add_client():
    if 'credentials' not in session:
        return redirect(url_for('authorize'))

    if request.method == 'POST':
        try:
            credentials = Credentials(**session['credentials'])
            drive = SimpleGoogleDrive(credentials)

            first_name = request.form.get('first_name', '').strip()
            surname = request.form.get('surname', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            status = request.form.get('status', 'prospect')
            portfolio_value = request.form.get('portfolio_value', '0')
            notes = request.form.get('notes', '').strip()

            if not first_name or not surname:
                raise ValueError("First name and surname required")

            client_id = f"WP{datetime.now().strftime('%Y%m%d%H%M%S')}"
            display_name = f"{surname}, {first_name}"
            
            folder_info = drive.create_client_folder(first_name, surname)
            if not folder_info:
                raise Exception("Failed to create folders")

            client_data = {
                'client_id': client_id,
                'display_name': display_name,
                'first_name': first_name,
                'surname': surname,
                'email': email,
                'phone': phone,
                'status': status,
                'date_added': datetime.now().strftime('%Y-%m-%d'),
                'folder_id': folder_info['client_folder_id'],
                'portfolio_value': float(portfolio_value) if portfolio_value else 0.0,
                'notes': notes
            }

            success = drive.add_client(client_data)
            if success:
                logger.info(f"Added client: {display_name}")
                return redirect(url_for('clients'))
            else:
                raise Exception("Failed to save client")
        except Exception as e:
            logger.error(f"Add client error: {e}")
            return f"Error adding client: {e}", 500

    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Add Client</title>
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
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-4xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Add New Client</h1>
            <p class="text-gray-600 mt-2">Client will be filed as "Surname, First Name" in A-Z folder system</p>
        </div>

        <div class="bg-white rounded-lg shadow p-8">
            <form method="POST" class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">First Name *</label>
                        <input type="text" name="first_name" required class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Surname *</label>
                        <input type="text" name="surname" required class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <p class="text-xs text-gray-500 mt-1">Will display as "Surname, First Name" for easy searching</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Email</label>
                        <input type="email" name="email" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Phone</label>
                        <input type="tel" name="phone" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Status</label>
                        <select name="status" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                            <option value="prospect">Prospect</option>
                            <option value="active">Active Client</option>
                            <option value="inactive">Inactive</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Portfolio Value (£)</label>
                        <input type="number" name="portfolio_value" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Notes</label>
                    <textarea name="notes" rows="4" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>
                </div>

                <div class="bg-blue-50 p-4 rounded-lg">
                    <h3 class="text-sm font-medium text-blue-800 mb-2">📁 Complete Filing System</h3>
                    <p class="text-sm text-blue-700">Client folder created with: Reviews, ID&V, FF & ATR, Research, LOAs, Suitability Letter, Meeting Notes, Terms of Business, Policy Information, Valuation</p>
                </div>

                <div class="flex justify-between">
                    <a href="/clients" class="px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">Cancel</a>
                    <button type="submit" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Create Client</button>
                </div>
            </form>
        </div>
    </main>
</body>
</html>
    ''')

@app.route('/factfind')
@app.route('/factfind/<client_id>')
def factfind(client_id=None):
    if 'credentials' not in session:
        return redirect(url_for('authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        clients = drive.get_clients()
        
        selected_client = None
        if client_id:
            selected_client = next((c for c in clients if c['client_id'] == client_id), None)

        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Fact Find</title>
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
                    <a href="/factfind" class="text-white font-semibold">Fact Find</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-6xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Client Fact Find</h1>
            <p class="text-gray-600 mt-2">Complete client assessment form</p>
            {% if selected_client %}
            <div class="mt-4 p-4 bg-blue-100 border border-blue-400 text-blue-700 rounded">
                <strong>Selected Client:</strong> {{ selected_client.display_name }}
            </div>
            {% endif %}
        </div>

        <div class="bg-white rounded-lg shadow p-8">
            <div class="space-y-8">
                <div class="border-b pb-6">
                    <h2 class="text-xl font-semibold mb-4">Select Client</h2>
                    <select class="w-full px-3 py-2 border border-gray-300 rounded-md" onchange="window.location.href='/factfind/' + this.value">
                        <option value="">Choose a client...</option>
                        {% for client in clients %}
                        <option value="{{ client.client_id }}" {% if selected_client and selected_client.client_id == client.client_id %}selected{% endif %}>
                            {{ client.display_name }}
                        </option>
                        {% endfor %}
                    </select>
                </div>

                {% if selected_client %}
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="bg-gray-50 p-4 rounded-lg">
                        <h3 class="font-semibold text-gray-800 mb-2">Client Information</h3>
                        <div class="space-y-2 text-sm">
                            <p><strong>Name:</strong> {{ selected_client.display_name }}</p>
                            <p><strong>Email:</strong> {{ selected_client.email or 'N/A' }}</p>
                            <p><strong>Phone:</strong> {{ selected_client.phone or 'N/A' }}</p>
                            <p><strong>Status:</strong> {{ selected_client.status.title() }}</p>
                            <p><strong>Portfolio:</strong> £{{ "{:,.0f}".format(selected_client.portfolio_value) }}</p>
                        </div>
                    </div>
                    
                    <div class="bg-yellow-50 p-4 rounded-lg">
                        <h3 class="font-semibold text-yellow-800 mb-2">🚧 Coming Soon</h3>
                        <p class="text-sm text-yellow-700">The complete fact find form will be implemented here. This will include:</p>
                        <ul class="text-sm text-yellow-700 mt-2 space-y-1">
                            <li>• Personal & Family Details</li>
                            <li>• Financial Objectives</li>
                            <li>• Income & Expenditure</li>
                            <li>• Assets & Liabilities</li>
                            <li>• Risk Assessment</li>
                            <li>• Investment Experience</li>
                        </ul>
                    </div>
                </div>
                
                <div class="text-center pt-6">
                    <p class="text-gray-600 mb-4">Fact Find form framework is ready for {{ selected_client.display_name }}</p>
                    <a href="/clients" class="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700">Back to Clients</a>
                </div>
                {% else %}
                <div class="text-center">
                    <p class="text-gray-600">Select a client above to begin assessment</p>
                    <p class="text-sm text-gray-500 mt-2">Or <a href="/clients/add" class="text-blue-600">add a new client</a> first</p>
                </div>
                {% endif %}
            </div>
        </div>
    </main>
</body>
</html>
        ''', clients=clients, selected_client=selected_client)
    except Exception as e:
        logger.error(f"Fact Find error: {e}")
        return f"Error: {e}", 500

@app.route('/test')
def test():
    connected = 'credentials' in session
    return f"""
    <h1>WealthPro CRM Test</h1>
    <p>✅ Flask working</p>
    <p>✅ Render deployment successful</p>
    <p>🔗 Google Drive connected: {'Yes' if connected else 'No'}</p>
    <p>🔧 Redirect URI: {REDIRECT_URI}</p>
    <p><a href="/">Go to Dashboard</a></p>
    """

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'WealthPro CRM'
    })

if __name__ == '__main__':
    logger.info(f"Starting WealthPro CRM on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)
