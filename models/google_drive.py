import os
import io
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaFileUpload
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


# ======= Constants =======

MIME_FOLDER = "application/vnd.google-apps.folder"
MIME_SPREADSHEET = "application/vnd.google-apps.spreadsheet"

# A single spreadsheet in Drive root to hold all tasks
TASKS_SPREADSHEET_NAME = "WealthPro CRM - Tasks"

# Top-level client buckets beneath your CRM root
ACTIVE_CLIENTS_DIR = "Active Clients"
ARCHIVED_CLIENTS_DIR = "Archived Clients"

# Default client subfolders (you can expand later)
DEFAULT_CLIENT_SUBFOLDERS = [
    "Communications",
    "Tasks",
    "Reviews",
    "Fact Find",
    "Compliance",
    "Portfolio",
    "Documents"
]

# Inside Tasks folder
TASKS_ONGOING_DIR = "Ongoing Tasks"
TASKS_COMPLETED_DIR = "Completed Tasks"

# Review pack subfolders
REVIEW_SUBFOLDERS = [
    "Agenda & Valuation",
    "FF&ATR",
    "ID&V & Sanction Search",
    "Meeting Notes",
    "Research",
    "Review Letter",
    "Client Confirmation",
    "Emails",
]

TASKS_HEADER = [
    "task_id",
    "client_id",
    "task_type",
    "title",
    "description",
    "due_date",
    "priority",
    "status",
    "created_date",
    "completed_date",
    "time_spent",
]


