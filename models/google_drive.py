    # -----------------------------
    # Communications (files under client/Communications)
    # -----------------------------
    def _get_client_communications_folder(self, client_id: str) -> str:
        """Ensure Communications/ exists under the client folder and return its id."""
        comms_id = self._ensure_folder(client_id, "Communications")
        return comms_id

    def add_communication_enhanced(self, comm: Dict, client: Dict) -> bool:
        """
        Save a communication as a .txt file under client/Communications.
        Filename format:
          YYYY-MM-DD HHMM - TYPE - SUBJECT [COMMID].txt
        """
        client_id = client.get("client_id") or client.get("folder_id")
        if not client_id:
            raise ValueError("client client_id/folder_id missing")

        comms_id = self._get_client_communications_folder(client_id)

        # Fields expected by the route/template
        communication_id = comm.get("communication_id", f"COM{datetime.now().strftime('%Y%m%d%H%M%S')}")
        date = (comm.get("date") or datetime.today().strftime("%Y-%m-%d")).strip()
        time = (comm.get("time") or "").replace(":", "")[:4]  # HHMM for filename
        ctype = (comm.get("type") or "").strip()
        subject = (comm.get("subject") or "No Subject").strip()

        # Safer subject for filename
        safe_subject = subject.replace("/", "-").replace("\\", "-")

        # Filename
        hhmm = time if time else "0000"
        filename = f"{date} {hhmm} - {ctype} - {safe_subject} [{communication_id}].txt"

        lines = [
            f"Communication ID: {communication_id}",
            f"Client ID: {client_id}",
            f"Date: {comm.get('date', '')}",
            f"Time: {comm.get('time', '')}",
            f"Type: {ctype}",
            f"Subject: {subject}",
            f"Duration: {comm.get('duration', '')}",
            f"Follow Up Required: {comm.get('follow_up_required', 'No')}",
            f"Follow Up Date: {comm.get('follow_up_date', '')}",
            f"Created By: {comm.get('created_by', '')}",
            "",
            "Details:",
            comm.get("details", "") or "",
            "",
            "Outcome:",
            comm.get("outcome", "") or "",
        ]
        content = ("\n".join(lines)).encode("utf-8")
        self._upload_bytes(comms_id, filename, content, "text/plain")
        return True

    def _parse_comm_filename(self, name: str) -> Dict:
        """
        Parse filename: 'YYYY-MM-DD HHMM - TYPE - SUBJECT [COMMID].txt'
        Returns minimal fields for list views.
        """
        out = {
            "communication_id": "",
            "date": "",
            "time": "",
            "type": "",
            "subject": "",
        }
        base = name[:-4] if name.lower().endswith(".txt") else name

        # Extract [COMMID]
        if "[" in base and "]" in base and base.rfind("[") < base.rfind("]"):
            s = base.rfind("[")
            e = base.rfind("]")
            out["communication_id"] = base[s+1:e].strip()
            base = (base[:s] + base[e+1:]).strip()

        # Split first " - " -> left: "YYYY-MM-DD HHMM", remainder
        parts = [p.strip() for p in base.split(" - ", 2)]
        if len(parts) >= 1:
            # Date + HHMM
            dt_part = parts[0]
            if " " in dt_part:
                d, t = dt_part.split(" ", 1)
                out["date"] = d.strip()
                out["time"] = f"{t[:2]}:{t[2:4]}" if len(t) >= 4 else ""
            else:
                out["date"] = dt_part.strip()

        if len(parts) >= 2:
            out["type"] = parts[1]

        if len(parts) >= 3:
            out["subject"] = parts[2]

        return out

    def get_client_communications(self, client_id: str) -> List[Dict]:
        """
        List communications under client/Communications. We parse filenames for
        date/time/type/subject; createdTime used for fallback sorting.
        """
        comms_id = self._get_client_communications_folder(client_id)
        out: List[Dict] = []
        page = None
        while True:
            resp = self.drive.files().list(
                q=(f"'{comms_id}' in parents and "
                   "mimeType!='application/vnd.google-apps.folder' and trashed=false"),
                fields="nextPageToken, files(id,name,createdTime,modifiedTime)",
                pageToken=page,
                orderBy="name_natural",
            ).execute()
            for f in resp.get("files", []):
                meta = self._parse_comm_filename(f.get("name", ""))
                out.append({
                    "communication_id": meta.get("communication_id") or f.get("id"),
                    "client_id": client_id,
                    "date": meta.get("date") or (f.get("createdTime", "")[:10] or ""),
                    "time": meta.get("time") or "",
                    "type": meta.get("type") or "Other",
                    "subject": meta.get("subject") or "No Subject",
                    # Details/outcome aren’t parsed here (would require reading file content);
                    # templates handle missing fields gracefully.
                    "details": "",
                    "outcome": "",
                    "duration": "",
                    "follow_up_required": "No",
                    "follow_up_date": "",
                    "created_date": f.get("createdTime", "")[:10],
                })
            page = resp.get("nextPageToken")
            if not page:
                break

        # Sort newest first by date/time; fallback to createdTime order already “name_natural”
        def sort_key(c):
            try:
                return datetime.strptime(f"{c.get('date','')} {c.get('time','00:00')}", "%Y-%m-%d %H:%M")
            except Exception:
                return datetime(1970, 1, 1)

        out.sort(key=sort_key, reverse=True)
        return out
