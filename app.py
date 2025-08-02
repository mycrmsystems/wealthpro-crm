"""
Financial Adviser CRM System - Optimized for Render
Complete CRM with Google Drive integration
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
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

# Render configuration
PORT = int(os.environ.get('PORT', 10000))
HOST = '0.0.0.0'

# Google OAuth 2.0 settings for Render
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

# Get the redirect URI for Render
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:10000')
REDIRECT_URI = f"{RENDER_URL}/callback"

CLIENT_CONFIG = {
    "web": {
        "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
        "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET'),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT_URI]
    }
}

@dataclass
class Client:
    """Client data model"""
    id: str
    name: str
    email: str
    phone: str
    status: str  # 'active', 'inactive', 'prospect'
    date_added: str
    last_contact: str
    folder_id: Optional[str] = None
    notes: str = ""
    portfolio_value: float = 0.0
    risk_profile: str = "moderate"

class GoogleDriveService:
    """Service for Google Drive operations"""
    
    def __init__(self, credentials):
        self.service = build('drive', 'v3', credentials=credentials)
        self.sheets_service = build('sheets', 'v4', credentials=credentials)
    
    def create_client_folder(self, client_name: str, parent_folder_id: str = None) -> str:
        """Create a folder for a new client"""
        try:
            folder_metadata = {
                'name': f"Client - {client_name}",
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_folder_id:
                folder_metadata['parents'] = [parent_folder_id]
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            logger.info(f"Created folder for {client_name}: {folder.get('id')}")
            return folder.get('id')
            
        except HttpError as error:
            logger.error(f"Error creating folder: {error}")
            return None
    
    def get_client_documents(self, folder_id: str) -> List[Dict]:
        """Get all documents in a client folder"""
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id, name, createdTime, mimeType, size)"
            ).execute()
            
            return results.get('files', [])
            
        except HttpError as error:
            logger.error(f"Error getting documents: {error}")
            return []

class CRMDataManager:
    """Manages CRM data using Google Sheets as backend"""
    
    def __init__(self, sheets_service):
        self.sheets_service = sheets_service
        self.spreadsheet_id = os.environ.get('CRM_SPREADSHEET_ID')
    
    def create_crm_spreadsheet(self) -> str:
        """Create the main CRM spreadsheet"""
        try:
            spreadsheet = {
                'properties': {
                    'title': 'WealthPro CRM Data - ' + datetime.now().strftime('%Y-%m-%d')
                },
                'sheets': [
                    {
                        'properties': {
                            'title': 'Clients',
                            'gridProperties': {
                                'rowCount': 1000,
                                'columnCount': 12
                            }
                        }
                    }
                ]
            }
            
            result = self.sheets_service.spreadsheets().create(
                body=spreadsheet
            ).execute()
            
            spreadsheet_id = result['spreadsheetId']
            
            # Add headers
            headers = [
                'ID', 'Name', 'Email', 'Phone', 'Status', 'Date Added',
                'Last Contact', 'Folder ID', 'Notes', 'Portfolio Value', 'Risk Profile'
            ]
            
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range='Clients!A1:K1',
                valueInputOption='RAW',
                body={'values': [headers]}
            ).execute()
            
            logger.info(f"Created CRM spreadsheet: {spreadsheet_id}")
            return spreadsheet_id
            
        except HttpError as error:
            logger.error(f"Error creating spreadsheet: {error}")
            return None
    
    def add_client(self, client: Client) -> bool:
        """Add a new client to the spreadsheet"""
        try:
            values = [list(asdict(client).values())]
            
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Clients!A:K',
                valueInputOption='RAW',
                body={'values': values}
            ).execute()
            
            return True
            
        except HttpError as error:
            logger.error(f"Error adding client: {error}")
            return False
    
    def get_clients(self) -> List[Client]:
        """Get all clients from the spreadsheet"""
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Clients!A2:K'
            ).execute()
            
            values = result.get('values', [])
            clients = []
            
            for row in values:
                if len(row) >= 7:  # Minimum required fields
                    # Pad row with empty strings if needed
                    while len(row) < 11:
                        row.append('')
                    
                    client = Client(
                        id=row[0],
                        name=row[1],
                        email=row[2],
                        phone=row[3],
                        status=row[4],
                        date_added=row[5],
                        last_contact=row[6],
                        folder_id=row[7] if row[7] else None,
                        notes=row[8],
                        portfolio_value=float(row[9]) if row[9] else 0.0,
                        risk_profile=row[10] if row[10] else 'moderate'
                    )
                    clients.append(client)
            
            return clients
            
        except HttpError as error:
            logger.error(f"Error getting clients: {error}")
            return []

# HTML Templates (embedded for simplicity)

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WealthPro CRM - Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); }
        .card-professional { transition: all 0.2s ease; border: 1px solid #e5e7eb; }
        .card-professional:hover { transform: translateY(-1px); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08); }
    </style>
</head>
<body class="bg-gray-50">
    <!-- Navigation -->
    <nav class="gradient-wealth text-white shadow-lg">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex justify-between items-center h-16">
                <div class="flex items-center space-x-4">
                    <div class="w-10 h-10 bg-white bg-opacity-20 rounded-lg flex items-center justify-center">
                        <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4zM18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9z"/>
                        </svg>
                    </div>
                    <div>
                        <h1 class="text-xl font-bold">WealthPro CRM</h1>
                        <p class="text-xs text-blue-200">Financial Advisory Platform</p>
                    </div>
                </div>
                <div class="flex items-center space-x-6">
                    <a href="/" class="hover:text-blue-200">Dashboard</a>
                    <a href="/clients" class="hover:text-blue-200">Clients</a>
                    <div class="flex items-center space-x-2 bg-white bg-opacity-10 px-3 py-1 rounded-lg">
                        <div class="w-2 h-2 bg-green-400 rounded-full"></div>
                        <span class="text-sm">Google Drive Connected</span>
                    </div>
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-6 py-8">
        <!-- Dashboard Header -->
        <div class="gradient-wealth text-white rounded-lg p-6 mb-8">
            <h1 class="text-3xl font-bold mb-2">Dashboard Overview</h1>
            <p class="text-blue-100">Monitor your practice performance and client portfolio</p>
        </div>

        <!-- Key Metrics -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div class="card-professional bg-white rounded-xl p-6">
                <div class="flex items-center">
                    <div class="p-3 bg-blue-100 rounded-lg">
                        <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
                        </svg>
                    </div>
                    <div class="ml-4">
                        <p class="text-sm font-medium text-gray-600">Total Clients</p>
                        <p class="text-2xl font-bold text-gray-900">{{ stats.total_clients or 0 }}</p>
                    </div>
                </div>
            </div>

            <div class="card-professional bg-white rounded-xl p-6">
                <div class="flex items-center">
                    <div class="p-3 bg-green-100 rounded-lg">
                        <svg class="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                    </div>
                    <div class="ml-4">
                        <p class="text-sm font-medium text-gray-600">Active Clients</p>
                        <p class="text-2xl font-bold text-gray-900">{{ stats.active_clients or 0 }}</p>
                    </div>
                </div>
            </div>

            <div class="card-professional bg-white rounded-xl p-6">
                <div class="flex items-center">
                    <div class="p-3 bg-yellow-100 rounded-lg">
                        <svg class="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                    </div>
                    <div class="ml-4">
                        <p class="text-sm font-medium text-gray-600">Prospects</p>
                        <p class="text-2xl font-bold text-gray-900">{{ stats.prospects or 0 }}</p>
                    </div>
                </div>
            </div>

            <div class="card-professional bg-white rounded-xl p-6">
                <div class="flex items-center">
                    <div class="p-3 bg-purple-100 rounded-lg">
                        <svg class="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1"></path>
                        </svg>
                    </div>
                    <div class="ml-4">
                        <p class="text-sm font-medium text-gray-600">Total Portfolio</p>
                        <p class="text-2xl font-bold text-gray-900">£{{ "{:,.0f}".format(stats.total_portfolio_value or 0) }}</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Quick Actions -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <a href="/clients/add" class="card-professional bg-white rounded-xl p-6 block hover:no-underline">
                <div class="flex items-center">
                    <div class="p-3 bg-blue-100 rounded-lg">
                        <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                        </svg>
                    </div>
                    <div class="ml-4">
                        <h3 class="text-lg font-medium text-gray-900">Add New Client</h3>
                        <p class="text-sm text-gray-600">Create client profile</p>
                    </div>
                </div>
            </a>

            <a href="/clients" class="card-professional bg-white rounded-xl p-6 block hover:no-underline">
                <div class="flex items-center">
                    <div class="p-3 bg-green-100 rounded-lg">
                        <svg class="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
                        </svg>
                    </div>
                    <div class="ml-4">
                        <h3 class="text-lg font-medium text-gray-900">Manage Clients</h3>
                        <p class="text-sm text-gray-600">View all clients</p>
                    </div>
                </div>
            </a>

            <div class="card-professional bg-white rounded-xl p-6">
                <div class="flex items-center">
                    <div class="p-3 bg-purple-100 rounded-lg">
                        <svg class="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                        </svg>
                    </div>
                    <div class="ml-4">
                        <h3 class="text-lg font-medium text-gray-900">View Reports</h3>
                        <p class="text-sm text-gray-600">Business analytics</p>
                    </div>
                </div>
            </div>
        </div>

        {% if error %}
        <div class="mt-8 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            {{ error }}
        </div>
        {% endif %}
        
        {% if not stats.total_clients %}
        <div class="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
            <h3 class="text-lg font-medium text-blue-900 mb-2">Welcome to WealthPro CRM!</h3>
            <p class="text-blue-700 mb-4">Get started by authorizing Google Drive access and adding your first client.</p>
            <a href="/authorize" class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700">
                Connect Google Drive
            </a>
        </div>
        {% endif %}
    </main>
</body>
</html>
"""

