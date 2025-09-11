# routes/products.py
from flask import Blueprint, render_template

products_bp = Blueprint("products", __name__, url_prefix="/products")

# Dummy product templates / companies / portfolios
_COMPANIES = ["Fidelity", "Vanguard", "Aviva"]
_PORTFOLIOS = ["Balanced", "Growth", "Income"]

@products_bp.route("", methods=["GET"])
def all_products():
    return render_template("simple_page.html",
                           title="Products",
                           subtitle="Master product list / per client summaries",
                           items=["(Products index here — AUM totals, filters, etc.)"])

@products_bp.route("/new-master", methods=["GET"])
def new_master():
    return render_template("simple_page.html",
                           title="New Product Template",
                           subtitle="Create reusable Company/Portfolio options",
                           items=[f"Companies: {', '.join(_COMPANIES)}",
                                  f"Portfolios: {', '.join(_PORTFOLIOS)}"])

# The per-client view is linked from /clients/<id>/products (handled in clients blueprint),
# but if you prefer, you can also expose /products/client/<id>
@products_bp.route("/client/<int:client_id>", methods=["GET"])
def products_for_client(client_id):
    return render_template("simple_page.html",
                           title=f"Products — Client #{client_id}",
                           subtitle="Shows product list, fees %, and per-product annual £",
                           items=["(Per-client product table with totals goes here)"])
routes/products.py → must export products_bp
