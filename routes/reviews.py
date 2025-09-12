# routes/reviews.py
from flask import Blueprint, render_template, url_for

bp = Blueprint("reviews", __name__, url_prefix="/reviews")

@bp.route("/", methods=["GET"])
def index():
    return render_template(
        "simple_page.html",
        title="Reviews",
        heading="Reviews",
        description="Annual reviews overview (placeholder).",
        back_url=url_for("auth.dashboard"),
    )

@bp.route("/client/<int:client_id>", methods=["GET"])
def list_reviews(client_id):
    return render_template(
        "simple_page.html",
        title="Client Reviews",
        heading=f"Client #{client_id} — Reviews",
        description="Client-specific reviews (placeholder).",
        back_url=url_for("clients.client_details", client_id=client_id),
    )

# === Alias expected by app.py ===
reviews_bp = bp
