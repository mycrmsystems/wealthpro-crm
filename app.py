"""
Financial Adviser CRM System - Optimized for Render
FIXED: Robust Google Drive integration with better session handling
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

# Initialize Flask app with robust session configuration
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
    SESSION_REFRESH_EACH_REQUEST=True
)

# Render configuration
PORT = int(os.environ.get('PORT', 10000))
HOST = '0.0.0.0'

# Google OAuth 2.0 settings for Render
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

# Get the redirect URI for Render - FIXED TO MATCH GOOGLE SETTINGS
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

def get_stored_credentials():
    """Get stored credentials from environment or session"""
    # First try session
    if 'credentials' in session:
        try:
            return Credentials(**session['credentials'])
        except Exception as e:
            logger.warning(f"Session credentials invalid: {e}")
    
    # Try environment variable (for persistent storage)
    stored_creds = os.environ.get('STORED_GOOGLE_CREDENTIALS')
    if stored_creds:
        try:
            creds_data = json.loads(base64.b64decode(stored_creds).decode())
            return Credentials(**creds_data)
        except Exception as e:
            logger.warning(f"Stored credentials invalid: {e}")
    
    return None

def store_credentials(credentials):
    """Store credentials in both session and log for environment variable"""
    creds_dict = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    # Store in session
    session['credentials'] = creds_dict
    session.permanent = True
    
    # Log encoded credentials for manual storage in environment
    encoded_creds = base64.b64encode(json.dumps(creds_dict).encode()).decode()
    logger.info(f"STORE THIS IN RENDER ENVIRONMENT VARIABLE 'STORED_GOOGLE_CREDENTIALS': {encoded_creds}")
    
    return creds_dict

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
    
    def find_workflow_folder(self) -> str:
        """Find the workflow folder in Google Drive"""
        try:
            # Search for folders with 'workflow' in the name (case insensitive)
            query = "mimeType='application/vnd.google-apps.folder' and (name contains 'workflow' or name contains 'Workflow' or name contains 'Work Flow')"
            results = self.service.files().list(
                q=query,
                fields="files(id, name)"
            ).execute()
            
            folders = results.get('files', [])
            if folders:
                logger.info(f"Found workflow folder: {folders[0]['name']} ({folders[0]['id']})")
                return folders[0]['id']
            else:
                logger.info("No workflow folder found, will create in root")
                return None
                
        except HttpError as error:
            logger.error(f"Error finding workflow folder: {error}")
            return None
    
    def create_main_crm_folder(self, parent_folder_id: str = None) -> str:
        """Create the main WealthPro CRM folder"""
        try:
            folder_metadata = {
                'name': 'WealthPro CRM Data',
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_folder_id:
                folder_metadata['parents'] = [parent_folder_id]
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            logger.info(f"Created main CRM folder: {folder.get('id')}")
            return folder.get('id')
            
        except HttpError as error:
            logger.error(f"Error creating main folder: {error}")
            return None
    
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
    
    def create_crm_spreadsheet(self, parent_folder_id: str = None) -> str:
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
            
            # Move to CRM folder if provided
            if parent_folder_id:
                drive_service = build('drive', 'v3', credentials=self.sheets_service._http.credentials)
                drive_service.files().update(
                    fileId=spreadsheet_id,
                    addParents=parent_folder_id,
                    removeParents='root',
                    fields='id, parents'
                ).execute()
            
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
                    {% if connected %}
                    <div class="flex items-center space-x-2 bg-white bg-opacity-10 px-3 py-1 rounded-lg">
                        <div class="w-2 h-2 bg-green-400 rounded-full"></div>
                        <span class="text-sm">Google Drive Connected</span>
                    </div>
                    {% else %}
                    <a href="/authorize" class="bg-white bg-opacity-10 px-3 py-1 rounded-lg text-sm hover:bg-opacity-20">
                        Connect Google Drive
                    </a>
                    {% endif %}
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-6 py-8">
        {% if not connected %}
        <!-- Welcome Screen -->
        <div class="gradient-wealth text-white rounded-lg p-8 mb-8 text-center">
            <h1 class="text-4xl font-bold mb-4">Welcome to WealthPro CRM!</h1>
            <p class="text-xl text-blue-100 mb-6">Professional Financial Advisory Platform</p>
            <a href="/authorize" class="inline-flex items-center px-6 py-3 bg-white text-blue-600 rounded-lg hover:bg-blue-50 transition-colors font-semibold">
                <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Connect Google Drive to Get Started
            </a>
        </div>
        
        <!-- Features Preview -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="card-professional bg-white rounded-xl p-6 text-center">
                <div class="w-16 h-16 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
                    </svg>
                </div>
                <h3 class="text-lg font-semibold text-gray-900 mb-2">Client Management</h3>
                <p class="text-gray-600">Organize client profiles with automatic Google Drive folder creation</p>
            </div>
            
            <div class="card-professional bg-white rounded-xl p-6 text-center">
                <div class="w-16 h-16 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                </div>
                <h3 class="text-lg font-semibold text-gray-900 mb-2">Fact Find Integration</h3>
                <p class="text-gray-600">Seamlessly integrate your existing fact find forms</p>
            </div>
            
            <div class="card-professional bg-white rounded-xl p-6 text-center">
                <div class="w-16 h-16 bg-purple-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                    </svg>
                </div>
                <h3 class="text-lg font-semibold text-gray-900 mb-2">Document Vault</h3>
                <p class="text-gray-600">Secure document storage with Google Drive integration</p>
            </div>
        </div>
        
        {% else %}
        
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
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
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
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 715.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
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

        <!-- Success Message -->
        <div class="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
            <h3 class="text-lg font-medium text-green-900 mb-2">🎉 Google Drive Successfully Connected!</h3>
            <p class="text-green-700 mb-3">Your CRM is now ready to create client folders and manage documents automatically.</p>
            {% if folder_info %}
            <p class="text-sm text-green-600">📁 CRM folder created in: {{ folder_info }}</p>
            {% endif %}
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
    """Main dashboard"""
    try:
        credentials = get_stored_credentials()
        connected = credentials is not None
        
        if not connected:
            return render_template_string(DASHBOARD_TEMPLATE, connected=False, stats={}, clients=[], error=None)
        
        # Get summary statistics
        data_manager = CRMDataManager(build('sheets', 'v4', credentials=credentials))
        
        clients = data_manager.get_clients()
        
        stats = {
            'total_clients': len(clients),
            'active_clients': len([c for c in clients if c.status == 'active']),
            'prospects': len([c for c in clients if c.status == 'prospect']),
            'total_portfolio_value': sum(c.portfolio_value for c in clients)
        }
        
        # Check if CRM folder exists
        drive_service = GoogleDriveService(credentials)
        workflow_folder = drive_service.find_workflow_folder()
        folder_info = "your workflow folder" if workflow_folder else "Google Drive root"
        
        return render_template_string(DASHBOARD_TEMPLATE, connected=True, stats=stats, clients=clients[:5], folder_info=folder_info, error=None)
    
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return render_template_string(DASHBOARD_TEMPLATE, connected=False, stats={}, clients=[], error="Error loading dashboard. Please reconnect to Google Drive.")

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
        logger.info(f"Starting OAuth flow with redirect_uri: {REDIRECT_URI}")
        return redirect(authorization_url)
    
    except Exception as e:
        logger.error(f"Authorization error: {e}")
        return f"Authorization setup error. Please check your Google OAuth configuration. Error: {e}", 500

@app.route('/callback')
def callback():
    """Handle OAuth callback - ROBUST VERSION"""
    try:
        logger.info(f"OAuth callback received. Request URL: {request.url}")
        
        # Verify state parameter
        if 'state' not in session:
            logger.error("No state in session")
            return redirect(url_for('index'))
        
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            state=session['state']
        )
        flow.redirect_uri = REDIRECT_URI
        
        authorization_response = request.url
        flow.fetch_token(authorization_response=authorization_response)
        
        credentials = flow.credentials
        
        # Store credentials using robust method
        store_credentials(credentials)
        
        # Initialize CRM folder structure
        try:
            drive_service = GoogleDriveService(credentials)
            data_manager = CRMDataManager(build('sheets', 'v4', credentials=credentials))
            
            # Find workflow folder
            workflow_folder_id = drive_service.find_workflow_folder()
            
            # Create main CRM folder (in workflow folder if found)
            main_folder_id = drive_service.create_main_crm_folder(workflow_folder_id)
            
            # Create CRM spreadsheet in the main folder
            if not data_manager.spreadsheet_id:
                spreadsheet_id = data_manager.create_crm_spreadsheet(main_folder_id)
                if spreadsheet_id:
                    logger.info(f"Created new CRM spreadsheet: {spreadsheet_id}")
                    
        except Exception as e:
            logger.warning(f"Could not create CRM structure: {e}")
        
        logger.info("OAuth callback successful, redirecting to dashboard")
        return redirect(url_for('index'))
    
    except Exception as e:
        logger.error(f"Callback error: {e}")
        return f"Authentication callback error: {e}. <a href='/'>Try again</a>", 500

@app.route('/clients')
def clients():
    """Simple clients page"""
    credentials = get_stored_credentials()
    if not credentials:
        return redirect(url_for('authorize'))
    
    return "<h1>Clients page - Coming soon!</h1><a href='/'>Back to Dashboard</a>"

@app.route('/clients/add')
def add_client():
    """Simple add client page"""
    credentials = get_stored_credentials()
    if not credentials:
        return redirect(url_for('authorize'))
    
    return "<h1>Add client page - Coming soon!</h1><a href='/'>Back to Dashboard</a>"

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    credentials = get_stored_credentials()
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'service': 'WealthPro CRM',
        'redirect_uri': REDIRECT_URI,
        'connected': credentials is not None
    })

@app.route('/test')
def test():
    """Test page to verify deployment"""
    credentials = get_stored_credentials()
    return f"""
    <h1>WealthPro CRM Test Page</h1>
    <p>✅ Flask is working!</p>
    <p>✅ Render deployment successful!</p>
    <p>🔧 Redirect URI: {REDIRECT_URI}</p>
    <p>🌐 Client ID configured: {'Yes' if os.environ.get('GOOGLE_CLIENT_ID') else 'No'}</p>
    <p>🔗 Google Drive connected: {'Yes' if credentials else 'No'}</p>
    <a href="/">Go to Dashboard</a>
    """

if __name__ == '__main__':
    # Render deployment
    app.run(host=HOST, port=PORT, debug=False)