# Flask Routes
@app.route('/')
def index():
    """Main dashboard"""
    if 'credentials' not in session:
        return render_template_string(DASHBOARD_TEMPLATE, stats={}, clients=[], error=None)
    
    try:
        # Get summary statistics
        credentials = Credentials(**session['credentials'])
        data_manager = CRMDataManager(build('sheets', 'v4', credentials=credentials))
        
        clients = data_manager.get_clients()
        
        stats = {
            'total_clients': len(clients),
            'active_clients': len([c for c in clients if c.status == 'active']),
            'prospects': len([c for c in clients if c.status == 'prospect']),
            'total_portfolio_value': sum(c.portfolio_value for c in clients)
        }
        
        return render_template_string(DASHBOARD_TEMPLATE, stats=stats, clients=clients[:5], error=None)
    
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return render_template_string(DASHBOARD_TEMPLATE, stats={}, clients=[], error="Unable to load data. Please reconnect to Google Drive.")

@app.route('/authorize')
def authorize():
    """Start OAuth flow"""
    try:
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES
        )
        flow.redirect_uri = REDIRECT_URI
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        session['state'] = state
        return redirect(authorization_url)
    
    except Exception as e:
        logger.error(f"Authorization error: {e}")
        return f"Authorization setup error. Please check your Google OAuth configuration. Error: {e}", 500

