# routes/products.py
from flask import Blueprint, render_template, url_for, request

bp = Blueprint("products", __name__, url_prefix="/products")

# Remembered dropdown values (placeholder in-memory); replace with DB later
REMEMBERED_COMPANIES = ["Acme Investments", "Alpha Pensions"]
REMEMBERED_PORTFOLIOS = ["Balanced", "Growth"]

def _sample_products(client_id):
    # includes fee % and annual fee value as requested
    items = [
        {"id": 201, "name": "ISA", "company": "Acme Investments", "portfolio": "Balanced", "value": 45000.00, "fee_pct": 1.0},
        {"id": 202, "name": "SIPP", "company": "Alpha Pensions", "portfolio": "Growth", "value": 120000.00, "fee_pct": 0.5},
    ]
    for p in items:
        p["client_id"] = client_id
        p["annual_fee"] = round(p["value"] * (p["fee_pct"] / 100.0), 2)
    return items

@bp.route("/client/<int:client_id>", methods=["GET"])
def list_products(client_id):
    items = _sample_products(client_id)
    total_value = round(sum(p["value"] for p in items), 2)
    total_fees = round(sum(p["annual_fee"] for p in items), 2)
    return render_template(
        "simple_page.html",
        title="Products",
        heading=f"Client #{client_id} — Products",
        description="Products (formerly Portfolio). Totals show value and annual fees.",
        back_url=url_for("clients.client_details", client_id=client_id),
        extra={
            "products": items,
            "total_value": total_value,
            "total_fees": total_fees,
            "companies": REMEMBERED_COMPANIES,
            "portfolios": REMEMBERED_PORTFOLIOS,
        },
    )

@bp.route("/client/<int:client_id>/new", methods=["GET", "POST"])
def new_product(client_id):
    # Placeholder create screen with remembered dropdowns
    return render_template(
        "simple_page.html",
        title="New Product",
        heading=f"Add Product for Client #{client_id}",
        description="Dropdowns remember Companies and Portfolios (placeholder).",
        back_url=url_for("products.list_products", client_id=client_id),
        extra={"companies": REMEMBERED_COMPANIES, "portfolios": REMEMBERED_PORTFOLIOS},
    )

# === Alias expected by app.py ===
products_bp = bp
