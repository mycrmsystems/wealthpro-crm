# routes/auth.py
import logging
from datetime import datetime
from flask import (
    Blueprint, render_template, session, redirect, url_for, request, jsonify
)

# -----------------------------
# Blueprint setup
# -----------------------------
bp = Blueprint("auth", __name__)
auth_bp = bp  # export alias so app.py can import `auth_bp`

logger = logging.getLogger(__name__)

# -----------------------------
# Dashboard route
# -----------------------------
@bp.route("/")
def dashboard():
    # Render your main dashboard template
    return render_template("dashboard.html")

# -----------------------------
# Auth routes (simple examples)
# -----------------------------
@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["user"] = request.form.get("username", "advisor")
        return redirect(url_for("auth.dashboard"))
    return render_template("login.html")

@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

# -----------------------------
# Health endpoint for this bp
# -----------------------------
@bp.route("/auth/health")
def auth_health():
    return jsonify(
        status="ok",
        now=datetime.utcnow().isoformat() + "Z",
        service="auth"
    )
