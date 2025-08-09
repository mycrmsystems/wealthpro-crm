"""
WealthPro CRM - Enhanced Version with ALL Original Features + New Features
PART 1 - Paste this into a new file
"""

import os
import json
import io
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import googleapiclient.http
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

# Global variable to store spreadsheet ID - ENHANCED WITH NEW SPREADSHEETS
SPREADSHEET_ID = None
PROFILES_SPREADSHEET_ID = None
COMMUNICATIONS_SPREADSHEET_ID = None
TASKS_SPREADSHEET_ID = None

class SimpleGoogleDrive:
    def __init__(self, credentials):
        global SPREADSHEET_ID, PROFILES_SPREADSHEET_ID, COMMUNICATIONS_SPREADSHEET_ID, TASKS_SPREADSHEET_ID
        self.service = build('drive', 'v3', credentials=credentials)
        self.sheets_service = build('sheets', 'v4', credentials=credentials)
        self.main_folder_id = None
        self.client_files_folder_id = None
        self.spreadsheet_id = SPREADSHEET_ID
        # NEW: Additional spreadsheet IDs for enhanced features
        self.profiles_spreadsheet_id = PROFILES_SPREADSHEET_ID
        self.communications_spreadsheet_id = COMMUNICATIONS_SPREADSHEET_ID
        self.tasks_spreadsheet_id = TASKS_SPREADSHEET_ID
        self.setup()

    def setup(self):
        global SPREADSHEET_ID, PROFILES_SPREADSHEET_ID, COMMUNICATIONS_SPREADSHEET_ID, TASKS_SPREADSHEET_ID
        try:
            if not self.spreadsheet_id:
                self.find_or_create_spreadsheet()
                SPREADSHEET_ID = self.spreadsheet_id
                
            # NEW: Create additional spreadsheets for enhanced features
            if not self.profiles_spreadsheet_id:
                self.find_or_create_profiles_spreadsheet()
                PROFILES_SPREADSHEET_ID = self.profiles_spreadsheet_id
                
            if not self.communications_spreadsheet_id:
                self.find_or_create_communications_spreadsheet()
                COMMUNICATIONS_SPREADSHEET_ID = self.communications_spreadsheet_id
                
            if not self.tasks_spreadsheet_id:
                self.find_or_create_tasks_spreadsheet()
                TASKS_SPREADSHEET_ID = self.tasks_spreadsheet_id
                
            logger.info(f"Setup complete - spreadsheet: {self.spreadsheet_id}")
        except Exception as e:
            logger.error(f"Setup error: {e}")

    # NEW ENHANCED FUNCTIONS - These create the additional spreadsheets for new features
    def find_or_create_profiles_spreadsheet(self):
        """Create spreadsheet for extended client profiles"""
        try:
            query = "name='WealthPro CRM - Client Profiles' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            spreadsheets = results.get('files', [])
            
            if spreadsheets:
                self.profiles_spreadsheet_id = spreadsheets[0]['id']
                logger.info(f"Found existing profiles spreadsheet: {self.profiles_spreadsheet_id}")
            else:
                self.create_new_profiles_spreadsheet()
        except Exception as e:
            logger.error(f"Error finding profiles spreadsheet: {e}")
            self.create_new_profiles_spreadsheet()

    def create_new_profiles_spreadsheet(self):
        """Create new spreadsheet for client profiles"""
        try:
            spreadsheet = {'properties': {'title': 'WealthPro CRM - Client Profiles'}}
            result = self.sheets_service.spreadsheets().create(body=spreadsheet).execute()
            self.profiles_spreadsheet_id = result['spreadsheetId']

            headers = [
                'Client ID', 'Address Line 1', 'Address Line 2', 'City', 'County', 'Postcode', 'Country',
                'Date of Birth', 'Occupation', 'Employer', 'Emergency Contact Name', 'Emergency Contact Phone',
                'Emergency Contact Relationship', 'Investment Goals', 'Risk Profile', 'Preferred Contact Method',
                'Next Review Date', 'Created Date', 'Last Updated'
            ]

            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.profiles_spreadsheet_id, range='Sheet1!A1:S1',
                valueInputOption='RAW', body={'values': [headers]}).execute()

            logger.info(f"Created new profiles spreadsheet: {self.profiles_spreadsheet_id}")
        except Exception as e:
            logger.error(f"Error creating profiles spreadsheet: {e}")

    def find_or_create_communications_spreadsheet(self):
        """Create spreadsheet for communication tracking"""
        try:
            query = "name='WealthPro CRM - Communications' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            spreadsheets = results.get('files', [])
            
            if spreadsheets:
                self.communications_spreadsheet_id = spreadsheets[0]['id']
                logger.info(f"Found existing communications spreadsheet: {self.communications_spreadsheet_id}")
            else:
                self.create_new_communications_spreadsheet()
        except Exception as e:
            logger.error(f"Error finding communications spreadsheet: {e}")
            self.create_new_communications_spreadsheet()

    def create_new_communications_spreadsheet(self):
        """Create new spreadsheet for communications"""
        try:
            spreadsheet = {'properties': {'title': 'WealthPro CRM - Communications'}}
            result = self.sheets_service.spreadsheets().create(body=spreadsheet).execute()
            self.communications_spreadsheet_id = result['spreadsheetId']

            headers = [
                'Communication ID', 'Client ID', 'Date', 'Type', 'Subject', 'Details', 
                'Outcome', 'Follow Up Required', 'Follow Up Date', 'Created By'
            ]

            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.communications_spreadsheet_id, range='Sheet1!A1:J1',
                valueInputOption='RAW', body={'values': [headers]}).execute()

            logger.info(f"Created new communications spreadsheet: {self.communications_spreadsheet_id}")
        except Exception as e:
            logger.error(f"Error creating communications spreadsheet: {e}")

    def find_or_create_tasks_spreadsheet(self):
        """Create spreadsheet for tasks and reminders"""
        try:
            query = "name='WealthPro CRM - Tasks & Reminders' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            spreadsheets = results.get('files', [])
            
            if spreadsheets:
                self.tasks_spreadsheet_id = spreadsheets[0]['id']
                logger.info(f"Found existing tasks spreadsheet: {self.tasks_spreadsheet_id}")
            else:
                self.create_new_tasks_spreadsheet()
        except Exception as e:
            logger.error(f"Error finding tasks spreadsheet: {e}")
            self.create_new_tasks_spreadsheet()

    def create_new_tasks_spreadsheet(self):
        """Create new spreadsheet for tasks"""
        try:
            spreadsheet = {'properties': {'title': 'WealthPro CRM - Tasks & Reminders'}}
            result = self.sheets_service.spreadsheets().create(body=spreadsheet).execute()
            self.tasks_spreadsheet_id = result['spreadsheetId']

            headers = [
                'Task ID', 'Client ID', 'Task Type', 'Title', 'Description', 'Due Date', 
                'Priority', 'Status', 'Created Date', 'Completed Date'
            ]

            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.tasks_spreadsheet_id, range='Sheet1!A1:J1',
                valueInputOption='RAW', body={'values': [headers]}).execute()

            logger.info(f"Created new tasks spreadsheet: {self.tasks_spreadsheet_id}")
        except Exception as e:
            logger.error(f"Error creating tasks spreadsheet: {e}")

    # ALL YOUR ORIGINAL FUNCTIONS START HERE - EXACTLY AS YOU HAD THEM
    def ensure_status_folders(self):
        """Create status folders only when needed"""
        try:
            if not hasattr(self, '_status_folders_created'):
                self.main_folder_id = self.create_folder('WealthPro CRM - Client Files', None)
                self.active_clients_folder_id = self.create_folder('Active Clients', self.main_folder_id)
                self.former_clients_folder_id = self.create_folder('Former Clients', self.main_folder_id)
                self.deceased_clients_folder_id = self.create_folder('Deceased Clients', self.main_folder_id)
                self._status_folders_created = True
                logger.info("Status folders created")
        except Exception as e:
            logger.error(f"Error creating status folders: {e}")

    def get_status_folder_id(self, status):
        """Get the appropriate main folder based on client status"""
        self.ensure_status_folders()
        if status == 'active':
            return getattr(self, 'active_clients_folder_id', None)
        elif status in ['no_longer_client', 'former']:
            return getattr(self, 'former_clients_folder_id', None)
        elif status in ['deceased', 'death']:
            return getattr(self, 'deceased_clients_folder_id', None)
        else:  # prospect or other
            return getattr(self, 'active_clients_folder_id', None)

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

    def create_client_folder(self, first_name, surname, status='prospect'):
        try:
            self.ensure_status_folders()
            letter = surname[0].upper() if surname else 'Z'
            status_folder_id = self.get_status_folder_id(status)
            letter_folder_id = self.create_folder(letter, status_folder_id)

            # Remove "Client -" prefix - just use "Surname, First Name"
            display_name = f"{surname}, {first_name}"
            client_folder_id = self.create_folder(display_name, letter_folder_id)
            reviews_folder_id = self.create_folder("Reviews", client_folder_id)

            document_folders = [
                "ID&V", "FF & ATR", "Research", "LOAs", "Suitability Letter",
                "Meeting Notes", "Terms of Business", "Policy Information", "Valuation"
            ]

            sub_folder_ids = {'Reviews': reviews_folder_id}
            for doc_type in document_folders:
                folder_id = self.create_folder(doc_type, client_folder_id)
                sub_folder_ids[doc_type] = folder_id

            logger.info(f"Created client folder for {display_name} in {status} section")
            return {
                'client_folder_id': client_folder_id,
                'sub_folders': sub_folder_ids
            }
        except Exception as e:
            logger.error(f"Error creating client folder: {e}")
            return None

