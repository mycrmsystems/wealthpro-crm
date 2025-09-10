# routes/auth.py
import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template

bp = Blueprint("auth", __name__)

@bp.route("/")
def dashboard():
    # Dummy data so the dashboard renders safely
    active_clients = 3
    archived_clients = 1
    aum_total = "£1,250,000.00"
    products_count = 8
    upcoming_tasks = [
        {"id": 101, "client_name": "Alice Brown", "title": "ISA top-up", "due_date": (datetime.utcnow()+timedelta(days=3)).date().isoformat(), "status": "ongoing"},
        {"id": 102, "client_name": "Bob Smith", "title": "Pension review", "due_date": (datetime.utcnow()+timedelta(days=10)).date().isoformat(), "status": "ongoing"},
    ]
    return render_template(
        "dashboard.html",
        active_clients=active_clients,
        archived_clients=archived_clients,
        aum_total=aum_total,
        upcoming_tasks_count=len(upcoming_tasks),
        products_count=products_count,
        upcoming_tasks=upcoming_tasks,
        clients=[
            {"id": 1, "name": "Alice Brown", "email": "alice@example.com", "phone": "07123 456789", "archived": False},
            {"id": 2, "name": "Bob Smith", "email": "bob@example.com", "phone": "07111 222333", "archived": False},
            {"id": 3, "name": "Carol Jones", "email": "carol@example.com", "phone": "07000 999888", "archived": True},
        ],
        now=datetime.utcnow().year,
    )
