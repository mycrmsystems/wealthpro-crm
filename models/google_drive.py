"""
WealthPro CRM - Google Drive Integration Model
FIXED VERSION - Uses single spreadsheet with multiple sheets
"""

import os
import io
import logging
from datetime import datetime, timedelta
from googleapiclient.discovery import build
import googleapiclient.http

# Configure logging
logger = logging.getLogger(__name__)

# Global variables to store spreadsheet IDs
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
            if not self.spreadsheet_id:
                self.find_or_create_spreadsheet()
                SPREADSHEET_ID = self.spreadsheet_id
                
            logger.info(f"Setup complete - spreadsheet: {self.spreadsheet_id}")
        except Exception as e:
            logger.error(f"Setup error: {e}")

    # ==================== SPREADSHEET CREATION FUNCTIONS ====================

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

    def ensure_tasks_sheet(self):
        """Make sure Tasks sheet exists in main spreadsheet"""
        try:
            # Check if Tasks sheet exists
            spreadsheet = self.sheets_service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheets = spreadsheet.get('sheets', [])
            
            tasks_sheet_exists = any(sheet['properties']['title'] == 'Tasks' for sheet in sheets)
            
            if not tasks_sheet_exists:
                # Create Tasks sheet
                request = {
                    'addSheet': {
                        'properties': {
                            'title': 'Tasks'
                        }
                    }
                }
                
                self.sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': [request]}
                ).execute()
                
                # Add headers
                headers = [
                    'Task ID', 'Client ID', 'Client Name', 'Task Type', 'Title', 
                    'Description', 'Due Date', 'Priority', 'Status', 'Created Date'
                ]
                
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range='Tasks!A1:J1',
                    valueInputOption='RAW',
                    body={'values': [headers]}
                ).execute()
                
                logger.info("Tasks sheet created successfully")
                
        except Exception as e:
            logger.error(f"Error ensuring tasks sheet: {e}")

    def ensure_profiles_sheet(self):
        """Make sure Profiles sheet exists in main spreadsheet"""
        try:
            # Check if Profiles sheet exists
            spreadsheet = self.sheets_service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheets = spreadsheet.get('sheets', [])
            
            profiles_sheet_exists = any(sheet['properties']['title'] == 'Profiles' for sheet in sheets)
            
            if not profiles_sheet_exists:
                # Create Profiles sheet
                request = {
                    'addSheet': {
                        'properties': {
                            'title': 'Profiles'
                        }
                    }
                }
                
                self.sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': [request]}
                ).execute()
                
                # Add headers
                headers = [
                    'Client ID', 'Address Line 1', 'Address Line 2', 'City', 'County', 'Postcode', 'Country',
                    'Date of Birth', 'Occupation', 'Employer', 'Emergency Contact Name', 'Emergency Contact Phone',
                    'Emergency Contact Relationship', 'Investment Goals', 'Risk Profile', 'Preferred Contact Method',
                    'Next Review Date', 'Created Date', 'Last Updated'
                ]
                
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range='Profiles!A1:S1',
                    valueInputOption='RAW',
                    body={'values': [headers]}
                ).execute()
                
                logger.info("Profiles sheet created successfully")
                
        except Exception as e:
            logger.error(f"Error ensuring profiles sheet: {e}")

    def ensure_communications_sheet(self):
        """Make sure Communications sheet exists in main spreadsheet"""
        try:
            # Check if Communications sheet exists
            spreadsheet = self.sheets_service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheets = spreadsheet.get('sheets', [])
            
            comms_sheet_exists = any(sheet['properties']['title'] == 'Communications' for sheet in sheets)
            
            if not comms_sheet_exists:
                # Create Communications sheet
                request = {
                    'addSheet': {
                        'properties': {
                            'title': 'Communications'
                        }
                    }
                }
                
                self.sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': [request]}
                ).execute()
                
                # Add headers
                headers = [
                    'Communication ID', 'Client ID', 'Date', 'Type', 'Subject', 'Details', 
                    'Outcome', 'Follow Up Required', 'Follow Up Date', 'Created By'
                ]
                
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range='Communications!A1:J1',
                    valueInputOption='RAW',
                    body={'values': [headers]}
                ).execute()
                
                logger.info("Communications sheet created successfully")
                
        except Exception as e:
            logger.error(f"Error ensuring communications sheet: {e}")

    # ==================== FOLDER MANAGEMENT FUNCTIONS ====================

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

    def create_client_folder_enhanced(self, first_name, surname, status='prospect'):
        """Enhanced folder creation with Tasks and Communications folders + Reviews sub-folders"""
        try:
            self.ensure_status_folders()
            letter = surname[0].upper() if surname else 'Z'
            status_folder_id = self.get_status_folder_id(status)
            letter_folder_id = self.create_folder(letter, status_folder_id)

            display_name = f"{surname}, {first_name}"
            client_folder_id = self.create_folder(display_name, letter_folder_id)
            
            # Create main Reviews folder
            reviews_folder_id = self.create_folder("Reviews", client_folder_id)

            # Original document folders
            document_folders = [
                "ID&V", "FF & ATR", "Research", "LOAs", "Suitability Letter",
                "Meeting Notes", "Terms of Business", "Policy Information", "Valuation"
            ]

            sub_folder_ids = {'Reviews': reviews_folder_id}
            
            # Create main document folders
            for doc_type in document_folders:
                folder_id = self.create_folder(doc_type, client_folder_id)
                sub_folder_ids[doc_type] = folder_id

            # ENHANCED: Create the same sub-folders inside Reviews folder
            for doc_type in document_folders:
                review_subfolder_id = self.create_folder(doc_type, reviews_folder_id)
                sub_folder_ids[f'Reviews_{doc_type}'] = review_subfolder_id

            # ENHANCED: Create Tasks and Communications folders
            tasks_folder_id = self.create_folder("Tasks", client_folder_id)
            communications_folder_id = self.create_folder("Communications", client_folder_id)
            
            sub_folder_ids['Tasks'] = tasks_folder_id
            sub_folder_ids['Communications'] = communications_folder_id

            logger.info(f"Created enhanced client folder for {display_name} in {status} section")
            return {
                'client_folder_id': client_folder_id,
                'sub_folders': sub_folder_ids
            }
        except Exception as e:
            logger.error(f"Error creating enhanced client folder: {e}")
            return None

    def get_folder_url(self, folder_id):
        return f"https://drive.google.com/drive/folders/{folder_id}"

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

    # ==================== CLIENT MANAGEMENT FUNCTIONS ====================

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

    def get_clients_enhanced(self):
        """Enhanced client retrieval with proper folder URLs"""
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

                    client_data = {
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
                    }
                    
                    # Add folder URL for easy access
                    if client_data['folder_id']:
                        client_data['folder_url'] = self.get_folder_url(client_data['folder_id'])
                    
                    clients.append(client_data)

            return sorted(clients, key=lambda x: x['display_name'])
        except Exception as e:
            logger.error(f"Error getting enhanced clients: {e}")
            return []

    def update_client_status(self, client_id, new_status):
        """Update client status and move folder"""
        try:
            clients = self.get_clients_enhanced()
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

    def delete_client(self, client_id):
        """Delete client from CRM and trash folder"""
        try:
            clients = self.get_clients_enhanced()
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

    # ==================== PROFILE MANAGEMENT FUNCTIONS ====================

    def add_client_profile(self, profile_data):
        """Add extended client profile data to Profiles sheet"""
        try:
            self.ensure_profiles_sheet()
            
            values = [list(profile_data.values())]
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Profiles!A:S',
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
            self.ensure_profiles_sheet()
            
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Profiles!A2:S'
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
            self.ensure_profiles_sheet()
            
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Profiles!A:S'
            ).execute()
            values = result.get('values', [])

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == client_id:
                    # Update existing row
                    updated_row = list(profile_data.values())
                    self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=f'Profiles!A{i+1}:S{i+1}',
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

    # ==================== COMMUNICATION FUNCTIONS ====================

    def add_communication_enhanced(self, comm_data, client_data):
        """Add communication to Communications sheet and save to Google Drive"""
        try:
            self.ensure_communications_sheet()
            
            # Save to spreadsheet
            values = [list(comm_data.values())]
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Communications!A:J',
                valueInputOption='RAW',
                body={'values': values}
            ).execute()
            
            # Save to Google Drive
            self.save_communication_to_drive(client_data, comm_data)
            
            logger.info(f"Added enhanced communication for client: {comm_data.get('client_id')}")
            return True
        except Exception as e:
            logger.error(f"Error adding enhanced communication: {e}")
            return False

    def get_client_communications(self, client_id):
        """Get all communications for a specific client"""
        try:
            self.ensure_communications_sheet()
            
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Communications!A2:J'
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

    def save_communication_to_drive(self, client, comm_data):
        """Save communication document to client's Communications folder"""
        try:
            if not client.get('folder_id'):
                return False

            query = f"name='Communications' and '{client['folder_id']}' in parents and trashed=false"
            results = self.service.files().list(q=query, fields="files(id)").execute()
            folders = results.get('files', [])

            if not folders:
                logger.error("Communications folder not found")
                return False

            comms_folder_id = folders[0]['id']

            # Create communication content with time tracking
            comm_content = f"""COMMUNICATION - {client['display_name']}
Communication ID: {comm_data.get('communication_id', '')}
Date: {comm_data.get('date', '')}
Time: {comm_data.get('time', 'Not recorded')}
Type: {comm_data.get('type', '')}
Subject: {comm_data.get('subject', '')}
Details: {comm_data.get('details', '')}
Outcome: {comm_data.get('outcome', '')}
Duration: {comm_data.get('duration', 'Not tracked')}
Follow Up Required: {comm_data.get('follow_up_required', 'No')}
Follow Up Date: {comm_data.get('follow_up_date', '')}
Created By: {comm_data.get('created_by', 'System User')}
"""

            file_metadata = {
                'name': f"Communication - {comm_data.get('type', 'Unknown')} - {comm_data.get('date', 'Unknown')}.txt",
                'parents': [comms_folder_id]
            }

            media = googleapiclient.http.MediaIoBaseUpload(
                io.BytesIO(comm_content.encode('utf-8')),
                mimetype='text/plain'
            )

            self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()

            logger.info(f"Saved communication to Google Drive for {client['display_name']}")
            return True
        except Exception as e:
            logger.error(f"Error saving communication to drive: {e}")
            return False

    # ==================== TASK MANAGEMENT FUNCTIONS - FIXED ====================

    def add_task_enhanced(self, task_data, client_data):
        """Add task to Tasks sheet and save to Google Drive"""
        try:
            self.ensure_tasks_sheet()
            
            # Prepare task data for spreadsheet
            task_row = [
                task_data.get('task_id', ''),
                task_data.get('client_id', ''),
                client_data.get('display_name', ''),
                task_data.get('task_type', ''),
                task_data.get('title', ''),
                task_data.get('description', ''),
                task_data.get('due_date', ''),
                task_data.get('priority', 'Medium'),
                task_data.get('status', 'Pending'),
                task_data.get('created_date', datetime.now().strftime('%Y-%m-%d'))
            ]
            
            # Add to Tasks sheet in main spreadsheet
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Tasks!A:J',
                valueInputOption='RAW',
                body={'values': [task_row]}
            ).execute()
            
            # Save to Google Drive
            self.save_task_to_drive(client_data, task_data)
            
            logger.info(f"Added task for client: {client_data.get('display_name')}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding task: {e}")
            return False

    def get_client_tasks(self, client_id):
        """Get all tasks for a specific client"""
        try:
            self.ensure_tasks_sheet()
            
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Tasks!A2:J'
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
                        'client_name': row[2],
                        'task_type': row[3],
                        'title': row[4],
                        'description': row[5],
                        'due_date': row[6],
                        'priority': row[7],
                        'status': row[8],
                        'created_date': row[9],
                        'completed_date': ''
                    })

            return sorted(tasks, key=lambda x: x['due_date'])
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            return []

    def get_upcoming_tasks(self, days_ahead=30):
        """Get all upcoming tasks within specified days"""
        try:
            self.ensure_tasks_sheet()
            
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Tasks!A2:J'
            ).execute()
            values = result.get('values', [])

            if not values:
                logger.info("No tasks found")
                return []

            upcoming_tasks = []
            today = datetime.now().date()
            future_date = today + timedelta(days=days_ahead)

            logger.info(f"Looking for tasks between {today} and {future_date}")

            for row in values:
                if len(row) >= 7 and row[6]:  # Check if due_date exists
                    try:
                        # Try multiple date formats
                        due_date_str = row[6].strip()
                        due_date = None
                        
                        # Try different date formats
                        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                            try:
                                due_date = datetime.strptime(due_date_str, fmt).date()
                                break
                            except ValueError:
                                continue
                        
                        if due_date and today <= due_date <= future_date:
                            status = row[8] if len(row) > 8 else 'Pending'
                            if status.lower() != 'completed':
                                task = {
                                    'task_id': row[0],
                                    'client_id': row[1],
                                    'client_name': row[2] if len(row) > 2 else 'Unknown',
                                    'task_type': row[3] if len(row) > 3 else '',
                                    'title': row[4] if len(row) > 4 else '',
                                    'description': row[5] if len(row) > 5 else '',
                                    'due_date': due_date_str,
                                    'due_date_obj': due_date,
                                    'priority': row[7] if len(row) > 7 else 'Medium',
                                    'status': status,
                                    'created_date': row[9] if len(row) > 9 else ''
                                }
                                upcoming_tasks.append(task)
                                logger.info(f"Found upcoming task: {task['title']}")
                                
                    except Exception as e:
                        logger.error(f"Error processing task: {e}")
                        continue

            logger.info(f"Found {len(upcoming_tasks)} upcoming tasks")
            return sorted(upcoming_tasks, key=lambda x: x['due_date_obj'])
            
        except Exception as e:
            logger.error(f"Error getting upcoming tasks: {e}")
            return []

    def complete_task(self, task_id):
        """Mark task as completed in Tasks sheet"""
        try:
            self.ensure_tasks_sheet()
            
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Tasks!A:J'
            ).execute()
            values = result.get('values', [])

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == task_id:
                    # Update status to Completed (column 9 = index 8)
                    if len(row) >= 9:
                        row[8] = 'Completed'
                    else:
                        while len(row) < 9:
                            row.append('')
                        row[8] = 'Completed'

                    self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=f'Tasks!A{i+1}:J{i+1}',
                        valueInputOption='RAW',
                        body={'values': [row]}
                    ).execute()

                    logger.info(f"Completed task: {task_id}")
                    return True

            return False
        except Exception as e:
            logger.error(f"Error completing task: {e}")
            return False

    def save_task_to_drive(self, client, task_data):
        """Save task document to client's Tasks folder"""
        try:
            if not client.get('folder_id'):
                return False

            query = f"name='Tasks' and '{client['folder_id']}' in parents and trashed=false"
            results = self.service.files().list(q=query, fields="files(id)").execute()
            folders = results.get('files', [])

            if not folders:
                logger.error("Tasks folder not found")
                return False

            tasks_folder_id = folders[0]['id']

            # Create task content with time tracking
            task_content = f"""TASK - {client['display_name']}
Task ID: {task_data.get('task_id', '')}
Created Date: {task_data.get('created_date', '')}
Due Date: {task_data.get('due_date', '')}
Priority: {task_data.get('priority', 'Medium')}
Type: {task_data.get('task_type', '')}
Title: {task_data.get('title', '')}
Description: {task_data.get('description', '')}
Status: {task_data.get('status', 'Pending')}
Time Spent: {task_data.get('time_spent', 'Not tracked')}
"""

            file_metadata = {
                'name': f"Task - {task_data.get('title', 'Untitled')} - {task_data.get('created_date', 'Unknown')}.txt",
                'parents': [tasks_folder_id]
            }

            media = googleapiclient.http.MediaIoBaseUpload(
                io.BytesIO(task_content.encode('utf-8')),
                mimetype='text/plain'
            )

            self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()

            logger.info(f"Saved task to Google Drive for {client['display_name']}")
            return True
        except Exception as e:
            logger.error(f"Error saving task to drive: {e}")
            return False

    # ==================== FACT FIND FUNCTIONS ====================

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