# PART 2 - PASTE THIS AT THE BOTTOM OF PART 1
    # YOUR ORIGINAL CLIENT MANAGEMENT FUNCTIONS + NEW ENHANCED FUNCTIONS

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

                    try:
                        portfolio_value = float(row[9]) if row[9] and str(row[9]).replace('.', '').replace('-', '').isdigit() else 0.0
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid portfolio value '{row[9]}', using 0.0")
                        portfolio_value = 0.0

                    clients.append({
                        'client_id': row[0],
                        'display_name': row[1],
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

    def update_client_status(self, client_id, new_status):
        """Update client status and move folder"""
        try:
            clients = self.get_clients()
            client = next((c for c in clients if c['client_id'] == client_id), None)
            if not client:
                logger.error(f"Client {client_id} not found")
                return False

            # Update spreadsheet
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A:K'
            ).execute()
            values = result.get('values', [])

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == client_id:
                    if len(row) > 6:
                        row[6] = new_status

                    self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=f'Sheet1!A{i+1}:K{i+1}',
                        valueInputOption='RAW',
                        body={'values': [row]}
                    ).execute()

                    logger.info(f"Updated client {client_id} status to {new_status}")

            # Move folder
            if client.get('folder_id'):
                self.move_client_folder(client, new_status)

            return True
        except Exception as e:
            logger.error(f"Error updating client status: {e}")
            return False

    def move_client_folder(self, client, new_status):
        """Move client folder to appropriate status folder"""
        try:
            old_folder_id = client['folder_id']
            if not old_folder_id:
                return False

            logger.info(f"Moving {client['display_name']} to {new_status} section")
            self.ensure_status_folders()

            new_status_folder_id = self.get_status_folder_id(new_status)
            letter = client['surname'][0].upper() if client['surname'] else 'Z'
            new_letter_folder_id = self.create_folder(letter, new_status_folder_id)

            # Get current parents
            file = self.service.files().get(fileId=old_folder_id, fields='parents').execute()
            previous_parents = ",".join(file.get('parents', []))

            # Move the folder
            self.service.files().update(
                fileId=old_folder_id,
                addParents=new_letter_folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()

            logger.info(f"Successfully moved {client['display_name']} to {new_status}")
            return True
        except Exception as e:
            logger.error(f"Error moving client folder: {e}")
            return False

    def delete_client(self, client_id):
        """Delete client from CRM and trash folder"""
        try:
            clients = self.get_clients()
            client = next((c for c in clients if c['client_id'] == client_id), None)
            if not client:
                return False

            # Delete from spreadsheet
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A:K'
            ).execute()
            values = result.get('values', [])

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == client_id:
                    self.sheets_service.spreadsheets().values().clear(
                        spreadsheetId=self.spreadsheet_id,
                        range=f'Sheet1!A{i+1}:K{i+1}'
                    ).execute()

            # Trash Google Drive folder
            if client.get('folder_id'):
                self.service.files().update(
                    fileId=client['folder_id'],
                    body={'trashed': True}
                ).execute()
                logger.info(f"Trashed folder for {client['display_name']}")

            return True
        except Exception as e:
            logger.error(f"Error deleting client: {e}")
            return False

    def save_fact_find_to_drive(self, client, fact_find_data):
        """Save fact find document to client's FF & ATR folder"""
        try:
            if not client.get('folder_id'):
                return False

            query = f"name='FF & ATR' and '{client['folder_id']}' in parents and trashed=false"
            results = self.service.files().list(q=query, fields="files(id)").execute()
            folders = results.get('files', [])

            if not folders:
                logger.error("FF & ATR folder not found")
                return False

            ff_atr_folder_id = folders[0]['id']

            fact_find_content = f"""FACT FIND - {client['display_name']}
Date: {fact_find_data.get('fact_find_date', '')}
Age: {fact_find_data.get('age', 'N/A')}
Marital Status: {fact_find_data.get('marital_status', 'N/A')}
Dependents: {fact_find_data.get('dependents', 'N/A')}
Employment: {fact_find_data.get('employment', 'N/A')}
Annual Income: £{fact_find_data.get('annual_income', 'N/A')}
Financial Objectives: {fact_find_data.get('financial_objectives', 'N/A')}
Risk Tolerance: {fact_find_data.get('risk_tolerance', 'N/A')}
Investment Experience: {fact_find_data.get('investment_experience', 'N/A')}
"""

            file_metadata = {
                'name': f"Fact Find - {client['display_name']} - {fact_find_data.get('fact_find_date', 'Unknown')}.txt",
                'parents': [ff_atr_folder_id]
            }

            media = googleapiclient.http.MediaIoBaseUpload(
                io.BytesIO(fact_find_content.encode('utf-8')),
                mimetype='text/plain'
            )

            self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()

            logger.info(f"Saved fact find for {client['display_name']}")
            return True
        except Exception as e:
            logger.error(f"Error saving fact find: {e}")
            return False

    def get_folder_url(self, folder_id):
        return f"https://drive.google.com/drive/folders/{folder_id}"

    # NEW ENHANCED FUNCTIONS FOR EXTENDED CLIENT PROFILES
    def add_client_profile(self, profile_data):
        """Add extended client profile data"""
        try:
            values = [list(profile_data.values())]
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.profiles_spreadsheet_id,
                range='Sheet1!A:S',
                valueInputOption='RAW',
                body={'values': values}
            ).execute()
            logger.info(f"Added client profile: {profile_data.get('client_id')}")
            return True
        except Exception as e:
            logger.error(f"Error adding client profile: {e}")
            return False

    def get_client_profile(self, client_id):
        """Get extended profile for a specific client"""
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.profiles_spreadsheet_id,
                range='Sheet1!A2:S'
            ).execute()
            values = result.get('values', [])

            for row in values:
                if len(row) > 0 and row[0] == client_id:
                    while len(row) < 19:  # Ensure all columns are present
                        row.append('')
                    
                    return {
                        'client_id': row[0],
                        'address_line_1': row[1],
                        'address_line_2': row[2],
                        'city': row[3],
                        'county': row[4],
                        'postcode': row[5],
                        'country': row[6],
                        'date_of_birth': row[7],
                        'occupation': row[8],
                        'employer': row[9],
                        'emergency_contact_name': row[10],
                        'emergency_contact_phone': row[11],
                        'emergency_contact_relationship': row[12],
                        'investment_goals': row[13],
                        'risk_profile': row[14],
                        'preferred_contact_method': row[15],
                        'next_review_date': row[16],
                        'created_date': row[17],
                        'last_updated': row[18]
                    }
            return None
        except Exception as e:
            logger.error(f"Error getting client profile: {e}")
            return None

    def update_client_profile(self, client_id, profile_data):
        """Update existing client profile"""
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.profiles_spreadsheet_id,
                range='Sheet1!A:S'
            ).execute()
            values = result.get('values', [])

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == client_id:
                    # Update existing row
                    updated_row = list(profile_data.values())
                    self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.profiles_spreadsheet_id,
                        range=f'Sheet1!A{i+1}:S{i+1}',
                        valueInputOption='RAW',
                        body={'values': [updated_row]}
                    ).execute()
                    logger.info(f"Updated client profile: {client_id}")
                    return True

            # If not found, add new profile
            return self.add_client_profile(profile_data)
        except Exception as e:
            logger.error(f"Error updating client profile: {e}")
            return False

    # NEW ENHANCED FUNCTIONS FOR COMMUNICATION TRACKING
    def add_communication(self, comm_data):
        """Add communication record"""
        try:
            values = [list(comm_data.values())]
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.communications_spreadsheet_id,
                range='Sheet1!A:J',
                valueInputOption='RAW',
                body={'values': values}
            ).execute()
            logger.info(f"Added communication for client: {comm_data.get('client_id')}")
            return True
        except Exception as e:
            logger.error(f"Error adding communication: {e}")
            return False

    def get_client_communications(self, client_id):
        """Get all communications for a specific client"""
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.communications_spreadsheet_id,
                range='Sheet1!A2:J'
            ).execute()
            values = result.get('values', [])

            communications = []
            for row in values:
                if len(row) > 1 and row[1] == client_id:  # row[1] is client_id
                    while len(row) < 10:
                        row.append('')
                    
                    communications.append({
                        'communication_id': row[0],
                        'client_id': row[1],
                        'date': row[2],
                        'type': row[3],
                        'subject': row[4],
                        'details': row[5],
                        'outcome': row[6],
                        'follow_up_required': row[7],
                        'follow_up_date': row[8],
                        'created_by': row[9]
                    })

            return sorted(communications, key=lambda x: x['date'], reverse=True)
        except Exception as e:
            logger.error(f"Error getting communications: {e}")
            return []

    # NEW ENHANCED FUNCTIONS FOR TASK MANAGEMENT
    def add_task(self, task_data):
        """Add task/reminder"""
        try:
            values = [list(task_data.values())]
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.tasks_spreadsheet_id,
                range='Sheet1!A:J',
                valueInputOption='RAW',
                body={'values': values}
            ).execute()
            logger.info(f"Added task for client: {task_data.get('client_id')}")
            return True
        except Exception as e:
            logger.error(f"Error adding task: {e}")
            return False

    def get_client_tasks(self, client_id):
        """Get all tasks for a specific client"""
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id,
                range='Sheet1!A2:J'
            ).execute()
            values = result.get('values', [])

            tasks = []
            for row in values:
                if len(row) > 1 and row[1] == client_id:  # row[1] is client_id
                    while len(row) < 10:
                        row.append('')
                    
                    tasks.append({
                        'task_id': row[0],
                        'client_id': row[1],
                        'task_type': row[2],
                        'title': row[3],
                        'description': row[4],
                        'due_date': row[5],
                        'priority': row[6],
                        'status': row[7],
                        'created_date': row[8],
                        'completed_date': row[9]
                    })

            return sorted(tasks, key=lambda x: x['due_date'])
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            return []

    def get_upcoming_tasks(self, days_ahead=7):
        """Get all upcoming tasks within specified days"""
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id,
                range='Sheet1!A2:J'
            ).execute()
            values = result.get('values', [])

            upcoming_tasks = []
            today = datetime.now()
            future_date = today + timedelta(days=days_ahead)

            for row in values:
                if len(row) >= 6 and row[5]:  # Check if due_date exists
                    try:
                        due_date = datetime.strptime(row[5], '%Y-%m-%d')
                        if today <= due_date <= future_date and row[7] != 'Completed':
                            while len(row) < 10:
                                row.append('')
                            
                            upcoming_tasks.append({
                                'task_id': row[0],
                                'client_id': row[1],
                                'task_type': row[2],
                                'title': row[3],
                                'description': row[4],
                                'due_date': row[5],
                                'priority': row[6],
                                'status': row[7],
                                'created_date': row[8],
                                'completed_date': row[9]
                            })
                    except ValueError:
                        continue  # Skip invalid dates

            return sorted(upcoming_tasks, key=lambda x: x['due_date'])
        except Exception as e:
            logger.error(f"Error getting upcoming tasks: {e}")
            return []

    def complete_task(self, task_id):
        """Mark task as completed"""
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id,
                range='Sheet1!A:J'
            ).execute()
            values = result.get('values', [])

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == task_id:
                    if len(row) > 7:
                        row[7] = 'Completed'  # Status
                    if len(row) > 9:
                        row[9] = datetime.now().strftime('%Y-%m-%d')  # Completed date
                    else:
                        row.append(datetime.now().strftime('%Y-%m-%d'))

                    self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.tasks_spreadsheet_id,
                        range=f'Sheet1!A{i+1}:J{i+1}',
                        valueInputOption='RAW',
                        body={'values': [row]}
                    ).execute()

                    logger.info(f"Completed task: {task_id}")
                    return True

            return False
        except Exception as e:
            logger.error(f"Error completing task: {e}")
            return False

