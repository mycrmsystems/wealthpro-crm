"""
Financial Adviser CRM System - Optimized for Render
FIXED: OAuth redirect URI properly configured (NO /callback)
"""

import os
import json
import base64
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

# Session configuration for Render
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Render configuration
PORT = int(os.environ.get('PORT', 10000))
HOST = '0.0.0.0'

# Google OAuth 2.0 settings - NO /callback to match Google Cloud Console
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://wealthpro-crm.onrender.com')
REDIRECT_URI = RENDER_URL  # NO /callback - exactly matches Google Cloud Console

CLIENT_CONFIG = {
    "web": {
        "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
        "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET'),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT_URI]
    }
}

class CRMDataManager:
    """Manages CRM data using Google Sheets as backend"""
    
    def __init__(self, sheets_service):
        self.sheets_service = sheets_service
        self.spreadsheet_id = None
        self.setup_crm_spreadsheet()
    
    def setup_crm_spreadsheet(self):
        """Setup or find the CRM spreadsheet"""
        try:
            # Try to find existing CRM spreadsheet
            # For now, we'll create a new one each time - you can modify this to search for existing
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
                                'columnCount': 15
                            }
                        }
                    }
                ]
            }
            
            result = self.sheets_service.spreadsheets().create(
                body=spreadsheet
            ).execute()
            
            self.spreadsheet_id = result['spreadsheetId']
            
            # Add headers
            headers = [
                'ID', 'Name', 'Email', 'Phone', 'Status', 'Date Added',
                'Last Contact', 'Client Folder ID', 'Notes', 'Portfolio Value', 
                'Risk Profile', 'Address', 'Date of Birth', 'Occupation'
            ]
            
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range='Clients!A1:N1',
                valueInputOption='RAW',
                body={'values': [headers]}
            ).execute()
            
            logger.info(f"Created CRM spreadsheet: {self.spreadsheet_id}")
            
        except HttpError as error:
            logger.error(f"Error setting up CRM spreadsheet: {error}")
    
    def add_client(self, client_data: Dict) -> bool:
        """Add a new client to the spreadsheet"""
        try:
            values = [list(client_data.values())]
            
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Clients!A:N',
                valueInputOption='RAW',
                body={'values': values}
            ).execute()
            
            return True
            
        except HttpError as error:
            logger.error(f"Error adding client: {error}")
            return False
    
    def get_clients(self) -> List[Dict]:
        """Get all clients from the spreadsheet"""
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Clients!A2:N'
            ).execute()
            
            values = result.get('values', [])
            clients = []
            
            for row in values:
                if len(row) >= 8:  # Minimum required fields
                    # Pad row with empty strings if needed
                    while len(row) < 14:
                        row.append('')
                    
                    client = {
                        'id': row[0],
                        'name': row[1], 
                        'email': row[2],
                        'phone': row[3],
                        'status': row[4],
                        'date_added': row[5],
                        'last_contact': row[6],
                        'folder_id': row[7] if row[7] else None,
                        'notes': row[8],
                        'portfolio_value': float(row[9]) if row[9] else 0.0,
                        'risk_profile': row[10] if row[10] else 'moderate',
                        'address': row[11],
                        'date_of_birth': row[12],
                        'occupation': row[13]
                    }
                    clients.append(client)
            
            return clients
            
        except HttpError as error:
            logger.error(f"Error getting clients: {error}")
            return []

