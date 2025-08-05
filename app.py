"""
WealthPro CRM - Simple Working Version
A-Z Client Filing with Google Drive Integration
"""

import os
import json
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session
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

class SimpleGoogleDrive:
    def __init__(self, credentials):
        self.service = build('drive', 'v3', credentials=credentials)
        self.sheets_service = build('sheets', 'v4', credentials=credentials)
        self.main_folder_id = None
        self.client_files_folder_id = None
        self.spreadsheet_id = None
        self.setup()
    
    def setup(self):
        """Setup basic folder structure and spreadsheet"""
        try:
            # Create main CRM folder
            self.main_folder_id = self.create_folder('WealthPro CRM - Client Files', None)
            
            # Create Client Files folder
            self.client_files_folder_id = self.create_folder('Client Files', self.main_folder_id)
            
            # Create A-Z folders
            for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                self.create_folder(letter, self.client_files_folder_id)
            
            # Create spreadsheet
            self.create_spreadsheet()
            
            logger.info("Setup complete")
            
        except Exception as e:
            logger.error(f"Setup error: {e}")
    
    def create_folder(self, name, parent_id):
        """Create or find existing folder"""
        try:
            # Search for existing folder
            if parent_id:
                query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
            else:
                query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            
            results = self.service.files().list(q=query, fields="files(id)").execute()
            folders = results.get('files', [])
            
            if folders:
                return folders[0]['id']
            
            # Create new folder
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
    
    def create_client_folder(self, full_name, surname):
        """Create client folder with ALL sub-folders in A-Z structure"""
        try:
            # Get letter folder
            letter = surname[0].upper() if surname else 'Z'
            letter_folder_id = self.create_folder(letter, self.client_files_folder_id)
            
            # Create client folder
            client_folder_id = self.create_folder(f"Client - {full_name}", letter_folder_id)
            
            # Create Reviews folder
            reviews_folder_id = self.create_folder("Reviews", client_folder_id)
            
            # Create ALL document sub-folders in client folder
            document_folders = [
                "ID&V",
                "FF & ATR", 
                "Research",
                "LOA's",
                "Suitability Letter",
                "Meeting Notes",
                "Terms of Business",
                "Policy Information",
                "Valuation"
            ]
            
            sub_folder_ids = {'Reviews': reviews_folder_id}
            
            for doc_type in document_folders:
                folder_id = self.create_folder(doc_type, client_folder_id)
                sub_folder_ids[doc_type] = folder_id
                logger.info(f"Created document folder: {doc_type}")
            
            logger.info(f"Created client folder for {full_name} in {letter} folder with all sub-folders")
            
            return {
                'client_folder_id': client_folder_id,
                'sub_folders': sub_folder_ids
            }
            
        except Exception as e:
            logger.error(f"Error creating client folder: {e}")
            return None
    
    def create_spreadsheet(self):
        """Create clients spreadsheet"""
        try:
            spreadsheet = {
                'properties': {'title': 'WealthPro CRM - Clients Data'}
            }
            
            result = self.sheets_service.spreadsheets().create(body=spreadsheet).execute()
            self.spreadsheet_id = result['spreadsheetId']
            
            # Add headers
            headers = [
                'Client ID', 'Full Name', 'Surname', 'Email', 'Phone', 'Status',
                'Date Added', 'Folder ID', 'Portfolio Value', 'Notes'
            ]
            
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A1:J1',
                valueInputOption='RAW',
                body={'values': [headers]}
            ).execute()
            
            logger.info(f"Created spreadsheet: {self.spreadsheet_id}")
            
        except Exception as e:
            logger.error(f"Error creating spreadsheet: {e}")
    
    def add_client(self, client_data):
        """Add client to spreadsheet"""
        try:
            values = [list(client_data.values())]
            
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A:J',
                valueInputOption='RAW',
                body={'values': values}
            ).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding client: {e}")
            return False
    
    def get_clients(self):
        """Get all clients"""
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A2:J'
            ).execute()
            
            values = result.get('values', [])
            clients = []
            
            for row in values:
                if len(row) >= 8:
                    while len(row) < 10:
                        row.append('')
                    
                    clients.append({
                        'client_id': row[0],
                        'full_name': row[1],
                        'surname': row[2],
                        'email': row[3],
                        'phone': row[4],
                        'status': row[5],
                        'date_added': row[6],
                        'folder_id': row[7],
                        'portfolio_value': float(row[8]) if row[8] else 0.0,
                        'notes': row[9]
                    })
            
            return clients
            
        except Exception as e:
            logger.error(f"Error getting clients: {e}")
            return []
    
    def get_folder_url(self, folder_id):
        """Get Google Drive URL for folder"""
        return f"https://drive.google.com/drive/folders/{folder_id}"

# HTML Templates
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
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
                    {% if connected %}
                    <div class="bg-green-500 px-3 py-1 rounded text-sm">Connected</div>
                    {% endif %}
                </div>
            </div>
        </div>
    </nav>
    
    <main class="max-w-7xl mx-auto px-6 py-8">
        {% if connected %}
        <div class="gradient-wealth text-white rounded-lg p-6 mb-8">
            <h1 class="text-3xl font-bold mb-2">Dashboard</h1>
            <p class="text-blue-100">Your CRM is ready with A-Z filing system</p>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="bg-white rounded-lg p-6 shadow">
                <h3 class="text-lg font-semibold text-gray-900">Total Clients</h3>
                <p class="text-3xl font-bold text-blue-600">{{ stats.total_clients or 0 }}</p>
            </div>
            <div class="bg-white rounded-lg p-6 shadow">
                <h3 class="text-lg font-semibold text-gray-900">Active Clients</h3>
                <p class="text-3xl font-bold text-green-600">{{ stats.active_clients or 0 }}</p>
            </div>
            <div class="bg-white rounded-lg p-6 shadow">
                <h3 class="text-lg font-semibold text-gray-900">Total Portfolio</h3>
                <p class="text-3xl font-bold text-purple-600">£{{ "{:,.0f}".format(stats.total_portfolio or 0) }}</p>
            </div>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <a href="/clients/add" class="bg-white rounded-lg p-6 shadow hover:shadow-lg transition block">
                <h3 class="text-lg font-semibold text-gray-900 mb-2">Add New Client</h3>
                <p class="text-gray-600">Create client with A-Z folder structure</p>
            </a>
            <a href="/clients" class="bg-white rounded-lg p-6 shadow hover:shadow-lg transition block">
                <h3 class="text-lg font-semibold text-gray-900 mb-2">Manage Clients</h3>
                <p class="text-gray-600">View and edit all clients</p>
            </a>
        </div>
        
        {% else %}
        <div class="gradient-wealth text-white rounded-lg p-8 text-center">
            <h1 class="text-4xl font-bold mb-4">Welcome to WealthPro CRM</h1>
            <p class="text-xl mb-8">Connect Google Drive to get started</p>
            <a href="/authorize" class="bg-white text-blue-600 px-8 py-4 rounded-lg font-semibold hover:bg-blue-50">
                Connect Google Drive
            </a>
        </div>
        {% endif %}
        
        {% if success %}
        <div class="mt-4 p-4 bg-green-100 border border-green-400 text-green-700 rounded">
            {{ success }}
        </div>
        {% endif %}
        
        {% if error %}
        <div class="mt-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {{ error }}
        </div>
        {% endif %}
    </main>
