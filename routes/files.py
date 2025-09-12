# routes/files.py
from flask import Blueprint, render_template, url_for

bp = Blueprint("files", __name__, url_prefix="/files")

@bp.route("/client/<int:client_id>", methods=["GET"])
def client_files(client_id):
    # Placeholder — wire to Google Drive later
    return render_template(
        "simple_page.html",
        title="Files",
        heading=f"Client #{client_id} — Files",
        description="Google Drive client folder integration (placeholder).",
        back_url=url_for("clients.client_details", client_id=client_id),
    )

# === Alias expected by app.py ===
files_bp = bp
