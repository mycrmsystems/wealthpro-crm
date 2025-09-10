# routes/reviews.py
from flask import Blueprint, render_template

reviews_bp = Blueprint("reviews", __name__)

@reviews_bp.route("/clients/<int:client_id>/reviews", methods=["GET"])
def client_reviews(client_id):
    return render_template("simple_page.html",
                           title=f"Client Reviews — #{client_id}",
                           subtitle="Annual review pack area",
                           items=["(Generate agenda/valuation docs here)"])
