# routes/auth.py
import logging
from datetime import datetime
from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify

bp = Blueprint("auth", __name__)
auth_bp = bp  # alias expected by app.py
logger = logging.getLogger(__name__)

@bp.route("/")
def dashboard():
    # Render the dashboard template (provided below).
    # We don't pass data here so the template must be resilient with defaults.
    return render_template("dashboard.html")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["user"] = request.form.get("username", "advisor")
        return redirect(url_for("auth.dashboard"))
    return render_template("login.html") if False else """
    <!doctype html><meta charset="utf-8"><title>Login</title>
    <h1>Login</h1>
    <form method="post">
      <label>Username <input name="username" required></label>
      <button type="submit">Login</button>
    </form>
    """

@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.dashboard"))

@bp.route("/auth/health")
def auth_health():
    return jsonify(status="ok", now=datetime.utcnow().isoformat() + "Z", service="auth")
