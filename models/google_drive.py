"""
WealthPro CRM - Google Drive Integration Model

What’s included:
- Fixed Google Drive root (your clients folder) via ROOT_CLIENTS_FOLDER_ID
- Client A–Z foldering by status
- Reviews: auto-create "Review {YEAR}" with subfolders you specified
- Two Word (.docx) templates in "Agenda & Valuation" with client name + today’s date
- Tasks saved to Tasks/Ongoing; on completion move to Tasks/Completed and rename with [Task Complete]
- "Review" pack creator + auto-create review task in Sheets and Drive
- Resilient deletes and Shared-Drive-safe operations
"""

import os
import io
import logging
from datetime import datetime, timedelta
from googleapiclient.discovery import build
import googleapiclient.http
from googleapiclient.errors import HttpError

# DOCX support
try:
    from docx import Document
    from docx.shared import Pt
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────────
# YOUR ROOT CLIENTS FOLDER (already provided by you previously)
# ────────────────────────────────────────────────────────────────────────────────
ROOT_CLIENTS_FOLDER_ID = "1DzljucgOkvm7rpfSCiYP1zlsOpwtbaWh"

# Optional: Shared Drive support (set SHARED_DRIVE_ID in the environment on Render)
SHARED_DRIVE_ID = os.getenv("SHARED_DRIVE_ID")
USE_SHARED_DRIVE = bool(SHARED_DRIVE_ID)

def _list_params():
    """Common params for files().list() that are Shared-Drive safe."""
    params = {"fields": "files(id,name,parents,mimeType)"}
    if USE_SHARED_DRIVE:
        params.update({
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
            "corpora": "drive",
            "driveId": SHARED_DRIVE_ID,
        })
    return params

def _supports_all_drives(kwargs: dict):
    """Add supportsAllDrives=True to create/get/update when using Shared Drives."""
    if USE_SHARED_DRIVE:
        kwargs["supportsAllDrives"] = True
    return kwargs

def _safe_dateparse(s):
    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except Exception:
            continue
    return None

# Cached IDs (reduce API calls)
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
        self.spreadsheet_id = SPREADSHEET_ID
        self.profiles_spreadsheet_id = PROFILES_SPREADSHEET_ID
        self.communications_spreadsheet_id = COMMUNICATIONS_SPREADSHEET_ID
        self.tasks_spreadsheet_id = TASKS_SPREADSHEET_ID

        self.setup()

    # ───────────────────────────────────────────
    # Setup & Spreadsheet creation
    # ───────────────────────────────────────────
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
            spreadsheets = self.service.files().list(q=query, **_list_params()).execute().get('files', [])
            if spreadsheets:
                self.spreadsheet_id = spreadsheets[0]['id']
            else:
                spreadsheet = {'properties': {'title': 'WealthPro CRM - Clients Data'}}
                result = self.sheets_service.spreadsheets().create(body=spreadsheet).execute()
                self.spreadsheet_id = result['spreadsheetId']
                headers = [
                    'Client ID', 'Display Name', 'First Name', 'Surname', 'Email', 'Phone', 'Status',
                    'Date Added', 'Folder ID', 'Portfolio Value', 'Notes'
                ]
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id, range='Sheet1!A1:K1',
                    valueInputOption='RAW', body={'values': [headers]}
                ).execute()
        except Exception as e:
            logger.error(f"Error with main spreadsheet: {e}")

    def find_or_create_profiles_spreadsheet(self):
        try:
            query = "name='WealthPro CRM - Client Profiles' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            spreadsheets = self.service.files().list(q=query, **_list_params()).execute().get('files', [])
            if spreadsheets:
                self.profiles_spreadsheet_id = spreadsheets[0]['id']
            else:
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
            logger.error(f"Error with profiles spreadsheet: {e}")

    def find_or_create_communications_spreadsheet(self):
        try:
            query = "name='WealthPro CRM - Communications' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            spreadsheets = self.service.files().list(q=query, **_list_params()).execute().get('files', [])
            if spreadsheets:
                self.communications_spreadsheet_id = spreadsheets[0]['id']
            else:
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
            logger.error(f"Error with communications spreadsheet: {e}")

    def find_or_create_tasks_spreadsheet(self):
        try:
            query = "name='WealthPro CRM - Tasks & Reminders' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            spreadsheets = self.service.files().list(q=query, **_list_params()).execute().get('files', [])
            if spreadsheets:
                self.tasks_spreadsheet_id = spreadsheets[0]['id']
            else:
                spreadsheet = {'properties': {'title': 'WealthPro CRM - Tasks & Reminders'}}
                result = self.sheets_service.spreadsheets().create(body=spreadsheet).execute()
                self.tasks_spreadsheet_id = result['spreadsheetId']
                headers = [
                    'Task ID', 'Client ID', 'Task Type', 'Title', 'Description', 'Due Date',
                    'Priority', 'Status', 'Created Date', 'Completed Date'
                ]
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.tasks_spreadsheet_id, range='Sheet1!A1:J1',
                    valueInputOption='RAW', body={'values': [headers]}
                ).execute()
        except Exception as e:
            logger.error(f"Error with tasks spreadsheet: {e}")

    # ───────────────────────────────────────────
    # Folder helpers
    # ───────────────────────────────────────────
    def ensure_status_folders(self):
        """Make sure root subfolders exist under your fixed ROOT folder."""
        if getattr(self, "_status_folders_created", False):
            return
        self.main_folder_id = ROOT_CLIENTS_FOLDER_ID
        self.active_clients_folder_id = self.create_folder('Active Clients', self.main_folder_id)
        self.former_clients_folder_id = self.create_folder('Former Clients', self.main_folder_id)
        self.deceased_clients_folder_id = self.create_folder('Deceased Clients', self.main_folder_id)
        self._status_folders_created = True

    def get_status_folder_id(self, status):
        self.ensure_status_folders()
        if status == 'active':
            return self.active_clients_folder_id
        if status in ['no_longer_client', 'former']:
            return self.former_clients_folder_id
        if status in ['deceased', 'death']:
            return self.deceased_clients_folder_id
        return self.active_clients_folder_id

    def create_folder(self, name, parent_id):
        try:
            q = ["mimeType='application/vnd.google-apps.folder'", "trashed=false", f"name='{name}'"]
            if parent_id:
                q.append(f"'{parent_id}' in parents")
            params = _list_params()
            params["q"] = " and ".join(q)
            folders = self.service.files().list(**params).execute().get('files', [])
            if folders:
                return folders[0]['id']

            body = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
            if parent_id:
                body['parents'] = [parent_id]
            kwargs = {"body": body, "fields": "id"}
            _supports_all_drives(kwargs)
            folder = self.service.files().create(**kwargs).execute()
            return folder.get('id')
        except Exception as e:
            logger.error(f"Error creating folder {name}: {e}")
            return None

    def get_or_create_subfolder(self, parent_id, sub_name):
        return self.create_folder(sub_name, parent_id)

    # ───────────────────────────────────────────
    # Reviews: year structure + .docx templates
    # ───────────────────────────────────────────
    def _docx_bytes(self, title: str, client_display_name: str):
        """
        Build a simple .docx with heading + metadata + placeholder sections.
        (Editable in Word afterwards.)
        """
        if not DOCX_AVAILABLE:
            logger.warning("python-docx not installed; skipping .docx generation.")
            return None

        today_str = datetime.now().strftime('%Y-%m-%d')
        year = datetime.now().year

        doc = Document()
        h = doc.add_heading(title, 0)
        for run in h.runs:
            run.font.size = Pt(20)

        # Meta
        doc.add_paragraph(f"Client: {client_display_name}")
        doc.add_paragraph(f"Date: {today_str}")
        doc.add_paragraph(f"Review Year: {year}")

        doc.add_paragraph("")  # spacing

        # Light placeholder sections users can edit later
        if "Agenda" in title:
            doc.add_heading("Agenda", level=1)
            doc.add_paragraph("1) Welcome & objectives")
            doc.add_paragraph("2) Portfolio performance & valuation")
            doc.add_paragraph("3) Risk profile and capacity for loss")
            doc.add_paragraph("4) Changes in circumstances")
            doc.add_paragraph("5) Recommendations & next steps")
        else:
            doc.add_heading("Valuation Summary", level=1)
            doc.add_paragraph("• Plan list and current valuations")
            doc.add_paragraph("• Contributions/withdrawals since last review")
            doc.add_paragraph("• Asset allocation overview")
            doc.add_paragraph("• Fees summary")

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf

    def _upload_docx(self, parent_folder_id: str, filename: str, file_like: io.BytesIO):
        file_metadata = {'name': filename, 'parents': [parent_folder_id]}
        media = googleapiclient.http.MediaIoBaseUpload(
            file_like,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        kwargs = {"body": file_metadata, "media_body": media, "fields": "id"}
        _supports_all_drives(kwargs)
        self.service.files().create(**kwargs).execute()

    def _get_or_create_review_year_structure(self, reviews_folder_id: str):
        """
        Inside Reviews/, create/find 'Review {YEAR}' and the required subfolders.
        Returns: (year_folder_id, subfolder_ids_dict)
        """
        year = datetime.now().year
        year_folder_name = f"Review {year}"
        year_folder_id = self.create_folder(year_folder_name, reviews_folder_id)

        subfolders = [
            "Agenda & Valuation",
            "FF&ATR",
            "ID&V & Sanction Search",
            "Meeting Notes",
            "Research",
            "Review Letter",
            "Client Confirmation",
            "Emails",
        ]
        ids = {}
        for name in subfolders:
            ids[name] = self.create_folder(name, year_folder_id)

        return year_folder_id, ids

    def _create_review_templates(self, client_display_name: str, agenda_val_folder_id: str):
        """Create the two Word templates in 'Agenda & Valuation' with client name & date."""
        year = datetime.now().year
        if not DOCX_AVAILABLE:
            logger.info("Skipping .docx template creation (python-docx not available).")
            return

        # Meeting Agenda
        agenda_stream = self._docx_bytes("Meeting Agenda", client_display_name)
        if agenda_stream:
            self._upload_docx(
                agenda_val_folder_id,
                f"Meeting Agenda – {client_display_name} – {year}.docx",
                agenda_stream
            )

        # Valuation Summary
        valuation_stream = self._docx_bytes("Valuation Summary", client_display_name)
        if valuation_stream:
            self._upload_docx(
                agenda_val_folder_id,
                f"Valuation Summary – {client_display_name} – {year}.docx",
                valuation_stream
            )

    def create_review_pack_for_client(self, client):
        """
        Public method used by the Review button:
        - ensures Reviews/Review {YEAR} structure
        - drops the two .docx templates in Agenda & Valuation
        """
        try:
            if not client.get('folder_id'):
                return False

            # Ensure Reviews/ exists
            reviews_q = f"name='Reviews' and '{client['folder_id']}' in parents and trashed=false"
            params = _list_params(); params["q"] = reviews_q
            revs = self.service.files().list(**params).execute().get('files', [])
            if revs:
                reviews_id = revs[0]['id']
            else:
                reviews_id = self.create_folder("Reviews", client['folder_id'])

            # Ensure Review {YEAR} & subfolders, then create templates
            year_folder_id, ids = self._get_or_create_review_year_structure(reviews_id)
            self._create_review_templates(client['display_name'], ids["Agenda & Valuation"])
            return True
        except Exception as e:
            logger.error(f"create_review_pack_for_client: {e}")
            return False

    # ───────────────────────────────────────────
    # Client folders & sheet
    # ───────────────────────────────────────────
    def create_client_folder_enhanced(self, first_name, surname, status='prospect'):
        try:
            self.ensure_status_folders()
            letter = surname[0].upper() if surname else 'Z'
            status_folder_id = self.get_status_folder_id(status)
            letter_folder_id = self.create_folder(letter, status_folder_id)

            display_name = f"{surname}, {first_name}"
            client_folder_id = self.create_folder(display_name, letter_folder_id)

            # Reviews root & this-year structure + templates
            reviews_folder_id = self.create_folder("Reviews", client_folder_id)
            try:
                year_folder_id, ids = self._get_or_create_review_year_structure(reviews_folder_id)
                self._create_review_templates(display_name, ids["Agenda & Valuation"])
            except Exception as e:
                logger.warning(f"Could not create Review year structure: {e}")

            # Legacy doc folders at client root
            document_folders = [
                "ID&V", "FF & ATR", "Research", "LOAs", "Suitability Letter",
                "Meeting Notes", "Terms of Business", "Policy Information", "Valuation"
            ]

            sub_folder_ids = {'Reviews': reviews_folder_id}
            for doc_type in document_folders:
                sub_folder_ids[doc_type] = self.create_folder(doc_type, client_folder_id)
            for doc_type in document_folders:
                sub_folder_ids[f"Reviews_{doc_type}"] = self.create_folder(doc_type, reviews_folder_id)

            # Tasks section with Ongoing & Completed
            tasks_folder_id = self.create_folder("Tasks", client_folder_id)
            sub_folder_ids['Tasks'] = tasks_folder_id
            sub_folder_ids['Tasks_Ongoing'] = self.get_or_create_subfolder(tasks_folder_id, "Ongoing")
            sub_folder_ids['Tasks_Completed'] = self.get_or_create_subfolder(tasks_folder_id, "Completed")

            # Communications
            sub_folder_ids['Communications'] = self.create_folder("Communications", client_folder_id)

            return {'client_folder_id': client_folder_id, 'sub_folders': sub_folder_ids}
        except Exception as e:
            logger.error(f"Error creating enhanced client folder: {e}")
            return None

    def get_folder_url(self, folder_id):
        return f"https://drive.google.com/drive/folders/{folder_id}"

    def move_client_folder(self, client, new_status):
        try:
            old_folder_id = client.get('folder_id')
            if not old_folder_id:
                return True
            self.ensure_status_folders()
            new_status_folder_id = self.get_status_folder_id(new_status)
            letter = client.get('surname', 'Z')[:1].upper() if client.get('surname') else 'Z'
            new_letter_folder_id = self.create_folder(letter, new_status_folder_id)

            get_kwargs = {"fileId": old_folder_id, "fields": "parents"}
            _supports_all_drives(get_kwargs)
            file = self.service.files().get(**get_kwargs).execute()
            previous_parents = ",".join(file.get('parents', []))

            upd = {"fileId": old_folder_id, "addParents": new_letter_folder_id,
                   "removeParents": previous_parents, "fields": "id,parents"}
            _supports_all_drives(upd)
            self.service.files().update(**upd).execute()
            return True
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning("move_client_folder: missing folder; skipping")
                return True
            logger.error(f"move_client_folder: {e}")
            return False
        except Exception as e:
            logger.error(f"move_client_folder: {e}")
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
                spreadsheetId=self.spreadsheet_id, range='Sheet1!A:K',
                valueInputOption='RAW', body={'values': [values[0]]}
            ).execute()
            return True
        except Exception as e:
            logger.error(f"add_client: {e}")
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
                while len(row) < 11:
                    row.append('')
                try:
                    portfolio_value = float(row[9]) if row[9] and str(row[9]).replace('.', '').isdigit() else 0.0
                except (ValueError, TypeError):
                    portfolio_value = 0.0
                client = {
                    'client_id': row[0], 'display_name': row[1], 'first_name': row[2], 'surname': row[3],
                    'email': row[4], 'phone': row[5], 'status': row[6], 'date_added': row[7],
                    'folder_id': row[8], 'portfolio_value': portfolio_value, 'notes': row[10]
                }
                client['folder_url'] = f"https://drive.google.com/drive/folders/{client['folder_id']}" if client['folder_id'] else None
                if client['display_name']:
                    clients.append(client)
            return sorted(clients, key=lambda x: x['display_name'])
        except Exception as e:
            logger.error(f"get_clients_enhanced: {e}")
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
                        spreadsheetId=self.spreadsheet_id, range=f'Sheet1!A{i+1}:K{i+1}',
                        valueInputOption='RAW', body={'values': [row]}
                    ).execute()
                    break
            self.move_client_folder(client, new_status)
            return True
        except Exception as e:
            logger.error(f"update_client_status: {e}")
            return False

    def delete_client(self, client_id):
        """Resilient delete: clears row and tries to trash Drive folder (ignores 404)."""
        try:
            clients = self.get_clients_enhanced()
            client = next((c for c in clients if c['client_id'] == client_id), None)

            # Clear row
            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range='Sheet1!A:K'
            ).execute()
            values = res.get('values', []) or []
            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == client_id:
                    blanks = [''] * 11
                    self.sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id, range=f'Sheet1!A{i+1}:K{i+1}',
                        valueInputOption='RAW', body={'values': [blanks]}
                    ).execute()
                    break

            # Trash Drive folder (non-blocking)
            if client and client.get('folder_id'):
                try:
                    kwargs = {"fileId": client['folder_id'], "body": {'trashed': True}}
                    _supports_all_drives(kwargs)
                    self.service.files().update(**kwargs).execute()
                except HttpError as e:
                    if e.resp.status != 404:
                        logger.warning(f"delete_client: Drive error {e}")
                except Exception as e:
                    logger.warning(f"delete_client: {e}")
            return True
        except Exception as e:
            logger.error(f"delete_client: {e}")
            return False

    # ───────────────────────────────────────────
    # Task helpers: Ongoing vs Completed in Drive
    # ───────────────────────────────────────────
    def _find_client_tasks_folder(self, client_folder_id):
        tasks_id = self.create_folder("Tasks", client_folder_id)
        ongoing_id = self.get_or_create_subfolder(tasks_id, "Ongoing")
        completed_id = self.get_or_create_subfolder(tasks_id, "Completed")
        return tasks_id, ongoing_id, completed_id

    def _task_filename(self, task_data, label_prefix=""):
        created = task_data.get('created_date') or datetime.now().strftime('%Y-%m-%d')
        title = task_data.get('title', 'Untitled')
        return f"{label_prefix}Task - {title} - {created}.txt"

    def save_task_to_drive(self, client, task_data):
        """Save the task file to Ongoing (pending) or Completed (if status completed)."""
        try:
            if not client.get('folder_id'):
                return False
            _, ongoing_id, completed_id = self._find_client_tasks_folder(client['folder_id'])
            status = (task_data.get('status') or '').lower()
            if status == 'completed':
                parent_id = completed_id
                label = "[Task Complete] "
            else:
                parent_id = ongoing_id
                label = ""

            content = f"""TASK - {client['display_name']}
Task ID: {task_data.get('task_id', '')}
Created Date: {task_data.get('created_date', '')}
Due Date: {task_data.get('due_date', '')}
Priority: {task_data.get('priority', 'Medium')}
Type: {task_data.get('task_type', '')}
Title: {task_data.get('title', '')}
Description: {task_data.get('description', '')}
Status: {task_data.get('status', 'Pending')}
Time Spent: {task_data.get('time_spent', 'Not tracked')}
Completed Date: {task_data.get('completed_date', '')}
"""
            file_metadata = {'name': self._task_filename(task_data, label), 'parents': [parent_id]}
            media = googleapiclient.http.MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain')
            kwargs = {"body": file_metadata, "media_body": media, "fields": "id"}
            _supports_all_drives(kwargs)
            self.service.files().create(**kwargs).execute()
            return True
        except Exception as e:
            logger.error(f"save_task_to_drive: {e}")
            return False

    def move_task_file_to_completed(self, client, task_data):
        """Move the existing Ongoing file to Completed and rename; if not found, create Completed file."""
        try:
            if not client.get('folder_id'):
                return False
            tasks_id, ongoing_id, completed_id = self._find_client_tasks_folder(client['folder_id'])

            expected_name = self._task_filename(task_data, "")
            q = f"name='{expected_name}' and '{ongoing_id}' in parents and trashed=false"
            params = _list_params()
            params["q"] = q
            files = self.service.files().list(**params).execute().get('files', [])

            if files:
                file_id = files[0]['id']
                get_kwargs = {"fileId": file_id, "fields": "parents"}
                _supports_all_drives(get_kwargs)
                meta = self.service.files().get(**get_kwargs).execute()
                prev_parents = ",".join(meta.get('parents', []))

                upd = {"fileId": file_id, "addParents": completed_id, "removeParents": prev_parents, "fields": "id,parents"}
                _supports_all_drives(upd)
                self.service.files().update(**upd).execute()

                rename = {"fileId": file_id, "body": {"name": self._task_filename(task_data, "[Task Complete] ")}}
                _supports_all_drives(rename)
                self.service.files().update(**rename).execute()
                return True
            else:
                # If the Ongoing file isn't found, just write a Completed copy
                self.save_task_to_drive(client, {**task_data, "status": "Completed"})
                return True
        except Exception as e:
            logger.warning(f"move_task_file_to_completed: {e}")
            return False

    def add_task_enhanced(self, task_data, client_data):
        """Append task to sheet and save file to Tasks/Ongoing."""
        try:
            row = [
                task_data.get('task_id', ''), task_data.get('client_id', ''), task_data.get('task_type', ''),
                task_data.get('title', ''), task_data.get('description', ''), task_data.get('due_date', ''),
                task_data.get('priority', 'Medium'), task_data.get('status', 'Pending'),
                task_data.get('created_date', datetime.now().strftime('%Y-%m-%d')),
                task_data.get('completed_date', '')
            ]
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.tasks_spreadsheet_id, range='Sheet1!A:J',
                valueInputOption='RAW', body={'values': [row]}
            ).execute()
            self.save_task_to_drive(client_data, task_data)
            return True
        except Exception as e:
            logger.error(f"add_task_enhanced: {e}")
            return False

    def complete_task(self, task_id):
        """Mark as Completed in sheet, set Completed Date, and move Drive file from Ongoing → Completed."""
        try:
            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id, range='Sheet1!A:J'
            ).execute()
            values = res.get('values', [])
            updated_task = None
            idx = None

            for i, row in enumerate(values):
                if len(row) > 0 and row[0] == task_id:
                    while len(row) < 10:
                        row.append('')
                    row[7] = 'Completed'  # Status
                    row[9] = datetime.now().strftime('%Y-%m-%d')  # Completed Date
                    updated_task = {
                        'task_id': row[0], 'client_id': row[1], 'task_type': row[2], 'title': row[3],
                        'description': row[4], 'due_date': row[5], 'priority': row[6], 'status': row[7],
                        'created_date': row[8], 'completed_date': row[9], 'time_spent': ''
                    }
                    idx = i + 1
                    break

            if updated_task is None:
                return False

            # Push the update
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.tasks_spreadsheet_id,
                range=f'Sheet1!A{idx}:J{idx}',
                valueInputOption='RAW',
                body={'values': [[
                    updated_task['task_id'], updated_task['client_id'], updated_task['task_type'],
                    updated_task['title'], updated_task['description'], updated_task['due_date'],
                    updated_task['priority'], updated_task['status'], updated_task['created_date'],
                    updated_task['completed_date']
                ]]}
            ).execute()

            # Move the file in Drive
            clients = self.get_clients_enhanced()
            client = next((c for c in clients if c['client_id'] == updated_task['client_id']), None)
            if client:
                self.move_task_file_to_completed(client, updated_task)

            return True
        except Exception as e:
            logger.error(f"complete_task: {e}")
            return False

    def get_client_tasks(self, client_id):
        try:
            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id, range='Sheet1!A2:J'
            ).execute()
            values = res.get('values', [])
            tasks = []
            for row in values:
                if len(row) > 1 and row[1] == client_id:
                    while len(row) < 10:
                        row.append('')
                    tasks.append({
                        'task_id': row[0], 'client_id': row[1], 'task_type': row[2], 'title': row[3],
                        'description': row[4], 'due_date': row[5], 'priority': row[6],
                        'status': row[7], 'created_date': row[8], 'completed_date': row[9]
                    })
            return sorted(tasks, key=lambda x: (x.get('completed_date') or x.get('due_date') or ''))
        except Exception as e:
            logger.error(f"get_client_tasks: {e}")
            return []

    def get_upcoming_tasks(self, days_ahead=30):
        """Return pending tasks due between today and today+days_ahead (default 30)."""
        try:
            if not self.tasks_spreadsheet_id:
                return []
            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.tasks_spreadsheet_id, range='Sheet1!A2:J'
            ).execute()
            values = res.get('values', [])
            if not values:
                return []

            today = datetime.now().date()
            end = today + timedelta(days=days_ahead)
            out = []
            for row in values:
                while len(row) < 10:
                    row.append('')
                status = (row[7] or '').lower()
                if status == 'completed':
                    continue
                due = _safe_dateparse(row[5]) if row[5] else None
                if due and today <= due <= end:
                    out.append({
                        'task_id': row[0], 'client_id': row[1], 'task_type': row[2], 'title': row[3],
                        'description': row[4], 'due_date': row[5], 'priority': row[6],
                        'status': row[7] or 'Pending', 'created_date': row[8], 'completed_date': row[9]
                    })
            out.sort(key=lambda x: _safe_dateparse(x['due_date']) or datetime.max.date())
            return out
        except Exception as e:
            logger.error(f"get_upcoming_tasks: {e}")
            return []

    # ───────────────────────────────────────────
    # Communications & Fact Find
    # ───────────────────────────────────────────
    def add_communication_enhanced(self, comm_data, client_data):
        try:
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.communications_spreadsheet_id, range='Sheet1!A:J',
                valueInputOption='RAW', body={'values': [list(comm_data.values())]}
            ).execute()
            self.save_communication_to_drive(client_data, comm_data)
            return True
        except Exception as e:
            logger.error(f"add_communication_enhanced: {e}")
            return False

    def get_client_communications(self, client_id):
        try:
            res = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.communications_spreadsheet_id, range='Sheet1!A2:J'
            ).execute()
            values = res.get('values', [])
            out = []
            for row in values:
                if len(row) > 1 and row[1] == client_id:
                    while len(row) < 10:
                        row.append('')
                    out.append({
                        'communication_id': row[0], 'client_id': row[1], 'date': row[2], 'type': row[3],
                        'subject': row[4], 'details': row[5], 'outcome': row[6], 'follow_up_required': row[7],
                        'follow_up_date': row[8], 'created_by': row[9]
                    })
            return sorted(out, key=lambda x: x['date'], reverse=True)
        except Exception as e:
            logger.error(f"get_client_communications: {e}")
            return []

    def save_communication_to_drive(self, client, comm_data):
        try:
            if not client.get('folder_id'):
                return False
            q = f"name='Communications' and '{client['folder_id']}' in parents and trashed=false"
            params = _list_params(); params["q"] = q
            folders = self.service.files().list(**params).execute().get('files', [])
            if not folders:
                logger.error("Communications folder not found")
                return False
            comms_id = folders[0]['id']
            content = f"""COMMUNICATION - {client['display_name']}
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
            file_metadata = {'name': f"Communication - {comm_data.get('type','Unknown')} - {comm_data.get('date','Unknown')}.txt", 'parents': [comms_id]}
            media = googleapiclient.http.MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain')
            kwargs = {"body": file_metadata, "media_body": media, "fields": "id"}; _supports_all_drives(kwargs)
            self.service.files().create(**kwargs).execute()
            return True
        except Exception as e:
            logger.error(f"save_communication_to_drive: {e}")
            return False

    def save_fact_find_to_drive(self, client, fact_find_data):
        try:
            if not client.get('folder_id'):
                return False
            q = f"name='FF & ATR' and '{client['folder_id']}' in parents and trashed=false"
            params = _list_params(); params["q"] = q
            folders = self.service.files().list(**params).execute().get('files', [])
            if not folders:
                logger.error("FF & ATR folder not found")
                return False
            ff_id = folders[0]['id']
            content = f"""FACT FIND - {client['display_name']}
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
            file_metadata = {'name': f"Fact Find - {client['display_name']} - {fact_find_data.get('fact_find_date','Unknown')}.txt", 'parents':[ff_id]}
            media = googleapiclient.http.MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain')
            kwargs = {"body": file_metadata, "media_body": media, "fields": "id"}; _supports_all_drives(kwargs)
            self.service.files().create(**kwargs).execute()
            return True
        except Exception as e:
            logger.error(f"save_fact_find_to_drive: {e}")
            return False

    # ───────────────────────────────────────────
    # Review task (for the Review button)
    # ───────────────────────────────────────────
    def create_review_task(self, client, due_in_days=14):
        """Create a task for the client review in Sheets and save task file to Drive."""
        try:
            task_data = {
                'task_id': f"TSK{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'client_id': client['client_id'],
                'task_type': 'Review',
                'title': f"Annual Review – {client['display_name']}",
                'description': 'Prepare and conduct annual review meeting',
                'due_date': (datetime.now() + timedelta(days=due_in_days)).strftime('%Y-%m-%d'),
                'priority': 'Medium',
                'status': 'Pending',
                'created_date': datetime.now().strftime('%Y-%m-%d'),
                'completed_date': '',
                'time_spent': ''
            }
            self.add_task_enhanced(task_data, client)
            return True
        except Exception as e:
            logger.error(f"create_review_task: {e}")
            return False
