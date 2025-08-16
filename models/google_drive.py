"""
WealthPro CRM - Google Drive Integration Model
FULL FILE — Step 4

Adds:
- Client "Tasks" subfolders: "Ongoing Tasks" and "Completed Tasks"
- Task files saved to Ongoing on create; moved to Completed and renamed on completion
- Reviews yearly structure: "Review {YYYY}" with requested subfolders
- Creates two DOCX templates in "Agenda & Valuation" each year:
  * Meeting Agenda – {First} {Surname} – {YYYY}.docx
  * Valuation – {First} {Surname} – {YYYY}.docx
- Uses cache_discovery=False for lower memory usage on Render
"""

import os
import io
import logging
from datetime import datetime, timedelta
from googleapiclient.discovery import build
import googleapiclient.http

# DOCX generation
try:
    from docx import Document
    from docx.shared import Pt
    HAVE_DOCX = True
except Exception:
    HAVE_DOCX = False

logger = logging.getLogger(__name__)

SPREADSHEET_ID = None
PROFILES_SPREADSHEET_ID = None
COMMUNICATIONS_SPREADSHEET_ID = None
TASKS_SPREADSHEET_ID = None


class SimpleGoogleDrive:
    def __init__(self, credentials):
        global SPREADSHEET_ID, PROFILES_SPREADSHEET_ID, COMMUNICATIONS_SPREADSHEET_ID, TASKS_SPREADSHEET_ID

        # Lower memory usage on Render
        self.service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
        self.sheets_service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)

        self.main_folder_id = None
        self.client_files_folder_id = None

        self.spreadsheet_id = SPREADSHEET_ID
        self.profiles_spreadsheet_id = PROFILES_SPREADSHEET_ID
        self.communications_spreadsheet_id = COMMUNICATIONS_SPREADSHEET_ID
        self.tasks_spreadsheet_id = TASKS_SPREADSHEET_ID

        self.setup()

    # ---------------------------------------------------------------------
    # One-time setup / find-or-create Sheets
    # ---------------------------------------------------------------------
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
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            spreadsheets = results.get('files', [])
            if spreadsheets:
                self.spreadsheet_id = spreadsheets[0]['id']
            else:
                self.create_new_spreadsheet()
        except Exception as e:
            logger.error(f"Error finding spreadsheet: {e}")
            self.create_new_spreadsheet()

    def create_new_spreadsheet(self):
        try:
            spreadsheet = {'properties': {'title': 'WealthPro CRM - Clients Data'}}
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
        except Exception as e:
            logger.error(f"Error creating spreadsheet: {e}")

    def find_or_create_profiles_spreadsheet(self):
        try:
            query = "name='WealthPro CRM - Client Profiles' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            spreadsheets = results.get('files', [])
            if spreadsheets:
                self.profiles_spreadsheet_id = spreadsheets[0]['id']
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
                valueInputOption='RAW', body={'values': [headers]}
            ).execute()
        except Exception as e:
            logger.error(f"Error creating profiles spreadsheet: {e}")

    def find_or_create_communications_spreadsheet(self):
        try:
            query = "name='WealthPro CRM - Communications' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            spreadsheets = results.get('files', [])
            if spreadsheets:
                self.communications_spreadsheet_id = spreadsheets[0]['id']
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
                valueInputOption='RAW', body={'values': [headers]}
            ).execute()
        except Exception as e:
            logger.error(f"Error creating communications spreadsheet: {e}")

    def find_or_create_tasks_spreadsheet(self):
        try:
            query = "name='WealthPro CRM - Tasks & Reminders' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            spreadsheets = results.get('files', [])
            if spreadsheets:
                self.tasks_spreadsheet_id = spreadsheets[0]['id']
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
                # Backward-compatible; file IDs are discovered by filename if needed
            ]

            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.tasks_spreadsheet_id, range='Sheet1!A1:J1',
                valueInputOption='RAW', body={'values': [headers]}
            ).execute()
        except Exception as e:
            logger.error(f"Error creating tasks spreadsheet: {e}")

    # ---------------------------------------------------------------------
    # Folders
    # ---------------------------------------------------------------------
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

            meta = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
            if parent_id:
                meta['parents'] = [parent_id]
            folder = self.service.files().create(body=meta, fields='id').execute()
            return folder.get('id')
        except Exception as e:
            logger.error(f"Error creating folder {name}: {e}")
            return None

    def ensure_task_subfolders(self, client_folder_id):
        """Ensure Tasks/Ongoing Tasks & Completed Tasks exist; return dict of IDs."""
        tasks_id = self.create_folder("Tasks", client_folder_id)
        ongoing_id = self.create_folder("Ongoing Tasks", tasks_id)
        completed_id = self.create_folder("Completed Tasks", tasks_id)
        return {'tasks': tasks_id, 'ongoing': ongoing_id, 'completed': completed_id}

    def ensure_reviews_year(self, client_first, client_surname, client_folder_id, year=None):
        """
        Ensure Reviews/year structure and create two DOCX templates in Agenda & Valuation.
        Returns dict with ids.
        """
        try:
            if not year:
                year = datetime.now().year

            reviews_root = self.create_folder("Reviews", client_folder_id)
            year_folder = self.create_folder(f"Review {year}", reviews_root)

            sub_names = [
                "Agenda & Valuation",
                "FF&ATR",
                "ID&V & Sanction Search",
                "Meeting Notes",
                "Research",
                "Review Letter",
                "Client Confirmation",
                "Emails"
            ]
            ids = {}
            for n in sub_names:
                ids[n] = self.create_folder(n, year_folder)

            # Create two DOCX files in Agenda & Valuation
            if HAVE_DOCX:
                full_name = f"{client_first} {client_surname}".strip()
                today_text = datetime.now().strftime("%-d %B %Y") if os.name != 'nt' else datetime.now().strftime("%#d %B %Y")
                # Windows strftime quirk handled above

                # 1) Meeting Agenda
                agenda_doc = Document()
                agenda_doc.styles['Normal'].font.name = 'Calibri'
                agenda_doc.styles['Normal'].font.size = Pt(11)
                agenda_doc.add_heading(f"Meeting Agenda – {full_name} – {year}", 1)
                agenda_doc.add_paragraph(f"Date: {today_text}")
                agenda_doc.add_paragraph("")
                agenda_doc.add_paragraph("1. Welcome and purpose of review")
                agenda_doc.add_paragraph("2. Review of objectives and circumstances")
                agenda_doc.add_paragraph("3. Portfolio valuation and performance")
                agenda_doc.add_paragraph("4. Charges and cost review")
                agenda_doc.add_paragraph("5. Risk profile reconfirmation (FF&ATR)")
                agenda_doc.add_paragraph("6. Research & recommendations (if any)")
                agenda_doc.add_paragraph("7. Next steps & actions")
                agenda_bytes = io.BytesIO()
                agenda_doc.save(agenda_bytes)
                agenda_bytes.seek(0)
                self._upload_bytes_as_file(
                    name=f"Meeting Agenda – {full_name} – {year}.docx",
                    parent_id=ids["Agenda & Valuation"],
                    content_bytes=agenda_bytes.getvalue(),
                    mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

                # 2) Valuation
                valuation_doc = Document()
                valuation_doc.styles['Normal'].font.name = 'Calibri'
                valuation_doc.styles['Normal'].font.size = Pt(11)
                valuation_doc.add_heading(f"Valuation – {full_name} – {year}", 1)
                valuation_doc.add_paragraph(f"Date: {today_text}")
                valuation_doc.add_paragraph("")
                valuation_doc.add_paragraph("Plan(s) Summary:")
                valuation_doc.add_paragraph("- Provider: ")
                valuation_doc.add_paragraph("- Plan Number: ")
                valuation_doc.add_paragraph("- Wrapper/Type: ")
                valuation_doc.add_paragraph("- Current Value: £")
                valuation_doc.add_paragraph("")
                valuation_doc.add_paragraph("Notes:")
                valuation_bytes = io.BytesIO()
                valuation_doc.save(valuation_bytes)
                valuation_bytes.seek(0)
                self._upload_bytes_as_file(
                    name=f"Valuation – {full_name} – {year}.docx",
                    parent_id=ids["Agenda & Valuation"],
                    content_bytes=valuation_bytes.getvalue(),
                    mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            else:
                logger.warning("python-docx not installed; skipping DOCX template creation.")

            return {'root': reviews_root, 'year': year_folder, **ids}
        except Exception as e:
            logger.error(f"Error ensuring yearly review structure: {e}")
            return {}

    def _upload_bytes_as_file(self, name, parent_id, content_bytes, mimetype):
        try:
            file_metadata = {'name': name, 'parents': [parent_id]}
            media = googleapiclient.http.MediaIoBaseUpload(
                io.BytesIO(content_bytes),
                mimetype=mimetype
            )
            self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        except Exception as e:
            logger.error(f"Error uploading file {name}: {e}")

    # ---------------------------------------------------------------------
    # Client create / move / delete
    # ---------------------------------------------------------------------
    def create_client_folder_enhanced(self, first_name, surname, status='prospect'):
        try:
            self.ensure_status_folders()
            letter = surname[0].upper() if surname else 'Z'
            status_folder_id = self.get_status_folder_id(status)
            letter_folder_id = self.create_folder(letter, status_folder_id)

            display_name = f"{surname}, {first_name}".strip().strip(',')
            client_folder_id = self.create_folder(display_name, letter_folder_id)

            # Base folders (per your earlier structure)
            reviews_folder_id = self.create_folder("Reviews", client_folder_id)
            document_folders = [
                "ID&V", "FF & ATR", "Research", "LOAs", "Suitability Letter",
                "Meeting Notes", "Terms of Business", "Policy Information", "Valuation"
            ]
            sub_folder_ids = {'Reviews': reviews_folder_id}
            for doc_type in document_folders:
                sub_folder_ids[doc_type] = self.create_folder(doc_type, client_folder_id)

            # Reviews subfolders under "Reviews"
            for doc_type in document_folders:
                sub_folder_ids[f'Reviews_{doc_type}'] = self.create_folder(doc_type, reviews_folder_id)

            # Tasks with Ongoing/Completed
            tasks_folder_id = self.create_folder("Tasks", client_folder_id)
            ongoing_id = self.create_folder("Ongoing Tasks", tasks_folder_id)
            completed_id = self.create_folder("Completed Tasks", tasks_folder_id)
            sub_folder_ids['Tasks'] = tasks_folder_id
            sub_folder_ids['Ongoing Tasks'] = ongoing_id
            sub_folder_ids['Completed Tasks'] = completed_id

            # Ensure this year's Reviews structure and docx templates
            self.ensure_reviews_year(first_name, surname, client_folder_id)

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
            old_folder_id = client.get('folder_id')
            if not old_folder_id:
                return False

            self.ensure_status_folders()
            new_status_folder_id = self.get_status_folder_id(new_status)
            letter = client.get('surname', 'Z')[:1].upper() if client.get('surname') else 'Z'
            new_letter_folder_id = self.create_folder(letter, new_status_folder_id)

            file = self.service.files().get(fileId=old_folder_id, fields='parents').execute()
            previous_parents = ",".join(file.get('parents', []))

            self.service.files().update(
                fileId=old_folder_id,
                addParents=new_letter_folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Error moving client folder: {e}")
            return False

    def delete_client(self, client_id):
        try:
            clients = self.get_clients_enhanced()
            client = next((c for c in clients if c['client_id'] == client_id), None)
            if not client:
                return False

            # Clear the row
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A:K'
            ).execute()
            values = result.get('values', []) or []

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == client_id:
                    self.sheets_service.spreadsheets().values().clear(
                        spreadsheetId=self.spreadsheet_id,
                        range=f'Sheet1!A{i+1}:K{i+1}'
                    ).execute()

            # Trash folder
            if client.get('folder_id'):
                self.service.files().update(fileId=client['folder_id'], body={'trashed': True}).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting client: {e}")
            return False

    # ---------------------------------------------------------------------
    # Clients sheet — read/write
    # ---------------------------------------------------------------------
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
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A:K'
            ).execute()
            values = result.get('values', []) or []
            clients = []

            for i, row in enumerate(values):
                if i == 0:
                    continue
                if not row:
                    continue

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
                    'notes': row[10],
                }
                client_data['folder_url'] = f"https://drive.google.com/drive/folders/{client_data['folder_id']}" if client_data['folder_id'] else None
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

            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Sheet1!A:K'
            ).execute()
            values = result.get('values', []) or []

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

            if client.get('folder_id'):
                self.move_client_folder(client, new_status)
            return True
        except Exception as e:
            logger.error(f"Error updating client status: {e}")
            return False

    # ---------------------------------------------------------------------
    # Profiles sheet
    # ---------------------------------------------------------------------
    def add_client_profile(self, profile_data):
        try:
            values = [list(profile_data.values())]
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.profiles_spreadsheet_id,
                range='Sheet1!A:S',
                valueInputOption='RAW',
                body={'values': values}
            ).execute()
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
            values = result.get('values', []) or []
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
            values = result.get('values', []) or []

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == client_id:
                    updated_row = list(profile_data.values())
                    self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.profiles_spreadsheet_id,
                        range=f'Sheet1!A{i+1}:S{i+1}',
                        valueInputOption='RAW',
                        body={'values': [updated_row]}
                    ).execute()
                    return True

            return self.add_client_profile(profile_data)
        except Exception as e:
            logger.error(f"Error updating client profile: {e}")
            return False

    # ---------------------------------------------------------------------
    # Communications
    # ---------------------------------------------------------------------
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
            values = result.get('values', []) or []
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
                        'created_by': row[9]
                    })
            return sorted(comms, key=lambda x: x['date'], reverse=True)
        except Exception as e:
            logger.error(f"Error getting communications: {e}")
            return []

    def save_communication_to_drive(self, client, comm_data):
        try:
            if not client.get('folder_id'):
                return False
            q = f"name='Communications' and '{client['folder_id']}' in parents and trashed=false"
            folders = self.service.files().list(q=q, fields="files(id)").execute().get('files', [])
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
Follow Up Required: {comm_data.get('follow_up_required','No')}
Follow Up Date: {comm_data.get('follow_up_date','')}
Created By: {comm_data.get('created_by','')}
"""
            file_metadata = {'name': f"Communication - {comm_data.get('type','Unknown')} - {comm_data.get('date','Unknown')}.txt",
                             'parents': [comms_folder_id]}
            media = googleapiclient.http.MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')),
                                                           mimetype='text/plain')
            self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            return True
        except Exception as e:
            logger.error(f"Error saving communication to drive: {e}")
            return False

    # ---------------------------------------------------------------------
    # Tasks
    # ---------------------------------------------------------------------
    def add_task_enhanced(self, task_data, client_data):
        """
        Append to sheet, save a task file in Ongoing Tasks.
        Filename includes Task ID so we can find/move it reliably later.
        """
        try:
            # 1) Append to sheet
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
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.tasks_spreadsheet_id,
                range='Sheet1!A:J',
                valueInputOption='RAW',
                body={'values': [task_row]}
            ).execute()

            # 2) Save to Drive (Ongoing Tasks)
            self.save_task_to_drive(client_data, task_data)
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
            values = result.get('values', []) or []
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
            # Order by due date (string safe)
            return sorted(tasks, key=lambda x: x['due_date'] or '9999-12-31')
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            return []

    def get_upcoming_tasks(self, days_ahead=30):
        """
        Returns OPEN tasks due within N days, sorted by due date.
        """
        try:
            if not self.tasks_spreadsheet_id:
                return []

            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id,
                range='Sheet1!A2:J'
            ).execute()
            values = result.get('values', []) or []

            upcoming = []
            today = datetime.now().date()
            future_date = today + timedelta(days=days_ahead)

            for row in values:
                while len(row) < 10:
                    row.append('')

                status = (row[7] or 'Pending').lower()
                if status == 'completed':
                    continue

                due_str = row[5].strip() if row[5] else ''
                due = None
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                    try:
                        due = datetime.strptime(due_str, fmt).date()
                        break
                    except ValueError:
                        continue
                if not due:
                    continue

                if today <= due <= future_date:
                    upcoming.append({
                        'task_id': row[0], 'client_id': row[1], 'task_type': row[2],
                        'title': row[3], 'description': row[4], 'due_date': row[5],
                        'priority': row[6], 'status': row[7], 'created_date': row[8], 'completed_date': row[9],
                        'due_date_obj': due
                    })

            return sorted(upcoming, key=lambda x: x['due_date_obj'])
        except Exception as e:
            logger.error(f"Error getting upcoming tasks: {e}")
            return []

    def complete_task(self, task_id):
        """
        Sets status to Completed in sheet and moves/renames the Drive file:
        Ongoing -> Completed; append " (Completed)" to the name.
        """
        try:
            # 1) Update sheet
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id,
                range='Sheet1!A:J'
            ).execute()
            values = result.get('values', []) or []

            target_row_index = None
            row_data = None
            for i, row in enumerate(values):
                if row and row[0] == task_id:
                    target_row_index = i + 1  # 1-based in Sheets
                    while len(row) < 10:
                        row.append('')
                    row[7] = 'Completed'
                    row[9] = datetime.now().strftime('%Y-%m-%d')
                    row_data = row
                    break

            if target_row_index:
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.tasks_spreadsheet_id,
                    range=f'Sheet1!A{target_row_index}:J{target_row_index}',
                    valueInputOption='RAW',
                    body={'values': [row_data]}
                ).execute()
            else:
                logger.warning(f"Task {task_id} not found in sheet; still trying to move any file.")
                row_data = None

            # 2) Move Drive file if we can find client + folder
            if row_data:
                client_id = row_data[1]
                clients = self.get_clients_enhanced()
                client = next((c for c in clients if c['client_id'] == client_id), None)
                if client and client.get('folder_id'):
                    self._move_task_file_to_completed(client, task_id)
            return True
        except Exception as e:
            logger.error(f"Error completing task: {e}")
            return False

    def save_task_to_drive(self, client, task_data):
        """
        Save a .txt task file into client/Tasks/Ongoing Tasks.
        Filename contains Task ID for reliable lookup on completion.
        """
        try:
            if not client.get('folder_id'):
                return False

            sub = self.ensure_task_subfolders(client['folder_id'])
            ongoing_folder_id = sub['ongoing']

            content = f"""TASK - {client['display_name']}