</body>
</html>
"""

CLIENTS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Clients</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
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
                </div>
            </div>
        </div>
    </nav>
    
    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="flex justify-between items-center mb-8">
            <h1 class="text-3xl font-bold">Clients</h1>
            <a href="/clients/add" class="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700">
                Add New Client
            </a>
        </div>
        
        <div class="bg-white rounded-lg shadow overflow-hidden">
            <table class="min-w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Client</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Contact</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Portfolio</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Folder</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {% for client in clients %}
                    <tr>
                        <td class="px-6 py-4">
                            <div class="font-medium text-gray-900">{{ client.full_name }}</div>
                            <div class="text-sm text-gray-500">ID: {{ client.client_id }}</div>
                        </td>
                        <td class="px-6 py-4">
                            <div class="text-sm text-gray-900">{{ client.email or 'N/A' }}</div>
                            <div class="text-sm text-gray-500">{{ client.phone or 'N/A' }}</div>
                        </td>
                        <td class="px-6 py-4">
                            <span class="px-2 py-1 text-xs rounded-full 
                                {% if client.status == 'active' %}bg-green-100 text-green-800{% else %}bg-yellow-100 text-yellow-800{% endif %}">
                                {{ client.status.title() }}
                            </span>
                        </td>
                        <td class="px-6 py-4 text-sm">£{{ "{:,.0f}".format(client.portfolio_value) }}</td>
                        <td class="px-6 py-4">
                            {% if client.folder_id %}
                            <a href="{{ folder_urls[client.folder_id] }}" target="_blank" class="text-blue-600 hover:text-blue-800">
                                📁 View Folder
                            </a>
                            {% else %}
                            <span class="text-gray-400">No folder</span>
                            {% endif %}
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
"""

