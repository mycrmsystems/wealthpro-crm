import os
import io
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials

# Optional: only needed if you later add Sheets features
# from googleapiclient.errors import HttpError

from docx import Document  # python-docx
from docx.shared import Pt, Inches

logger = logging.getLogger(__name__)


def _build_drive_service(credentials: Credentials):
    """
    Build the Google Drive v3 service with discovery cache disabled (saves memory).
    """
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _safe_date(date_str: str) -> Optional[datetime]:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None


class SimpleGoogleDrive:
    """
    Thin helper around Google Drive folders/files for WealthPro CRM.

    Folder layout expected under the provided GDRIVE_ROOT_FOLDER_ID:

      ROOT (GDRIVE_ROOT_FOLDER_ID)
        A
          <Client A>
            Tasks/
              Ongoing Tasks/
              Completed Tasks/
            Reviews/
              (Review YEAR created by review pack step)
            ...
        B
          <Client B>
        ...
        (Clients can also live directly under ROOT without A–Z)

    Tasks are stored as small .txt files inside:
      - Ongoing Tasks (status=Pending)
      - Completed Tasks (status=Completed)

    File name format for tasks:
      "YYYY-MM-DD - <Priority> - <TaskType> - <Title> [<TaskID>].txt"

    """

    def __init__(self, credentials: Credentials):
        self.drive = _build_drive_service(credentials)
        self.root_folder_id = os.environ.get("GDRIVE_ROOT_FOLDER_ID", "").strip()

        if not self.root_folder_id:
            # We raise a clear error that the app catches and displays.
            raise RuntimeError(
                "GDRIVE_ROOT_FOLDER_ID is not set. Please set it in Render env vars."
            )
        logger.info("Google Drive/Sheets setup complete.")

    # -----------------------------
    # Helpers: Folders & Files
    # -----------------------------
    def _list_folders(self, parent_id: str) -> List[Dict]:
        """List folders directly under parent_id."""
        svc = self.drive
        folders = []
        page_token = None
        query = (
            f"'{parent_id}' in parents and "
            "mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        while True:
            resp = svc.files().list(
                q=query,
                fields="nextPageToken, files(id, name)",
                pageToken=page_token,
            ).execute()
            folders.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return folders

    def _find_child_folder(self, parent_id: str, name: str) -> Optional[Dict]:
        """Find a folder with exact name under parent_id (not trashed)."""
        svc = self.drive
        # Use parameterized-style escaping by replacing single quotes within the name
        # with \u2019 (typographic apostrophe) to avoid query parse issues.
        # Drive v3 search is literal and OK with this simple defense.
        safe_name = (name or "").replace("'", "’")
        query = (
            f"'{parent_id}' in parents and "
            "mimeType='application/vnd.google-apps.folder' and "
            f"name='{safe_name}' and trashed=false"
        )
        resp = svc.files().list(
            q=query,
            fields="files(id, name)",
            pageSize=1
        ).execute()
        items = resp.get("files", [])
        return items[0] if items else None

    def _ensure_folder(self, parent_id: str, name: str) -> str:
        """Ensure a folder exists with name under parent_id. Return folder id."""
        existing = self._find_child_folder(parent_id, name)
        if existing:
            return existing["id"]

        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = self.drive.files().create(
            body=file_metadata, fields="id, name"
        ).execute()
        return folder["id"]

    def _upload_bytes(
        self,
        parent_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "text/plain",
    ) -> str:
        """Upload a bytes blob as a file to Drive. Return file id."""
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
        metadata = {"name": filename, "parents": [parent_id]}
        created = self.drive.files().create(
            body=metadata, media_body=media, fields="id, name"
        ).execute()
        return created["id"]

    def _move_file(self, file_id: str, new_parent_id: str):
        """Move a file to a new parent (removing all old parents)."""
        # Get current parents
        file = self.drive.files().get(
            fileId=file_id, fields="parents, name"
        ).execute()
        prev_parents = ",".join(file.get("parents", [])) if file.get("parents") else ""
        self.drive.files().update(
            fileId=file_id,
            addParents=new_parent_id,
            removeParents=prev_parents,
            fields="id, parents",
        ).execute()

    def _rename_file(self, file_id: str, new_name: str):
        self.drive.files().update(fileId=file_id, body={"name": new_name}, fields="id,name").execute()

    # -----------------------------
    # Clients
    # -----------------------------
    def create_client_enhanced_folders(self, display_name: str) -> str:
        """
        Create (if needed) the A–Z index folder and the core structure for one client.
        Returns the client folder id.
        """
        display_name = (display_name or "").strip()
        if not display_name:
            raise ValueError("display_name required")

        # A–Z index (first letter of display name, uppercase; non-alpha goes to '#')
        first = display_name[0].upper()
        index_letter = first if first.isalpha() else "#"
        idx_id = self._ensure_folder(self.root_folder_id, index_letter)

        # Client folder
        client_id = self._ensure_folder(idx_id, display_name)

        # Core subfolders
        tasks_id = self._ensure_folder(client_id, "Tasks")
        self._ensure_folder(tasks_id, "Ongoing Tasks")
        self._ensure_folder(tasks_id, "Completed Tasks")
        self._ensure_folder(client_id, "Reviews")

        # (Other subfolders can be added here if desired)
        logger.info("Created enhanced client folder for %s in active section", display_name)
        return client_id

    def get_clients_enhanced(self) -> List[Dict]:
        """
        Return a flat list of client folders **inside** A–Z index folders (or directly under root),
        skipping the A–Z index folders themselves.
        """
        svc = self.drive
        root_id = self.root_folder_id
        clients: List[Dict] = []

        page_token = None
        while True:
            resp = svc.files().list(
                q=(
                    f"'{root_id}' in parents and "
                    "mimeType='application/vnd.google-apps.folder' and trashed=false"
                ),
                fields="nextPageToken, files(id, name)",
                pageToken=page_token,
            ).execute()
            root_children = resp.get("files", [])
            page_token = resp.get("nextPageToken")

            for item in root_children:
                name = (item.get("name") or "").strip()
                fid = item.get("id")

                # If A–Z index, descend into it
                if len(name) == 1 and name.isalpha() and name.upper() == name:
                    sub_token = None
                    while True:
                        sub = svc.files().list(
                            q=(
                                f"'{fid}' in parents and "
                                "mimeType='application/vnd.google-apps.folder' and trashed=false"
                            ),
                            fields="nextPageToken, files(id, name)",
                            pageToken=sub_token,
                        ).execute()
                        for child in sub.get("files", []):
                            child_name = (child.get("name") or "").strip()
                            clients.append(
                                {
                                    "client_id": child.get("id"),
                                    "display_name": child_name,
                                    "status": "Active",
                                    "folder_id": child.get("id"),
                                }
                            )
                        sub_token = sub.get("nextPageToken")
                        if not sub_token:
                            break
                    continue

                # Otherwise, treat as a client directly under root
                clients.append(
                    {
                        "client_id": fid,
                        "display_name": name,
                        "status": "Active",
                        "folder_id": fid,
                    }
                )

            if not page_token:
                break

        clients.sort(key=lambda c: (c["display_name"] or "").lower())
        return clients

    # -----------------------------
    # Tasks
    # -----------------------------
    def _get_client_tasks_folder_ids(self, client_id: str) -> Dict[str, str]:
        """
        Return dict with keys: 'tasks', 'ongoing', 'completed' for this client.
        Creates them if missing.
        """
        tasks_id = self._ensure_folder(client_id, "Tasks")
        ongoing_id = self._ensure_folder(tasks_id, "Ongoing Tasks")
        completed_id = self._ensure_folder(tasks_id, "Completed Tasks")
        return {"tasks": tasks_id, "ongoing": ongoing_id, "completed": completed_id}

    def add_task_enhanced(self, task: Dict, client: Dict) -> bool:
        """
        Create a task file under Ongoing Tasks.
        task dict should contain:
          - task_id (string)
          - client_id
          - task_type
          - title
          - description
          - due_date (YYYY-MM-DD)
          - priority (Low/Medium/High)
          - status (Pending)
          - created_date
          - completed_date
          - time_spent (optional)
        """
        client_id = client.get("client_id") or client.get("folder_id")
        if not client_id:
            raise ValueError("client client_id/folder_id missing")

        fids = self._get_client_tasks_folder_ids(client_id)

        # Build filename
        due = task.get("due_date", "")
        pr = task.get("priority", "Medium")
        ttype = task.get("task_type", "")
        title = (task.get("title") or "").strip()
        tid = task.get("task_id", f"TSK{datetime.now().strftime('%Y%m%d%H%M%S')}")
        filename = f"{due} - {pr} - {ttype} - {title} [{tid}].txt"

        # File content
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

        self._upload_bytes(fids["ongoing"], filename, content, mime_type="text/plain")
        return True

    def complete_task(self, task_file_id: str) -> bool:
        """
        Move the task file to Completed Tasks and rename it with 'COMPLETED - ' prefix.
        """
        # Find file info and its client by looking up parents repeatedly (simple approach)
        file = self.drive.files().get(fileId=task_file_id, fields="id, name, parents").execute()
        if not file:
            return False

        # Try to locate the client's Completed Tasks by climbing up to "Tasks"
        parent_ids = file.get("parents", [])
        if not parent_ids:
            return False

        # Find client folder by traversing up until we see 'Tasks'
        # We make up to 4 hops to be safe: file -> Ongoing -> Tasks -> Client
        current_id = parent_ids[0]
        tasks_id = None
        client_id = None

        for _ in range(4):
            node = self.drive.files().get(fileId=current_id, fields="id,name,parents").execute()
            if not node:
                break
            name = node.get("name") or ""
            if name == "Tasks":
                tasks_id = node["id"]
                # its parent should be the client folder
                p = node.get("parents", [])
                if p:
                    client_id = p[0]
                break
            parents = node.get("parents", [])
            if parents:
                current_id = parents[0]
            else:
                break

        if not (tasks_id and client_id):
            # fallback: do nothing
            return False

        # Ensure Completed Tasks exists
        folders = self._get_client_tasks_folder_ids(client_id)
        completed_id = folders["completed"]

        # Move file
        self._move_file(task_file_id, completed_id)

        # Rename
        current_name = file["name"]
        if not current_name.startswith("COMPLETED - "):
            new_name = f"COMPLETED - {current_name}"
            self._rename_file(task_file_id, new_name)

        return True

    def _parse_task_filename(self, name: str) -> Dict:
        """
        Parse filename into task fields. Expected:
          YYYY-MM-DD - Priority - Type - Title [TaskID].txt
        """
        result = {
            "due_date": "",
            "priority": "",
            "task_type": "",
            "title": "",
            "task_id": "",
        }
        base = name
        if base.lower().endswith(".txt"):
            base = base[:-4]

        # Extract [TaskID]
        tid = ""
        if "[" in base and "]" in base and base.rfind("[") < base.rfind("]"):
            start = base.rfind("[")
            end = base.rfind("]")
            tid = base[start + 1 : end].strip()
            base = (base[:start] + base[end + 1 :]).strip()
        result["task_id"] = tid

        # Split the leading three ' - ' parts
        parts = [p.strip() for p in base.split(" - ", 3)]
        if len(parts) >= 4:
            result["due_date"], result["priority"], result["task_type"], result["title"] = parts
        else:
            # fallback: best-effort
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
        """
        Return all tasks for a client from Ongoing and Completed.
        """
        fids = self._get_client_tasks_folder_ids(client_id)
        out: List[Dict] = []

        for status, folder_id in (("Pending", fids["ongoing"]), ("Completed", fids["completed"])):
            page_token = None
            while True:
                resp = self.drive.files().list(
                    q=(
                        f"'{folder_id}' in parents and "
                        "mimeType!='application/vnd.google-apps.folder' and trashed=false"
                    ),
                    fields="nextPageToken, files(id, name, createdTime, modifiedTime)",
                    pageToken=page_token,
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
                            "description": "",  # could be fetched by downloading content if needed
                            "created_date": (f.get("createdTime", "")[:10] or ""),
                            "completed_date": (f.get("modifiedTime", "")[:10] if status == "Completed" else ""),
                            "time_spent": "",
                        }
                    )
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break

        # Sort by due_date (Pending first, then Completed)
        def sort_key(t):
            d = _safe_date(t.get("due_date", ""))
            return (0 if t["status"] == "Pending" else 1, d or datetime(1970, 1, 1))

        out.sort(key=sort_key)
        return out

    def get_upcoming_tasks(self, days: int = 30) -> List[Dict]:
        """
        Scan all client Ongoing Tasks folders and return tasks due within the next `days`.
        Keep tasks listed until marked Completed (i.e., only look in Ongoing).
        """
        upcoming: List[Dict] = []
        clients = self.get_clients_enhanced()
        today = datetime.today().date()
        horizon = today + timedelta(days=days)

        for c in clients:
            client_id = c["client_id"]
            fids = self._get_client_tasks_folder_ids(client_id)
            ongoing_id = fids["ongoing"]
            page_token = None
            while True:
                resp = self.drive.files().list(
                    q=(
                        f"'{ongoing_id}' in parents and "
                        "mimeType!='application/vnd.google-apps.folder' and trashed=false"
                    ),
                    fields="nextPageToken, files(id, name, createdTime)",
                    pageToken=page_token,
                    orderBy="name_natural",
                ).execute()
                for f in resp.get("files", []):
                    meta = self._parse_task_filename(f.get("name", ""))
                    dd = _safe_date(meta.get("due_date", ""))
                    if dd:
                        if today <= dd.date() <= horizon:
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
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break

        # Sort by due date
        upcoming.sort(key=lambda t: _safe_date(t["due_date"]) or datetime(1970, 1, 1))
        return upcoming

    # -----------------------------
    # Review Pack
    # -----------------------------
    def _get_reviews_folder(self, client_id: str) -> str:
        return self._ensure_folder(client_id, "Reviews")

    def _uk_date_str(self, dt: datetime) -> str:
        # Example: 16 August 2025
        return dt.strftime("%-d %B %Y") if hasattr(dt, "strftime") else ""

    def create_review_pack_for_client(self, client: Dict) -> Dict[str, str]:
        """
        Create "Review <YEAR>" with your specified subfolders,
        and drop two generated Word docs into "Agenda & Valuation".
        Returns dict with created IDs.
        """
        client_id = client.get("client_id") or client.get("folder_id")
        display_name = client.get("display_name") or "Client"
        if not client_id:
            raise ValueError("client client_id/folder_id missing")

        year = datetime.today().year
        reviews_root = self._get_reviews_folder(client_id)
        review_year_name = f"Review {year}"
        review_year_id = self._ensure_folder(reviews_root, review_year_name)

        # Subfolders you requested
        subfolders = [
            "Agenda & Valuation",
            "FF&ATR",
            "ID&V & Sanction Search",
            "Meeting Notes",
            "Research",
            "Review Letter",
            "Client Confirmation",
            "Emails",
            # "Review Letter" is already in list
        ]
        ids = {"review_year_id": review_year_id}
        for sf in subfolders:
            ids[sf] = self._ensure_folder(review_year_id, sf)

        # Generate docs into "Agenda & Valuation"
        agenda_val_id = ids["Agenda & Valuation"]
        today_str = self._uk_date_str(datetime.today())

        # (1) Meeting Agenda.docx
        agenda_doc = self._build_agenda_doc(display_name, today_str)
        self._upload_docx(agenda_val_id, f"Meeting Agenda – {display_name} – {year}.docx", agenda_doc)

        # (2) Valuation Summary.docx
        val_doc = self._build_valuation_doc(display_name, today_str)
        self._upload_docx(agenda_val_id, f"Valuation Summary – {display_name} – {year}.docx", val_doc)

        return ids

    def _upload_docx(self, parent_id: str, filename: str, document: Document):
        bio = io.BytesIO()
        document.save(bio)
        bio.seek(0)
        media = MediaIoBaseUpload(
            bio,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            resumable=False,
        )
        metadata = {"name": filename, "parents": [parent_id]}
        self.drive.files().create(
            body=metadata, media_body=media, fields="id,name"
        ).execute()

    # -----------------------------
    # Word doc builders
    # -----------------------------
    def _build_agenda_doc(self, client_display_name: str, date_str: str) -> Document:
        """
        Creates a simple Meeting Agenda Word doc with client name & date.
        """
        doc = Document()
        # Title
        p = doc.add_paragraph()
        run = p.add_run("Client Review Meeting Agenda")
        run.bold = True
        run.font.size = Pt(16)

        # Meta
        doc.add_paragraph(f"Client: {client_display_name}")
        doc.add_paragraph(f"Date: {date_str}")
        doc.add_paragraph("")

        # Outline
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
        """
        Creates a simple Valuation Summary Word doc with client name & date.
        """
        doc = Document()
        # Title
        p = doc.add_paragraph()
        run = p.add_run("Valuation Summary")
        run.bold = True
        run.font.size = Pt(16)

        # Meta
        doc.add_paragraph(f"Client: {client_display_name}")
        doc.add_paragraph(f"Date: {date_str}")
        doc.add_paragraph("")

        # Placeholder table
        table = doc.add_table(rows=1, cols=3)
        hdr = table.rows[0].cells
        hdr[0].text = "Plan / Account"
        hdr[1].text = "Provider"
        hdr[2].text = "Value (£)"

        # Example empty line for the adviser to fill in
        row = table.add_row().cells
        row[0].text = ""
        row[1].text = ""
        row[2].text = ""

        # Totals placeholder
        doc.add_paragraph("")
        doc.add_paragraph("Total Value: £")

        return doc