class GoogleDriveService:
    """Service for Google Drive operations"""
    
    def __init__(self, credentials):
        self.service = build('drive', 'v3', credentials=credentials)
        self.sheets_service = build('sheets', 'v4', credentials=credentials)
    
    def create_crm_main_folder(self) -> str:
        """Create main WealthPro CRM folder"""
        try:
            folder_metadata = {
                'name': 'WealthPro CRM - Client Files',
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            logger.info(f"Created main CRM folder: {folder.get('id')}")
            return folder.get('id')
            
        except HttpError as error:
            logger.error(f"Error creating main CRM folder: {error}")
            return None
    
    def create_client_folder_structure(self, client_name: str, parent_folder_id: str = None) -> Dict:
        """Create complete folder structure for a new client"""
        try:
            # Create main client folder
            client_folder_metadata = {
                'name': f"Client - {client_name}",
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_folder_id:
                client_folder_metadata['parents'] = [parent_folder_id]
            
            client_folder = self.service.files().create(
                body=client_folder_metadata,
                fields='id'
            ).execute()
            
            client_folder_id = client_folder.get('id')
            logger.info(f"Created client folder for {client_name}: {client_folder_id}")
            
            # Create sub-folders within client folder
            sub_folders = [
                "01 - Personal Documents",
                "02 - Financial Statements", 
                "03 - Investment Documents",
                "04 - Insurance Documents",
                "05 - Tax Documents",
                "06 - Estate Planning",
                "07 - Fact Find Forms",
                "08 - Meeting Notes",
                "09 - Correspondence",
                "10 - Reports & Proposals"
            ]
            
            sub_folder_ids = {}
            
            for folder_name in sub_folders:
                sub_folder_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [client_folder_id]
                }
                
                sub_folder = self.service.files().create(
                    body=sub_folder_metadata,
                    fields='id'
                ).execute()
                
                sub_folder_ids[folder_name] = sub_folder.get('id')
                logger.info(f"Created sub-folder: {folder_name}")
            
            return {
                'client_folder_id': client_folder_id,
                'sub_folders': sub_folder_ids
            }
            
        except HttpError as error:
            logger.error(f"Error creating client folder structure: {error}")
            return None
    
    def get_folder_url(self, folder_id: str) -> str:
        """Get the Google Drive URL for a folder"""
        return f"https://drive.google.com/drive/folders/{folder_id}"

# HTML Templates
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
                    {% if google_connected %}
                    <div class="flex items-center space-x-2 bg-white bg-opacity-10 px-3 py-1 rounded-lg">
                        <div class="w-2 h-2 bg-green-400 rounded-full"></div>
                        <span class="text-sm">Google Drive Connected</span>
                    </div>
                    {% endif %}
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-6 py-8">
        {% if google_connected %}
        <!-- Connected Dashboard -->
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
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0Â 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
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

        {% else %}
        <!-- Welcome Screen (Not Connected) -->
        <div class="gradient-wealth text-white rounded-lg p-8 mb-8 text-center">
            <h1 class="text-4xl font-bold mb-4">Welcome to WealthPro CRM!</h1>
            <p class="text-xl text-blue-100 mb-8">Professional Financial Advisory Platform</p>
            <a href="/authorize" class="inline-flex items-center px-8 py-4 bg-white text-blue-600 font-semibold rounded-lg hover:bg-blue-50 transition-colors">
                <svg class="w-6 h-6 mr-3" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M20 6L9 17l-5-5"/>
                </svg>
                Connect Google Drive to Get Started
            </a>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div class="card-professional bg-white rounded-xl p-8 text-center">
                <div class="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 515.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
                    </svg>
                </div>
                <h3 class="text-xl font-semibold text-gray-900 mb-2">Client Management</h3>
                <p class="text-gray-600">Organize client profiles with automatic Google Drive folder creation</p>
            </div>

            <div class="card-professional bg-white rounded-xl p-8 text-center">
                <div class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                </div>
                <h3 class="text-xl font-semibold text-gray-900 mb-2">Fact Find Integration</h3>
                <p class="text-gray-600">Seamlessly integrate your existing fact find forms</p>
            </div>

            <div class="card-professional bg-white rounded-xl p-8 text-center">
                <div class="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m-2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                </div>
                <h3 class="text-xl font-semibold text-gray-900 mb-2">Document Vault</h3>
                <p class="text-gray-600">Secure document storage with Google Drive integration</p>
            </div>
        </div>
        {% endif %}

        {% if success %}
        <div class="mt-8 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded">
            {{ success }}
        </div>
        {% endif %}

        {% if error %}
        <div class="mt-8 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            {{ error }}
        </div>
        {% endif %}
    </main>
</body>
</html>
"""

# Flask Routes
@app.route('/')
def index():
    """Main dashboard - ALSO HANDLES OAUTH CALLBACK"""
    
    # Log all incoming requests for debugging
    logger.info(f"=== MAIN ROUTE REQUEST ===")
    logger.info(f"Request args: {dict(request.args)}")
    logger.info(f"Session keys: {list(session.keys())}")
    
    # Check if this is an OAuth callback (has state and code parameters)
    if request.args.get('state') and request.args.get('code'):
        logger.info("OAuth callback detected - processing...")
        return handle_oauth_callback()
    
    # Normal dashboard logic
    google_connected = 'credentials' in session
    logger.info(f"Google connected: {google_connected}")
    
    # Check for success message
    oauth_success = session.pop('oauth_success', False)
    success_message = "Google Drive connected successfully!" if oauth_success else None
    
    if google_connected:
        try:
            # Get basic stats (can be expanded later)
            stats = {
                'total_clients': 0,
                'active_clients': 0,
                'prospects': 0,
                'total_portfolio_value': 0
            }
            return render_template_string(DASHBOARD_TEMPLATE, 
                                        google_connected=True, 
                                        stats=stats, 
                                        error=None,
                                        success=success_message)
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            return render_template_string(DASHBOARD_TEMPLATE, 
                                        google_connected=False, 
                                        error="Error loading dashboard data")
    
    return render_template_string(DASHBOARD_TEMPLATE, 
                                google_connected=False, 
                                error=None,
                                success=success_message)

def handle_oauth_callback():
    """Handle OAuth callback on the main route"""
    try:
        logger.info("=== OAUTH CALLBACK DETECTED ON MAIN ROUTE ===")
        logger.info(f"Request URL: {request.url}")
        logger.info(f"Request args: {request.args}")
        logger.info(f"Session keys: {list(session.keys())}")
        
        # Check if state exists
        if 'state' not in session:
            logger.error("NO STATE IN SESSION")
            return render_template_string(DASHBOARD_TEMPLATE, 
                                        google_connected=False, 
                                        error="Session state missing - please try connecting again")
        
        # Verify state parameter
        request_state = request.args.get('state')
        if request_state != session['state']:
            logger.error(f"State mismatch: session={session['state']}, request={request_state}")
            return render_template_string(DASHBOARD_TEMPLATE, 
                                        google_connected=False, 
                                        error="Invalid state parameter - please try connecting again")
        
        # Check for error in callback
        if 'error' in request.args:
            logger.error(f"OAuth error: {request.args.get('error')}")
            return render_template_string(DASHBOARD_TEMPLATE, 
                                        google_connected=False, 
                                        error=f"OAuth error: {request.args.get('error')}")
        
        # Get authorization code
        code = request.args.get('code')
        if not code:
            logger.error("No authorization code received")
            return render_template_string(DASHBOARD_TEMPLATE, 
                                        google_connected=False, 
                                        error="No authorization code received")
        
        logger.info("Creating OAuth flow for token exchange")
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            state=session['state']
        )
        flow.redirect_uri = REDIRECT_URI
        
        # Exchange code for credentials
        logger.info("Fetching token...")
        flow.fetch_token(authorization_response=request.url)
        
        credentials = flow.credentials
        logger.info("Successfully obtained credentials")
        
        # Store credentials in session
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        logger.info("Credentials stored in session successfully")
        
        # Test the credentials by making a simple API call
        try:
            drive_service = build('drive', 'v3', credentials=credentials)
            about = drive_service.about().get(fields="user").execute()
            user_email = about.get('user', {}).get('emailAddress', 'Unknown')
            logger.info(f"Successfully connected to Google Drive for user: {user_email}")
        except Exception as api_error:
            logger.error(f"Error testing Google Drive API: {api_error}")
        
        # Clear the state and redirect to clean URL
        session.pop('state', None)
        
        logger.info("OAuth successful - redirecting to clean dashboard")
        
        # Add a success message to session
        session['oauth_success'] = True
        
        return redirect(url_for('index'))
    
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return render_template_string(DASHBOARD_TEMPLATE, 
                                    google_connected=False, 
                                    error=f"Authentication error: {e}")

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
        logger.info(f"Starting OAuth flow - state stored: {state}")
        logger.info(f"Redirect URI: {REDIRECT_URI}")
        
        return redirect(authorization_url)
    
    except Exception as e:
        logger.error(f"Authorization error: {e}")
        return f"Authorization setup error: {e}", 500

@app.route('/callback')
def callback():
    """Legacy callback route - redirects to main route"""
    # In case anything still tries to use /callback, redirect to main route
    return redirect(url_for('index'))

@app.route('/clients')
def clients():
    """Clients management page"""
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    
    try:
        credentials = Credentials(**session['credentials'])
        drive_service = GoogleDriveService(credentials)
        data_manager = CRMDataManager(build('sheets', 'v4', credentials=credentials))
        
        clients_list = data_manager.get_clients()
        
        # Create clients page HTML
        clients_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>WealthPro CRM - Clients</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                body {{ font-family: 'Inter', sans-serif; }}
                .gradient-wealth {{ background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); }}
            </style>
        </head>
        <body class="bg-gray-50">
            <nav class="gradient-wealth text-white shadow-lg">
                <div class="max-w-7xl mx-auto px-6">
                    <div class="flex justify-between items-center h-16">
                        <div class="flex items-center space-x-4">
                            <h1 class="text-xl font-bold">WealthPro CRM</h1>
                        </div>
                        <div class="flex items-center space-x-6">
                            <a href="/" class="hover:text-blue-200">Dashboard</a>
                            <a href="/clients" class="text-white font-semibold">Clients</a>
                        </div>
                    </div>
                </div>
            </nav>
            
            <main class="max-w-7xl mx-auto px-6 py-8">
                <div class="flex justify-between items-center mb-8">
                    <h1 class="text-3xl font-bold text-gray-900">Client Management</h1>
                    <a href="/clients/add" class="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors">
                        Add New Client
                    </a>
                </div>
                
                <div class="bg-white rounded-lg shadow overflow-hidden">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Client</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Contact</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Portfolio</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Drive Folder</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
        """
        
        if clients_list:
            for client in clients_list:
                folder_link = ""
                if client.get('folder_id'):
                    folder_url = drive_service.get_folder_url(client['folder_id'])
                    folder_link = f'<a href="{folder_url}" target="_blank" class="text-blue-600 hover:text-blue-800">📁 View Folder</a>'
                else:
                    folder_link = '<span class="text-gray-400">No folder</span>'
                
                status_color = {
                    'active': 'bg-green-100 text-green-800',
                    'inactive': 'bg-red-100 text-red-800', 
                    'prospect': 'bg-yellow-100 text-yellow-800'
                }.get(client.get('status', 'prospect'), 'bg-gray-100 text-gray-800')
                
                clients_html += f"""
                            <tr>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="text-sm font-medium text-gray-900">{client.get('name', 'N/A')}</div>
                                    <div class="text-sm text-gray-500">ID: {client.get('id', 'N/A')}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <div class="text-sm text-gray-900">{client.get('email', 'N/A')}</div>
                                    <div class="text-sm text-gray-500">{client.get('phone', 'N/A')}</div>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {status_color}">
                                        {client.get('status', 'prospect').title()}
                                    </span>
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                    £{client.get('portfolio_value', 0):,.0f}
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm">
                                    {folder_link}
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                    <a href="/clients/edit/{client.get('id', '')}" class="text-indigo-600 hover:text-indigo-900 mr-4">Edit</a>
                                    <a href="/clients/view/{client.get('id', '')}" class="text-green-600 hover:text-green-900">View</a>
                                </td>
                            </tr>
                """
        else:
            clients_html += """
                            <tr>
                                <td colspan="6" class="px-6 py-4 text-center text-gray-500">
                                    No clients found. <a href="/clients/add" class="text-blue-600 hover:text-blue-800">Add your first client</a>
                                </td>
                            </tr>
            """
        
        clients_html += """
                        </tbody>
                    </table>
                </div>
            </main>
        </body>
        </html>
        """
        
        return clients_html
        
    except Exception as e:
        logger.error(f"Error loading clients page: {e}")
        return f"Error loading clients: {e}", 500

@app.route('/clients/add', methods=['GET', 'POST'])
def add_client():
    """Add new client page"""
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    
    if request.method == 'POST':
        try:
            credentials = Credentials(**session['credentials'])
            drive_service = GoogleDriveService(credentials)
            data_manager = CRMDataManager(build('sheets', 'v4', credentials=credentials))
            
            # Get form data
            client_name = request.form.get('name', '').strip()
            client_email = request.form.get('email', '').strip()
            client_phone = request.form.get('phone', '').strip()
            client_status = request.form.get('status', 'prospect')
            client_address = request.form.get('address', '').strip()
            client_dob = request.form.get('date_of_birth', '').strip()
            client_occupation = request.form.get('occupation', '').strip()
            portfolio_value = request.form.get('portfolio_value', '0')
            risk_profile = request.form.get('risk_profile', 'moderate')
            notes = request.form.get('notes', '').strip()
            
            if not client_name:
                raise ValueError("Client name is required")
            
            # Generate client ID
            client_id = f"WP{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create folder structure in Google Drive
            logger.info(f"Creating folder structure for client: {client_name}")
            
            # First ensure we have a main CRM folder
            main_folder_id = drive_service.create_crm_main_folder()
            
            # Create client folder structure
            folder_structure = drive_service.create_client_folder_structure(
                client_name, 
                main_folder_id
            )
            
            if not folder_structure:
                raise Exception("Failed to create Google Drive folder structure")
            
            # Prepare client data
            client_data = {
                'id': client_id,
                'name': client_name,
                'email': client_email,
                'phone': client_phone,
                'status': client_status,
                'date_added': datetime.now().strftime('%Y-%m-%d'),
                'last_contact': datetime.now().strftime('%Y-%m-%d'),
                'folder_id': folder_structure['client_folder_id'],
                'notes': notes,
                'portfolio_value': float(portfolio_value) if portfolio_value else 0.0,
                'risk_profile': risk_profile,
                'address': client_address,
                'date_of_birth': client_dob,
                'occupation': client_occupation
            }
            
            # Add client to spreadsheet
            success = data_manager.add_client(client_data)
            
            if success:
                logger.info(f"Successfully added client: {client_name}")
                # Redirect to clients page with success message
                return redirect(url_for('clients'))
            else:
                raise Exception("Failed to save client data")
                
        except Exception as e:
            logger.error(f"Error adding client: {e}")
            error_message = str(e)
        
    # Show add client form (GET request or POST with error)
    add_client_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WealthPro CRM - Add Client</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; }
            .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); }
        </style>
    </head>
    <body class="bg-gray-50">
        <nav class="gradient-wealth text-white shadow-lg">
            <div class="max-w-7xl mx-auto px-6">
                <div class="flex justify-between items-center h-16">
                    <div class="flex items-center space-x-4">
                        <h1 class="text-xl font-bold">WealthPro CRM</h1>
                    </div>
                    <div class="flex items-center space-x-6">
                        <a href="/" class="hover:text-blue-200">Dashboard</a>
                        <a href="/clients" class="hover:text-blue-200">Clients</a>
                    </div>
                </div>
            </div>
        </nav>
        
        <main class="max-w-4xl mx-auto px-6 py-8">
            <div class="mb-8">
                <h1 class="text-3xl font-bold text-gray-900">Add New Client</h1>
                <p class="text-gray-600 mt-2">Create a new client profile with automatic Google Drive folder structure</p>
            </div>
            
            <div class="bg-white rounded-lg shadow p-8">
                <form method="POST" class="space-y-6">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Full Name *</label>
                            <input type="text" name="name" required class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
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
                            <label class="block text-sm font-medium text-gray-700 mb-2">Date of Birth</label>
                            <input type="date" name="date_of_birth" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Occupation</label>
                            <input type="text" name="occupation" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Portfolio Value (£)</label>
                            <input type="number" name="portfolio_value" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Risk Profile</label>
                            <select name="risk_profile" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                                <option value="conservative">Conservative</option>
                                <option value="moderate" selected>Moderate</option>
                                <option value="aggressive">Aggressive</option>
                            </select>
                        </div>
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Address</label>
                        <textarea name="address" rows="2" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Notes</label>
                        <textarea name="notes" rows="4" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>
                    </div>
                    
                    <div class="bg-blue-50 p-4 rounded-lg">
                        <h3 class="text-sm font-medium text-blue-800 mb-2">📁 Google Drive Folder Structure</h3>
                        <p class="text-sm text-blue-700">When you create this client, the following folder structure will be automatically created in your Google Drive:</p>
                        <ul class="text-xs text-blue-600 mt-2 ml-4 space-y-1">
                            <li>• 01 - Personal Documents</li>
                            <li>• 02 - Financial Statements</li>
                            <li>• 03 - Investment Documents</li>
                            <li>• 04 - Insurance Documents</li>
                            <li>• 05 - Tax Documents</li>
                            <li>• 06 - Estate Planning</li>
                            <li>• 07 - Fact Find Forms</li>
                            <li>• 08 - Meeting Notes</li>
                            <li>• 09 - Correspondence</li>
                            <li>• 10 - Reports & Proposals</li>
                        </ul>
                    </div>
                    
                    <div class="flex justify-between">
                        <a href="/clients" class="px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">Cancel</a>
                        <button type="submit" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Create Client & Folders</button>
                    </div>
                </form>
            </div>
        </main>
    </body>
    </html>
    """
    
    return add_client_html

@app.route('/session-test')
def session_test():
    """Test if sessions work on Render"""
    if 'test_data' not in session:
        session['test_data'] = 'session_works'
        return """
        <div style="font-family: Arial; padding: 20px;">
            <h2>Session Test - Step 1</h2>
            <p>✅ Session data set successfully</p>
            <a href="/session-test" style="background: #007cba; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Click here to test persistence</a>
            <br><br>
            <a href="/">Back to Dashboard</a>
        </div>
        """
    else:
        return f"""
        <div style="font-family: Arial; padding: 20px;">
            <h2>Session Test - Step 2</h2>
            <p>✅ Session data found: {session['test_data']}</p>
            <p>✅ Sessions are working on Render!</p>
            <a href="/session-test-clear" style="background: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Clear session data</a>
            <br><br>
            <a href="/">Back to Dashboard</a>
        </div>
        """

@app.route('/session-test-clear')
def session_test_clear():
    """Clear session test data"""
    session.pop('test_data', None)
    return redirect(url_for('session_test'))

@app.route('/test')
def test():
    """Test page to verify deployment and configuration"""
    google_connected = 'credentials' in session
    
    return f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px;">
        <h1>WealthPro CRM Test Page</h1>
        <p>✅ Flask is working!</p>
        <p>✅ Render deployment successful!</p>
        <p>🔧 Redirect URI: {REDIRECT_URI}</p>
        <p>🌐 Client ID configured: {'Yes' if CLIENT_CONFIG['web']['client_id'] else 'No'}</p>
        <p>🔗 Google Drive connected: {'Yes' if google_connected else 'No'}</p>
        <p><a href="/session-test">Test Sessions</a></p>
        <p><a href="/">Go to Dashboard</a></p>
        <p><strong>DEBUG: RENDER_URL = {RENDER_URL}</strong></p>
    </div>
    """

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'service': 'WealthPro CRM'
    })

if __name__ == '__main__':
    logger.info(f"Starting WealthPro CRM on {HOST}:{PORT}")
    logger.info(f"Redirect URI configured as: {REDIRECT_URI}")
    app.run(host=HOST, port=PORT, debug=False)
