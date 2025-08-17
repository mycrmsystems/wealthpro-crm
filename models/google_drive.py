import os
import io
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaFileUpload
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

MIME_FOLDER = "application/vnd.google-apps.folder"
MIME_SPREADSHEET = "application/vnd.google-apps.spreadsheet"

TASKS_SPREADSHEET_NAME = "WealthPro CRM - Tasks"

ACTIVE_CLIENTS_DIR = "Active Clients"
ARCHIVED_CLIENTS_DIR = "Archived Clients"

DEFAULT_CLIENT_SUBFOLDERS = [
    "Communications",
    "Tasks",
    "Reviews",
    "Fact Find",
    "Compliance",
    "Portfolio",
    "Documents",
]

TASKS_ONGOING_DIR = "Ongoing Tasks"
TASKS_COMPLETED_DIR = "Completed Tasks"

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
    """
    Google Drive + Sheets wrapper for WealthPro CRM.

    NOTE ON TEMPLATE SAFETY:
    - Every client dict we return includes safe defaults for fields your templates tend to format:
      first_name, last_name, display_name, email, phone, created_at, status.
    - Dates are always strings (e.g., '2025-08-16') so Jinja won't see None/Undefined.
    """

    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        self.drive = build("drive", "v3", credentials=self.credentials, cache_discovery=False)
        self.sheets = build("sheets", "v4", credentials=self.credentials, cache_discovery=False)

        self.root_folder_id = os.environ.get("GDRIVE_ROOT_FOLDER_ID")
        if not self.root_folder_id:
            raise RuntimeError("GDRIVE_ROOT_FOLDER_ID is not set. Please set it in Render env vars.")

        self.active_clients_id = self.find_or_create_subfolder(self.root_folder_id, ACTIVE_CLIENTS_DIR)
        self.archived_clients_id = self.find_or_create_subfolder(self.root_folder_id, ARCHIVED_CLIENTS_DIR)

        self.tasks_spreadsheet_id = self._ensure_tasks_spreadsheet()

        logger.info("Google Drive/Sheets setup complete.")

    # ----------------------------- FOLDERS/FILES -----------------------------

    def find_or_create_subfolder(self, parent_id: str, name: str) -> str:
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
        mime_clause = f"and mimeType = '{mime_type}' " if mime_type else ""
        q = f"trashed = false and '{parent_id}' in parents and name = '{name}' {mime_clause}"
        res = self.drive.files().list(q=q, spaces="drive", fields="files(id, name, mimeType)", pageSize=10).execute()
        files = res.get("files", [])
        return files[0] if files else None

    def upload_file_to_drive(self, local_path: str, name: str, parent_id: str, mime_type: Optional[str] = None) -> str:
        media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
        body = {"name": name, "parents": [parent_id]}
        created = self.drive.files().create(body=body, media_body=media, fields="id").execute()
        return created["id"]

    # ----------------------------- CLIENT HELPERS -----------------------------

    @staticmethod
    def _split_display_name(display_name: str) -> Tuple[str, str]:
        """
        Convert 'Surname, Firstname' -> (Firstname, Surname)
        If it doesn't match that pattern, try a sensible split; otherwise return ('', display_name).
        """
        disp = (display_name or "").strip()
        if ", " in disp:
            parts = disp.split(", ", 1)
            last = parts[0].strip()
            first = parts[1].strip()
            return (first, last)
        # Fallbacks
        tokens = disp.split()
        if len(tokens) >= 2:
            # 'First Last ...' -> take first token as first_name, last token as last_name
            return (tokens[0].strip(), tokens[-1].strip())
        if disp:
            return ("", disp)
        return ("", "")

    def create_enhanced_client_folder(self, client: Dict) -> Dict:
        """
        Create 'Active Clients/<Surname, Firstname>' with standard subfolders plus Tasks/Ongoing+Completed.
        This returns a fully-populated client dict safe for templates.
        """
        first = (client.get("first_name") or "").strip()
        last = (client.get("last_name") or "").strip()
        display_name = client.get("display_name") or f"{last}, {first}".strip(", ").strip()

        # Main folder
        client_folder_id = self.find_or_create_subfolder(self.active_clients_id, display_name)

        # Subfolders
        sub_ids = {}
        for name in DEFAULT_CLIENT_SUBFOLDERS:
            sub_ids[name] = self.find_or_create_subfolder(client_folder_id, name)

        # Tasks structure
        tasks_folder_id = sub_ids["Tasks"]
        self.find_or_create_subfolder(tasks_folder_id, TASKS_ONGOING_DIR)
        self.find_or_create_subfolder(tasks_folder_id, TASKS_COMPLETED_DIR)

        # Safe client dict for templates
        created_at_str = datetime.utcnow().strftime("%Y-%m-%d")
        safe_first, safe_last = self._split_display_name(display_name)

        result = {
            "client_id": client_folder_id,      # use folder id as the client id (Drive-backed)
            "folder_id": client_folder_id,
            "display_name": display_name or f"{safe_last}, {safe_first}",
            "first_name": first or safe_first or "",
            "last_name": last or safe_last or "",
            "email": client.get("email", "") or "",
            "phone": client.get("phone", "") or "",
            "created_at": client.get("created_at", created_at_str) or created_at_str,
            "status": "Active",
            "subfolders": sub_ids,
        }
        logger.info(f"Created enhanced client folder for {result['display_name']} in active section")
        return result

    def archive_client_folder(self, display_name: str) -> None:
        q = (
            "mimeType = 'application/vnd.google-apps.folder' and trashed = false "
            f"and '{self.active_clients_id}' in parents and name = '{display_name}'"
        )
        res = self.drive.files().list(q=q, spaces="drive", fields="files(id, name)").execute()
        files = res.get("files", [])
        if not files:
            return
        client_id = files[0]["id"]
        self.drive.files().update(
            fileId=client_id,
            addParents=self.archived_clients_id,
            removeParents=self.active_clients_id,
            fields="id, parents",
        ).execute()

    def get_clients_enhanced(self) -> List[Dict]:
        """
        Enumerate Active + Archived client folders and return SAFE client dicts
        with all fields your templates expect.
        """
        clients: List[Dict] = []

        def list_children(parent_id: str, archived: bool) -> None:
            q = f"mimeType = '{MIME_FOLDER}' and trashed = false and '{parent_id}' in parents"
            page_token = None
            while True:
                resp = self.drive.files().list(
                    q=q,
                    spaces="drive",
                    fields="nextPageToken, files(id, name, createdTime)",
                    pageSize=100,
                    pageToken=page_token,
                ).execute()
                for f in resp.get("files", []):
                    disp = f.get("name") or ""
                    cid = f.get("id")
                    created_time = f.get("createdTime") or ""
                    # Normalize created date string (YYYY-MM-DD)
                    try:
                        created_at = datetime.fromisoformat(created_time.replace("Z", "+00:00")).strftime("%Y-%m-%d")
                    except Exception:
                        created_at = datetime.utcnow().strftime("%Y-%m-%d")

                    first, last = self._split_display_name(disp)

                    clients.append(
                        {
                            "client_id": cid,
                            "folder_id": cid,
                            "display_name": disp,
                            "first_name": first or "",
                            "last_name": last or "",
                            "email": "",
                            "phone": "",
                            "created_at": created_at,
                            "status": "Archived" if archived else "Active",
                        }
                    )
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break

        list_children(self.active_clients_id, archived=False)
        list_children(self.archived_clients_id, archived=True)

        clients.sort(key=lambda c: (c["status"], c["display_name"].lower()))
        return clients

    # ----------------------------- TASKS (SHEETS) -----------------------------

    def _ensure_tasks_spreadsheet(self) -> str:
        existing = self._find_file_in_parent(self.root_folder_id, TASKS_SPREADSHEET_NAME, MIME_SPREADSHEET)
        if existing:
            spreadsheet_id = existing["id"]
        else:
            body = {"name": TASKS_SPREADSHEET_NAME, "mimeType": MIME_SPREADSHEET, "parents": [self.root_folder_id]}
            created = self.drive.files().create(body=body, fields="id").execute()
            spreadsheet_id = created["id"]

        rng = "Tasks!1:1"
        try:
            resp = self.sheets.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=rng).execute()
            values = resp.get("values", [])
            if not values or values[0] != TASKS_HEADER:
                self.sheets.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id, range=rng, valueInputOption="RAW", body={"values": [TASKS_HEADER]}
                ).execute()
        except HttpError:
            requests = [{"addSheet": {"properties": {"title": "Tasks"}}}]
            self.sheets.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()
            self.sheets.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id, range=rng, valueInputOption="RAW", body={"values": [TASKS_HEADER]}
            ).execute()

        return spreadsheet_id

    def add_task_enhanced(self, task_data: Dict, client: Dict) -> bool:
        created_str = datetime.utcnow().strftime("%Y-%m-%d")
        row = [
            task_data.get("task_id", ""),
            task_data.get("client_id", ""),
            task_data.get("task_type", ""),
            task_data.get("title", ""),
            task_data.get("description", ""),
            task_data.get("due_date", ""),
            task_data.get("priority", ""),
            task_data.get("status", "Pending"),
            task_data.get("created_date", created_str) or created_str,
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

        # Best-effort Drive stub in Ongoing
        try:
            client_folder_id = client.get("folder_id") or client.get("client_id")
            tasks_folder_id = self.find_or_create_subfolder(client_folder_id, "Tasks")
            ongoing_id = self.find_or_create_subfolder(tasks_folder_id, TASKS_ONGOING_DIR)

            name = f"{task_data.get('due_date','')} - {task_data.get('title','Task')} ({task_data.get('priority','')}).txt"
            content = io.BytesIO(
                (
                    f"Title: {task_data.get('title','')}\n"
                    f"Type: {task_data.get('task_type','')}\n"
                    f"Client: {client.get('display_name','')}\n"
                    f"Due: {task_data.get('due_date','')}\n"
                    f"Priority: {task_data.get('priority','')}\n"
                    f"Status: {task_data.get('status','Pending')}\n"
                    f"Created: {row[8]}\n"
                    f"Description:\n{task_data.get('description','')}\n"
                ).encode("utf-8")
            )
            media = MediaIoBaseUpload(content, mimetype="text/plain", resumable=False)
            body = {"name": name, "parents": [ongoing_id]}
            self.drive.files().create(body=body, media_body=media, fields="id").execute()
        except Exception as e:
            logger.warning(f"Could not create Drive task stub file: {e}")

        return True

    def _read_all_tasks(self) -> List[Dict]:
        resp = self.sheets.spreadsheets().values().get(
            spreadsheetId=self.tasks_spreadsheet_id, range="Tasks!A2:K"
        ).execute()
        rows = resp.get("values", [])
        tasks = []
        for r in rows:
            r = r + [""] * (len(TASKS_HEADER) - len(r))
            data = dict(zip(TASKS_HEADER, r))
            tasks.append(data)
        return tasks

    def get_upcoming_tasks(self, days: int) -> List[Dict]:
        all_tasks = self._read_all_tasks()
        out = []
        today = datetime.utcnow().date()
        horizon = today + timedelta(days=days)

        for t in all_tasks:
            status = (t.get("status") or "").strip().lower()
            if status == "completed":
                continue
            due_raw = (t.get("due_date") or "").strip()
            if not due_raw:
                continue
            due = None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    due = datetime.strptime(due_raw, fmt).date()
                    break
                except ValueError:
                    continue
            if not due:
                continue
            if due <= horizon:
                out.append(t)

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
        resp = self.sheets.spreadsheets().values().get(
            spreadsheetId=self.tasks_spreadsheet_id, range="Tasks!A2:K"
        ).execute()
        rows = resp.get("values", [])
        changed = False

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

        # Move any Drive stub Ongoing -> Completed
        try:
            match = next((r for r in new_rows if r[0] == task_id), None)
            if match:
                client_id = match[1]
                title = match[3]
                due_date = match[5]
                guess_name = f"{due_date} - {title} ("

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

    # ----------------------------- DASHBOARD SUMMARY -----------------------------

    def get_dashboard_summary(self) -> Dict:
        """
        Provide safe summary numbers for the dashboard:
        - total_active_clients
        - total_archived_clients
        - tasks_due_30 (list of tasks due within next 30 days, excluding Completed)
        """
        # Count clients
        def count_children(parent_id: str) -> int:
            q = f"mimeType = '{MIME_FOLDER}' and trashed = false and '{parent_id}' in parents"
            total = 0
            page_token = None
            while True:
                resp = self.drive.files().list(
                    q=q, spaces="drive", fields="nextPageToken, files(id)", pageSize=200, pageToken=page_token
                ).execute()
                total += len(resp.get("files", []))
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
            return total

        active = count_children(self.active_clients_id)
        archived = count_children(self.archived_clients_id)
        tasks30 = self.get_upcoming_tasks(30)

        return {
            "total_active_clients": active,
            "total_archived_clients": archived,
            "tasks_due_30": tasks30,
        }

    # ----------------------------- REVIEW PACK -----------------------------

    def create_review_pack_for_client(self, client: dict) -> dict:
        display_name = client.get("display_name") or f"{client.get('last_name','')}, {client.get('first_name','')}".strip(", ")
        first, last = self._split_display_name(display_name)
        full_name = (f"{client.get('first_name') or first} {client.get('last_name') or last}").strip() or display_name

        client_folder_id = client.get("folder_id") or client.get("client_id")
        if not client_folder_id:
            raise ValueError("Client record has no Drive folder id.")

        reviews_folder_id = self.find_or_create_subfolder(client_folder_id, "Reviews")
        year_str = str(datetime.utcnow().year)
        review_year_folder_id = self.find_or_create_subfolder(reviews_folder_id, f"Review {year_str}")

        sub_ids = {}
        for name in REVIEW_SUBFOLDERS:
            sub_ids[name] = self.find_or_create_subfolder(review_year_folder_id, name)

        agenda_folder_id = sub_ids["Agenda & Valuation"]

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

    # ----------------------------- DELETE CLIENT -----------------------------

    def delete_client_enhanced(self, client_folder_id: str) -> bool:
        try:
            self.drive.files().update(fileId=client_folder_id, body={"trashed": True}).execute()
            return True
        except HttpError as e:
            logger.error(f"Error deleting client folder {client_folder_id}: {e}")
            return False
