# routes/auth.py
import os
from flask import Blueprint, render_template, redirect, url_for

bp = Blueprint("auth", __name__)  # generic export
auth_bp = bp                      # explicit name expected by app.py (alias)

@bp.route("/", methods=["GET"])
def dashboard():
    """
    Root route -> Dashboard.
    Uses templates/dashboard.html. If you have brand CSS in static/style.css,
    that will still apply (we don't touch your styles here).
    """
    return render_template("dashboard.html")

# --- Optional convenience routes (do not remove features) ---

@bp.route("/login")
def login():
    # If you have OAuth, integrate here. For now, just go to dashboard.
    return redirect(url_for("auth.dashboard"))

@bp.route("/logout")
def logout():
    # Clear session if you use it. Keep simple redirect.
    return redirect(url_for("auth.dashboard"))