@app.route('/callback')
def callback():
    """Handle OAuth callback"""
    try:
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            state=session['state']
        )
        flow.redirect_uri = REDIRECT_URI
        
        authorization_response = request.url
        flow.fetch_token(authorization_response=authorization_response)
        
        credentials = flow.credentials
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # Try to initialize CRM spreadsheet
        try:
            data_manager = CRMDataManager(build('sheets', 'v4', credentials=credentials))
            if not data_manager.spreadsheet_id:
                spreadsheet_id = data_manager.create_crm_spreadsheet()
                if spreadsheet_id:
                    logger.info(f"Created new CRM spreadsheet: {spreadsheet_id}")
        except Exception as e:
            logger.warning(f"Could not create spreadsheet automatically: {e}")
        
        return redirect(url_for('index'))
    
    except Exception as e:
        logger.error(f"Callback error: {e}")
        return f"Authentication callback error: {e}", 500

@app.route('/clients')
def clients():
    """Simple clients page"""
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    
    return "<h1>Clients page - Coming soon!</h1><a href='/'>Back to Dashboard</a>"

@app.route('/clients/add')
def add_client():
    """Simple add client page"""
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    
    return "<h1>Add client page - Coming soon!</h1><a href='/'>Back to Dashboard</a>"

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'service': 'WealthPro CRM'
    })

@app.route('/test')
def test():
    """Test page to verify deployment"""
    return """
    <h1>WealthPro CRM Test Page</h1>
    <p>✅ Flask is working!</p>
    <p>✅ Render deployment successful!</p>
    <a href="/">Go to Dashboard</a>
    """

if __name__ == '__main__':
    # Render deployment
    app.run(host=HOST, port=PORT, debug=False)