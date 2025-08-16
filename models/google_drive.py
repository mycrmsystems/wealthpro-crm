# models/google_drive.py
import io
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


class SimpleGoogleDrive:
    """
    Thin wrapper around Google Drive (and optionally Sheets) for WealthPro CRM.

    Folder layout (per client):
      <ROOT>/
        <Client Display Name>/                         (client_root)
          meta.json                                    (client metadata)
          Communications/
            communications.json
          Tasks/
            Ongoing Tasks/
              <task_id>.txt
            Completed Tasks/
              COMPLETED - <task_id>.txt
            tasks.json                                 (all tasks list)
          Reviews/
            Review <YEAR>/
              Agenda & Valuation/
              FF&ATR/
              ID&V & Sanction Search/
              Meeting Notes/
              Research/
              Review Letter/
              Client Confirmation/
              Emails/
              Review Letter/       (duplicate kept per your original spec)
    """

    def __init__(self, credentials: Credentials):
        # Disable discovery caching to reduce memory and avoid cache warnings
        self.drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        # self.sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)  # if needed later

        # Base folder id must be set as an environment variable in Render
        import os

        self.root_folder_id = os.environ.get("GDRIVE_ROOT_FOLDER_ID")
        if not self.root_folder_id:
            raise RuntimeError(
                "GDRIVE_ROOT_FOLDER_ID is not set. Please set the Google Drive base folder ID in Render env vars."
            )

        logger.info("Google Drive/Sheets setup complete.")

    # ---------------------------------------------------------------------
    # Low-level helpers
    # ---------------------------------------------------------------------
    def _create_folder(self, name: str, parent_id: str) -> Optional[str]:
        """Create a folder under parent_id and return its file id."""
        try:
            file_metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            }
            f = self.drive.files().create(body=file_metadata, fields="id,name").execute()
            return f.get("id")
        except HttpError as e:
            logger.error(f"_create_folder error: {e}")
            return None

    def _find_folder(self, name: str, parent_id: str) -> Optional[str]:
        """Find a subfolder by name under parent_id (safe against quotes)."""
        try:
            safe_name = name.replace("'", "\\'")
            q = (
                "mimeType='application/vnd.google-apps.folder' "
                f"and name='{safe_name}' "
                f"and '{parent_id}' in parents and trashed=false"
            )
            resp = self.drive.files().list(q=q, fields="files(id,name)", pageSize=1).execute()
            files = resp.get("files", [])
            return files[0]["id"] if files else None
        except HttpError as e:
            logger.error(f"_find_folder error: {e}")
            return None

    def _find_or_create_folder(self, name: str, parent_id: str) -> Optional[str]:
        fid = self._find_folder(name, parent_id)
        if fid:
            return fid
        return self._create_folder(name, parent_id)

    def _find_file_in_folder(self, name: str, parent_id: str) -> Optional[str]:
        """Find a file by name under parent_id."""
        try:
            safe_name = name.replace("'", "\\'")
            q = f"name='{safe_name}' and '{parent_id}' in parents and trashed=false"
            resp = self.drive.files().list(q=q, fields="files(id,name)", pageSize=1).execute()
            files = resp.get("files", [])
            return files[0]["id"] if files else None
        except HttpError as e:
            logger.error(f"_find_file_in_folder error: {e}")
            return None

    def _upload_json(self, name: str, data: dict, parent_id: str) -> Optional[str]:
        """Create a JSON file under parent_id."""
        try:
            body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            media = MediaIoBaseUpload(io.BytesIO(body), mimetype="application/json", resumable=False)
            file_metadata = {"name": name, "parents": [parent_id]}
            f = self.drive.files().create(body=file_metadata, media_body=media, fields="id,name").execute()
            return f.get("id")
        except HttpError as e:
            logger.error(f"_upload_json error: {e}")
            return None

    def _update_json_file(self, file_id: str, data: dict) -> bool:
        """Overwrite an existing JSON file by id."""
        try:
            body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            media = MediaIoBaseUpload(io.BytesIO(body), mimetype="application/json", resumable=False)
            self.drive.files().update(fileId=file_id, media_body=media).execute()
            return True
        except HttpError as e:
            logger.error(f"_update_json_file error: {e}")
            return False

    def _download_json(self, file_id: str) -> Optional[dict]:
        """Download and parse JSON file."""
        try:
            request = self.drive.files().get_media(fileId=file_id)
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            buf.seek(0)
            return json.load(io.TextIOWrapper(buf, encoding="utf-8"))
        except HttpError as e:
            logger.error(f"_download_json error: {e}")
            return None
        except Exception as e:
            logger.error(f"_download_json parse error: {e}")
            return None

    def _upload_text(self, name: str, content: str, parent_id: str) -> Optional[str]:
        """Create a text/plain file under parent_id."""
        try:
            media = MediaIoBaseUpload(io.BytesIO(content.encode("utf-8")), mimetype="text/plain", resumable=False)
            file_metadata = {"name": name, "parents": [parent_id]}
            f = self.drive.files().create(body=file_metadata, media_body=media, fields="id,name,parents").execute()
            return f.get("id")
        except HttpError as e:
            logger.error(f"_upload_text error: {e}")
            return None

    def _move_file(self, file_id: str, new_parent_id: str) -> bool:
        """Move file to another folder (replace all parents)."""
        try:
            # First, get current parents
            file_obj = self.drive.files().get(fileId=file_id, fields="parents").execute()
            prev_parents = ",".join(file_obj.get("parents", []))
            self.drive.files().update(
                fileId=file_id, addParents=new_parent_id, removeParents=prev_parents, fields="id, parents"
            ).execute()
            return True
        except HttpError as e:
            logger.error(f"_move_file error: {e}")
            return False

    def _rename_file(self, file_id: str, new_name: str) -> bool:
        try:
            self.drive.files().update(fileId=file_id, body={"name": new_name}).execute()
            return True
        except HttpError as e:
            logger.error(f"_rename_file error: {e}")
            return False

    # ---------------------------------------------------------------------
    # Client helpers
    # ---------------------------------------------------------------------
    def _ensure_client_structure(self, display_name: str) -> Tuple[str, Dict[str, str]]:
        """
        Ensure client folder exists with required subfolders/files.
        Returns: (client_folder_id, subfolder_ids dict)
        """
        client_folder_id = self._find_or_create_folder(display_name, self.root_folder_id)

        # Communications
        comms_id = self._find_or_create_folder("Communications", client_folder_id)
        if self._find_file_in_folder("communications.json", comms_id) is None:
            self._upload_json("communications.json", [], comms_id)

        # Tasks + subfolders
        tasks_root_id = self._find_or_create_folder("Tasks", client_folder_id)
        ongoing_id = self._find_or_create_folder("Ongoing Tasks", tasks_root_id)
        completed_id = self._find_or_create_folder("Completed Tasks", tasks_root_id)
        if self._find_file_in_folder("tasks.json", tasks_root_id) is None:
            self._upload_json("tasks.json", [], tasks_root_id)

        # Reviews
        reviews_id = self._find_or_create_folder("Reviews", client_folder_id)

        # Meta
        if self._find_file_in_folder("meta.json", client_folder_id) is None:
            meta = {
                "display_name": display_name,
                "folder_id": client_folder_id,
                "created": datetime.utcnow().isoformat(),
            }
            self._upload_json("meta.json", meta, client_folder_id)

        return client_folder_id, {
            "communications": comms_id,
            "tasks_root": tasks_root_id,
            "tasks_ongoing": ongoing_id,
            "tasks_completed": completed_id,
            "reviews": reviews_id,
        }

    def _get_client_folder_by_id(self, client_id: str) -> Optional[str]:
        """
        We store client_id inside meta.json of each client folder. To find a client by id,
        scan direct children under root and read meta.json. (Kept simple; root usually holds only client folders.)
        """
        try:
            q = f"'{self.root_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            page_token = None
            while True:
                resp = self.drive.files().list(
                    q=q, fields="nextPageToken, files(id,name)", pageSize=100, pageToken=page_token
                ).execute()
                for it in resp.get("files", []):
                    # Read meta.json if present
                    meta_id = self._find_file_in_folder("meta.json", it["id"])
                    if meta_id:
                        meta = self._download_json(meta_id) or {}
                        if meta.get("client_id") == client_id:
                            return it["id"]
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
            return None
        except HttpError as e:
            logger.error(f"_get_client_folder_by_id error: {e}")
            return None

    def get_clients_enhanced(self) -> List[dict]:
        """
        Return client summaries from all folders under the root.
        A client is a folder under root with a 'meta.json'.
        """
        result: List[dict] = []
        try:
            q = f"'{self.root_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            page_token = None
            while True:
                resp = self.drive.files().list(
                    q=q, fields="nextPageToken, files(id,name)", pageSize=200, pageToken=page_token
                ).execute()
                for folder in resp.get("files", []):
                    meta_id = self._find_file_in_folder("meta.json", folder["id"])
                    if not meta_id:
                        # Not a client folder we manage
                        continue
                    meta = self._download_json(meta_id) or {}
                    display_name = meta.get("display_name") or folder["name"]
                    client_id = meta.get("client_id")
                    if not client_id:
                        # If missing, synthesize a stable id and save back
                        client_id = f"WP{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                        meta["client_id"] = client_id
                        self._update_json_file(meta_id, meta)
                    result.append(
                        {
                            "client_id": client_id,
                            "display_name": display_name,
                            "folder_id": folder["id"],
                        }
                    )
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
            return sorted(result, key=lambda x: x["display_name"].lower())
        except HttpError as e:
            logger.error(f"get_clients_enhanced error: {e}")
            return []

    # ---------------------------------------------------------------------
    # Communications
    # ---------------------------------------------------------------------
    def add_communication_enhanced(self, comm_data: dict, client: dict) -> bool:
        """
        Append a communication record to the client's communications.json.
        """
        try:
            client_folder_id, subs = self._ensure_client_structure(client["display_name"])
            comms_id = subs["communications"]
            json_id = self._find_file_in_folder("communications.json", comms_id)
            data = self._download_json(json_id) or []
            data.insert(0, comm_data)  # newest first
            return self._update_json_file(json_id, data)
        except Exception as e:
            logger.error(f"add_communication_enhanced error: {e}")
            return False

    def get_client_communications(self, client_id: str) -> List[dict]:
        """
        Read communications.json for a given client.
        """
        try:
            client_folder_id = self._get_client_folder_by_id(client_id)
            if not client_folder_id:
                return []
            comms_id = self._find_folder("Communications", client_folder_id)
            if not comms_id:
                return []
            json_id = self._find_file_in_folder("communications.json", comms_id)
            if not json_id:
                return []
            data = self._download_json(json_id) or []
            # Normalize keys for Jinja access via dot (optional)
            return [{k: v for k, v in item.items()} for item in data]
        except Exception as e:
            logger.error(f"get_client_communications error: {e}")
            return []

    # ---------------------------------------------------------------------
    # Tasks
    # ---------------------------------------------------------------------
    def add_task_enhanced(self, task_data: dict, client: dict) -> bool:
        """
        Add a task to tasks.json AND create/mirror a .txt file under Tasks/Ongoing Tasks.
        """
        try:
            client_folder_id, subs = self._ensure_client_structure(client["display_name"])
            tasks_root = subs["tasks_root"]
            ongoing_id = subs["tasks_ongoing"]

            # Save json
            json_id = self._find_file_in_folder("tasks.json", tasks_root)
            tasks = self._download_json(json_id) or []
            tasks.append(task_data)
            ok = self._update_json_file(json_id, tasks)
            if not ok:
                return False

            # Create a small task text file to appear in Drive
            due = task_data.get("due_date", "")
            title = task_data.get("title", "Task")
            task_id = task_data.get("task_id")
            filename = f"{due} - {title} [{task_id}].txt".strip()
            content = (
                f"Task ID: {task_id}\n"
                f"Client: {client['display_name']}\n"
                f"Type: {task_data.get('task_type','')}\n"
                f"Title: {title}\n"
                f"Due: {due}\n"
                f"Priority: {task_data.get('priority','')}\n"
                f"Status: {task_data.get('status','Pending')}\n"
                f"Created: {task_data.get('created_date','')}\n"
                f"Description:\n{task_data.get('description','')}\n"
            )
            self._upload_text(filename, content, ongoing_id)
            return True
        except Exception as e:
            logger.error(f"add_task_enhanced error: {e}")
            return False

    def get_client_tasks(self, client_id: str) -> List[dict]:
        """
        Return all tasks (pending + completed) for a client from tasks.json.
        """
        try:
            client_folder_id = self._get_client_folder_by_id(client_id)
            if not client_folder_id:
                return []
            tasks_root = self._find_folder("Tasks", client_folder_id)
            if not tasks_root:
                return []
            json_id = self._find_file_in_folder("tasks.json", tasks_root)
            if not json_id:
                return []
            tasks = self._download_json(json_id) or []
            # newest due date last; leave display sorting to templates if needed
            return tasks
        except Exception as e:
            logger.error(f"get_client_tasks error: {e}")
            return []

    def complete_task(self, task_id: str) -> bool:
        """
        Mark a task as Completed:
          - Update tasks.json status + completed_date
          - Move its .txt file from Ongoing Tasks to Completed Tasks and rename with 'COMPLETED - ' prefix
        """
        try:
            # Iterate through clients to locate the task (kept simple)
            clients = self.get_clients_enhanced()
            found = False
            for client in clients:
                client_folder_id = client["folder_id"]
                tasks_root = self._find_folder("Tasks", client_folder_id)
                if not tasks_root:
                    continue

                json_id = self._find_file_in_folder("tasks.json", tasks_root)
                if not json_id:
                    continue

                tasks = self._download_json(json_id) or []
                changed = False
                for t in tasks:
                    if t.get("task_id") == task_id:
                        if t.get("status") != "Completed":
                            t["status"] = "Completed"
                            t["completed_date"] = datetime.utcnow().strftime("%Y-%m-%d")
                            changed = True
                        found = True

                        # Move file in Drive
                        ongoing_id = self._find_folder("Ongoing Tasks", tasks_root)
                        completed_id = self._find_folder("Completed Tasks", tasks_root)
                        if ongoing_id and completed_id:
                            # Find the file by its pattern "[task_id]"
                            q = (
                                f"'{ongoing_id}' in parents and "
                                "mimeType!='application/vnd.google-apps.folder' and "
                                "trashed=false"
                            )
                            resp = self.drive.files().list(q=q, fields="files(id,name)").execute()
                            for f in resp.get("files", []):
                                if f"[{task_id}]" in f["name"]:
                                    # Move and rename
                                    self._move_file(f["id"], completed_id)
                                    new_name = f"COMPLETED - {f['name']}"
                                    self._rename_file(f["id"], new_name)
                                    break
                        break

                if changed:
                    self._update_json_file(json_id, tasks)
                if found:
                    break

            return found
        except Exception as e:
            logger.error(f"complete_task error: {e}")
            return False

    def get_upcoming_tasks(self, days: int = 30) -> List[dict]:
        """
        Gather all *Pending* tasks across all clients with due_date within the next `days`.
        """
        try:
            horizon = datetime.utcnow().date() + timedelta(days=days)
            today = datetime.utcnow().date()
            upcoming: List[dict] = []
            for client in self.get_clients_enhanced():
                client_tasks = self.get_client_tasks(client["client_id"])
                for t in client_tasks:
                    status = t.get("status", "Pending")
                    if status == "Completed":
                        continue
                    due_str = t.get("due_date")
                    if not due_str:
                        continue
                    try:
                        due = datetime.strptime(due_str, "%Y-%m-%d").date()
                    except ValueError:
                        # allow dd/mm/yyyy as fallback
                        try:
                            due = datetime.strptime(due_str, "%d/%m/%Y").date()
                        except ValueError:
                            continue
                    if today <= due <= horizon:
                        # include client_id so templates can join to display name
                        t_copy = dict(t)
                        t_copy["client_id"] = client["client_id"]
                        upcoming.append(t_copy)

            # Sort by due date then priority
            priority_order = {"High": 0, "Medium": 1, "Low": 2}
            upcoming.sort(
                key=lambda x: (
                    x.get("due_date") or "",
                    priority_order.get(x.get("priority", "Medium"), 1),
                )
            )
            return upcoming
        except Exception as e:
            logger.error(f"get_upcoming_tasks error: {e}")
            return []

    # ---------------------------------------------------------------------
    # Reviews pack creation (NEW)
    # ---------------------------------------------------------------------
    def create_review_pack_for_client(self, client: dict) -> bool:
        """
        Create/ensure the annual Review folder structure and its subfolders:
          Reviews/
            Review <YEAR>/
              Agenda & Valuation/
              FF&ATR/
              ID&V & Sanction Search/
              Meeting Notes/
              Research/
              Review Letter/
              Client Confirmation/
              Emails/
              Review Letter/  (duplicate name kept by request)
        """
        try:
            # Ensure client structure first (in case new client)
            client_folder_id, subs = self._ensure_client_structure(client["display_name"])
            reviews_id = subs["reviews"]

            # Year folder
            year_name = f"Review {datetime.now().year}"
            year_folder_id = self._find_or_create_folder(year_name, reviews_id)

            # Subfolders
            subfolders = [
                "Agenda & Valuation",
                "FF&ATR",
                "ID&V & Sanction Search",
                "Meeting Notes",
                "Research",
                "Review Letter",
                "Client Confirmation",
                "Emails",
                "Review Letter",  # duplicate kept intentionally
            ]
            for name in subfolders:
                self._find_or_create_folder(name, year_folder_id)

            logger.info(f"Review pack created/ensured for {client.get('display_name')}: {year_name}")
            return True
        except Exception as e:
            logger.error(f"create_review_pack_for_client error: {e}")
            return False