Task ID: {task_data.get('task_id','')}
Created Date: {task_data.get('created_date','')}
Due Date: {task_data.get('due_date','')}
Priority: {task_data.get('priority','Medium')}
Type: {task_data.get('task_type','')}
Title: {task_data.get('title','')}
Description: {task_data.get('description','')}
Status: {task_data.get('status','Pending')}
Time Spent: {task_data.get('time_spent','Not tracked')}
"""
            filename = f"Task {task_data.get('task_id','')} - {task_data.get('title','Untitled')} - {task_data.get('created_date','Unknown')}.txt"
            file_metadata = {'name': filename, 'parents': [ongoing_folder_id]}
            media = googleapiclient.http.MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain')
            self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            return True
        except Exception as e:
            logger.error(f"Error saving task to drive: {e}")
            return False

    def _move_task_file_to_completed(self, client, task_id):
        """
        Find the task file in Ongoing by Task ID, move to Completed, and rename with (Completed).
        """
        try:
            folders = self.ensure_task_subfolders(client['folder_id'])
            ongoing_id = folders['ongoing']
            completed_id = folders['completed']

            # Find file in Ongoing containing the Task ID
            q = f"mimeType!='application/vnd.google-apps.folder' and '{ongoing_id}' in parents and trashed=false and name contains '{task_id}'"
            files = self.service.files().list(q=q, fields="files(id, name, parents)").execute().get('files', [])

            if not files:
                logger.warning(f"No ongoing task file found for {task_id}")
                return False

            f = files[0]
            previous_parents = ",".join(f.get('parents', []))
            new_name = f"{f['name']} (Completed)"

            # Move
            self.service.files().update(
                fileId=f['id'],
                addParents=completed_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()

            # Rename
            self.service.files().update(
                fileId=f['id'],
                body={'name': new_name}
            ).execute()

            return True
        except Exception as e:
            logger.error(f"Error moving task file to Completed: {e}")
            return False

    # ---------------------------------------------------------------------
    # Fact Find files
    # ---------------------------------------------------------------------
    def save_fact_find_to_drive(self, client, fact_find_data):
        try:
            if not client.get('folder_id'):
                return False
            q = f"name='FF & ATR' and '{client['folder_id']}' in parents and trashed=false"
            folders = self.service.files().list(q=q, fields="files(id)").execute().get('files', [])
            if not folders:
                return False
            ff_atr_folder_id = folders[0]['id']

            content = f"""FACT FIND - {client['display_name']}
Date: {fact_find_data.get('fact_find_date','')}
Age: {fact_find_data.get('age','')}
Marital Status: {fact_find_data.get('marital_status','')}
Dependents: {fact_find_data.get('dependents','')}
Employment: {fact_find_data.get('employment','')}
Annual Income: £{fact_find_data.get('annual_income','')}
Financial Objectives: {fact_find_data.get('financial_objectives','')}
Risk Tolerance: {fact_find_data.get('risk_tolerance','')}
Investment Experience: {fact_find_data.get('investment_experience','')}
"""
            file_metadata = {'name': f"Fact Find - {client['display_name']} - {fact_find_data.get('fact_find_date','Unknown')}.txt",
                             'parents': [ff_atr_folder_id]}
            media = googleapiclient.http.MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain')
            self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            return True
        except Exception as e:
            logger.error(f"Error saving fact find: {e}")
            return False
