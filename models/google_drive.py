# models/google_drive.py
import io
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials

from docx import Document

logger = logging.getLogger(__name__)

# ---------------------------
# Utility helpers
# ---------------------------

def _today_str(fmt="%Y-%m-%d"):
    return datetime.now().strftime(fmt)

def _this_year() -> int:
    return datetime.now().year

def _safe(s: Optional[str]) -> str:
    return s if s else ""

def _name_for_drive(first_name: str, surname: str) -> str:
    # Display as "Surname, First Name"
    return f"{_safe(surname).strip()}, {_safe(first_name).strip()}".strip(", ").strip()

def _ensure_fields(d: dict, keys: List[str]):
    for k in keys:
        d.setdefault(k, "")

# ---------------------------
# Google Drive / Docs wrapper
# ---------------------------

class SimpleGoogleDrive:
    """
    A minimal Drive/Sheets helper that matches the methods your routes use.
    - Creates the client folder structure (including Tasks/Ongoing Tasks, Tasks/Completed Tasks)
    - Adds & completes tasks (moves files to Completed Tasks + renames with "(Completed)")
    - Creates annual Review pack folder with subfolders and two .docx templates
    - Basic in-Drive "database" via a Clients sheet emulated with a JSON file (optional) or
      via a hidden metadata file inside the client folder. For simplicity here, we list clients
      by scanning Drive folders under a known root.
    """

    # ==== Change this to your real root folder ID (you already provided this earlier) ====
    ROOT_FOLDER_ID = "1DzljucgOkvm7rpfSCiYP1zlsOpwtbaWh"  # WealthPro - Clients Folders

    # Subfolder buckets for client status
    BUCKETS = {
        "active": "Active Clients",
        "prospect": "Prospects",
        "no_longer_client": "Former Clients",
        "deceased": "Deceased Clients",
    }

    # Standard client subfolders
    CLIENT_SUBFOLDERS = [
        "Reviews",
        "ID&V",
        "FF & ATR",
        "Research",
        "LOAs",
        "Suitability Letter",
        "Meeting Notes",
        "Terms of Business",
        "Policy Information",
        "Valuation",
        "Tasks",
        "Communications",
    ]

    # Tasks subfolders
    TASKS_ONGOING = "Ongoing Tasks"
    TASKS_COMPLETED = "Completed Tasks"

    # Review required subfolders (inside the year folder)
    REVIEW_YEAR_SUBS = [
        "Agenda & Valuation",
        "FF&ATR",
        "ID&V & Sanction Search",
        "Meeting Notes",
        "Research",
        "Review Letter",
        "Client Confirmation",
        "Emails",
        "Review Letter",  # user listed this twice; we keep once, but to honor request we’ll keep as is
    ]

    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        # IMPORTANT: cache_discovery=False keeps memory lighter on Render free tier
        self.drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        logger.info("Google Drive/Sheets setup complete.")

    # ------------- Low-level Drive helpers -------------

    def _find_folder(self, name: str, parent_id: str) -> Optional[str]:
        try:
            q = (
                f"mimeType='application/vnd.google-apps.folder' "
                f"and name='{name.replace(\"'\", \"\\'\")}' "
                f"and '{parent_id}' in parents and trashed=false"
            )
            resp = self.drive.files().list(q=q, fields="files(id, name)", pageSize=1).execute()
            files = resp.get("files", [])
            return files[0]["id"] if files else None
        except HttpError as e:
            logger.error(f"_find_folder error: {e}")
            return None

    def _create_folder(self, name: str, parent_id: str) -> Optional[str]:
        try:
            meta = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            }
            f = self.drive.files().create(body=meta, fields="id").execute()
            return f.get("id")
        except HttpError as e:
            logger.error(f"_create_folder error creating {name}: {e}")
            return None

    def _ensure_folder(self, name: str, parent_id: str) -> Optional[str]:
        fid = self._find_folder(name, parent_id)
        return fid or self._create_folder(name, parent_id)

    def _find_file_in_folder(self, name: str, parent_id: str) -> Optional[str]:
        try:
            q = (
                f"name='{name.replace(\"'\", \"\\'\")}' "
                f"and '{parent_id}' in parents and trashed=false"
            )
            resp = self.drive.files().list(q=q, fields="files(id, name)", pageSize=1).execute()
            files = resp.get("files", [])
            return files[0]["id"] if files else None
        except HttpError as e:
            logger.error(f"_find_file_in_folder error: {e}")
            return None

    def _upload_bytes(self, name: str, parent_id: str, buf: io.BytesIO, mimetype: str) -> Optional[str]:
        try:
            media = MediaIoBaseUpload(buf, mimetype=mimetype, resumable=False)
            meta = {"name": name, "parents": [parent_id]}
            f = self.drive.files().create(body=meta, media_body=media, fields="id").execute()
            return f.get("id")
        except HttpError as e:
            logger.error(f"_upload_bytes error {name}: {e}")
            return None

    def _rename_file(self, file_id: str, new_name: str) -> bool:
        try:
            self.drive.files().update(fileId=file_id, body={"name": new_name}).execute()
            return True
        except HttpError as e:
            logger.error(f"_rename_file error: {e}")
            return False

    def _move_file(self, file_id: str, old_parent_id: str, new_parent_id: str) -> bool:
        try:
            self.drive.files().update(
                fileId=file_id,
                addParents=new_parent_id,
                removeParents=old_parent_id,
                fields="id, parents",
            ).execute()
            return True
        except HttpError as e:
            logger.error(f"_move_file error: {e}")
            return False

    def _get_web_link(self, file_or_folder_id: str) -> str:
        try:
            f = self.drive.files().get(fileId=file_or_folder_id, fields="webViewLink").execute()
            return f.get("webViewLink", "")
        except HttpError as e:
            logger.error(f"_get_web_link error: {e}")
            return ""

    # ------------- Client listing helpers -------------

    def _ensure_status_buckets(self) -> Dict[str, str]:
        ids = {}
        for key, name in self.BUCKETS.items():
            fid = self._ensure_folder(name, self.ROOT_FOLDER_ID)
            if not fid:
                logger.error(f"Could not ensure bucket: {name}")
            ids[key] = fid
        return ids

    def get_clients_enhanced(self) -> List[dict]:
        """
        Lists clients by scanning status buckets under the ROOT_FOLDER_ID.
        Client folder names are "Surname, FirstName".
        We build a minimal client dict used by routes.
        """
        results = []
        buckets = self._ensure_status_buckets()

        for status_key, bucket_id in buckets.items():
            if not bucket_id:
                continue
            try:
                q = f"mimeType='application/vnd.google-apps.folder' and '{bucket_id}' in parents and trashed=false"
                resp = self.drive.files().list(q=q, fields="files(id, name, createdTime)", pageSize=200).execute()
                for f in resp.get("files", []):
                    display_name = f["name"]
                    # Construct a pseudo client_id from createdTime + hash
                    created = f.get("createdTime", "")[:19].replace(":", "").replace("-", "").replace("T", "")
                    client_id = f"WP{created}"
                    results.append({
                        "client_id": client_id,
                        "display_name": display_name,
                        "first_name": display_name.split(", ")[1] if ", " in display_name else display_name,
                        "surname": display_name.split(", ")[0] if ", " in display_name else display_name,
                        "email": "",
                        "phone": "",
                        "status": status_key,
                        "date_added": _today_str(),
                        "folder_id": f["id"],
                        "folder_url": self._get_web_link(f["id"]),
                        "portfolio_value": 0.0,
                        "notes": "",
                    })
            except HttpError as e:
                logger.error(f"get_clients_enhanced: listing error: {e}")

        # Sort by surname, display_name
        results.sort(key=lambda c: c["display_name"].lower())
        return results

    # ------------- Client CRUD used by routes -------------

    def create_client_folder_enhanced(self, first_name: str, surname: str, status: str) -> Optional[dict]:
        buckets = self._ensure_status_buckets()
        parent = buckets.get(status, buckets.get("prospect"))
        if not parent:
            return None

        display = _name_for_drive(first_name, surname)
        client_folder_id = self._ensure_folder(display, parent)
        if not client_folder_id:
            return None

        # Ensure standard subfolders
        for sub in self.CLIENT_SUBFOLDERS:
            self._ensure_folder(sub, client_folder_id)

        # Ensure Tasks substructure
        tasks_id = self._ensure_folder("Tasks", client_folder_id)
        if tasks_id:
            self._ensure_folder(self.TASKS_ONGOING, tasks_id)
            self._ensure_folder(self.TASKS_COMPLETED, tasks_id)

        logger.info(f"Created enhanced client folder for {display} in {status} section")

        return {
            "client_folder_id": client_folder_id,
            "display_name": display,
            "folder_url": self._get_web_link(client_folder_id),
        }

    def add_client(self, client_data: dict) -> bool:
        # In this implementation, folder creation is the “truth”. Nothing else to persist.
        # You can optionally store a small metadata file inside the client folder if needed.
        return True

    def update_client_status(self, client_id: str, new_status: str) -> bool:
        # We need to find the client by ID from our listing
        clients = self.get_clients_enhanced()
        client = next((c for c in clients if c["client_id"] == client_id), None)
        if not client:
            return False

        buckets = self._ensure_status_buckets()
        dest_parent = buckets.get(new_status)
        if not dest_parent:
            return False

        try:
            # Move the client folder from current parent to the new bucket
            # To do that we need its current parent(s)
            file_info = self.drive.files().get(fileId=client["folder_id"], fields="parents").execute()
            old_parents = ",".join(file_info.get("parents", []))
            if not old_parents:
                # If Drive doesn't return parents (shouldn't happen), fallback: just add new parent
                self.drive.files().update(
                    fileId=client["folder_id"],
                    addParents=dest_parent,
                    fields="id, parents"
                ).execute()
            else:
                self.drive.files().update(
                    fileId=client["folder_id"],
                    addParents=dest_parent,
                    removeParents=old_parents,
                    fields="id, parents"
                ).execute()
            return True
        except HttpError as e:
            logger.error(f"update_client_status error: {e}")
            return False

    def delete_client(self, client_id: str) -> bool:
        clients = self.get_clients_enhanced()
        client = next((c for c in clients if c["client_id"] == client_id), None)
        if not client:
            return False
        try:
            # Move to Trash (safe delete)
            self.drive.files().update(fileId=client["folder_id"], body={"trashed": True}).execute()
            return True
        except HttpError as e:
            logger.error(f"delete_client error: {e}")
            return False

    # Profile storage as a small JSON-ish docx or txt inside the client folder.
    # To keep things simple, we won't over-engineer — just a text file with key: value pairs.
    PROFILE_FILENAME = "_profile.txt"

    def update_client_profile(self, client_id: str, profile_data: dict) -> bool:
        client = self._client_by_id(client_id)
        if not client:
            return False

        buf = io.BytesIO()
        lines = [f"{k}: {v}" for k, v in profile_data.items()]
        buf.write("\n".join(lines).encode("utf-8"))
        buf.seek(0)

        # Overwrite if exists: remove then upload
        existing = self._find_file_in_folder(self.PROFILE_FILENAME, client["folder_id"])
        if existing:
            try:
                self.drive.files().delete(fileId=existing).execute()
            except HttpError:
                pass

        return bool(self._upload_bytes(self.PROFILE_FILENAME, client["folder_id"], buf, "text/plain"))

    def get_client_profile(self, client_id: str) -> Optional[dict]:
        client = self._client_by_id(client_id)
        if not client:
            return None

        file_id = self._find_file_in_folder(self.PROFILE_FILENAME, client["folder_id"])
        if not file_id:
            return None

        try:
            data = self.drive.files().get_media(fileId=file_id).execute()
            text = data.decode("utf-8", errors="ignore")
            out = {}
            for line in text.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    out[k.strip()] = v.strip()
            return out
        except HttpError as e:
            logger.error(f"get_client_profile error: {e}")
            return None

    def _client_by_id(self, client_id: str) -> Optional[dict]:
        clients = self.get_clients_enhanced()
        return next((c for c in clients if c["client_id"] == client_id), None)

    # ------------- Tasks -------------

    def _ensure_tasks_dirs(self, client_folder_id: str) -> (Optional[str], Optional[str]):
        tasks_id = self._ensure_folder("Tasks", client_folder_id)
        if not tasks_id:
            return None, None
        ongoing_id = self._ensure_folder(self.TASKS_ONGOING, tasks_id)
        completed_id = self._ensure_folder(self.TASKS_COMPLETED, tasks_id)
        return ongoing_id, completed_id

    def add_task_enhanced(self, task_data: dict, client: dict) -> bool:
        # Write a small task file to Ongoing Tasks
        ongoing_id, _ = self._ensure_tasks_dirs(client["folder_id"])
        if not ongoing_id:
            return False

        title = _safe(task_data.get("title"))
        due = _safe(task_data.get("due_date"))
        t_id = _safe(task_data.get("task_id"))
        body = []
        for k in ["task_id", "task_type", "title", "description", "due_date", "priority",
                  "status", "created_date", "completed_date", "time_spent", "client_id"]:
            body.append(f"{k}: {task_data.get(k, '')}")
        buf = io.BytesIO("\n".join(body).encode("utf-8"))
        buf.seek(0)

        name = f"{due} – {title} – {t_id}.txt" if due else f"{title} – {t_id}.txt"
        return bool(self._upload_bytes(name, ongoing_id, buf, "text/plain"))

    def complete_task(self, task_id: str) -> bool:
        """
        Look through all client folders → Tasks/Ongoing Tasks to find a file that contains the task_id,
        then move it to Tasks/Completed Tasks and rename with " (Completed)".
        """
        clients = self.get_clients_enhanced()
        for c in clients:
            ongoing_id, completed_id = self._ensure_tasks_dirs(c["folder_id"])
            if not ongoing_id or not completed_id:
                continue

            # List files in Ongoing
            try:
                q = f"'{ongoing_id}' in parents and trashed=false"
                resp = self.drive.files().list(q=q, fields="files(id, name)", pageSize=200).execute()
                for f in resp.get("files", []):
                    if task_id in f["name"]:
                        # Move
                        moved = self._move_file(f["id"], ongoing_id, completed_id)
                        # Rename
                        new_name = f["name"]
                        if "(Completed)" not in new_name:
                            # insert completion tag before extension
                            if "." in new_name:
                                base, ext = new_name.rsplit(".", 1)
                                new_name = f"{base} (Completed).{ext}"
                            else:
                                new_name = f"{new_name} (Completed)"
                        if moved:
                            self._rename_file(f["id"], new_name)
                            return True
            except HttpError as e:
                logger.error(f"complete_task list/move error: {e}")
        return False

    def get_upcoming_tasks(self, days: int = 30) -> List[dict]:
        """
        Scan all Ongoing Tasks; parse 'due_date' line inside each file.
        Return tasks due within the next `days` days, excluding completed ones.
        """
        limit = datetime.now() + timedelta(days=days)
        out = []
        clients = self.get_clients_enhanced()
        for c in clients:
            ongoing_id, _ = self._ensure_tasks_dirs(c["folder_id"])
            if not ongoing_id:
                continue
            try:
                q = f"'{ongoing_id}' in parents and trashed=false"
                resp = self.drive.files().list(q=q, fields="files(id, name)", pageSize=200).execute()
                for f in resp.get("files", []):
                    # Pull file content to parse fields
                    try:
                        data = self.drive.files().get_media(fileId=f["id"]).execute()
                        text = data.decode("utf-8", errors="ignore")
                        fields = {}
                        for line in text.splitlines():
                            if ":" in line:
                                k, v = line.split(":", 1)
                                fields[k.strip()] = v.strip()
                        _ensure_fields(fields, ["title", "due_date", "priority", "status", "task_type", "client_id"])
                        due_raw = fields.get("due_date", "")
                        due_dt = None
                        if due_raw:
                            try:
                                due_dt = datetime.strptime(due_raw, "%Y-%m-%d")
                            except ValueError:
                                pass
                        if due_dt and due_dt <= limit:
                            out.append({
                                "task_id": fields.get("task_id", ""),
                                "client_id": fields.get("client_id", ""),
                                "title": fields["title"],
                                "due_date": due_raw,
                                "priority": fields["priority"] or "Medium",
                                "status": fields["status"] or "Pending",
                                "task_type": fields["task_type"] or "Other",
                                "description": fields.get("description", ""),
                                "created_date": fields.get("created_date", ""),
                                "completed_date": fields.get("completed_date", ""),
                            })
                    except HttpError:
                        continue
            except HttpError as e:
                logger.error(f"get_upcoming_tasks error: {e}")
        # sort by due date
        out.sort(key=lambda t: t["due_date"] or "9999-12-31")
        return out

    def get_client_tasks(self, client_id: str) -> List[dict]:
        c = self._client_by_id(client_id)
        if not c:
            return []
        tasks = []
        ongoing_id, completed_id = self._ensure_tasks_dirs(c["folder_id"])
        for folder_id in [ongoing_id, completed_id]:
            if not folder_id:
                continue
            try:
                q = f"'{folder_id}' in parents and trashed=false"
                resp = self.drive.files().list(q=q, fields="files(id, name)", pageSize=200).execute()
                for f in resp.get("files", []):
                    try:
                        data = self.drive.files().get_media(fileId=f["id"]).execute()
                        text = data.decode("utf-8", errors="ignore")
                        fields = {}
                        for line in text.splitlines():
                            if ":" in line:
                                k, v = line.split(":", 1)
                                fields[k.strip()] = v.strip()
                        _ensure_fields(fields, ["title", "due_date", "priority", "status", "task_type"])
                        tasks.append({
                            "task_id": fields.get("task_id", ""),
                            "title": fields["title"],
                            "due_date": fields["due_date"],
                            "priority": fields["priority"] or "Medium",
                            "status": fields["status"] or ("Completed" if folder_id == completed_id else "Pending"),
                            "task_type": fields["task_type"] or "Other",
                            "description": fields.get("description", ""),
                            "created_date": fields.get("created_date", ""),
                            "completed_date": fields.get("completed_date", ""),
                        })
                    except HttpError:
                        continue
            except HttpError as e:
                logger.error(f"get_client_tasks error: {e}")
        # Order with ongoing first, then completed; within each by due_date
        tasks.sort(key=lambda t: (t["status"] != "Pending", t["due_date"] or "9999-12-31"))
        return tasks

    # ------------- Communications -------------

    def add_communication_enhanced(self, comm_data: dict, client: dict) -> bool:
        comms_id = self._ensure_folder("Communications", client["folder_id"])
        if not comms_id:
            return False
        # Store a simple txt log per entry
        doc_name = f"{comm_data.get('date','')}_{comm_data.get('time','')}_{comm_data.get('communication_id','')}.txt"
        lines = [f"{k}: {comm_data.get(k,'')}" for k in [
            "communication_id","client_id","date","time","type","subject","details",
            "outcome","duration","follow_up_required","follow_up_date","created_by"
        ]]
        buf = io.BytesIO("\n".join(lines).encode("utf-8"))
        buf.seek(0)
        return bool(self._upload_bytes(doc_name, comms_id, buf, "text/plain"))

    def get_client_communications(self, client_id: str) -> List[dict]:
        c = self._client_by_id(client_id)
        if not c:
            return []
        comms_id = self._ensure_folder("Communications", c["folder_id"])
        if not comms_id:
            return []
        out = []
        try:
            q = f"'{comms_id}' in parents and trashed=false"
            resp = self.drive.files().list(q=q, fields="files(id, name)", pageSize=200).execute()
            for f in resp.get("files", []):
                try:
                    data = self.drive.files().get_media(fileId=f["id"]).execute()
                    text = data.decode("utf-8", errors="ignore")
                    item = {}
                    for line in text.splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            item[k.strip()] = v.strip()
                    _ensure_fields(item, ["type", "date", "time", "subject", "details", "outcome",
                                          "duration", "follow_up_required", "follow_up_date"])
                    out.append(item)
                except HttpError:
                    continue
        except HttpError as e:
            logger.error(f"get_client_communications error: {e}")
        # latest first
        out.sort(key=lambda r: r.get("date", ""), reverse=True)
        return out

    # ------------- Fact Find -------------

    def save_fact_find_to_drive(self, client: dict, fact_find_data: dict) -> bool:
        ff_id = self._ensure_folder("FF & ATR", client["folder_id"])
        if not ff_id:
            return False
        name = f"Fact Find – {fact_find_data.get('fact_find_date', _today_str())}.txt"
        lines = [f"{k}: {v}" for k, v in fact_find_data.items()]
        buf = io.BytesIO("\n".join(lines).encode("utf-8"))
        buf.seek(0)
        return bool(self._upload_bytes(name, ff_id, buf, "text/plain"))

    # ------------- Review pack creation -------------

    def create_review_pack_for_client(self, client: dict) -> Optional[dict]:
        """
        Creates (if not present):
          Reviews/
          Reviews/Review {YEAR}/
          Reviews/Review {YEAR}/[listed subfolders]
          Reviews/Review {YEAR}/Agenda & Valuation/Meeting Agenda – {Client} – {YEAR}.docx
          Reviews/Review {YEAR}/Agenda & Valuation/Meeting Valuation – {Client} – {YEAR}.docx
        Returns dict with folder ids and file links.
        """
        client_folder_id = client["folder_id"]
        reviews_id = self._ensure_folder("Reviews", client_folder_id)
        if not reviews_id:
            return None

        year = _this_year()
        year_folder_name = f"Review {year}"
        year_id = self._ensure_folder(year_folder_name, reviews_id)
        if not year_id:
            return None

        # Ensure subfolders for the year
        sub_ids = {}
        for sub in self.REVIEW_YEAR_SUBS:
            sub_ids[sub] = self._ensure_folder(sub, year_id)

        # Ensure Agenda & Valuation has two .docx templates
        agenda_id = sub_ids.get("Agenda & Valuation")
        if agenda_id:
            # Create two docx files with client name + date
            client_name_first_last = f"{_safe(client.get('first_name'))} {_safe(client.get('surname'))}".strip()
            if not client_name_first_last:
                # Fallback: parse from display_name which is "Surname, First"
                disp = client.get("display_name", "")
                if ", " in disp:
                    s, f = disp.split(", ", 1)
                    client_name_first_last = f"{f} {s}".strip()
                else:
                    client_name_first_last = disp

            # Date format like “16 August 2025”
            pretty_date = datetime.now().strftime("%-d %B %Y") if hasattr(datetime.now(), "strftime") else _today_str("%d %B %Y")

            agenda_title = f"Meeting Agenda – {client_name_first_last} – {year}.docx"
            valuation_title = f"Meeting Valuation – {client_name_first_last} – {year}.docx"

            # Only create if not present
            if not self._find_file_in_folder(agenda_title, agenda_id):
                self._upload_bytes(
                    agenda_title, agenda_id,
                    self._generate_agenda_docx(client_name_first_last, pretty_date),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            if not self._find_file_in_folder(valuation_title, agenda_id):
                self._upload_bytes(
                    valuation_title, agenda_id,
                    self._generate_valuation_docx(client_name_first_last, pretty_date),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

        return {
            "reviews_folder_id": reviews_id,
            "year_folder_id": year_id,
            "subfolder_ids": sub_ids,
            "reviews_folder_url": self._get_web_link(reviews_id),
            "year_folder_url": self._get_web_link(year_id),
        }

    # ------------- .docx generators -------------

    def _generate_agenda_docx(self, client_name: str, pretty_date: str) -> io.BytesIO:
        """
        Build a simple agenda .docx. If you have a specific layout, we can adjust the sections later.
        """
        doc = Document()
        doc.add_heading("Client Review – Meeting Agenda", level=1)
        p = doc.add_paragraph()
        p.add_run("Client: ").bold = True
        p.add_run(client_name)
        p = doc.add_paragraph()
        p.add_run("Date: ").bold = True
        p.add_run(pretty_date)

        doc.add_paragraph("")
        doc.add_paragraph("Agenda")
        bul = doc.add_paragraph(style="List Bullet")
        bul.add_run("Welcome and purpose of meeting")
        bul2 = doc.add_paragraph(style="List Bullet")
        bul2.add_run("Review of current portfolio and performance")
        bul3 = doc.add_paragraph(style="List Bullet")
        bul3.add_run("Update on goals, circumstances, and risk profile")
        bul4 = doc.add_paragraph(style="List Bullet")
        bul4.add_run("Fees, charges, and any recommended changes")
        bul5 = doc.add_paragraph(style="List Bullet")
        bul5.add_run("Next steps & actions")

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf

    def _generate_valuation_docx(self, client_name: str, pretty_date: str) -> io.BytesIO:
        """
        Build a simple valuation .docx shell.
        """
        doc = Document()
        doc.add_heading("Client Review – Valuation Summary", level=1)
        p = doc.add_paragraph()
        p.add_run("Client: ").bold = True
        p.add_run(client_name)
        p = doc.add_paragraph()
        p.add_run("Date: ").bold = True
        p.add_run(pretty_date)

        doc.add_paragraph("")
        doc.add_paragraph("Plan(s) and Valuation")
        tbl = doc.add_table(rows=1, cols=4)
        hdr = tbl.rows[0].cells
        hdr[0].text = "Provider"
        hdr[1].text = "Policy / Plan"
        hdr[2].text = "Valuation Date"
        hdr[3].text = "Value (£)"
        # Leave rows empty for manual entry each year.

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf
