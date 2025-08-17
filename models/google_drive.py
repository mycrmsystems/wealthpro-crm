def get_clients_enhanced(self):
    """
    Return a flat list of client folders **inside** A–Z index folders (or directly under root),
    skipping the A–Z index folders themselves.

    Each client dict has at least:
      - client_id: Google Drive folder ID
      - display_name: folder name (e.g., "Smith, Jane")
      - status: "Active" (default)
      - folder_id: same as client_id
    """
    svc = self.drive  # Drive v3 service
    root_id = self.root_folder_id

    clients = []

    # 1) List immediate children of the root (these may be A–Z or client folders)
    page_token = None
    while True:
        resp = svc.files().list(
            q=(
                f"'{root_id}' in parents and "
                "mimeType='application/vnd.google-apps.folder' and "
                "trashed = false"
            ),
            fields="nextPageToken, files(id, name)",
            pageToken=page_token
        ).execute()
        root_children = resp.get("files", [])
        page_token = resp.get("nextPageToken")
        for item in root_children:
            name = (item.get("name") or "").strip()
            folder_id = item.get("id")

            # If this is an A–Z index folder (single upper-case letter), descend into it
            if len(name) == 1 and name.isalpha() and name.upper() == name:
                # List its children (actual client folders)
                sub_token = None
                while True:
                    sub = svc.files().list(
                        q=(
                            f"'{folder_id}' in parents and "
                            "mimeType='application/vnd.google-apps.folder' and "
                            "trashed = false"
                        ),
                        fields="nextPageToken, files(id, name)",
                        pageToken=sub_token
                    ).execute()
                    for child in sub.get("files", []):
                        child_name = (child.get("name") or "").strip()
                        clients.append({
                            "client_id": child.get("id"),
                            "display_name": child_name,
                            "status": "Active",
                            "folder_id": child.get("id"),
                        })
                    sub_token = sub.get("nextPageToken")
                    if not sub_token:
                        break
                continue

            # Not an A–Z letter folder → treat as a client folder directly under root
            clients.append({
                "client_id": folder_id,
                "display_name": name,
                "status": "Active",
                "folder_id": folder_id,
            })

        if not page_token:
            break

    # Sort by display_name for a nicer list
    clients.sort(key=lambda c: (c["display_name"] or "").lower())

    return clients
