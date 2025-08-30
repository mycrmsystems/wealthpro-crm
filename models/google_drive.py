# models/google_drive.py

import os
import io
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials

from docx import Document
from docx.shared import Pt

__all__ = ["SimpleGoogleDrive"]

logger = logging.getLogger(__name__)


# -----------------------------
# Helpers
# -----------------------------
def _build_drive_service(credentials: Credentials):
    """Build Google Drive v3 service with discovery cache disabled (lower memory)."""
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _safe_date(date_str: str) -> Optional[datetime]:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None


def _escape_drive_name(value: str) -> str:
    """Make a name safe for a Drive v3 query single-quoted string."""
    return (value or "").replace("'", "’")


def _is_letter(name: str) -> bool:
    return len(name) == 1 and name.isalpha() and name.upper() == name


# -----------------------------
# Main class
# -----------------------------
class SimpleGoogleDrive:
    """
    Google Drive helper for WealthPro CRM.

    Supported root structures:

    A) Letters directly under ROOT:
       ROOT
         A/
           Client/
         B/
         ...
         Z/

    B) Categories then letters:
       ROOT
         Active Clients/
           A/
             Client/
         Archived Clients/
           A/
             Client/

    Each client folder (top-level) will contain:
      - Documents/
      - Communications/
      - ID&V & Sanction Search/
      - Tasks/
          Ongoing Tasks/
          Completed Tasks/
      - Reviews/
      - Client Data/
          profile.json
    """

    def __init__(self, credentials: Credentials):
        self.drive = _build_drive_service(credentials)
        self.root_folder_id = os.environ.get("GDRIVE_ROOT_FOLDER_ID", "").strip()
        if not self.root_folder_id:
            raise RuntimeError("GDRIVE_ROOT_FOLDER_ID is not set. Set it in Render env vars.")
        logger.info("Google Drive ready.")

    # -----------------------------
    # Low-level Drive ops
    # -----------------------------
    def _list_folders(self, parent_id: str) -> List[Dict]:
        folders: List[Dict] = []
        page_token = None
        query = (
            f"'{parent_id}' in parents and "
            "mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        while True:
            resp = self.drive.files().list(
                q=query,
                fields="nextPageToken, files(id, name, parents)",
                pageToken=page_token,
                pageSize=1000,
            ).execute()
            folders.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return folders

    def _list_files(self, parent_id: str) -> List[Dict]:
        files: List[Dict] = []
        page = None
        q = (
            f"'{parent_id}' in parents and "
            "mimeType!='application/vnd.google-apps.folder' and trashed=false"
        )
        while True:
            resp = self.drive.files().list(
                q=q,
                fields="nextPageToken, files(id,name,mimeType,parents,createdTime,modifiedTime)",
                pageToken=page,
                pageSize=1000,
                orderBy="name_natural",
            ).execute()
            files.extend(resp.get("files", []))
            page = resp.get("nextPageToken")
            if not page:
                break
        return files

    def _find_child_folder(self, parent_id: str, name: str) -> Optional[Dict]:
        safe_name = _escape_drive_name(name)
        query = (
            f"'{parent_id}' in parents and "
            "mimeType='application/vnd.google-apps.folder' and "
            f"name='{safe_name}' and trashed=false"
        )
        resp = self.drive.files().list(q=query, fields="files(id, name, parents)", pageSize=1).execute()
        files = resp.get("files", [])
        return files[0] if files else None

    def _ensure_folder(self, parent_id: str, name: str) -> str:
        existing = self._find_child_folder(parent_id, name)
        if existing:
            return existing["id"]
        body = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        created = self.drive.files().create(body=body, fields="id,name,parents").execute()
        return created["id"]

    def _move_id_to_parent(self, file_or_folder_id: str, new_parent_id: str):
        obj = self.drive.files().get(fileId=file_or_folder_id, fields="parents").execute()
        prev = ",".join(obj.get("parents", [])) if obj.get("parents") else ""
        self.drive.files().update(
            fileId=file_or_folder_id,
            addParents=new_parent_id,
            removeParents=prev,
            fields="id,parents",
        ).execute()

    def _rename(self, file_id: str, new_name: str):
        self.drive.files().update(fileId=file_id, body={"name": new_name}, fields="id,name").execute()

    # -----------------------------
    # Topology helpers
    # -----------------------------
    def _letters_at_root(self) -> bool:
        letters = [f for f in self._list_folders(self.root_folder_id) if _is_letter(f.get("name", ""))]
        return len(letters) > 0

    def _ensure_category(self, name: str) -> str:
        """Ensure a category folder (e.g., 'Active Clients', 'Archived Clients') under root."""
        return self._ensure_folder(self.root_folder_id, name)

    def _ensure_letter_under(self, parent_id: str, letter: str) -> str:
        letter = letter.upper() if letter and letter.isalpha() else "#"
        return self._ensure_folder(parent_id, letter)

    def _active_parent_for_letters(self) -> str:
        # Prefer letters directly under ROOT; else 'Active Clients' category under root
        if self._letters_at_root():
            return self.root_folder_id
        return self._ensure_category("Active Clients")

    def _archived_parent_for_letters(self) -> str:
        return self._ensure_category("Archived Clients")

    def _client_letter_parent(self, display_name: str, archived: bool = False) -> str:
        parent = self._archived_parent_for_letters() if archived else self._active_parent_for_letters()
        first = (display_name[:1] or "#").upper()
        letter = first if first.isalpha() else "#"
        return self._ensure_letter_under(parent, letter)

    # -----------------------------
    # Client creation & listing
    # -----------------------------
    def ensure_client_core_subfolders(self, client_id: str):
        """Create/ensure the expected top-level subfolders under a client folder."""
        documents = self._ensure_folder(client_id, "Documents")
        self._ensure_folder(client_id, "Communications")
        self._ensure_folder(client_id, "ID&V & Sanction Search")
        tasks = self._ensure_folder(client_id, "Tasks")
        self._ensure_folder(tasks, "Ongoing Tasks")
        self._ensure_folder(tasks, "Completed Tasks")
        self._ensure_folder(client_id, "Reviews")
        cdata = self._ensure_folder(client_id, "Client Data")
        # Ensure profile.json exists (empty stub if missing)
        self._ensure_profile_json(cdata)

    def create_client_enhanced_folders(self, display_name: str) -> str:
        """
        Create A–Z index under either ROOT letters or 'Active Clients' letters,
        then create client folder + all core subfolders.
        """
        display_name = (display_name or "").strip()
        if not display_name:
            raise ValueError("display_name required")

        letter_parent = self._client_letter_parent(display_name, archived=False)
        client_id = self._ensure_folder(letter_parent, display_name)
        self.ensure_client_core_subfolders(client_id)
        logger.info("Created client folder for %s with full subfolders", display_name)
        return client_id

    def _is_client_folder(self, folder_id: str) -> bool:
        """Heuristic: treat as client if it has at least one of the known subfolders."""
        names = {f.get("name", "") for f in self._list_folders(folder_id)}
        markers = {"Tasks", "Reviews", "Documents", "Communications", "Client Data"}
        return len(names & markers) > 0

    def get_clients_enhanced(self) -> List[Dict]:
        """
        Return all client folders (active + archived where present),
        with a computed portfolio_value from Client Data/profile.json.
        """
        clients: List[Dict] = []

        def add_clients_from_letter_parent(letter_parent: str, status: str):
            for letter in self._list_folders(letter_parent):
                if not _is_letter(letter.get("name", "")):
                    continue
                for child in self._list_folders(letter["id"]):
                    if self._is_client_folder(child["id"]) or True:
                        display_name = (child.get("name") or "").strip()
                        portfolio_value = self._compute_portfolio_value(child["id"])
                        clients.append(
                            {
                                "client_id": child["id"],
                                "display_name": display_name,
                                "status": status,
                                "folder_id": child["id"],
                                "portfolio_value": portfolio_value,
                            }
                        )

        # Active space
        if self._letters_at_root():
            add_clients_from_letter_parent(self.root_folder_id, "active")
        else:
            active_cat = self._ensure_category("Active Clients")
            add_clients_from_letter_parent(active_cat, "active")

        # Archived space (if present)
        archived_cat = self._ensure_category("Archived Clients")
        add_clients_from_letter_parent(archived_cat, "archived")

        clients.sort(key=lambda c: (c["display_name"] or "").lower())
        return clients

    # -----------------------------
    # Profile (Client Data/profile.json)
    # -----------------------------
    def _get_client_data_folder(self, client_id: str) -> str:
        return self._ensure_folder(client_id, "Client Data")

    def _find_profile_file(self, client_id: str) -> Tuple[Optional[str], Optional[str]]:
        cdata = self._get_client_data_folder(client_id)
        for f in self._list_files(cdata):
            if (f.get("name") or "").lower() == "profile.json":
                return cdata, f["id"]
        return cdata, None

    def _ensure_profile_json(self, client_data_folder_id: str):
        # If missing, create an empty structure
        existing = [f for f in self._list_files(client_data_folder_id) if (f.get("name","").lower() == "profile.json")]
        if existing:
            return
        stub = {
            "investments": [],
            "pensions": [],
            "notes": "",
            # Optionally, a cached computed_total for quick display (kept in sync on edit screens)
            "computed_total": 0.0
        }
        data = json.dumps(stub, indent=2).encode("utf-8")
        self._upload_bytes(client_data_folder_id, "profile.json", data, "application/json")

    def read_profile(self, client_id: str) -> Dict:
        cdata, file_id = self._find_profile_file(client_id)
        if not cdata:
            cdata = self._get_client_data_folder(client_id)
        if not file_id:
            self._ensure_profile_json(cdata)
            _, file_id = self._find_profile_file(client_id)

        request = self.drive.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        try:
            return json.loads(fh.read().decode("utf-8"))
        except Exception:
            return {"investments": [], "pensions": [], "notes": "", "computed_total": 0.0}

    def write_profile(self, client_id: str, profile: Dict) -> bool:
        cdata, file_id = self._find_profile_file(client_id)
        if not cdata:
            cdata = self._get_client_data_folder(client_id)
        blob = json.dumps(profile, indent=2).encode("utf-8")
        if file_id:
            # Replace by creating new binary and using update with uploadType
            media = MediaIoBaseUpload(io.BytesIO(blob), mimetype="application/json", resumable=False)
            self.drive.files().update(fileId=file_id, media_body=media).execute()
        else:
            self._upload_bytes(cdata, "profile.json", blob, "application/json")
        return True

    def _compute_portfolio_value(self, client_id: str) -> float:
        prof = self.read_profile(client_id)
        total = 0.0
        for item in prof.get("investments", []):
            try:
                total += float(item.get("value") or 0)
            except Exception:
                pass
        for item in prof.get("pensions", []):
            try:
                total += float(item.get("value") or 0)
            except Exception:
                pass
        return float(total)

    # -----------------------------
    # Tasks (Drive-based)
    # -----------------------------
    def _get_client_tasks_folder_ids(self, client_id: str) -> Dict[str, str]:
        tasks_id = self._ensure_folder(client_id, "Tasks")
        ongoing_id = self._ensure_folder(tasks_id, "Ongoing Tasks")
        completed_id = self._ensure_folder(tasks_id, "Completed Tasks")
        return {"tasks": tasks_id, "ongoing": ongoing_id, "completed": completed_id}

    def add_task_enhanced(self, task: Dict, client: Dict) -> bool:
        """Save a task as a .txt file in Ongoing Tasks."""
        client_id = client.get("client_id") or client.get("folder_id")
        if not client_id:
            raise ValueError("client client_id/folder_id missing")

        fids = self._get_client_tasks_folder_ids(client_id)

        due = task.get("due_date", "")
        pr = task.get("priority", "Medium")
        ttype = task.get("task_type", "")
        title = (task.get("title") or "").strip()
        tid = task.get("task_id", f"TSK{datetime.now().strftime('%Y%m%d%H%M%S')}")

        filename = f"{due} - {pr} - {ttype} - {title} [{tid}].txt"

        lines = [
            f"Task ID: {tid}",
            f"Client ID: {client_id}",
            f"Title: {title}",
            f"Type: {ttype}",
            f"Priority: {pr}",
            f"Due Date: {due}",
            f"Status: {task.get('status','Pending')}",
            f"Created: {task.get('created_date','')}",
            f"Completed: {task.get('completed_date','')}",
        ]
        if task.get("time_spent"):
            lines.append(f"Time Allocated: {task.get('time_spent')}")
        if task.get("description"):
            lines.append("")
            lines.append("Description:")
            lines.append(task["description"])

        content = ("\n".join(lines)).encode("utf-8")
        self._upload_bytes(fids["ongoing"], filename, content, "text/plain")
        return True

    def complete_task(self, task_file_id: str) -> bool:
        """Move the task file to Completed Tasks and prefix with 'COMPLETED - '."""
        file = self.drive.files().get(fileId=task_file_id, fields="id,name,parents").execute()
        if not file:
            return False

        # climb up to find 'Tasks' then the client folder
        parent = (file.get("parents") or [None])[0]
        client_id = None

        hops = 0
        while parent and hops < 6:
            node = self.drive.files().get(fileId=parent, fields="id,name,parents").execute()
            name = node.get("name") or ""
            if name == "Tasks":
                par = node.get("parents") or []
                client_id = par[0] if par else None
                break
            parent = (node.get("parents") or [None])[0]
            hops += 1

        if not client_id:
            return False

        fids = self._get_client_tasks_folder_ids(client_id)
        completed = fids["completed"]

        self._move_id_to_parent(task_file_id, completed)

        current_name = file.get("name", "")
        if not current_name.startswith("COMPLETED - "):
            self._rename(task_file_id, f"COMPLETED - {current_name}")

        return True

    def _parse_task_filename(self, name: str) -> Dict:
        result = {"due_date": "", "priority": "", "task_type": "", "title": "", "task_id": ""}
        base = name[:-4] if name.lower().endswith(".txt") else name
        if "[" in base and "]" in base and base.rfind("[") < base.rfind("]"):
            s = base.rfind("["); e = base.rfind("]")
            result["task_id"] = base[s + 1 : e].strip()
            base = (base[:s] + base[e + 1 :]).strip()
        parts = [p.strip() for p in base.split(" - ", 4)]
        if len(parts) >= 4:
            result["due_date"], result["priority"], result["task_type"], result["title"] = parts[:4]
        else:
            if parts: result["due_date"] = parts[0]
            if len(parts) > 1: result["priority"] = parts[1]
            if len(parts) > 2: result["task_type"] = parts[2]
            if len(parts) > 3: result["title"] = parts[3]
        return result

    def get_client_tasks(self, client_id: str) -> List[Dict]:
        fids = self._get_client_tasks_folder_ids(client_id)
        out: List[Dict] = []
        for status, folder in (("Pending", fids["ongoing"]), ("Completed", fids["completed"])):
            page = None
            while True:
                resp = self.drive.files().list(
                    q=(f"'{folder}' in parents and "
                       "mimeType!='application/vnd.google-apps.folder' and trashed=false"),
                    fields="nextPageToken, files(id,name,createdTime,modifiedTime)",
                    pageToken=page,
                    orderBy="name_natural",
                ).execute()
                for f in resp.get("files", []):
                    meta = self._parse_task_filename(f.get("name", ""))
                    out.append(
                        {
                            "task_id": f.get("id"),
                            "client_id": client_id,
                            "title": meta.get("title", ""),
                            "task_type": meta.get("task_type", ""),
                            "due_date": meta.get("due_date", ""),
                            "priority": meta.get("priority", "Medium"),
                            "status": status,
                            "description": "",
                            "created_date": (f.get("createdTime", "")[:10] or ""),
                            "completed_date": (f.get("modifiedTime", "")[:10] if status == "Completed" else ""),
                            "time_spent": "",
                        }
                    )
                page = resp.get("nextPageToken")
                if not page:
                    break

        def sort_key(t):
            d = _safe_date(t.get("due_date", ""))
            return (0 if t["status"] == "Pending" else 1, d or datetime(1970, 1, 1))

        out.sort(key=sort_key)
        return out

    def get_upcoming_tasks(self, days: int = 30) -> List[Dict]:
        """Scan all clients' Ongoing Tasks and return those due within `days`."""
        upcoming: List[Dict] = []
        clients = self.get_clients_enhanced()
        today = datetime.today().date()
        horizon = today + timedelta(days=days)

        for c in clients:
            if c.get("status") == "archived":
                continue  # ignore archived clients for upcoming
            client_id = c["client_id"]
            fids = self._get_client_tasks_folder_ids(client_id)
            ongoing = fids["ongoing"]
            page = None
            while True:
                resp = self.drive.files().list(
                    q=(f"'{ongoing}' in parents and "
                       "mimeType!='application/vnd.google-apps.folder' and trashed=false"),
                    fields="nextPageToken, files(id,name,createdTime)",
                    pageToken=page,
                    orderBy="name_natural",
                ).execute()
                for f in resp.get("files", []):
                    meta = self._parse_task_filename(f.get("name", ""))
                    dd = _safe_date(meta.get("due_date", ""))
                    if dd and today <= dd.date() <= horizon:
                        upcoming.append(
                            {
                                "task_id": f.get("id"),
                                "client_id": client_id,
                                "title": meta.get("title", ""),
                                "task_type": meta.get("task_type", ""),
                                "due_date": meta.get("due_date", ""),
                                "priority": meta.get("priority", "Medium"),
                                "status": "Pending",
                                "description": "",
                                "created_date": f.get("createdTime", "")[:10],
                                "completed_date": "",
                                "time_spent": "",
                            }
                        )
                page = resp.get("nextPageToken")
                if not page:
                    break

        upcoming.sort(key=lambda t: _safe_date(t["due_date"]) or datetime(1970, 1, 1))
        return upcoming

    # -----------------------------
    # Archive / Restore
    # -----------------------------
    def archive_client(self, client_id: str, display_name: str) -> bool:
        """Move client folder to Archived Clients A–Z."""
        dst_letters_parent = self._archived_parent_for_letters()
        letter_parent = self._ensure_letter_under(dst_letters_parent, (display_name[:1] or "#"))
        self._move_id_to_parent(client_id, letter_parent)
        return True

    def restore_client(self, client_id: str, display_name: str) -> bool:
        """Move client folder back to Active A–Z."""
        dst_letters_parent = self._active_parent_for_letters()
        letter_parent = self._ensure_letter_under(dst_letters_parent, (display_name[:1] or "#"))
        self._move_id_to_parent(client_id, letter_parent)
        return True

    # -----------------------------
    # Review pack (unchanged content logic)
    # -----------------------------
    def _uk_date_str(self, dt: datetime) -> str:
        try:
            return dt.strftime("%-d %B %Y")
        except ValueError:
            return dt.strftime("%d %B %Y")

    def create_review_pack_for_client(self, client: Dict) -> Dict[str, str]:
        """Build Review <YEAR> structure and create two Word docs in 'Agenda & Valuation'."""
        client_id = client.get("client_id") or client.get("folder_id")
        display_name = client.get("display_name") or "Client"
        if not client_id:
            raise ValueError("client client_id/folder_id missing")

        year = datetime.today().year
        reviews_root = self._ensure_folder(client_id, "Reviews")
        yr_id = self._ensure_folder(reviews_root, f"Review {year}")

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
        created = {"review_year_id": yr_id}
        for sf in subfolders:
            created[sf] = self._ensure_folder(yr_id, sf)

        agenda_val = created["Agenda & Valuation"]
        today_str = self._uk_date_str(datetime.today())

        # Agenda doc (styled, simple)
        agenda_doc = self._build_agenda_doc(display_name, today_str)
        self._upload_docx(agenda_val, f"Meeting Agenda – {display_name} – {year}.docx", agenda_doc)

        # Valuation doc (styled, simple)
        val_doc = self._build_valuation_doc(display_name, today_str)
        self._upload_docx(agenda_val, f"Valuation Summary – {display_name} – {year}.docx", val_doc)

        return created

    def _upload_docx(self, parent_id: str, filename: str, document: Document):
        stream = io.BytesIO()
        document.save(stream)
        stream.seek(0)
        media = MediaIoBaseUpload(
            stream,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            resumable=False,
        )
        meta = {"name": filename, "parents": [parent_id]}
        self.drive.files().create(body=meta, media_body=media, fields="id,name").execute()

    # -----------------------------
    # Word document builders (kept simple & consistent)
    # -----------------------------
    def _build_agenda_doc(self, client_display_name: str, date_str: str) -> Document:
        doc = Document()
        p = doc.add_paragraph()
        r = p.add_run("Client Review Meeting Agenda")
        r.bold = True
        r.font.size = Pt(16)
        doc.add_paragraph(f"Client: {client_display_name}")
        doc.add_paragraph(f"Date: {date_str}")
        doc.add_paragraph("")
        items = [
            "1. Welcome & objectives",
            "2. Personal & financial updates",
            "3. Investment performance & valuation",
            "4. Risk profile (ATR) & capacity",
            "5. Charges & costs",
            "6. Portfolio changes / recommendations",
            "7. Action points & next steps",
        ]
        for it in items:
            para = doc.add_paragraph(it)
            para.runs[0].font.size = Pt(11)
        return doc

    def _build_valuation_doc(self, client_display_name: str, date_str: str) -> Document:
        doc = Document()
        p = doc.add_paragraph()
        r = p.add_run("Valuation Summary")
        r.bold = True
        r.font.size = Pt(16)

        doc.add_paragraph(f"Client: {client_display_name}")
        doc.add_paragraph(f"Date: {date_str}")
        doc.add_paragraph("")

        table = doc.add_table(rows=1, cols=3)
        hdr = table.rows[0].cells
        hdr[0].text = "Plan / Account"
        hdr[1].text = "Provider"
        hdr[2].text = "Value (£)"

        # starter row
        row = table.add_row().cells
        row[0].text = ""
        row[1].text = ""
        row[2].text = ""

        doc.add_paragraph("")
        doc.add_paragraph("Total Value: £")
        return doc
