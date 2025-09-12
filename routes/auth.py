# routes/auth.py
import os
from flask import Blueprint, render_template, redirect, url_for, session, request, flash

bp = Blueprint("auth", __name__)

@bp.route("/", methods=["GET"])
def dashboard():
    # Renders your main dashboard template
    return render_template("dashboard.html")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Dummy login to keep app working; replace with your logic anytime
        session["user"] = request.form.get("username") or "advisor"
        flash("Logged in.", "success")
        return redirect(url_for("auth.dashboard"))
    return render_template(
        "simple_page.html",
        title="Login",
        heading="Login",
        description="Enter your credentials (placeholder).",
        back_url=url_for("auth.dashboard"),
    )

@bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("auth.dashboard"))

# === Alias expected by app.py ===
auth_bp = bp
