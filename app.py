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

@dataclass
class Client:
    """Client data model"""
    id: str
    name: str
    email: str
    phone: str
    status: str
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
    """Clients page"""
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    
    return "<h1>Clients Management - Coming Soon!</h1><p>This will show your client list with Google Drive folders.</p><a href='/'>Back to Dashboard</a>"

@app.route('/clients/add')
def add_client():
    """Add client page"""
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    
    return "<h1>Add New Client - Coming Soon!</h1><p>This will create client profiles and Google Drive folders.</p><a href='/'>Back to Dashboard</a>"

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