class SimpleGoogleDrive:
    """Wrapper around Google Drive + Sheets for WealthPro CRM."""

    def __init__(self, credentials: Credentials):
        self.credentials = credentials

        # Build clients (with discovery cache disabled to trim memory)
        self.drive = build("drive", "v3", credentials=self.credentials, cache_discovery=False)
        self.sheets = build("sheets", "v4", credentials=self.credentials, cache_discovery=False)

        # Required root env var (set this in Render)
        self.root_folder_id = os.environ.get("GDRIVE_ROOT_FOLDER_ID")
        if not self.root_folder_id:
            raise RuntimeError("GDRIVE_ROOT_FOLDER_ID is not set. Please set it in Render env vars.")

        # Ensure the two top-level client buckets exist
        self.active_clients_id = self.find_or_create_subfolder(self.root_folder_id, ACTIVE_CLIENTS_DIR)
        self.archived_clients_id = self.find_or_create_subfolder(self.root_folder_id, ARCHIVED_CLIENTS_DIR)

        # Ensure tasks spreadsheet exists (used by tasks pages)
        self.tasks_spreadsheet_id = self._ensure_tasks_spreadsheet()

        logger.info("Google Drive/Sheets setup complete.")

    # ---------------------------------------------------------------------
    # Folder & File Helpers
    # ---------------------------------------------------------------------

    def find_or_create_subfolder(self, parent_id: str, name: str) -> str:
        """
        Return folder ID for 'name' under parent_id, creating if missing.
        Uses a safe list query to avoid escaping issues.
        """
        q = (
            "mimeType = 'application/vnd.google-apps.folder' "
            "and trashed = false "
            f"and '{parent_id}' in parents "
            f"and name = '{name}'"
        )
        res = self.drive.files().list(q=q, spaces="drive", fields="files(id, name)", pageSize=10).execute()
        files = res.get("files", [])
        if files:
            return files[0]["id"]

        body = {"name": name, "mimeType": MIME_FOLDER, "parents": [parent_id]}
        created = self.drive.files().create(body=body, fields="id").execute()
        return created["id"]

    def _find_file_in_parent(self, parent_id: str, name: str, mime_type: Optional[str] = None) -> Optional[dict]:
        """Find a file by exact name under a parent."""
        mime_clause = f"and mimeType = '{mime_type}' " if mime_type else ""
        q = f"trashed = false and '{parent_id}' in parents and name = '{name}' {mime_clause}"
        res = self.drive.files().list(q=q, spaces="drive", fields="files(id, name, mimeType)", pageSize=10).execute()
        files = res.get("files", [])
        return files[0] if files else None

    def upload_file_to_drive(self, local_path: str, name: str, parent_id: str, mime_type: Optional[str] = None) -> str:
        """Upload a local file to Drive under parent_id. Returns file ID."""
        media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
        body = {"name": name, "parents": [parent_id]}
        created = self.drive.files().create(body=body, media_body=media, fields="id").execute()
        return created["id"]

    # ---------------------------------------------------------------------
    # Clients
    # ---------------------------------------------------------------------

    def create_enhanced_client_folder(self, client: Dict) -> Dict:
        """
        Create an 'Active Clients/<Surname, Firstname>' folder with default subfolders,
        including 'Tasks' with 'Ongoing Tasks' & 'Completed Tasks'.
        """
        # Preferred display: "Surname, Firstname"
        first = (client.get("first_name") or "").strip()
        last = (client.get("last_name") or "").strip()
        display_name = client.get("display_name") or f"{last}, {first}".strip(", ")

        # Main client folder
        client_folder_id = self.find_or_create_subfolder(self.active_clients_id, display_name)

        # Subfolders
        sub_ids = {}
        for name in DEFAULT_CLIENT_SUBFOLDERS:
            sub_ids[name] = self.find_or_create_subfolder(client_folder_id, name)

        # Tasks sub-subfolders
        tasks_folder_id = sub_ids["Tasks"]
        self.find_or_create_subfolder(tasks_folder_id, TASKS_ONGOING_DIR)
        self.find_or_create_subfolder(tasks_folder_id, TASKS_COMPLETED_DIR)

        logger.info(f"Created enhanced client folder for {display_name} in active section")
        return {
            "display_name": display_name,
            "folder_id": client_folder_id,
            "subfolders": sub_ids,
        }

    def archive_client_folder(self, display_name: str) -> None:
        """Move a client folder from Active to Archived (if exists)."""
        # Find folder under Active
        q = (
            "mimeType = 'application/vnd.google-apps.folder' and trashed = false "
            f"and '{self.active_clients_id}' in parents and name = '{display_name}'"
        )
        res = self.drive.files().list(q=q, spaces="drive", fields="files(id, name)").execute()
        files = res.get("files", [])
        if not files:
            return

        client_id = files[0]["id"]
        # Update parents: remove Active, add Archived
        self.drive.files().update(
            fileId=client_id,
            addParents=self.archived_clients_id,
            removeParents=self.active_clients_id,
            fields="id, parents",
        ).execute()

    def get_clients_enhanced(self) -> List[Dict]:
        """
        Build client list by enumerating subfolders of 'Active Clients' and 'Archived Clients'.
        Each becomes a 'client' entry with IDs and display names.
        """
        clients: List[Dict] = []

        def list_children(parent_id: str, archived: bool) -> None:
            q = f"mimeType = '{MIME_FOLDER}' and trashed = false and '{parent_id}' in parents"
            page_token = None
            while True:
                resp = self.drive.files().list(
                    q=q,
                    spaces="drive",
                    fields="nextPageToken, files(id, name)",
                    pageSize=100,
                    pageToken=page_token,
                ).execute()
                for f in resp.get("files", []):
                    disp = f.get("name")
                    cid = f.get("id")
                    clients.append(
                        {
                            "client_id": cid,  # use folder id as stable client_id for Drive-derived registry
                            "display_name": disp,
                            "folder_id": cid,
                            "status": "Archived" if archived else "Active",
                            "first_name": "",
                            "last_name": "",
                        }
                    )
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break

        list_children(self.active_clients_id, archived=False)
        list_children(self.archived_clients_id, archived=True)
        # Sort by name
        clients.sort(key=lambda c: c["display_name"].lower())
        return clients

    # ---------------------------------------------------------------------
    # Tasks (stored in a single Sheets spreadsheet in Drive root)
    # ---------------------------------------------------------------------

    def _ensure_tasks_spreadsheet(self) -> str:
        """Find or create the central tasks spreadsheet & ensure header row."""
        # Try to find by name under root
        existing = self._find_file_in_parent(self.root_folder_id, TASKS_SPREADSHEET_NAME, MIME_SPREADSHEET)
        if existing:
            spreadsheet_id = existing["id"]
        else:
            body = {"name": TASKS_SPREADSHEET_NAME, "mimeType": MIME_SPREADSHEET, "parents": [self.root_folder_id]}
            created = self.drive.files().create(body=body, fields="id").execute()
            spreadsheet_id = created["id"]

        # Ensure header row exists
        rng = "Tasks!1:1"
        try:
            resp = self.sheets.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=rng).execute()
            values = resp.get("values", [])
            if not values or values[0] != TASKS_HEADER:
                self.sheets.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=rng,
                    valueInputOption="RAW",
                    body={"values": [TASKS_HEADER]},
                ).execute()
        except HttpError:
            # Create the "Tasks" sheet if missing, then write header
            requests = [{"addSheet": {"properties": {"title": "Tasks"}}}]
            self.sheets.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()
            self.sheets.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=rng,
                valueInputOption="RAW",
                body={"values": [TASKS_HEADER]},
            ).execute()

        return spreadsheet_id

    def add_task_enhanced(self, task_data: Dict, client: Dict) -> bool:
        """Append a task row to the central tasks spreadsheet."""
        row = [
            task_data.get("task_id", ""),
            task_data.get("client_id", ""),
            task_data.get("task_type", ""),
            task_data.get("title", ""),
            task_data.get("description", ""),
            task_data.get("due_date", ""),
            task_data.get("priority", ""),
            task_data.get("status", "Pending"),
            task_data.get("created_date", datetime.utcnow().strftime("%Y-%m-%d")),
            task_data.get("completed_date", ""),
            task_data.get("time_spent", ""),
        ]
        self.sheets.spreadsheets().values().append(
            spreadsheetId=self.tasks_spreadsheet_id,
            range="Tasks!A:K",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

        # Optionally, create a small note file inside the client's "Ongoing Tasks" folder
        try:
            # Ensure the client has Tasks/Ongoing Tasks path
            client_folder_id = client.get("folder_id") or client.get("client_id")
            tasks_folder_id = self.find_or_create_subfolder(client_folder_id, "Tasks")
            ongoing_id = self.find_or_create_subfolder(tasks_folder_id, TASKS_ONGOING_DIR)

            # Create a tiny .txt stub for users who like to see files in Drive
            name = f"{task_data.get('due_date','')} - {task_data.get('title','Task')} ({task_data.get('priority','')}).txt"
            content = io.BytesIO(
                (
                    f"Title: {task_data.get('title','')}\n"
                    f"Type: {task_data.get('task_type','')}\n"
                    f"Client: {client.get('display_name','')}\n"
                    f"Due: {task_data.get('due_date','')}\n"
                    f"Priority: {task_data.get('priority','')}\n"
                    f"Status: {task_data.get('status','Pending')}\n"
                    f"Created: {task_data.get('created_date','')}\n"
                    f"Description:\n{task_data.get('description','')}\n"
                ).encode("utf-8")
            )
            media = MediaIoBaseUpload(content, mimetype="text/plain", resumable=False)
            body = {"name": name, "parents": [ongoing_id]}
            self.drive.files().create(body=body, media_body=media, fields="id").execute()
        except Exception as e:
            # Non-fatal
            logger.warning(f"Could not create Drive task stub file: {e}")

        return True

    def _read_all_tasks(self) -> List[Dict]:
        resp = self.sheets.spreadsheets().values().get(
            spreadsheetId=self.tasks_spreadsheet_id, range="Tasks!A2:K"
        ).execute()
        rows = resp.get("values", [])
        tasks = []
        for r in rows:
            # pad row length
            r = r + [""] * (len(TASKS_HEADER) - len(r))
            data = dict(zip(TASKS_HEADER, r))
            tasks.append(data)
        return tasks

    def get_upcoming_tasks(self, days: int) -> List[Dict]:
        """Return tasks due in next <days>, keeping any overdue items (status != Completed)."""
        all_tasks = self._read_all_tasks()
        out = []

        today = datetime.utcnow().date()
        horizon = today + timedelta(days=days)

        for t in all_tasks:
            status = (t.get("status") or "").strip()
            if status.lower() == "completed":
                continue

            due_raw = (t.get("due_date") or "").strip()
            if not due_raw:
                continue
            try:
                due = datetime.strptime(due_raw, "%Y-%m-%d").date()
            except ValueError:
                # try UK-style fallback
                try:
                    due = datetime.strptime(due_raw, "%d/%m/%Y").date()
                except ValueError:
                    continue

            # keep if overdue OR within horizon
            if due <= horizon:
                out.append(t)

        # sort by due_date ascending
        def parse_date(s: str) -> datetime:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(s, fmt)
                except ValueError:
                    continue
            return datetime.max

        out.sort(key=lambda x: parse_date(x.get("due_date", "")))
        return out

    def get_client_tasks(self, client_id: str) -> List[Dict]:
        all_tasks = self._read_all_tasks()
        return [t for t in all_tasks if (t.get("client_id") or "") == client_id]

    def complete_task(self, task_id: str) -> bool:
        """Mark a task Completed in the sheet and move any .txt stub from Ongoing to Completed."""
        # Read the sheet first
        resp = self.sheets.spreadsheets().values().get(
            spreadsheetId=self.tasks_spreadsheet_id, range="Tasks!A2:K"
        ).execute()
        rows = resp.get("values", [])
        changed = False

        # We will write back via batchUpdate to preserve other rows
        new_rows = []
        today = datetime.utcnow().strftime("%Y-%m-%d")
        for r in rows:
            r = r + [""] * (len(TASKS_HEADER) - len(r))
            row_map = dict(zip(TASKS_HEADER, r))
            if row_map.get("task_id") == task_id:
                row_map["status"] = "Completed"
                row_map["completed_date"] = today
                changed = True
            new_rows.append([row_map.get(h, "") for h in TASKS_HEADER])

        if changed:
            self.sheets.spreadsheets().values().update(
                spreadsheetId=self.tasks_spreadsheet_id,
                range="Tasks!A2",
                valueInputOption="RAW",
                body={"values": new_rows},
            ).execute()

        # Best-effort: move any matching stub file from Ongoing to Completed
        try:
            # Find client_id to locate its folder
            match = next((r for r in new_rows if r[0] == task_id), None)
            if match:
                client_id = match[1]
                title = match[3]
                due_date = match[5]
                # Guess the file name we created before
                guess_name = f"{due_date} - {title} ("
                # Search in Ongoing folder
                tasks_folder_id = self.find_or_create_subfolder(client_id, "Tasks")
                ongoing_id = self.find_or_create_subfolder(tasks_folder_id, TASKS_ONGOING_DIR)
                completed_id = self.find_or_create_subfolder(tasks_folder_id, TASKS_COMPLETED_DIR)

                q = (
                    "trashed = false "
                    f"and '{ongoing_id}' in parents "
                    "and mimeType != 'application/vnd.google-apps.folder'"
                )
                res = self.drive.files().list(q=q, spaces="drive", fields="files(id, name, parents)", pageSize=100).execute()
                for f in res.get("files", []):
                    if f.get("name", "").startswith(guess_name):
                        # move parent from ongoing to completed
                        file_id = f["id"]
                        self.drive.files().update(
                            fileId=file_id,
                            addParents=completed_id,
                            removeParents=ongoing_id,
                            fields="id, parents",
                        ).execute()
                        break
        except Exception as e:
            logger.warning(f"Could not move stub task file to Completed: {e}")

        return changed

    # ---------------------------------------------------------------------
    # Review Pack
    # ---------------------------------------------------------------------

    def create_review_pack_for_client(self, client: dict) -> dict:
        """
        Creates 'Reviews/Review <YEAR>' structure and generates two .docx files under
        'Agenda & Valuation' with the client's name and today's date.
        """
        display_name = client.get("display_name") or f"{client.get('last_name','')}, {client.get('first_name','')}".strip(", ")
        first = (client.get("first_name") or "").strip()
        last = (client.get("last_name") or "").strip()
        full_name = f"{first} {last}".strip() or display_name

        # Locate client folder
        client_folder_id = client.get("folder_id") or client.get("client_id")
        if not client_folder_id:
            raise ValueError("Client record has no Drive folder id.")

        # Reviews/Review <YEAR>
        reviews_folder_id = self.find_or_create_subfolder(client_folder_id, "Reviews")
        year_str = str(datetime.utcnow().year)
        review_year_folder_id = self.find_or_create_subfolder(reviews_folder_id, f"Review {year_str}")

        # Required subfolders
        sub_ids = {}
        for name in REVIEW_SUBFOLDERS:
            sub_ids[name] = self.find_or_create_subfolder(review_year_folder_id, name)

        agenda_folder_id = sub_ids["Agenda & Valuation"]

        # Create two Word docs
        try:
            from docx import Document
        except Exception as e:
            raise RuntimeError("python-docx is required. Ensure python-docx is in requirements.txt") from e

        today_str = datetime.utcnow().strftime("%d %B %Y")

        # Meeting Agenda
        agenda_doc = Document()
        agenda_doc.add_heading("Review Meeting Agenda", level=1)
        agenda_doc.add_paragraph(f"Client: {full_name}")
        agenda_doc.add_paragraph(f"Date: {today_str}")
        agenda_doc.add_paragraph("")
        agenda_doc.add_paragraph("Agenda:")
        agenda_doc.add_paragraph("1. Update on circumstances and objectives")
        agenda_doc.add_paragraph("2. Review of risk profile and capacity for loss")
        agenda_doc.add_paragraph("3. Portfolio/plan performance & valuation")
        agenda_doc.add_paragraph("4. Fees, charges & ongoing service")
        agenda_doc.add_paragraph("5. Actions & next steps")

        local_agenda = f"/tmp/{full_name.replace(' ', '_')}_Agenda_{year_str}.docx"
        agenda_doc.save(local_agenda)
        agenda_file_id = self.upload_file_to_drive(
            local_path=local_agenda,
            name=f"{full_name} - Meeting Agenda {year_str}.docx",
            parent_id=agenda_folder_id,
            mime_type=None,
        )

        # Valuation Summary
        val_doc = Document()
        val_doc.add_heading("Valuation Summary", level=1)
        val_doc.add_paragraph(f"Client: {full_name}")
        val_doc.add_paragraph(f"Date: {today_str}")
        val_doc.add_paragraph("")
        val_doc.add_paragraph("Plans/Investments:")
        val_doc.add_paragraph("- (Enter plan details here)")
        val_doc.add_paragraph("")
        val_doc.add_paragraph("Notes:")
        val_doc.add_paragraph("- (Add any relevant notes)")

        local_val = f"/tmp/{full_name.replace(' ', '_')}_Valuation_{year_str}.docx"
        val_doc.save(local_val)
        valuation_file_id = self.upload_file_to_drive(
            local_path=local_val,
            name=f"{full_name} - Valuation Summary {year_str}.docx",
            parent_id=agenda_folder_id,
            mime_type=None,
        )

        return {
            "reviews_folder_id": reviews_folder_id,
            "review_year_folder_id": review_year_folder_id,
            "subfolders": sub_ids,
            "agenda_doc_id": agenda_file_id,
            "valuation_doc_id": valuation_file_id,
        }

    # ---------------------------------------------------------------------
    # Optional: delete client (best-effort)
    # ---------------------------------------------------------------------

    def delete_client_enhanced(self, client_folder_id: str) -> bool:
        """
        Trashes the client folder by id (which moves to Drive bin; still recoverable).
        """
        try:
            self.drive.files().update(fileId=client_folder_id, body={"trashed": True}).execute()
            return True
        except HttpError as e:
            logger.error(f"Error deleting client folder {client_folder_id}: {e}")
            return False
