# routes/clients.py
from flask import Blueprint, render_template, url_for, request

bp = Blueprint("clients", __name__, url_prefix="/clients")

@bp.route("/", methods=["GET"])
def list_clients():
    # Placeholder list view; hook up to your DB later
    sample_clients = [
        {"id": 1, "name": "Jane Doe"},
        {"id": 2, "name": "John Smith"},
    ]
    return render_template(
        "simple_page.html",
        title="Clients",
        heading="Clients",
        description="Basic client list (placeholder).",
        back_url=url_for("auth.dashboard"),
        extra={"clients": sample_clients},
    )

@bp.route("/<int:client_id>", methods=["GET"])
def client_details(client_id):
    # Minimal details page; link out to client Products/Tasks/etc.
    links = [
        {"label": "Products", "href": url_for("products.list_products", client_id=client_id)},
        {"label": "Tasks", "href": url_for("tasks.list_tasks", client_id=client_id)},
        {"label": "Reviews", "href": url_for("reviews.list_reviews", client_id=client_id)},
        {"label": "Files", "href": url_for("files.client_files", client_id=client_id)},
    ]
    return render_template(
        "simple_page.html",
        title=f"Client #{client_id}",
        heading=f"Client #{client_id} details",
        description="Client overview (placeholder). Use the links below.",
        back_url=url_for("clients.list_clients"),
        extra={"links": links},
    )

# === Alias expected by app.py ===
clients_bp = bp
