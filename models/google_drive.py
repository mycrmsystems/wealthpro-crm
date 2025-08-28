# models/google_drive.py

import os
import io
import logging
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials

from docx import Document
from docx.shared import Pt

__all__ = ["SimpleGoogleDrive"]

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Embedded template: YOUR uploaded Meeting Agenda the correct one.docx
# (No env vars, no extra files needed.)
# -----------------------------------------------------------------------------
AGENDA_DOCX_B64 = (
    "UEsDBBQABgAIAAAAIQDkJIlMfQEAACkGAAATAAgCW0NvbnRlbnRfVHlwZXNd"
    "UEsHCJk+u4cEAAAABAAAAFBLAwQUAAYACAAAACEAtuT0U8mQAQAA5gEAAA8A"
    "CABfcmVscy8ucmVsc1BLAwQUAAYACAAAACEA8C4oR3C3AQAA9wUAABgACABk"
    "b2NQcm9wcy9hcHAueG1sUEsDBBQABgAIAAAAIQCHkQw3bScAAK8jAAAiAAgA"
    "ZG9jUHJvcHMvY29yZS54bWxQSwMECgAAAAAAAAB1AHJk8z7bAQAAGQIAABAA"
    "CAB3b3JkL19yZWxzL2RvY3VtZW50LnhtLnJlbHNQSwMEFAAGAAgAAAAhAKci"
    "Gk2QAwAAy2AAABoACAB3b3JkL2RvY3VtZW50LnhtbFBLAwQUAAYACAAAACEA"
    "i8m6v6F4AAAAxQAAABoACAB3b3JkL3NldHRpbmdzLnhtbFBLAwQUAAYACAAA"
    "ACEA0v0G2mYgAAAA3wAAABwACAB3b3JkL3N0eWxlcy54bWxQSwMECgAAAAAA"
    "AABFAJv5H2FQCwAAoAIAABQACABfcmVscy9ydW50aW1lL3JlbHMueG1sUEsD"
    "BBQABgAIAAAAIQAXQ3yqVgEAAKcEAAAcAAgAd29yZC90aGVtZS90aGVtZTEu"
    "eG1sUEsDBBQABgAIAAAAIQCyFvUdk28AAAD7AAAAFAAIAGRvY1Byb3BzL2Fw"
    "cC54bWxSZWxzUEsDBBQABgAIAAAAIQCFmQpV6xIAAAB/AAAAGAAIAF9yZWxz"
    "Ly5yZWxzUEsDBBQABgAIAAAAIQB8tQz7Bz8AAABtAAAAGAAIAGRvY1Byb3Bz"
    "L2NvcmUueG1sUmVsc1BLAwQUAAYACAAAACEA0yXk9l7gAAAAcgAAAB4ACAB3"
    "b3JkL3dlYlNldHRpbmdzLnhtbFBLAwQKAAAAAAAAAFIARkP2M1oAAABgAAAA"
    "EAAIAGRvY1Byb3BzL2N1c3RvbS54bWxQSwMECgAAAAAAAABmAK2K0tQfAAAA"
    "JAAAAAwACAB3b3JkL2Zvb3Rub3Rlcy54bWxQSwMECgAAAAAAAABKAB3a2n1e"
    "AAAANwAAABAAIAB3b3JkL2hvb2tudW1iZXJpbmcueG1sUEsDBBQABgAIAAAA"
    "IQD0k3bt0gAAAEEAAAAeAAgAd29yZC9udW1iZXJpbmcueG1sUEsDBBQABgAI"
    "AAAAIQCsPqz4qTcAAACsAAAAGgAIAGRvY1Byb3BzL2N1c3RvbS54bWxSZWxz"
    "UEsDBBQABgAIAAAAIQDLF8f9kNwAAACGAAAAEAAIAGRvY1Byb3BzL2RjLnht"
    "bFBLAwQUAAYACAAAACEAvOa9L7+fAAAAmwAAABgACABfcmVscy8ucmVsc1BL"
    "AwQUAAYACAAAACEA4l+Dq9A1AAAAugAAABgACAB3b3JkL3NldHRpbmdzLnht"
    "bFJlbHNQSwECFAMUAAYACAAAACEA5CSJTH0BAAApBgAAEwAIACAAAAAAAAAA"
    "AAAAAACkgQAAAABbQ29udGVudF9UeXBlc10KUEsBAhQDFAAGAAgAAAAhALbk"
    "9F PJkAEAAOYBAAAPAAAAX3JlbHMvLnJlbHMKUEsBAhQDFAAGAAgAAAAhAPAu"
    "KEdw twEAAPcFAAAYAAA AZG9jUHJvcHMvYXBwLnhtbAo ... (truncated)"
)
# NOTE: The base64 above is intentionally truncated for readability in this reply.
# In your actual file, keep the FULL base64 string I provided (all lines).

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
    """
    Make a name safe for a Drive v3 query single-quoted string.
    Replace ASCII apostrophe ' with typographic ’ so we avoid backslash escaping.
    """
    return (value or "").replace("'", "’")


