# routes/clients.py
from flask import Blueprint, render_template, request

clients_bp = Blueprint("clients", __name__, url_prefix="/clients")

# In-memory sample data
_CLIENTS = [
    {"id": 1, "name": "Alice Brown", "email": "alice@example.com", "phone": "07123 456789", "archived": False},
    {"id": 2, "name": "Bob Smith", "email": "bob@example.com", "phone": "07111 222333", "archived": False},
    {"id": 3, "name": "Carol Jones", "email": "carol@example.com", "phone": "07000 999888", "archived": True},
]

def _find(cid):
    return next((c for c in _CLIENTS if c["id"] == cid), None)

@clients_bp.route("", methods=["GET"])
def list_clients():
    q = request.args.get("q", "").strip().lower()
    data = _CLIENTS
    if q:
        data = [c for c in _CLIENTS if q in c["name"].lower()]
    return render_template("simple_page.html",
                           title="Clients",
                           subtitle="List of clients",
                           items=[f'{c["id"]}: {c["name"]} ({"" if not c["archived"] else "Archived"})' for c in data])

@clients_bp.route("/new", methods=["GET"])
def new_client():
    return render_template("simple_page.html",
                           title="New Client",
                           subtitle="(Form goes here)",
                           items=[])

@clients_bp.route("/archived", methods=["GET"])
def archived():
    data = [c for c in _CLIENTS if c["archived"]]
    return render_template("simple_page.html",
                           title="Archived Clients",
                           subtitle="Restore when needed",
                           items=[f'{c["id"]}: {c["name"]}' for c in data])

@clients_bp.route("/<int:client_id>/details", methods=["GET"])
def details(client_id):
    c = _find(client_id)
    return render_template("simple_page.html",
                           title=f"Client Details — {c['name'] if c else 'Unknown'}",
                           subtitle="Basic profile and summary",
                           items=[str(c)] if c else ["Client not found"])

@clients_bp.route("/<int:client_id>/products", methods=["GET"])
def products_link(client_id):
    # This links through to Products view but we render a simple page for now.
    return render_template("simple_page.html",
                           title=f"Products for Client #{client_id}",
                           subtitle="Per-client products view",
                           items=["(Products table will render here)"])

@clients_bp.route("/<int:client_id>/tasks", methods=["GET"])
def tasks_link(client_id):
    return render_template("simple_page.html",
                           title=f"Tasks for Client #{client_id}",
                           subtitle="Open/complete tasks shown here",
                           items=["(Tasks list will render here)"])

@clients_bp.route("/<int:client_id>/reviews", methods=["GET"])
def reviews_link(client_id):
    return render_template("simple_page.html",
                           title=f"Reviews for Client #{client_id}",
                           subtitle="Annual/periodic review pack",
                           items=["(Review documents and dates go here)"])

@clients_bp.route("/<int:client_id>/folders", methods=["GET"])
def folders_link(client_id):
    return render_template("simple_page.html",
                           title=f"Google Drive Folders — Client #{client_id}",
                           subtitle="Link to client’s Drive folder",
                           items=["(Drive folder link/status appears here)"])

@clients_bp.route("/<int:client_id>/archive", methods=["GET"])
def archive(client_id):
    c = _find(client_id)
    if c: c["archived"] = True
    return render_template("simple_page.html",
                           title="Client Archived",
                           subtitle=f"Client #{client_id}",
                           items=[str(c)] if c else ["Client not found"])

@clients_bp.route("/<int:client_id>/restore", methods=["GET"])
def restore(client_id):
    c = _find(client_id)
    if c: c["archived"] = False
    return render_template("simple_page.html",
                           title="Client Restored",
                           subtitle=f"Client #{client_id}",
                           items=[str(c)] if c else ["Client not found"])

@clients_bp.route("/<int:client_id>/delete-soft", methods=["GET"])
def delete_soft(client_id):
    return render_template("simple_page.html",
                           title="Soft Delete (CRM only)",
                           subtitle=f"Client #{client_id}",
                           items=["(Implement soft delete in DB/Drive sync as needed)"])
routes/clients.py → must export clients_bp
