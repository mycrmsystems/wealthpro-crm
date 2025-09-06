# routes/auth.py
import logging
from datetime import datetime
from flask import (
    Blueprint, render_template, session, redirect, url_for, request, jsonify, current_app
)
from jinja2 import TemplateNotFound

# -----------------------------
# Blueprint setup
# -----------------------------
bp = Blueprint("auth", __name__)
# Export alias expected by app.py
auth_bp = bp

logger = logging.getLogger(__name__)

# -----------------------------
# Helpers
# -----------------------------
def _render_dashboard():
    """
    Try dashboard.html, then index.html. If neither exists, return a minimal inline page.
    This prevents TemplateNotFound from crashing the root route.
    """
    try:
        return render_template("dashboard.html")
    except TemplateNotFound:
        pass

    try:
        return render_template("index.html")
    except TemplateNotFound:
        pass

    # Last-resort inline dashboard so app never 500s if templates are missing.
    return (
        """
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8">
            <title>WealthPro CRM – Dashboard</title>
            <style>
              body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 2rem; }
              .card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 1rem 1.25rem; max-width: 900px; }
              .muted { color: #6b7280; font-size: 0.9rem; }
              a.button { display:inline-block; padding:.6rem 1rem; border-radius:10px; text-decoration:none; border:1px solid #111827; }
              .row { display:flex; gap:.5rem; flex-wrap:wrap; margin-top: .75rem;}
            </style>
          </head>
          <body>
            <h1>WealthPro CRM</h1>
            <div class="card">
              <p class="muted">Template file <code>templates/dashboard.html</code> was not found.
              Add it back to restore your full UI.</p>
              <div class="row">
                <a class="button" href="/clients">Clients</a>
                <a class="button" href="/tasks">Tasks</a>
                <a class="button" href="/products">Products</a>
                <a class="button" href="/reviews">Reviews</a>
              </div>
            </div>
          </body>
        </html>
        """,
        200,
        {"Content-Type": "text/html; charset=utf-8"},
    )

# -----------------------------
# Routes
# -----------------------------
@bp.route("/")
def dashboard():
    return _render_dashboard()

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Very basic placeholder login (replace with real auth if you have it)
        session["user"] = request.form.get("username", "advisor")
        return redirect(url_for("auth.dashboard"))
    # Try to render a login template if present; otherwise a minimal inline form
    try:
        return render_template("login.html")
    except TemplateNotFound:
        return (
            """
            <!doctype html>
            <html>
              <head><meta charset="utf-8"><title>Login</title></head>
              <body>
                <h1>Login</h1>
                <form method="post">
                  <label>Username <input name="username" required></label>
                  <button type="submit">Login</button>
                </form>
              </body>
            </html>
            """,
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )

@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

@bp.route("/auth/health")
def auth_health():
    return jsonify(
        status="ok",
        now=datetime.utcnow().isoformat() + "Z",
        service="auth"
    )
