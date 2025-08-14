# models/google_drive.py
"""
WealthPro CRM - Google Drive Integration Model
CLEAN WORKING VERSION - RESTORE CLIENTS AND FIX FOLDERS
"""

import os
import io
import logging
from datetime import datetime, timedelta
from googleapiclient.discovery import build
import googleapiclient.http

logger = logging.getLogger(__name__)

SPREADSHEET_ID = None
PROFILES_SPREADSHEET_ID = None
COMMUNICATIONS_SPREADSHEET_ID = None
TASKS_SPREADSHEET_ID = None

class SimpleGoogleDrive:
    def __init__(self, credentials):
        global SPREADSHEET_ID, PROFILES_SPREADSHEET_ID, COMMUNICATIONS_SPREADSHEET_ID, TASKS_SPREADSHEET_ID
        # ↓↓↓ Memory-friendly clients
        self.service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
        self.sheets_service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)
        self.main_folder_id = None
        self.client_files_folder_id = None
        self.spreadsheet_id = SPREADSHEET_ID
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

    def find_or_create_profiles_spreadsheet(self):
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

    def ensure_status_folders(self):
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
        self.ensure_status_folders()
        if status == 'active':
            return getattr(self, 'active_clients_folder_id', None)
        elif status in ['no_longer_client', 'former']:
            return getattr(self, 'former_clients_folder_id', None)
        elif status in ['deceased', 'death']:
            return getattr(self, 'deceased_clients_folder_id', None)
        else:
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
        try:
            self.ensure_status_folders()
            letter = surname[0].upper() if surname else 'Z'
            status_folder_id = self.get_status_folder_id(status)
            letter_folder_id = self.create_folder(letter, status_folder_id)

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

            for doc_type in document_folders:
                review_subfolder_id = self.create_folder(doc_type, reviews_folder_id)
                sub_folder_ids[f'Reviews_{doc_type}'] = review_subfolder_id

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
        try:
            old_folder_id = client['folder_id']
            if not old_folder_id:
                return False

            logger.info(f"Moving {client['display_name']} to {new_status} section")
            self.ensure_status_folders()

            new_status_folder_id = self.get_status_folder_id(new_status)
            letter = client['surname'][0].upper() if client['surname'] else 'Z'
            new_letter_folder_id = self.create_folder(letter, new_status_folder_id)

            file = self.service.files().get(fileId=old_folder_id, fields='parents').execute()
            previous_parents = ",".join(file.get('parents', []))

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

    def add_client(self, client_data):
        try:
            values = [[
                client_data.get('client_id', ''),
                client_data.get('display_name', ''),
                client_data.get('first_name', ''),
                client_data.get('surname', ''),
                client_data.get('email', ''),
                client_data.get('phone', ''),
                client_data.get('status', ''),
                client_data.get('date_added', ''),
                client_data.get('folder_id', ''),
                client_data.get('portfolio_value', 0),
                client_data.get('notes', '')
            ]]
            
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
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A:K'
            ).execute()
            values = result.get('values', [])

            clients = []
            for i, row in enumerate(values):
                if i == 0:
                    continue
                    
                if row and len(row) > 0:
                    if len(row) >= 9:
                        while len(row) < 11:
                            row.append('')
                        
                        try:
                            portfolio_value = float(row[9]) if row[9] and str(row[9]).replace('.', '').isdigit() else 0.0
                        except (ValueError, TypeError):
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
                    else:
                        data_string = str(row[0])
                        import re
                        
                        client_id_match = re.search(r'(WP\d{14})', data_string)
                        if not client_id_match:
                            continue
                        client_id = client_id_match.group(1)
                        
                        folder_id_matches = re.findall(r'(1[A-Za-z0-9_-]{33})', data_string)
                        folder_id = folder_id_matches[0] if folder_id_matches else None
                        
                        email_match = re.search(r'([^@\s]+@[^@\s]+\.[^@\s]+)', data_string)
                        email = email_match.group(1) if email_match else ''
                        
                        if email:
                            email_pos = data_string.find(email)
                            name_section = data_string[len(client_id):email_pos]
                            display_name = name_section.strip()
                            display_name = re.sub(r'\d+$', '', display_name).strip()
                        else:
                            display_name = "Unknown Client"
                        
                        status_match = re.search(r'(prospect|active|no_longer_client|deceased)', data_string, re.IGNORECASE)
                        status = status_match.group(1).lower() if status_match else 'prospect'
                        
                        portfolio_matches = re.findall(r'(\d+)', data_string)
                        portfolio_value = 0.0
                        if portfolio_matches:
                            for match in reversed(portfolio_matches):
                                if len(match) <= 8 and not match.startswith('2025'):
                                    portfolio_value = float(match)
                                    break
                        
                        phone_matches = re.findall(r'(\d{8,15})', data_string)
                        phone = ''
                        if phone_matches:
                            for p in phone_matches:
                                if not p.startswith('WP') and not p.startswith('2025') and len(p) >= 8:
                                    phone = p
                                    break
                        
                        client_data = {
                            'client_id': client_id,
                            'display_name': display_name,
                            'first_name': '',
                            'surname': '',
                            'email': email,
                            'phone': phone,
                            'status': status,
                            'date_added': '2025-08-06',
                            'folder_id': folder_id,
                            'portfolio_value': portfolio_value,
                            'notes': ''
                        }
                    
                    if client_data['folder_id']:
                        client_data['folder_url'] = f"https://drive.google.com/drive/folders/{client_data['folder_id']}"
                    else:
                        client_data['folder_url'] = None
                    
                    clients.append(client_data)

            logger.info(f"Successfully loaded {len(clients)} clients")
            return sorted(clients, key=lambda x: x['display_name'])
            
        except Exception as e:
            logger.error(f"Error getting clients: {e}")
            return []

    def update_client_status(self, client_id, new_status):
        try:
            clients = self.get_clients_enhanced()
            client = next((c for c in clients if c['client_id'] == client_id), None)
            if not client:
                logger.error(f"Client {client_id} not found")
                return False

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

            if client.get('folder_id'):
                self.move_client_folder(client, new_status)

            return True
        except Exception as e:
            logger.error(f"Error updating client status: {e}")
            return False

    def delete_client(self, client_id):
        try:
            clients = self.get_clients_enhanced()
            client = next((c for c in clients if c['client_id'] == client_id), None)
            if not client:
                return False

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

    def add_client_profile(self, profile_data):
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
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.profiles_spreadsheet_id,
                range='Sheet1!A2:S'
            ).execute()
            values = result.get('values', [])

            for row in values:
                if len(row) > 0 and row[0] == client_id:
                    while len(row) < 19:
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
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.profiles_spreadsheet_id,
                range='Sheet1!A:S'
            ).execute()
            values = result.get('values', [])

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == client_id:
                    updated_row = list(profile_data.values())
                    self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.profiles_spreadsheet_id,
                        range=f'Sheet1!A{i+1}:S{i+1}',
                        valueInputOption='RAW',
                        body={'values': [updated_row]}
                    ).execute()
                    logger.info(f"Updated client profile: {client_id}")
                    return True

            return self.add_client_profile(profile_data)
        except Exception as e:
            logger.error(f"Error updating client profile: {e}")
            return False

    def add_communication_enhanced(self, comm_data, client_data):
        try:
            values = [list(comm_data.values())]
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.communications_spreadsheet_id,
                range='Sheet1!A:J',
                valueInputOption='RAW',
                body={'values': values}
            ).execute()
            
            self.save_communication_to_drive(client_data, comm_data)
            
            logger.info(f"Added enhanced communication for client: {comm_data.get('client_id')}")
            return True
        except Exception as e:
            logger.error(f"Error adding enhanced communication: {e}")
            return False

    def get_client_communications(self, client_id):
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.communications_spreadsheet_id,
                range='Sheet1!A2:J'
            ).execute()
            values = result.get('values', [])

            communications = []
            for row in values:
                if len(row) > 1 and row[1] == client_id:
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

    def add_task_enhanced(self, task_data, client_data):
        try:
            task_row = [
                task_data.get('task_id', ''),
                task_data.get('client_id', ''),
                task_data.get('task_type', ''),
                task_data.get('title', ''),
                task_data.get('description', ''),
                task_data.get('due_date', ''),
                task_data.get('priority', 'Medium'),
                task_data.get('status', 'Pending'),
                task_data.get('created_date', datetime.now().strftime('%Y-%m-%d')),
                task_data.get('completed_date', '')
            ]
            
            result = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.tasks_spreadsheet_id,
                range='Sheet1!A:J',
                valueInputOption='RAW',
                body={'values': [task_row]}
            ).execute()
            
            logger.info(f"Task saved to spreadsheet: {result}")
            
            self.save_task_to_drive(client_data, task_data)
            
            logger.info(f"Added enhanced task for client: {task_data.get('client_id')}")
            return True
        except Exception as e:
            logger.error(f"Error adding enhanced task: {e}")
            return False

    def get_client_tasks(self, client_id):
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id,
                range='Sheet1!A2:J'
            ).execute()
            values = result.get('values', [])

            tasks = []
            for row in values:
                if len(row) > 1 and row[1] == client_id:
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

    def get_upcoming_tasks(self, days_ahead=30):
        try:
            if not self.tasks_spreadsheet_id:
                logger.error("Tasks spreadsheet ID not found")
                return []
                
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id,
                range='Sheet1!A2:J'
            ).execute()
            values = result.get('values', [])

            if not values:
                logger.info("No tasks found in spreadsheet")
                return []

            upcoming_tasks = []
            today = datetime.now().date()
            future_date = today + timedelta(days=days_ahead)

            logger.info(f"Looking for tasks between {today} and {future_date}")

            for i, row in enumerate(values, start=2):
                if len(row) >= 6 and row[5]:
                    try:
                        due_date_str = row[5].strip()
                        due_date = None
                        
                        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                            try:
                                due_date = datetime.strptime(due_date_str, fmt).date()
                                break
                            except ValueError:
                                continue
                        
                        if due_date and today <= due_date <= future_date:
                            status = row[7] if len(row) > 7 else 'Pending'
                            if status.lower() != 'completed':
                                while len(row) < 10:
                                    row.append('')
                                
                                client_name = self.get_client_name_by_id(row[1]) if len(row) > 1 else 'Unknown Client'
                                
                                task = {
                                    'task_id': row[0],
                                    'client_id': row[1],
                                    'client_name': client_name,
                                    'task_type': row[2],
                                    'title': row[3],
                                    'description': row[4],
                                    'due_date': due_date_str,
                                    'due_date_obj': due_date,
                                    'priority': row[6],
                                    'status': status,
                                    'created_date': row[8],
                                    'completed_date': row[9]
                                }
                                upcoming_tasks.append(task)
                                logger.info(f"Found upcoming task: {task['title']} for {client_name}")
                                
                    except Exception as e:
                        logger.error(f"Error processing task row {i}: {e}")
                        continue

            logger.info(f"Found {len(upcoming_tasks)} upcoming tasks")
            return sorted(upcoming_tasks, key=lambda x: x['due_date_obj'])
            
        except Exception as e:
            logger.error(f"Error getting upcoming tasks: {e}")
            return []

    def get_client_name_by_id(self, client_id):
        try:
            clients = self.get_clients_enhanced()
            for client in clients:
                if client['client_id'] == client_id:
                    return client['display_name']
            return 'Unknown Client'
        except Exception as e:
            logger.error(f"Error getting client name: {e}")
            return 'Unknown Client'

    def complete_task(self, task_id):
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id,
                range='Sheet1!A:J'
            ).execute()
            values = result.get('values', [])

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == task_id:
                    if len(row) > 7:
                        row[7] = 'Completed'
                    if len(row) > 9:
                        row[9] = datetime.now().strftime('%Y-%m-%d')
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

    def save_task_to_drive(self, client, task_data):
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

    def save_fact_find_to_drive(self, client, fact_find_data):
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