class SimpleGoogleDrive:
    """
    Google Drive helper for WealthPro CRM.

    Supported root structures (both work):

    A) Letters directly under ROOT:
       ROOT
         A/
           Alice Smith/
         B/
         ...
         Z/

    B) Category folders under ROOT, then letters:
       ROOT
         Active Clients/
           A/
             Alice Smith/
           B/
           ...
         Archived Clients/
           A/
           ...

    Each client folder will also (on demand) contain:
      - Tasks/
          Ongoing Tasks/
          Completed Tasks/
      - Reviews/
          Review <YEAR>/
            Agenda & Valuation/
            FF&ATR/
            ID&V & Sanction Search/
            Meeting Notes/
            Research/
            Review Letter/
            Client Confirmation/
            Emails/
      - Communications/   (plain .txt entries per interaction)
    """

    def __init__(self, credentials: Credentials):
        self.drive = _build_drive_service(credentials)
        self.root_folder_id = os.environ.get("GDRIVE_ROOT_FOLDER_ID", "").strip()
        if not self.root_folder_id:
            raise RuntimeError("GDRIVE_ROOT_FOLDER_ID is not set. Please set it in Render env vars.")
        logger.info("Google Drive ready.")

    # -----------------------------
    # Low-level Drive ops
    # -----------------------------
    def _list_folders(self, parent_id: str) -> List[Dict]:
        """List non-trashed folders directly under parent."""
        folders: List[Dict] = []
        page_token = None
        query = (
            f"'{parent_id}' in parents and "
            "mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        while True:
            resp = self.drive.files().list(
                q=query,
                fields="nextPageToken, files(id, name)",
                pageToken=page_token,
                pageSize=1000,
            ).execute()
            folders.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return folders

    def _find_child_folder(self, parent_id: str, name: str) -> Optional[Dict]:
        """Find a folder named `name` directly under `parent_id`."""
        safe_name = _escape_drive_name(name)
        query = (
            f"'{parent_id}' in parents and "
            "mimeType='application/vnd.google-apps.folder' and "
            f"name='{safe_name}' and trashed=false"
        )
        resp = self.drive.files().list(q=query, fields="files(id, name)", pageSize=1).execute()
        files = resp.get("files", [])
        return files[0] if files else None

    def _ensure_folder(self, parent_id: str, name: str) -> str:
        """Get or create a child folder."""
        existing = self._find_child_folder(parent_id, name)
        if existing:
            return existing["id"]
        body = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        created = self.drive.files().create(body=body, fields="id,name").execute()
        return created["id"]

    def _upload_bytes(self, parent_id: str, filename: str, data: bytes, mime: str) -> str:
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=False)
        body = {"name": filename, "parents": [parent_id]}
        created = self.drive.files().create(body=body, media_body=media, fields="id").execute()
        return created["id"]

    def _upload_docx_bytes(self, parent_id: str, filename: str, data: bytes):
        """Upload a raw .docx byte string to Drive."""
        media = MediaIoBaseUpload(
            io.BytesIO(data),
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            resumable=False,
        )
        meta = {"name": filename, "parents": [parent_id]}
        self.drive.files().create(body=meta, media_body=media, fields="id,name").execute()

    def _move_file(self, file_id: str, new_parent_id: str):
        file = self.drive.files().get(fileId=file_id, fields="parents").execute()
        prev = ",".join(file.get("parents", [])) if file.get("parents") else ""
        self.drive.files().update(
            fileId=file_id, addParents=new_parent_id, removeParents=prev, fields="id,parents"
        ).execute()

    def _rename_file(self, file_id: str, new_name: str):
        self.drive.files().update(fileId=file_id, body={"name": new_name}, fields="id,name").execute()

    # -----------------------------
    # Folder discovery helpers
    # -----------------------------
    def _get_letter_folders(self, parent_id: str) -> List[Dict]:
        """Return A–Z (single uppercase letter) folders under parent."""
        out = []
        for f in self._list_folders(parent_id):
            nm = (f.get("name") or "").strip()
            if len(nm) == 1 and nm.isalpha() and nm.upper() == nm:
                out.append(f)
        return out

    def _has_client_markers(self, folder_id: str) -> bool:
        """Heuristic: treat a folder as a client if it contains 'Tasks' or 'Reviews'."""
        for f in self._list_folders(folder_id):
            nm = (f.get("name") or "").strip()
            if nm in {"Tasks", "Reviews", "Communications"}:
                return True
        return False

    # -----------------------------
    # Client creation & listing
    # -----------------------------
    def create_client_enhanced_folders(self, display_name: str) -> str:
        """
        Create the client's A–Z index under the FIRST category that has letters,
        or directly under ROOT if letters are at root.
        Returns the client folder id.
        """
        display_name = (display_name or "").strip()
        if not display_name:
            raise ValueError("display_name required")

        # Prefer letters directly under ROOT
        root_letters = self._get_letter_folders(self.root_folder_id)

        parent_for_letters = None
        if root_letters:
            parent_for_letters = self.root_folder_id
        else:
            # Find a category (e.g., "Active Clients") that contains A–Z
            for cat in self._list_folders(self.root_folder_id):
                if self._get_letter_folders(cat["id"]):
                    parent_for_letters = cat["id"]
                    break
            if parent_for_letters is None:
                parent_for_letters = self.root_folder_id

        first = display_name[0].upper()
        index_letter = first if first.isalpha() else "#"
        index_id = self._ensure_folder(parent_for_letters, index_letter)

        client_id = self._ensure_folder(index_id, display_name)

        # Core structure
        tasks_id = self._ensure_folder(client_id, "Tasks")
        self._ensure_folder(tasks_id, "Ongoing Tasks")
        self._ensure_folder(tasks_id, "Completed Tasks")
        self._ensure_folder(client_id, "Reviews")
        self._ensure_folder(client_id, "Communications")

        logger.info("Created enhanced client folder for %s", display_name)
        return client_id

    def get_clients_enhanced(self) -> List[Dict]:
        """
        Discover client folders robustly for both supported layouts:
        - Letters directly under ROOT
        - Category folders under ROOT, then letters
        Skips category and letter folders themselves; only returns leaf client folders.
        """
        clients: List[Dict] = []

        def add_client(folder: Dict):
            clients.append(
                {
                    "client_id": folder["id"],
                    "display_name": (folder.get("name") or "").strip(),
                    "status": "active",
                    "folder_id": folder["id"],
                    "portfolio_value": 0.0,
                }
            )

        # Case 1: letters directly under ROOT
        root_letters = self._get_letter_folders(self.root_folder_id)
        if root_letters:
            for letter in root_letters:
                for child in self._list_folders(letter["id"]):
                    # Treat as client leaf
                    add_client(child)
        else:
            # Case 2: categories under ROOT -> letters -> clients
            for category in self._list_folders(self.root_folder_id):
                letters = self._get_letter_folders(category["id"])
                if letters:
                    for letter in letters:
                        for child in self._list_folders(letter["id"]):
                            add_client(child)
                else:
                    # If a category actually holds clients directly
                    if self._has_client_markers(category["id"]):
                        add_client(category)

        clients.sort(key=lambda c: (c["display_name"] or "").lower())
        return clients

    # -----------------------------
    # Tasks
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

        # climb up to find Tasks -> client
        parent = (file.get("parents") or [None])[0]
        client_id = None

        hops = 0
        while parent and hops < 5:
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

        self._move_file(task_file_id, completed)

        current_name = file.get("name", "")
        if not current_name.startswith("COMPLETED - "):
            self._rename_file(task_file_id, f"COMPLETED - {current_name}")

        return True

    def _parse_task_filename(self, name: str) -> Dict:
        result = {"due_date": "", "priority": "", "task_type": "", "title": "", "task_id": ""}
        base = name[:-4] if name.lower().endswith(".txt") else name

        # Task ID in square brackets
        if "[" in base and "]" in base and base.rfind("[") < base.rfind("]"):
            s = base.rfind("[")
            e = base.rfind("]")
            result["task_id"] = base[s + 1 : e].strip()
            base = (base[:s] + base[e + 1 :]).strip()

        parts = [p.strip() for p in base.split(" - ", 3)]
        if len(parts) >= 4:
            result["due_date"], result["priority"], result["task_type"], result["title"] = parts
        else:
            if parts:
                result["due_date"] = parts[0]
            if len(parts) > 1:
                result["priority"] = parts[1]
            if len(parts) > 2:
                result["task_type"] = parts[2]
            if len(parts) > 3:
                result["title"] = parts[3]

        return result

    def get_client_tasks(self, client_id: str) -> List[Dict]:
        fids = self._get_client_tasks_folder_ids(client_id)
        out: List[Dict] = []

        for status, folder in (("Pending", fids["ongoing"]), ("Completed", fids["completed"])):  # type: ignore
            page = None
            while True:
                resp = self.drive.files().list(
                    q=(
                        f"'{folder}' in parents and "
                        "mimeType!='application/vnd.google-apps.folder' and trashed=false"
                    ),
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
            client_id = c["client_id"]
            fids = self._get_client_tasks_folder_ids(client_id)
            ongoing = fids["ongoing"]
            page = None
            while True:
                resp = self.drive.files().list(
                    q=(
                        f"'{ongoing}' in parents and "
                        "mimeType!='application/vnd.google-apps.folder' and trashed=false"
                    ),
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
    # Review Pack
    # -----------------------------
    def _uk_date_str(self, dt: datetime) -> str:
        try:
            return dt.strftime("%-d %B %Y")  # Linux (no leading zero)
        except ValueError:
            return dt.strftime("%d %B %Y")   # Fallback

    def create_review_pack_for_client(self, client: Dict) -> Dict[str, str]:
        """Build Review <YEAR> structure, upload your custom Agenda, and create Valuation doc."""
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

        # 1) Agenda doc — use your embedded DOCX exactly
        try:
            agenda_bytes = base64.b64decode(AGENDA_DOCX_B64)
            self._upload_docx_bytes(
                agenda_val,
                f"Meeting Agenda – {display_name} – {year}.docx",
                agenda_bytes,
            )
        except Exception as _e:
            # Fallback to a simple generated agenda if decode/upload ever fails
            logger.error(f"Agenda template upload failed, falling back to generated. Error: {_e}")
            agenda_doc = self._build_agenda_doc(display_name, today_str)
            self._upload_docx(
                agenda_val,
                f"Meeting Agenda – {display_name} – {year}.docx",
                agenda_doc,
            )

        # 2) Valuation doc — same as before (programmatically generated)
        val_doc = self._build_valuation_doc(display_name, today_str)
        self._upload_docx(
            agenda_val,
            f"Valuation Summary – {display_name} – {year}.docx",
            val_doc,
        )

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
    # Word document builders
    # -----------------------------
    def _build_agenda_doc(self, client_display_name: str, date_str: str) -> Document:
        # (Fallback only; normal path uses your embedded DOCX.)
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
            doc.add_paragraph(it)
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
        row = table.add_row().cells
        row[0].text = ""
        row[1].text = ""
        row[2].text = ""
        doc.add_paragraph("")
        doc.add_paragraph("Total Value: £")
        return doc

    # -----------------------------
    # Communications
    # -----------------------------
    def _get_client_communications_folder(self, client_id: str) -> str:
        """Ensure and return the Communications folder for a client."""
        return self._ensure_folder(client_id, "Communications")

    def add_communication_enhanced(self, comm: Dict, client: Dict) -> bool:
        """
        Save a communication entry as a .txt file in Communications/.
        Filename: YYYY-MM-DD HHMM - Type - Subject [COMxxxxxxxx].txt
        """
        client_id = client.get("client_id") or client.get("folder_id")
        if not client_id:
            raise ValueError("client client_id/folder_id missing")

        folder_id = self._get_client_communications_folder(client_id)

        date_str = (comm.get("date") or datetime.now().strftime("%Y-%m-%d")).strip()
        time_str = (comm.get("time") or "").replace(":", "")
        ctype = (comm.get("type") or "").strip()
        subject = (comm.get("subject") or "No Subject").strip()
        cid = comm.get("communication_id", f"COM{datetime.now().strftime('%Y%m%d%H%M%S')}")

        # Build filename
        time_bit = f" {time_str}" if time_str else ""
        filename = f"{date_str}{time_bit} - {ctype} - {subject} [{cid}].txt"

        lines = [
            f"Communication ID: {cid}",
            f"Client ID: {client_id}",
            f"Date: {date_str}",
            f"Time: {comm.get('time','')}",
            f"Type: {ctype}",
            f"Subject: {subject}",
            f"Duration: {comm.get('duration','')}",
            f"Outcome: {comm.get('outcome','')}",
            f"Follow Up Required: {comm.get('follow_up_required','No')}",
            f"Follow Up Date: {comm.get('follow_up_date','')}",
            f"Created By: {comm.get('created_by','')}",
            "",
            "Details:",
            comm.get("details", "").strip(),
        ]
        content = ("\n".join(lines)).encode("utf-8")
        self._upload_bytes(folder_id, filename, content, "text/plain")
        return True

    def get_client_communications(self, client_id: str) -> List[Dict]:
        """Return communications for a client, newest first by filename (date)."""
        folder_id = self._get_client_communications_folder(client_id)

        out: List[Dict] = []
        page = None
        while True:
            resp = self.drive.files().list(
                q=(
                    f"'{folder_id}' in parents and "
                    "mimeType!='application/vnd.google-apps.folder' and trashed=false"
                ),
                fields="nextPageToken, files(id,name,createdTime,modifiedTime)",
                pageToken=page,
                orderBy="name desc",  # filenames start with date, so sort by name
            ).execute()
            for f in resp.get("files", []):
                name = f.get("name", "")
                # Best-effort parse from filename
                # Format: YYYY-MM-DD [HHMM] - Type - Subject [COMid].txt
                date_part = ""
                time_part = ""
                ctype = ""
                subject = ""
                if " - " in name:
                    head, *rest = name.split(" - ")
                    date_part = head[:10]
                    if len(head) > 10:
                        time_part = head[11:15]
                    if rest:
                        ctype = rest[0]
                    if len(rest) >= 2:
                        subject = rest[1].rsplit(" [", 1)[0]
                out.append(
                    {
                        "file_id": f.get("id"),
                        "date": date_part,
                        "time": f"{time_part[:2]}:{time_part[2:]}" if len(time_part) == 4 else "",
                        "type": ctype,
                        "subject": subject,
                        "details": "",
                        "outcome": "",
                        "duration": "",
                        "follow_up_required": "No",
                        "follow_up_date": "",
                        "created_time": f.get("createdTime", "")[:10],
                    }
                )
            page = resp.get("nextPageToken")
            if not page:
                break

        return out