# END OF PART 2
# COPY AND PASTE PART 3 TO THE BOTTOM OF THIS FILE WHEN I GIVE IT TO YOU

# PART 3 - PASTE THIS AT THE BOTTOM OF PARTS 1+2
# ALL YOUR ORIGINAL ROUTES + NEW ENHANCED ROUTES

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
            upcoming_tasks = drive.get_upcoming_tasks(7)  # NEW: Get tasks for next 7 days

            stats = {
                'total_clients': len(clients),
                'prospects': len([c for c in clients if c.get('status') == 'prospect']),
                'active_clients': len([c for c in clients if c.get('status') == 'active']),
                'former_clients': len([c for c in clients if c.get('status') == 'no_longer_client']),
                'deceased': len([c for c in clients if c.get('status') == 'deceased']),
                'active_portfolio': sum(c.get('portfolio_value', 0) for c in clients if c.get('status') == 'active'),
                'upcoming_tasks': len(upcoming_tasks)  # NEW: Tasks count
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
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
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
                            <span class="px-2 py-1 text-xs rounded-full {% if client.status == 'active' %}bg-green-100 text-green-800{% elif client.status == 'deceased' %}bg-gray-100 text-gray-800{% elif client.status == 'no_longer_client' %}bg-red-100 text-red-800{% else %}bg-yellow-100 text-yellow-800{% endif %}">
                                {{ client.status.replace('_', ' ').title() }}
                            </span>
                        </td>
                        <td class="px-6 py-4 text-sm">£{{ "{:,.0f}".format(client.portfolio_value) }}</td>
                        <td class="px-6 py-4">
                            <div class="flex space-x-2">
                                {% if client.folder_id %}
                                <a href="{{ folder_urls[client.folder_id] }}" target="_blank" class="text-blue-600 hover:text-blue-800 text-sm">📁 Folder</a>
                                {% endif %}
                                <a href="/clients/{{ client.client_id }}/profile" class="text-purple-600 hover:text-purple-800 text-sm">👤 Profile</a>
                                <a href="/factfind/{{ client.client_id }}" class="text-green-600 hover:text-green-800 text-sm">📋 Fact Find</a>
                                <a href="/clients/edit/{{ client.client_id }}" class="text-orange-600 hover:text-orange-800 text-sm">✏️ Edit</a>
                                <a href="/clients/delete/{{ client.client_id }}" onclick="return confirm('Are you sure you want to delete this client? This will move their folder to Google Drive trash.')" class="text-red-600 hover:text-red-800 text-sm">🗑️ Delete</a>
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

            folder_info = drive.create_client_folder(first_name, surname, status)
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
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
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
                            <option value="no_longer_client">No Longer Client</option>
                            <option value="deceased">Deceased</option>
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

@app.route('/clients/edit/<client_id>', methods=['GET', 'POST'])
def edit_client(client_id):
    if 'credentials' not in session:
        return redirect(url_for('authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        if request.method == 'POST':
            new_status = request.form.get('status')
            logger.info(f"Updating client {client_id} to {new_status}")
            
            success = drive.update_client_status(client_id, new_status)
            if success:
                logger.info(f"Successfully updated client {client_id}")
                return redirect(url_for('clients'))
            else:
                return f"Error updating client status", 500

        clients = drive.get_clients()
        client = next((c for c in clients if c['client_id'] == client_id), None)
        if not client:
            return "Client not found", 404

        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Edit Client</title>
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
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-4xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Edit Client: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Change client status and update records</p>
        </div>

        <div class="bg-white rounded-lg shadow p-8">
            <form method="POST" class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Current Status</label>
                        <p class="text-lg font-semibold text-gray-900 capitalize">{{ client.status.replace('_', ' ') }}</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">New Status</label>
                        <select name="status" class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                            <option value="prospect" {% if client.status == 'prospect' %}selected{% endif %}>Prospect</option>
                            <option value="active" {% if client.status == 'active' %}selected{% endif %}>Active Client</option>
                            <option value="no_longer_client" {% if client.status == 'no_longer_client' %}selected{% endif %}>No Longer Client</option>
                            <option value="deceased" {% if client.status == 'deceased' %}selected{% endif %}>Deceased</option>
                        </select>
                    </div>
                </div>

                <div class="bg-blue-50 p-4 rounded-lg">
                    <h3 class="text-sm font-medium text-blue-800 mb-2">📁 Folder Organization</h3>
                    <p class="text-sm text-blue-700">Changing status will move the client's Google Drive folder to:</p>
                    <ul class="text-sm text-blue-700 mt-1">
                        <li>• Active Client → Active Clients folder</li>
                        <li>• No Longer Client → Former Clients folder</li>
                        <li>• Deceased → Deceased Clients folder</li>
                    </ul>
                </div>

                <div class="flex justify-between">
                    <a href="/clients" class="px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">Cancel</a>
                    <button type="submit" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Update Client Status</button>
                </div>
            </form>
        </div>
    </main>
</body>
</html>
        ''', client=client)

    except Exception as e:
        logger.error(f"Edit client error: {e}")
        return f"Error: {e}", 500

@app.route('/clients/delete/<client_id>')
def delete_client(client_id):
    if 'credentials' not in session:
        return redirect(url_for('authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)

        success = drive.delete_client(client_id)
        if success:
            logger.info(f"Successfully deleted client {client_id}")
            return redirect(url_for('clients'))
        else:
            return f"Error deleting client", 500

    except Exception as e:
        logger.error(f"Delete client error: {e}")
        return f"Error: {e}", 500

# END OF PART 3
# COPY AND PASTE PART 4 TO THE BOTTOM OF THIS FILE WHEN I GIVE IT TO YOU

# PART 4 - FINAL PART - PASTE THIS AT THE BOTTOM OF PARTS 1+2+3
# NEW ENHANCED ROUTES + ORIGINAL FACTFIND ROUTE + APP STARTUP

# NEW ENHANCED ROUTE: Client Profile Management
@app.route('/clients/<client_id>/profile', methods=['GET', 'POST'])
def client_profile(client_id):
    if 'credentials' not in session:
        return redirect(url_for('authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        
        clients = drive.get_clients()
        client = next((c for c in clients if c['client_id'] == client_id), None)
        if not client:
            return "Client not found", 404

        if request.method == 'POST':
            profile_data = {
                'client_id': client_id,
                'address_line_1': request.form.get('address_line_1', ''),
                'address_line_2': request.form.get('address_line_2', ''),
                'city': request.form.get('city', ''),
                'county': request.form.get('county', ''),
                'postcode': request.form.get('postcode', ''),
                'country': request.form.get('country', 'UK'),
                'date_of_birth': request.form.get('date_of_birth', ''),
                'occupation': request.form.get('occupation', ''),
                'employer': request.form.get('employer', ''),
                'emergency_contact_name': request.form.get('emergency_contact_name', ''),
                'emergency_contact_phone': request.form.get('emergency_contact_phone', ''),
                'emergency_contact_relationship': request.form.get('emergency_contact_relationship', ''),
                'investment_goals': request.form.get('investment_goals', ''),
                'risk_profile': request.form.get('risk_profile', ''),
                'preferred_contact_method': request.form.get('preferred_contact_method', ''),
                'next_review_date': request.form.get('next_review_date', ''),
                'created_date': datetime.now().strftime('%Y-%m-%d'),
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            success = drive.update_client_profile(client_id, profile_data)
            if success:
                return redirect(url_for('client_profile', client_id=client_id))

        profile = drive.get_client_profile(client_id)
        
        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Client Profile</title>
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
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-6xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Client Profile: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Extended client information and preferences</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Left Column - Basic Info -->
            <div class="bg-white rounded-lg shadow p-6">
                <h3 class="text-lg font-semibold mb-4">Basic Information</h3>
                <div class="space-y-3 text-sm">
                    <p><strong>Client ID:</strong> {{ client.client_id }}</p>
                    <p><strong>Name:</strong> {{ client.display_name }}</p>
                    <p><strong>Email:</strong> {{ client.email or 'N/A' }}</p>
                    <p><strong>Phone:</strong> {{ client.phone or 'N/A' }}</p>
                    <p><strong>Status:</strong> {{ client.status.title() }}</p>
                    <p><strong>Portfolio:</strong> £{{ "{:,.0f}".format(client.portfolio_value) }}</p>
                    <p><strong>Date Added:</strong> {{ client.date_added }}</p>
                </div>
                
                <div class="mt-6 space-y-2">
                    <a href="/clients/{{ client.client_id }}/communications" class="block w-full bg-blue-600 text-white px-4 py-2 rounded text-center hover:bg-blue-700">
                        Communications
                    </a>
                    <a href="/clients/{{ client.client_id }}/tasks" class="block w-full bg-green-600 text-white px-4 py-2 rounded text-center hover:bg-green-700">
                        Tasks & Reminders
                    </a>
                </div>
            </div>

            <!-- Right Columns - Extended Profile Form -->
            <div class="lg:col-span-2">
                <div class="bg-white rounded-lg shadow p-6">
                    <form method="POST" class="space-y-6">
                        <!-- Address Information -->
                        <div>
                            <h3 class="text-lg font-semibold mb-4">Address Information</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div class="md:col-span-2">
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Address Line 1</label>
                                    <input type="text" name="address_line_1" value="{{ profile.address_line_1 if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                                <div class="md:col-span-2">
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Address Line 2</label>
                                    <input type="text" name="address_line_2" value="{{ profile.address_line_2 if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">City</label>
                                    <input type="text" name="city" value="{{ profile.city if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">County</label>
                                    <input type="text" name="county" value="{{ profile.county if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Postcode</label>
                                    <input type="text" name="postcode" value="{{ profile.postcode if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Country</label>
                                    <input type="text" name="country" value="{{ profile.country if profile else 'UK' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                            </div>
                        </div>

                        <!-- Personal Information -->
                        <div>
                            <h3 class="text-lg font-semibold mb-4">Personal Information</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Date of Birth</label>
                                    <input type="date" name="date_of_birth" value="{{ profile.date_of_birth if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Occupation</label>
                                    <input type="text" name="occupation" value="{{ profile.occupation if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                                <div class="md:col-span-2">
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Employer</label>
                                    <input type="text" name="employer" value="{{ profile.employer if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                            </div>
                        </div>

                        <!-- Emergency Contact -->
                        <div>
                            <h3 class="text-lg font-semibold mb-4">Emergency Contact</h3>
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Name</label>
                                    <input type="text" name="emergency_contact_name" value="{{ profile.emergency_contact_name if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                                    <input type="tel" name="emergency_contact_phone" value="{{ profile.emergency_contact_phone if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Relationship</label>
                                    <input type="text" name="emergency_contact_relationship" value="{{ profile.emergency_contact_relationship if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                </div>
                            </div>
                        </div>

                        <!-- Investment Preferences -->
                        <div>
                            <h3 class="text-lg font-semibold mb-4">Investment Preferences</h3>
                            <div class="space-y-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Investment Goals</label>
                                    <textarea name="investment_goals" rows="3" class="w-full px-3 py-2 border border-gray-300 rounded-md">{{ profile.investment_goals if profile else '' }}</textarea>
                                </div>
                                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-1">Risk Profile</label>
                                        <select name="risk_profile" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                            <option value="">Select...</option>
                                            <option value="Conservative" {% if profile and profile.risk_profile == 'Conservative' %}selected{% endif %}>Conservative</option>
                                            <option value="Balanced" {% if profile and profile.risk_profile == 'Balanced' %}selected{% endif %}>Balanced</option>
                                            <option value="Growth" {% if profile and profile.risk_profile == 'Growth' %}selected{% endif %}>Growth</option>
                                            <option value="Aggressive" {% if profile and profile.risk_profile == 'Aggressive' %}selected{% endif %}>Aggressive</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-1">Preferred Contact</label>
                                        <select name="preferred_contact_method" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                            <option value="">Select...</option>
                                            <option value="Email" {% if profile and profile.preferred_contact_method == 'Email' %}selected{% endif %}>Email</option>
                                            <option value="Phone" {% if profile and profile.preferred_contact_method == 'Phone' %}selected{% endif %}>Phone</option>
                                            <option value="Post" {% if profile and profile.preferred_contact_method == 'Post' %}selected{% endif %}>Post</option>
                                            <option value="Meeting" {% if profile and profile.preferred_contact_method == 'Meeting' %}selected{% endif %}>Meeting</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-1">Next Review Date</label>
                                        <input type="date" name="next_review_date" value="{{ profile.next_review_date if profile else '' }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="flex justify-between pt-6">
                            <a href="/clients" class="px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">Back to Clients</a>
                            <button type="submit" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Save Profile</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </main>
</body>
</html>
        ''', client=client, profile=profile)

    except Exception as e:
        logger.error(f"Client profile error: {e}")
        return f"Error: {e}", 500

# NEW ENHANCED ROUTE: Communication Tracking
@app.route('/clients/<client_id>/communications', methods=['GET', 'POST'])
def client_communications(client_id):
    if 'credentials' not in session:
        return redirect(url_for('authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        
        clients = drive.get_clients()
        client = next((c for c in clients if c['client_id'] == client_id), None)
        if not client:
            return "Client not found", 404

        if request.method == 'POST':
            comm_data = {
                'communication_id': f"COM{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'client_id': client_id,
                'date': request.form.get('date', datetime.now().strftime('%Y-%m-%d')),
                'type': request.form.get('type', ''),
                'subject': request.form.get('subject', ''),
                'details': request.form.get('details', ''),
                'outcome': request.form.get('outcome', ''),
                'follow_up_required': request.form.get('follow_up_required', 'No'),
                'follow_up_date': request.form.get('follow_up_date', ''),
                'created_by': 'System User'
            }

            success = drive.add_communication(comm_data)
            if success:
                return redirect(url_for('client_communications', client_id=client_id))

        communications = drive.get_client_communications(client_id)
        
        return render_template_string('''
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
                    <a href="/factfind" class="hover:text-blue-200">Fact Find</a>
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-6xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Communications: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Track all interactions with this client</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Add New Communication Form -->
            <div class="lg:col-span-1">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold mb-4">Add Communication</h3>
                    <form method="POST" class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Date</label>
                            <input type="date" name="date" value="{{ datetime.now().strftime('%Y-%m-%d') }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Type</label>
                            <select name="type" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                <option value="">Select...</option>
                                <option value="Phone Call">Phone Call</option>
                                <option value="Email">Email</option>
                                <option value="Meeting">Meeting</option>
                                <option value="Letter">Letter</option>
                                <option value="Other">Other</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Subject</label>
                            <input type="text" name="subject" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Details</label>
                            <textarea name="details" rows="4" class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Outcome</label>
                            <textarea name="outcome" rows="2" class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Follow Up Required?</label>
                            <select name="follow_up_required" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                <option value="No">No</option>
                                <option value="Yes">Yes</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Follow Up Date</label>
                            <input type="date" name="follow_up_date" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <button type="submit" class="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                            Add Communication
                        </button>
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
                                <div class="border-l-4 border-blue-500 pl-4 py-2">
                                    <div class="flex justify-between items-start">
                                        <div>
                                            <h4 class="font-semibold text-gray-900">{{ comm.subject or 'No Subject' }}</h4>
                                            <p class="text-sm text-gray-600">{{ comm.type }} - {{ comm.date }}</p>
                                        </div>
                                        {% if comm.follow_up_required == 'Yes' %}
                                        <span class="bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded">Follow Up: {{ comm.follow_up_date }}</span>
                                        {% endif %}
                                    </div>
                                    {% if comm.details %}
                                    <p class="text-gray-700 mt-2">{{ comm.details }}</p>
                                    {% endif %}
                                    {% if comm.outcome %}
                                    <p class="text-gray-600 mt-1"><strong>Outcome:</strong> {{ comm.outcome }}</p>
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
            <a href="/clients/{{ client.client_id }}/profile" class="bg-gray-600 text-white px-6 py-3 rounded-lg hover:bg-gray-700">
                Back to Profile
            </a>
        </div>
    </main>
</body>
</html>
        ''', client=client, communications=communications, datetime=datetime)

    except Exception as e:
        logger.error(f"Communications error: {e}")
        return f"Error: {e}", 500

# NEW ENHANCED ROUTE: Tasks Management
@app.route('/tasks')
def tasks():
    if 'credentials' not in session:
        return redirect(url_for('authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        upcoming_tasks = drive.get_upcoming_tasks(30)  # Next 30 days
        clients = drive.get_clients()
        
        # Create client lookup for task display
        client_lookup = {c['client_id']: c['display_name'] for c in clients}

        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Tasks & Reminders</title>
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
                    <a href="/tasks" class="text-white font-semibold">Tasks</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Tasks & Reminders</h1>
            <p class="text-gray-600 mt-2">Manage your client follow-ups and reviews</p>
        </div>

        <div class="bg-white rounded-lg shadow">
            <div class="p-6 border-b">
                <h3 class="text-lg font-semibold">Upcoming Tasks (Next 30 Days)</h3>
            </div>
            <div class="p-6">
                {% if upcoming_tasks %}
                    <div class="space-y-4">
                        {% for task in upcoming_tasks %}
                        <div class="border-l-4 {% if task.priority == 'High' %}border-red-500{% elif task.priority == 'Medium' %}border-yellow-500{% else %}border-green-500{% endif %} pl-4 py-3 bg-gray-50 rounded-r">
                            <div class="flex justify-between items-start">
                                <div>
                                    <h4 class="font-semibold text-gray-900">{{ task.title }}</h4>
                                    <p class="text-sm text-gray-600">Client: {{ client_lookup.get(task.client_id, 'Unknown') }}</p>
                                    <p class="text-sm text-gray-500">Due: {{ task.due_date }} | Priority: {{ task.priority }}</p>
                                </div>
                                <div class="flex space-x-2">
                                    <span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">{{ task.task_type }}</span>
                                    {% if task.status != 'Completed' %}
                                    <a href="/tasks/{{ task.task_id }}/complete" class="bg-green-100 text-green-800 text-xs px-2 py-1 rounded hover:bg-green-200">Mark Complete</a>
                                    {% endif %}
                                </div>
                            </div>
                            {% if task.description %}
                            <p class="text-gray-700 mt-2">{{ task.description }}</p>
                            {% endif %}
                        </div>
                        {% endfor %}
                    </div>
                {% else %}
                    <p class="text-gray-500 text-center py-8">No upcoming tasks.</p>
                {% endif %}
            </div>
        </div>
    </main>
</body>
</html>
        ''', upcoming_tasks=upcoming_tasks, client_lookup=client_lookup)

    except Exception as e:
        logger.error(f"Tasks error: {e}")
        return f"Error: {e}", 500

# NEW ENHANCED ROUTE: Complete Task
@app.route('/tasks/<task_id>/complete')
def complete_task_route(task_id):
    if 'credentials' not in session:
        return redirect(url_for('authorize'))

    try:
        credentials = Credentials(**session['credentials'])
        drive = SimpleGoogleDrive(credentials)
        
        success = drive.complete_task(task_id)
        if success:
            return redirect(url_for('tasks'))
        else:
            return "Error completing task", 500

    except Exception as e:
        logger.error(f"Complete task error: {e}")
        return f"Error: {e}", 500

# ORIGINAL FACTFIND ROUTE (UNCHANGED)
@app.route('/factfind')
@app.route('/factfind/<client_id>', methods=['GET', 'POST'])
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

        if request.method == 'POST' and selected_client:
            fact_find_data = {
                'age': request.form.get('age', ''),
                'marital_status': request.form.get('marital_status', ''),
                'dependents': request.form.get('dependents', ''),
                'employment': request.form.get('employment', ''),
                'annual_income': request.form.get('annual_income', ''),
                'financial_objectives': request.form.get('financial_objectives', ''),
                'risk_tolerance': request.form.get('risk_tolerance', ''),
                'investment_experience': request.form.get('investment_experience', ''),
                'fact_find_date': datetime.now().strftime('%Y-%m-%d')
            }

            drive_success = drive.save_fact_find_to_drive(selected_client, fact_find_data)
            if drive_success:
                logger.info(f"Saved fact find for {selected_client['display_name']}")
                return redirect(url_for('clients'))
            else:
                return f"Error saving fact find data", 500

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
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
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
                <form method="POST" class="space-y-6">
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

                        <div class="bg-blue-50 p-4 rounded-lg">
                            <h3 class="font-semibold text-blue-800 mb-2">📋 Personal Details</h3>
                            <div class="space-y-3">
                                <div>
                                    <label class="block text-xs font-medium text-gray-700 mb-1">Age</label>
                                    <input type="number" name="age" class="w-full px-2 py-1 border border-gray-300 rounded text-sm">
                                </div>
                                <div>
                                    <label class="block text-xs font-medium text-gray-700 mb-1">Marital Status</label>
                                    <select name="marital_status" class="w-full px-2 py-1 border border-gray-300 rounded text-sm">
                                        <option value="">Select...</option>
                                        <option value="single">Single</option>
                                        <option value="married">Married</option>
                                        <option value="divorced">Divorced</option>
                                        <option value="widowed">Widowed</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="block text-xs font-medium text-gray-700 mb-1">Dependents</label>
                                    <input type="number" name="dependents" class="w-full px-2 py-1 border border-gray-300 rounded text-sm">
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Employment Status</label>
                            <input type="text" name="employment" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Annual Income (£)</label>
                            <input type="number" name="annual_income" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                    </div>

                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Financial Objectives</label>
                        <textarea name="financial_objectives" rows="3" class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Risk Tolerance</label>
                            <select name="risk_tolerance" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                <option value="">Select...</option>
                                <option value="low">Low</option>
                                <option value="medium">Medium</option>
                                <option value="high">High</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Investment Experience</label>
                            <select name="investment_experience" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                <option value="">Select...</option>
                                <option value="none">None</option>
                                <option value="limited">Limited</option>
                                <option value="some">Some</option>
                                <option value="extensive">Extensive</option>
                            </select>
                        </div>
                    </div>

                    <div class="text-center pt-6">
                        <button type="submit" class="bg-green-600 text-white px-8 py-3 rounded-lg hover:bg-green-700 mr-4">Save Fact Find</button>
                        <a href="/clients" class="bg-gray-600 text-white px-6 py-3 rounded-lg hover:bg-gray-700">Cancel</a>
                    </div>
                </form>
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

# ORIGINAL TEST AND HEALTH ROUTES (UNCHANGED)
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

# APP STARTUP (UNCHANGED)
if __name__ == '__main__':
    logger.info(f"Starting WealthPro CRM on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)