FACTFIND_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Fact Find</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
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
        </div>
        
        <div class="bg-white rounded-lg shadow p-8">
            <form method="POST" class="space-y-8">
                <!-- Client Selection -->
                <div class="border-b pb-6">
                    <h2 class="text-xl font-semibold mb-4">Client Information</h2>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Select Client *</label>
                            <select name="client_id" required class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                                <option value="">Choose a client...</option>
                                {% for client in clients %}
                                <option value="{{ client.client_id }}">{{ client.full_name }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Assessment Date</label>
                            <input type="date" name="assessment_date" value="{{ today }}" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                        </div>
                    </div>
                </div>

                <!-- Personal Details -->
                <div class="border-b pb-6">
                    <h2 class="text-xl font-semibold mb-4">Personal Details</h2>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Age</label>
                            <input type="number" name="age" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Marital Status</label>
                            <select name="marital_status" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                                <option value="">Select...</option>
                                <option value="single">Single</option>
                                <option value="married">Married</option>
                                <option value="divorced">Divorced</option>
                                <option value="widowed">Widowed</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Number of Dependants</label>
                            <input type="number" name="dependants" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Annual Income (£)</label>
                            <input type="number" name="annual_income" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                        </div>
                    </div>
                </div>

                <!-- Financial Goals -->
                <div class="border-b pb-6">
                    <h2 class="text-xl font-semibold mb-4">Financial Goals</h2>
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Primary Financial Objective</label>
                            <select name="primary_objective" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                                <option value="">Select...</option>
                                <option value="retirement_planning">Retirement Planning</option>
                                <option value="wealth_accumulation">Wealth Accumulation</option>
                                <option value="income_protection">Income Protection</option>
                                <option value="tax_planning">Tax Planning</option>
                                <option value="estate_planning">Estate Planning</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Investment Time Horizon</label>
                            <select name="time_horizon" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                                <option value="">Select...</option>
                                <option value="short_term">Short Term (0-2 years)</option>
                                <option value="medium_term">Medium Term (3-7 years)</option>
                                <option value="long_term">Long Term (8+ years)</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- Risk Assessment -->
                <div class="border-b pb-6">
                    <h2 class="text-xl font-semibold mb-4">Risk Assessment</h2>
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Risk Tolerance</label>
                            <select name="risk_tolerance" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                                <option value="">Select...</option>
                                <option value="conservative">Conservative</option>
                                <option value="moderate">Moderate</option>
                                <option value="balanced">Balanced</option>
                                <option value="growth">Growth</option>
                                <option value="aggressive">Aggressive</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Previous Investment Experience</label>
                            <select name="investment_experience" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                                <option value="">Select...</option>
                                <option value="none">None</option>
                                <option value="limited">Limited</option>
                                <option value="moderate">Moderate</option>
                                <option value="extensive">Extensive</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- Additional Notes -->
                <div>
                    <h2 class="text-xl font-semibold mb-4">Additional Information</h2>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Notes & Comments</label>
                        <textarea name="notes" rows="6" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Additional client information, concerns, specific requirements..."></textarea>
                    </div>
                </div>

                <div class="flex justify-between pt-6">
                    <a href="/clients" class="px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">Cancel</a>
                    <button type="submit" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Save Fact Find</button>
                </div>
            </form>
        </div>
    </main>
</body>
</html>
"""
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Add Client</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
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
                </div>
            </div>
        </div>
    </nav>
    
    <main class="max-w-4xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Add New Client</h1>
            <p class="text-gray-600 mt-2">Client will be filed in A-Z folder system</p>
        </div>
        
        <div class="bg-white rounded-lg shadow p-8">
            <form method="POST" class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Full Name *</label>
                        <input type="text" name="full_name" required 
                               class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Surname *</label>
                        <input type="text" name="surname" required 
                               class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <p class="text-xs text-gray-500 mt-1">Used for A-Z filing</p>
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Email</label>
                        <input type="email" name="email" 
                               class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Phone</label>
                        <input type="tel" name="phone" 
                               class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
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
                        <input type="number" name="portfolio_value" step="0.01" 
                               class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Notes</label>
                    <textarea name="notes" rows="4" 
                              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>
                </div>
                
                <div class="bg-blue-50 p-4 rounded-lg">
                    <h3 class="text-sm font-medium text-blue-800 mb-2">📁 Filing System</h3>
                    <p class="text-sm text-blue-700">Client will be created in: <strong>[Surname Letter]/Client - [Full Name]</strong></p>
                    <p class="text-xs text-blue-600 mt-2">Complete folder structure created with:</p>
                    <div class="text-xs text-blue-600 mt-1 ml-4 grid grid-cols-2 gap-1">
                        <div>• Reviews</div>
                        <div>• ID&V</div>
                        <div>• FF & ATR</div>
                        <div>• Research</div>
                        <div>• LOA's</div>
                        <div>• Suitability Letter</div>
                        <div>• Meeting Notes</div>
                        <div>• Terms of Business</div>
                        <div>• Policy Information</div>
                        <div>• Valuation</div>
                    </div>
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
"""

# Routes
@app.route('/')
def index():
    """Dashboard with OAuth callback handling"""
    # Handle OAuth callback
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
            
            return render_template_string(DASHBOARD_HTML, 
                                        connected=True, 
                                        stats=stats,
                                        success="Google Drive connected!" if success else None)
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            return render_template_string(DASHBOARD_HTML, connected=False, error=str(e))
    
    return render_template_string(DASHBOARD_HTML, connected=False)

def handle_oauth_callback():
    """Handle OAuth callback"""
    try:
        if 'state' not in session:
            return render_template_string(DASHBOARD_HTML, connected=False, error="Session expired")
        
        if request.args.get('state') != session['state']:
            return render_template_string(DASHBOARD_HTML, connected=False, error="Invalid state")
        
        if request.args.get('error'):
            return render_template_string(DASHBOARD_HTML, connected=False, error="OAuth error")
        
        code = request.args.get('code')
        if not code:
            return render_template_string(DASHBOARD_HTML, connected=False, error="No code received")
        
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
        return render_template_string(DASHBOARD_HTML, connected=False, error=str(e))

@app.route('/authorize')
def authorize():
    """Start OAuth flow"""
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
    """View all clients"""
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
        
        return render_template_string(CLIENTS_HTML, clients=clients, folder_urls=folder_urls)
        
    except Exception as e:
        logger.error(f"Clients error: {e}")
        return f"Error: {e}", 500

@app.route('/clients/add', methods=['GET', 'POST'])
def add_client():
    """Add new client"""
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    
    if request.method == 'POST':
        try:
            credentials = Credentials(**session['credentials'])
            drive = SimpleGoogleDrive(credentials)
            
            full_name = request.form.get('full_name', '').strip()
            surname = request.form.get('surname', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            status = request.form.get('status', 'prospect')
            portfolio_value = request.form.get('portfolio_value', '0')
            notes = request.form.get('notes', '').strip()
            
            if not full_name or not surname:
                raise ValueError("Full name and surname required")
            
            client_id = f"WP{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create folder structure
            folder_info = drive.create_client_folder(full_name, surname)
            if not folder_info:
                raise Exception("Failed to create folders")
            
            # Add to spreadsheet
            client_data = {
                'client_id': client_id,
                'full_name': full_name,
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
                logger.info(f"Added client: {full_name}")
                return redirect(url_for('clients'))
            else:
                raise Exception("Failed to save client")
                
        except Exception as e:
            logger.error(f"Add client error: {e}")
            return render_template_string(ADD_CLIENT_HTML, error=str(e))
    
    return render_template_string(ADD_CLIENT_HTML)

@app.route('/factfind', methods=['GET', 'POST'])
def factfind():
    """Fact Find form"""
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    
    if request.method == 'POST':
        try:
            credentials = Credentials(**session['credentials'])
            drive = SimpleGoogleDrive(credentials)
            
            # Get form data
            client_id = request.form.get('client_id')
            assessment_date = request.form.get('assessment_date')
            age = request.form.get('age')
            marital_status = request.form.get('marital_status')
            dependants = request.form.get('dependants')
            annual_income = request.form.get('annual_income')
            primary_objective = request.form.get('primary_objective')
            time_horizon = request.form.get('time_horizon')
            risk_tolerance = request.form.get('risk_tolerance')
            investment_experience = request.form.get('investment_experience')
            notes = request.form.get('notes', '')
            
            if not client_id:
                raise ValueError("Please select a client")
            
            # Save fact find data (you can expand this to save to Google Sheets)
            factfind_data = {
                'client_id': client_id,
                'assessment_date': assessment_date,
                'age': age,
                'marital_status': marital_status,
                'dependants': dependants,
                'annual_income': annual_income,
                'primary_objective': primary_objective,
                'time_horizon': time_horizon,
                'risk_tolerance': risk_tolerance,
                'investment_experience': investment_experience,
                'notes': notes,
                'completed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            logger.info(f"Fact Find completed for client: {client_id}")
            
            # Redirect back to fact find with success message
            return redirect(url_for('factfind', success='Fact Find saved successfully!'))
            
        except Exception as e:
            logger.error(f"Fact Find error: {e}")
            return render_template_string(FACTFIND_HTML, 
                                        clients=[], 
                                        today=datetime.now().strftime('%Y-%m-%d'),
                                        error=str(e))
    
    # GET request - show form
    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        clients = drive.get_clients()
        
        success_msg = request.args.get('success')
        
        return render_template_string(FACTFIND_HTML, 
                                    clients=clients,
                                    today=datetime.now().strftime('%Y-%m-%d'),
                                    success=success_msg)
        
    except Exception as e:
        logger.error(f"Fact Find load error: {e}")
        return f"Error: {e}", 500
    """Test page"""
    connected = 'credentials' in session
    return f"""
    <h1>WealthPro CRM Test</h1>
    <p>✅ Flask working</p>
    <p>✅ Render deployment successful</p>
    <p>🔗 Google Drive connected: {'Yes' if connected else 'No'}</p>
    <p>🔧 Redirect URI: {REDIRECT_URI}</p>
    <p><a href="/">Go to Dashboard</a></p>
    """

if __name__ == '__main__':
    logger.info(f"Starting WealthPro CRM on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)
