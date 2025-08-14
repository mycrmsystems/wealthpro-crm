"""
WealthPro CRM - Google Drive Integration Model
FULL WORKING VERSION — Tasks folders (Ongoing/Completed) + file move on completion
"""

import os
import io
import re
import logging
from datetime import datetime, timedelta

from googleapiclient.discovery import build
import googleapiclient.http

logger = logging.getLogger(__name__)

# Cached spreadsheet IDs for this process (so we don’t recreate needlessly)
SPREADSHEET_ID = None
PROFILES_SPREADSHEET_ID = None
COMMUNICATIONS_SPREADSHEET_ID = None
TASKS_SPREADSHEET_ID = None


class SimpleGoogleDrive:
    def __init__(self, credentials):
        """
        Build Drive & Sheets clients. We explicitly set cache_discovery=False to
        reduce memory/CPU on Render free tier.
        """
        global SPREADSHEET_ID, PROFILES_SPREADSHEET_ID, COMMUNICATIONS_SPREADSHEET_ID, TASKS_SPREADSHEET_ID

        self.service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
        self.sheets_service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)

        # Root/status folders (created on demand)
        self.main_folder_id = None
        self.active_clients_folder_id = None
        self.former_clients_folder_id = None
        self.deceased_clients_folder_id = None

        # Sheets
        self.spreadsheet_id = SPREADSHEET_ID
        self.profiles_spreadsheet_id = PROFILES_SPREADSHEET_ID
        self.communications_spreadsheet_id = COMMUNICATIONS_SPREADSHEET_ID
        self.tasks_spreadsheet_id = TASKS_SPREADSHEET_ID

        self.setup()

    # ---------------------------
    # One-time setup (Sheets)
    # ---------------------------
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

            logger.info("Google Drive/Sheets setup complete.")
        except Exception as e:
            logger.error(f"Setup error: {e}")

    def find_or_create_spreadsheet(self):
        try:
            query = "name='WealthPro CRM - Clients Data' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            res = self.service.files().list(q=query, fields="files(id,name)").execute()
            files = res.get('files', [])
            if files:
                self.spreadsheet_id = files[0]['id']
            else:
                self.create_new_spreadsheet()
        except Exception as e:
            logger.error(f"Error finding client spreadsheet: {e}")
            self.create_new_spreadsheet()

    def create_new_spreadsheet(self):
        try:
            body = {'properties': {'title': 'WealthPro CRM - Clients Data'}}
            created = self.sheets_service.spreadsheets().create(body=body).execute()
            self.spreadsheet_id = created['spreadsheetId']
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
        except Exception as e:
            logger.error(f"Error creating client spreadsheet: {e}")

    def find_or_create_profiles_spreadsheet(self):
        try:
            query = "name='WealthPro CRM - Client Profiles' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            res = self.service.files().list(q=query, fields="files(id,name)").execute()
            files = res.get('files', [])
            if files:
                self.profiles_spreadsheet_id = files[0]['id']
            else:
                self.create_new_profiles_spreadsheet()
        except Exception as e:
            logger.error(f"Error finding profiles spreadsheet: {e}")
            self.create_new_profiles_spreadsheet()

    def create_new_profiles_spreadsheet(self):
        try:
            body = {'properties': {'title': 'WealthPro CRM - Client Profiles'}}
            created = self.sheets_service.spreadsheets().create(body=body).execute()
            self.profiles_spreadsheet_id = created['spreadsheetId']
            headers = [
                'Client ID', 'Address Line 1', 'Address Line 2', 'City', 'County', 'Postcode', 'Country',
                'Date of Birth', 'Occupation', 'Employer', 'Emergency Contact Name', 'Emergency Contact Phone',
                'Emergency Contact Relationship', 'Investment Goals', 'Risk Profile', 'Preferred Contact Method',
                'Next Review Date', 'Created Date', 'Last Updated'
            ]
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.profiles_spreadsheet_id, range='Sheet1!A1:S1',
                valueInputOption='RAW', body={'values': [headers]}
            ).execute()
        except Exception as e:
            logger.error(f"Error creating profiles spreadsheet: {e}")

    def find_or_create_communications_spreadsheet(self):
        try:
            query = "name='WealthPro CRM - Communications' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            res = self.service.files().list(q=query, fields="files(id,name)").execute()
            files = res.get('files', [])
            if files:
                self.communications_spreadsheet_id = files[0]['id']
            else:
                self.create_new_communications_spreadsheet()
        except Exception as e:
            logger.error(f"Error finding communications spreadsheet: {e}")
            self.create_new_communications_spreadsheet()

    def create_new_communications_spreadsheet(self):
        try:
            body = {'properties': {'title': 'WealthPro CRM - Communications'}}
            created = self.sheets_service.spreadsheets().create(body=body).execute()
            self.communications_spreadsheet_id = created['spreadsheetId']
            headers = [
                'Communication ID', 'Client ID', 'Date', 'Type', 'Subject', 'Details',
                'Outcome', 'Follow Up Required', 'Follow Up Date', 'Created By'
            ]
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.communications_spreadsheet_id, range='Sheet1!A1:J1',
                valueInputOption='RAW', body={'values': [headers]}
            ).execute()
        except Exception as e:
            logger.error(f"Error creating communications spreadsheet: {e}")

    def find_or_create_tasks_spreadsheet(self):
        try:
            query = "name='WealthPro CRM - Tasks & Reminders' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            res = self.service.files().list(q=query, fields="files(id,name)").execute()
            files = res.get('files', [])
            if files:
                self.tasks_spreadsheet_id = files[0]['id']
            else:
                self.create_new_tasks_spreadsheet()
        except Exception as e:
            logger.error(f"Error finding tasks spreadsheet: {e}")
            self.create_new_tasks_spreadsheet()

    def create_new_tasks_spreadsheet(self):
        try:
            body = {'properties': {'title': 'WealthPro CRM - Tasks & Reminders'}}
            created = self.sheets_service.spreadsheets().create(body=body).execute()
            self.tasks_spreadsheet_id = created['spreadsheetId']
            headers = [
                'Task ID', 'Client ID', 'Task Type', 'Title', 'Description', 'Due Date',
                'Priority', 'Status', 'Created Date', 'Completed Date'
            ]
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.tasks_spreadsheet_id, range='Sheet1!A1:J1',
                valueInputOption='RAW', body={'values': [headers]}
            ).execute()
        except Exception as e:
            logger.error(f"Error creating tasks spreadsheet: {e}")

    # ---------------------------
    # Status folders (A–Z, Active/Former/Deceased)
    # ---------------------------
    def ensure_status_folders(self):
        try:
            if not hasattr(self, '_status_folders_created'):
                self.main_folder_id = self.create_folder('WealthPro CRM - Client Files', None)
                self.active_clients_folder_id = self.create_folder('Active Clients', self.main_folder_id)
                self.former_clients_folder_id = self.create_folder('Former Clients', self.main_folder_id)
                self.deceased_clients_folder_id = self.create_folder('Deceased Clients', self.main_folder_id)
                self._status_folders_created = True
        except Exception as e:
            logger.error(f"Error creating status folders: {e}")

    def get_status_folder_id(self, status):
        self.ensure_status_folders()
        if status == 'active':
            return self.active_clients_folder_id
        elif status in ['no_longer_client', 'former']:
            return self.former_clients_folder_id
        elif status in ['deceased', 'death']:
            return self.deceased_clients_folder_id
        else:
            return self.active_clients_folder_id

    # ---------------------------
    # Generic folder helpers
    # ---------------------------
    def create_folder(self, name, parent_id):
        try:
            if parent_id:
                query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
            else:
                query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"

            res = self.service.files().list(q=query, fields="files(id)").execute()
            folders = res.get('files', [])
            if folders:
                return folders[0]['id']

            meta = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
            if parent_id:
                meta['parents'] = [parent_id]
            folder = self.service.files().create(body=meta, fields='id').execute()
            return folder.get('id')
        except Exception as e:
            logger.error(f"Error creating folder {name}: {e}")
            return None

    def get_or_create_task_subfolders(self, client_folder_id):
        """
        Ensure the client has Tasks/Ongoing Tasks/Completed Tasks and return their IDs.
        """
        tasks_id = self.create_folder("Tasks", client_folder_id)
        ongoing_id = self.create_folder("Ongoing Tasks", tasks_id)
        completed_id = self.create_folder("Completed Tasks", tasks_id)
        return tasks_id, ongoing_id, completed_id

    # ---------------------------
    # Client folder structure
    # ---------------------------
    def create_client_folder_enhanced(self, first_name, surname, status='prospect'):
        """
        Creates the client folder in the relevant status area, A–Z under surname initial.
        Builds standard subfolders including Tasks/Ongoing/Completed + Communications + Reviews tree.
        """
        try:
            self.ensure_status_folders()
            letter = surname[0].upper() if surname else 'Z'
            status_folder_id = self.get_status_folder_id(status)
            letter_folder_id = self.create_folder(letter, status_folder_id)

            display_name = f"{surname}, {first_name}"
            client_folder_id = self.create_folder(display_name, letter_folder_id)

            # Reviews root (Year subfolders can be added later by review features)
            reviews_folder_id = self.create_folder("Reviews", client_folder_id)

            # Standard document subfolders (top level)
            document_folders = [
                "ID&V", "FF & ATR", "Research", "LOAs", "Suitability Letter",
                "Meeting Notes", "Terms of Business", "Policy Information", "Valuation"
            ]
            sub_folder_ids = {'Reviews': reviews_folder_id}
            for doc_type in document_folders:
                sub_folder_ids[doc_type] = self.create_folder(doc_type, client_folder_id)

            # Reviews mirror (optional yearly subfolders will be created elsewhere)
            for doc_type in document_folders:
                sub_folder_ids[f"Reviews_{doc_type}"] = self.create_folder(doc_type, reviews_folder_id)

            # Communications
            communications_folder_id = self.create_folder("Communications", client_folder_id)
            sub_folder_ids['Communications'] = communications_folder_id

            # Tasks (with Ongoing/Completed)
            tasks_folder_id, ongoing_id, completed_id = self.get_or_create_task_subfolders(client_folder_id)
            sub_folder_ids['Tasks'] = tasks_folder_id
            sub_folder_ids['Tasks_Ongoing'] = ongoing_id
            sub_folder_ids['Tasks_Completed'] = completed_id

            logger.info(f"Created enhanced client folder for {display_name} in {status} section")
            return {'client_folder_id': client_folder_id, 'sub_folders': sub_folder_ids}
        except Exception as e:
            logger.error(f"Error creating enhanced client folder: {e}")
            return None

    def get_folder_url(self, folder_id):
        return f"https://drive.google.com/drive/folders/{folder_id}"

    def move_client_folder(self, client, new_status):
        """
        Move the client’s whole folder to the new status/letter parent.
        """
        try:
            old_folder_id = client.get('folder_id')
            if not old_folder_id:
                return False

            self.ensure_status_folders()
            new_status_folder_id = self.get_status_folder_id(new_status)
            letter = (client.get('surname') or 'Z')[0].upper()
            new_letter_folder_id = self.create_folder(letter, new_status_folder_id)

            file = self.service.files().get(fileId=old_folder_id, fields='parents').execute()
            prev_parents = ",".join(file.get('parents', []))

            self.service.files().update(
                fileId=old_folder_id,
                addParents=new_letter_folder_id,
                removeParents=prev_parents,
                fields='id, parents'
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Error moving client folder: {e}")
            return False

    # ---------------------------
    # Clients sheet I/O
    # ---------------------------
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
            return True
        except Exception as e:
            logger.error(f"Error adding client: {e}")
            return False

    def get_clients_enhanced(self):
        try:
            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range='Sheet1!A:K'
            ).execute()
            values = res.get('values', [])

            clients = []
            for i, row in enumerate(values):
                if i == 0:
                    continue
                if not row:
                    continue

                # Pad row to 11 columns to avoid index errors
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
                client_data['folder_url'] = self.get_folder_url(row[8]) if row[8] else None
                if client_data['client_id']:
                    clients.append(client_data)

            return sorted(clients, key=lambda x: x['display_name'] or '')
        except Exception as e:
            logger.error(f"Error getting clients: {e}")
            return []

    def update_client_status(self, client_id, new_status):
        try:
            clients = self.get_clients_enhanced()
            client = next((c for c in clients if c['client_id'] == client_id), None)
            if not client:
                return False

            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range='Sheet1!A:K'
            ).execute()
            values = res.get('values', [])

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == client_id:
                    while len(row) < 11:
                        row.append('')
                    row[6] = new_status
                    self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=f'Sheet1!A{i+1}:K{i+1}',
                        valueInputOption='RAW',
                        body={'values': [row]}
                    ).execute()
                    break

            # Move folder in Drive, if exists
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

            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range='Sheet1!A:K'
            ).execute()
            values = res.get('values', [])

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == client_id:
                    self.sheets_service.spreadsheets().values().clear(
                        spreadsheetId=self.spreadsheet_id, range=f'Sheet1!A{i+1}:K{i+1}'
                    ).execute()
                    break

            # Trash Drive folder (soft delete)
            if client.get('folder_id'):
                self.service.files().update(fileId=client['folder_id'], body={'trashed': True}).execute()

            return True
        except Exception as e:
            logger.error(f"Error deleting client: {e}")
            return False

    # ---------------------------
    # Profiles
    # ---------------------------
    def add_client_profile(self, profile_data):
        try:
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.profiles_spreadsheet_id,
                range='Sheet1!A:S',
                valueInputOption='RAW',
                body={'values': [list(profile_data.values())]}
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Error adding client profile: {e}")
            return False

    def get_client_profile(self, client_id):
        try:
            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.profiles_spreadsheet_id, range='Sheet1!A2:S'
            ).execute()
            values = res.get('values', []) or []
            for row in values:
                if len(row) > 0 and row[0] == client_id:
                    while len(row) < 19:
                        row.append('')
                    keys = [
                        'client_id','address_line_1','address_line_2','city','county','postcode','country',
                        'date_of_birth','occupation','employer','emergency_contact_name','emergency_contact_phone',
                        'emergency_contact_relationship','investment_goals','risk_profile','preferred_contact_method',
                        'next_review_date','created_date','last_updated'
                    ]
                    return dict(zip(keys, row))
            return None
        except Exception as e:
            logger.error(f"Error getting client profile: {e}")
            return None

    def update_client_profile(self, client_id, profile_data):
        try:
            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.profiles_spreadsheet_id, range='Sheet1!A:S'
            ).execute()
            values = res.get('values', []) or []

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == client_id:
                    self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.profiles_spreadsheet_id,
                        range=f'Sheet1!A{i+1}:S{i+1}',
                        valueInputOption='RAW',
                        body={'values': [list(profile_data.values())]}
                    ).execute()
                    return True

            return self.add_client_profile(profile_data)
        except Exception as e:
            logger.error(f"Error updating client profile: {e}")
            return False

    # ---------------------------
    # Communications
    # ---------------------------
    def add_communication_enhanced(self, comm_data, client_data):
        try:
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.communications_spreadsheet_id,
                range='Sheet1!A:J',
                valueInputOption='RAW',
                body={'values': [list(comm_data.values())]}
            ).execute()
            self.save_communication_to_drive(client_data, comm_data)
            return True
        except Exception as e:
            logger.error(f"Error adding enhanced communication: {e}")
            return False

    def get_client_communications(self, client_id):
        try:
            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.communications_spreadsheet_id, range='Sheet1!A2:J'
            ).execute()
            values = res.get('values', []) or []
            comms = []
            for row in values:
                if len(row) > 1 and row[1] == client_id:
                    while len(row) < 10:
                        row.append('')
                    comms.append({
                        'communication_id': row[0],
                        'client_id': row[1],
                        'date': row[2],
                        'type': row[3],
                        'subject': row[4],
                        'details': row[5],
                        'outcome': row[6],
                        'follow_up_required': row[7],
                        'follow_up_date': row[8],
                        'created_by': row[9],
                        # optional extra fields in UI:
                        'time': '',
                        'duration': ''
                    })
            return sorted(comms, key=lambda x: x['date'], reverse=True)
        except Exception as e:
            logger.error(f"Error getting communications: {e}")
            return []

    def save_communication_to_drive(self, client, comm_data):
        try:
            folder_id = client.get('folder_id')
            if not folder_id:
                return False

            # Find Communications folder under client root
            query = f"name='Communications' and '{folder_id}' in parents and trashed=false"
            res = self.service.files().list(q=query, fields="files(id)").execute()
            folders = res.get('files', [])
            if not folders:
                return False
            comms_folder_id = folders[0]['id']

            content = f"""COMMUNICATION - {client['display_name']}
Communication ID: {comm_data.get('communication_id','')}
Date: {comm_data.get('date','')}
Time: {comm_data.get('time','')}
Type: {comm_data.get('type','')}
Subject: {comm_data.get('subject','')}
Details: {comm_data.get('details','')}
Outcome: {comm_data.get('outcome','')}
Duration: {comm_data.get('duration','')}
Follow Up Required: {comm_data.get('follow_up_required','')}
Follow Up Date: {comm_data.get('follow_up_date','')}
Created By: {comm_data.get('created_by','')}
"""
            file_metadata = {
                'name': f"{comm_data.get('communication_id','COM')} - {comm_data.get('type','Unknown')} - {comm_data.get('date','Unknown')}.txt",
                'parents': [comms_folder_id]
            }
            media = googleapiclient.http.MediaIoBaseUpload(
                io.BytesIO(content.encode('utf-8')), mimetype='text/plain'
            )
            self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            return True
        except Exception as e:
            logger.error(f"Error saving communication to Drive: {e}")
            return False

    # ---------------------------
    # Tasks
    # ---------------------------
    def add_task_enhanced(self, task_data, client_data):
        """
        Save the task row in the Tasks sheet and write a file into the client’s
        Tasks/Ongoing Tasks folder. The filename begins with Task ID so we can
        reliably find & move it when completed.
        """
        try:
            # 1) Save to sheet
            row = [
                task_data.get('task_id',''),
                task_data.get('client_id',''),
                task_data.get('task_type',''),
                task_data.get('title',''),
                task_data.get('description',''),
                task_data.get('due_date',''),
                task_data.get('priority','Medium'),
                task_data.get('status','Pending'),
                task_data.get('created_date', datetime.now().strftime('%Y-%m-%d')),
                task_data.get('completed_date','')
            ]
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.tasks_spreadsheet_id,
                range='Sheet1!A:J',
                valueInputOption='RAW',
                body={'values': [row]}
            ).execute()

            # 2) Save task file into Ongoing Tasks
            self.save_task_to_drive(client_data, task_data)
            return True
        except Exception as e:
            logger.error(f"Error adding enhanced task: {e}")
            return False

    def get_client_tasks(self, client_id):
        try:
            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id, range='Sheet1!A2:J'
            ).execute()
            values = res.get('values', []) or []
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
            # Sort by due date (string-safe)
            return sorted(tasks, key=lambda x: (x['due_date'] or '9999-12-31'))
        except Exception as e:
            logger.error(f"Error getting client tasks: {e}")
            return []

    def get_upcoming_tasks(self, days_ahead=30):
        """
        Returns all tasks due within next N days (and not completed).
        """
        try:
            if not self.tasks_spreadsheet_id:
                return []

            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id, range='Sheet1!A2:J'
            ).execute()
            values = res.get('values', []) or []
            upcoming = []
            today = datetime.now().date()
            future = today + timedelta(days=days_ahead)

            for row in values:
                while len(row) < 10:
                    row.append('')
                due_str = row[5].strip() if len(row) > 5 and row[5] else ''
                status = (row[7] or 'Pending').lower()
                if not due_str or status == 'completed':
                    continue

                due_date = None
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                    try:
                        due_date = datetime.strptime(due_str, fmt).date()
                        break
                    except ValueError:
                        continue
                if not due_date:
                    continue

                if today <= due_date <= future:
                    upcoming.append({
                        'task_id': row[0], 'client_id': row[1], 'task_type': row[2],
                        'title': row[3], 'description': row[4], 'due_date': row[5],
                        'priority': row[6], 'status': row[7], 'created_date': row[8],
                        'completed_date': row[9],
                        'due_date_obj': due_date
                    })

            return sorted(upcoming, key=lambda x: x['due_date_obj'])
        except Exception as e:
            logger.error(f"Error getting upcoming tasks: {e}")
            return []

    def get_client_name_by_id(self, client_id):
        try:
            for c in self.get_clients_enhanced():
                if c['client_id'] == client_id:
                    return c['display_name']
            return 'Unknown Client'
        except Exception as e:
            logger.error(f"Error getting client name: {e}")
            return 'Unknown Client'

    def complete_task(self, task_id):
        """
        Mark the task Completed in the sheet, set Completed Date, and move its
        Drive file from Ongoing → Completed (rename to include '(Completed)').
        """
        try:
            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id, range='Sheet1!A:J'
            ).execute()
            values = res.get('values', []) or []

            target_row_index = None
            client_id_for_task = None
            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == task_id:
                    target_row_index = i
                    if len(row) > 1:
                        client_id_for_task = row[1]
                    # pad
                    while len(row) < 10:
                        row.append('')
                    # update status + completed date
                    row[7] = 'Completed'
                    row[9] = datetime.now().strftime('%Y-%m-%d')
                    self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.tasks_spreadsheet_id,
                        range=f'Sheet1!A{ i+1 }:J{ i+1 }',
                        valueInputOption='RAW',
                        body={'values': [row]}
                    ).execute()
                    break

            if client_id_for_task:
                # get client to find folders
                clients = self.get_clients_enhanced()
                client = next((c for c in clients if c['client_id'] == client_id_for_task), None)
                if client and client.get('folder_id'):
                    self._move_task_file_to_completed(client, task_id)

            return True if target_row_index is not None else False
        except Exception as e:
            logger.error(f"Error completing task: {e}")
            return False

    def save_task_to_drive(self, client, task_data):
        """
        Create a small .txt file for the task in the client's Ongoing Tasks folder.
        The filename starts with Task ID so we can locate it later.
        """
        try:
            folder_id = client.get('folder_id')
            if not folder_id:
                return False

            # Ensure Tasks/Ongoing/Completed exist
            _, ongoing_id, _ = self.get_or_create_task_subfolders(folder_id)

            content = f"""TASK - {client['display_name']}
Task ID: {task_data.get('task_id','')}
Created Date: {task_data.get('created_date','')}
Due Date: {task_data.get('due_date','')}
Priority: {task_data.get('priority','Medium')}
Type: {task_data.get('task_type','')}
Title: {task_data.get('title','')}
Description: {task_data.get('description','')}
Status: {task_data.get('status','Pending')}
Time Spent: {task_data.get('time_spent','')}
"""

            filename = f"{task_data.get('task_id','TSK')} - {task_data.get('title','Untitled')} - Created {task_data.get('created_date','Unknown')}.txt"
            file_metadata = {'name': filename, 'parents': [ongoing_id]}
            media = googleapiclient.http.MediaIoBaseUpload(
                io.BytesIO(content.encode('utf-8')), mimetype='text/plain'
            )
            self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            return True
        except Exception as e:
            logger.error(f"Error saving task to drive: {e}")
            return False

    def _move_task_file_to_completed(self, client, task_id):
        """
        Find the task file in Ongoing Tasks by filename prefix "{task_id} -"
        and move+rename it into Completed Tasks with "(Completed)" suffix.
        """
        try:
            folder_id = client.get('folder_id')
            if not folder_id:
                return False

            # Ensure we have the subfolders
            _, ongoing_id, completed_id = self.get_or_create_task_subfolders(folder_id)

            # Find file in Ongoing whose name starts with "{task_id} -"
            query = (
                f"'{ongoing_id}' in parents and trashed=false "
                f"and name contains '{task_id} -'"
            )
            res = self.service.files().list(q=query, fields="files(id,name,parents)").execute()
            files = res.get('files', []) or []
            if not files:
                # Could be in Tasks root from older runs; try broader search
                query_any = (
                    f"'{folder_id}' in parents and trashed=false and name contains '{task_id} -'"
                )
                res_any = self.service.files().list(q=query_any, fields="files(id,name,parents)").execute()
                files = res_any.get('files', []) or []
                if not files:
                    return False

            f = files[0]
            prev_parents = ",".join(f.get('parents', []))
            new_name = f"{f['name']} (Completed)"

            self.service.files().update(
                fileId=f['id'],
                addParents=completed_id,
                removeParents=prev_parents,
                body={'name': new_name},
                fields="id, parents, name"
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Error moving task file to completed: {e}")
            return False

    # ---------------------------
    # Fact Find (simple text file)
    # ---------------------------
    def save_fact_find_to_drive(self, client, fact_find_data):
        try:
            folder_id = client.get('folder_id')
            if not folder_id:
                return False

            query = f"name='FF & ATR' and '{folder_id}' in parents and trashed=false"
            res = self.service.files().list(q=query, fields="files(id)").execute()
            folders = res.get('files', [])
            if not folders:
                return False
            ff_atr_folder_id = folders[0]['id']

            content = f"""FACT FIND - {client['display_name']}
Date: {fact_find_data.get('fact_find_date','')}
Age: {fact_find_data.get('age','N/A')}
Marital Status: {fact_find_data.get('marital_status','N/A')}
Dependents: {fact_find_data.get('dependents','N/A')}
Employment: {fact_find_data.get('employment','N/A')}
Annual Income: £{fact_find_data.get('annual_income','N/A')}
Financial Objectives: {fact_find_data.get('financial_objectives','N/A')}
Risk Tolerance: {fact_find_data.get('risk_tolerance','N/A')}
Investment Experience: {fact_find_data.get('investment_experience','N/A')}
"""
            file_metadata = {
                'name': f"Fact Find - {client['display_name']} - {fact_find_data.get('fact_find_date','Unknown')}.txt",
                'parents': [ff_atr_folder_id]
            }
            media = googleapiclient.http.MediaIoBaseUpload(
                io.BytesIO(content.encode('utf-8')), mimetype='text/plain'
            )
            self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            return True
        except Exception as e:
            logger.error(f"Error saving fact find: {e}")
            return False
