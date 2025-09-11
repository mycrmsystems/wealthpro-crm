# routes/files.py
from flask import Blueprint, render_template

files_bp = Blueprint("files", __name__)

@files_bp.route("/drive/connect", methods=["GET"])
def drive_connect():
    return render_template(
        "simple_page.html",
        title="Google Drive",
        subtitle="Connect your Drive account",
        items=["(OAuth flow goes here)"],
    )

@files_bp.route("/drive/check", methods=["GET"])
def drive_check():
    return render_template(
        "simple_page.html",
        title="Drive Status",
        subtitle="Connection / folders status",
        items=["(Connection OK / missing scopes / etc.)"],
    )
