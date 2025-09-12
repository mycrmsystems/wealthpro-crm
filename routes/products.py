# routes/products.py
from flask import Blueprint, render_template, url_for

bp = Blueprint("products", __name__, url_prefix="/products")

# --- In-memory remembered values (placeholder) ---
REMEMBERED_COMPANIES = ["Acme Investments", "Alpha Pensions"]
REMEMBERED_PORTFOLIOS = ["Balanced", "Growth"]

def _sample_products(client_id):
    items = [
        {"id": 201, "name": "ISA",  "company": "Acme Investments", "portfolio": "Balanced", "value": 45000.00,  "fee_pct": 1.0},
        {"id": 202, "name": "SIPP", "company": "Alpha Pensions",   "portfolio": "Growth",   "value": 120000.00, "fee_pct": 0.5},
    ]
    for p in items:
        p["client_id"] = client_id
        p["annual_fee"] = round(p["value"] * (p["fee_pct"] / 100.0), 2)
    return items

# ---------- NEW: root Products page (no client_id needed) ----------
@bp.route("/", methods=["GET"])
def list_products():
    # This makes the dashboard link work without needing a client_id.
    links = [
        {"label": "Open Clients to choose a client", "href": url_for("clients.list_clients")},
    ]
    return render_template(
        "simple_page.html",
        title="Products",
        heading="Products",
        description="Choose a client to view their products.",
        back_url=url_for("auth.dashboard"),
        extra={"links": links, "companies": REMEMBERED_COMPANIES, "portfolios": REMEMBERED_PORTFOLIOS},
    )

# Client-specific Products
@bp.route("/client/<int:client_id>", methods=["GET"])
def client_products(client_id):
    items = _sample_products(client_id)
    total_value = round(sum(p["value"] for p in items), 2)
    total_fees  = round(sum(p["annual_fee"] for p in items), 2)

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

# === Alias expected by app.py ===
products_bp = bp
