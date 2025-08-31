"""
WealthPro CRM - Products (Portfolio) Routes
- Per-client Products list with add/edit
- Persists each product as a JSON file under Google Drive: Client/Products/
- Remembers Companies and Portfolios by scanning existing product files (global options)
- Shows per-client totals (Value, Annual Fees)
"""

import logging
from datetime import datetime
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)
products_bp = Blueprint("products", __name__)

@products_bp.route("/clients/<client_id>/products", methods=["GET", "POST"])
def client_products(client_id):
    if "credentials" not in session:
        return redirect(url_for("auth.authorize"))
    try:
        creds = Credentials(**session["credentials"])
        drive = SimpleGoogleDrive(creds)

        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c["client_id"] == client_id), None)
        if not client:
            return "Client not found", 404

        # Add product
        if request.method == "POST":
            product = {
                "product_id": f"PRD{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "company": request.form.get("company", ""),
                "portfolio": request.form.get("portfolio", ""),
                "product_name": request.form.get("product_name", ""),
                "value": request.form.get("value", "0"),
                "charge_pct": request.form.get("charge_pct", "0"),
                "as_of": request.form.get("as_of", datetime.now().strftime("%Y-%m-%d")),
            }
            drive.add_product(product, client)
            return redirect(url_for("products.client_products", client_id=client_id))

        # Load list + global options
        products = drive.get_client_products(client_id)
        total_value = sum(p.get("value", 0.0) for p in products)
        total_fees = sum(p.get("annual_fee", 0.0) for p in products)
        companies, portfolios = drive.get_global_product_options()

        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Products</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: "Inter", sans-serif; }
        .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); }
        td, th { white-space: nowrap; }
    </style>
</head>
<body class="bg-gray-50">
    <nav class="gradient-wealth text-white shadow-lg">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex justify-between items-center h-16">
                <h1 class="text-xl font-bold">WealthPro CRM</h1>
                <div class="flex items-center space-x-6">
                    <a href="/" class="hover:text-blue-200">Dashboard</a>
                    <a href="/clients" class="hover:text-blue-200">Clients</a>
                    <a href="/tasks" class="hover:text-blue-200">Tasks</a>
                    <a href="#" class="text-white font-semibold">Products</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Products: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Manage client products. Saved to Google Drive → Products/</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Add Product Form -->
            <div class="lg:col-span-1">
                <div class="bg-white rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold mb-4">Add Product</h3>
                    <form method="POST" class="space-y-4">
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">As of</label>
                                <input type="date" name="as_of" value="{{ datetime.now().strftime('%Y-%m-%d') }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div></div>
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Company</label>
                            <input name="company" list="companies" placeholder="Type or select..." class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            <datalist id="companies">
                                {% for c in companies %}<option value="{{ c }}"></option>{% endfor %}
                            </datalist>
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Portfolio</label>
                            <input name="portfolio" list="portfolios" placeholder="Type or select..." class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            <datalist id="portfolios">
                                {% for p in portfolios %}<option value="{{ p }}"></option>{% endfor %}
                            </datalist>
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Product Name</label>
                            <input type="text" name="product_name" placeholder="e.g., SIPP / ISA / GIA / Bond..." class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>

                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Value (£)</label>
                                <input type="number" step="0.01" name="value" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Annual Charge %</label>
                                <input type="number" step="0.001" name="charge_pct" value="1.0" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                            </div>
                        </div>

                        <div class="bg-blue-50 p-3 rounded">
                            <p class="text-xs text-blue-700">💾 Saves to Google Drive: {{ client.display_name }} / Products</p>
                        </div>

                        <button type="submit" class="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                            Add Product
                        </button>
                    </form>
                </div>
            </div>

            <!-- Products table -->
            <div class="lg:col-span-2">
                <div class="bg-white rounded-lg shadow overflow-hidden">
                    <div class="p-6 border-b flex items-center justify-between">
                        <h3 class="text-lg font-semibold">Products</h3>
                        <div class="text-sm text-gray-600">Total: {{ products|length }}</div>
                    </div>
                    <div class="p-6 overflow-auto">
                        {% if products %}
                        <table class="min-w-full text-sm">
                            <thead class="bg-gray-50">
                                <tr>
                                    <th class="px-4 py-2 text-left">As of</th>
                                    <th class="px-4 py-2 text-left">Company</th>
                                    <th class="px-4 py-2 text-left">Portfolio</th>
                                    <th class="px-4 py-2 text-left">Product</th>
                                    <th class="px-4 py-2 text-right">Value (£)</th>
                                    <th class="px-4 py-2 text-right">Charge %</th>
                                    <th class="px-4 py-2 text-right">Annual Fee (£)</th>
                                    <th class="px-4 py-2 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y">
                                {% for p in products %}
                                <tr>
                                    <td class="px-4 py-2">{{ p.as_of }}</td>
                                    <td class="px-4 py-2">{{ p.company }}</td>
                                    <td class="px-4 py-2">{{ p.portfolio }}</td>
                                    <td class="px-4 py-2">{{ p.product_name }}</td>
                                    <td class="px-4 py-2 text-right">£{{ "{:,.2f}".format(p.value or 0) }}</td>
                                    <td class="px-4 py-2 text-right">{{ "{:.3f}".format(p.charge_pct or 0) }}%</td>
                                    <td class="px-4 py-2 text-right">£{{ "{:,.2f}".format(p.annual_fee or 0) }}</td>
                                    <td class="px-4 py-2 text-right">
                                        <a href="/clients/{{ client.client_id }}/products/{{ p.file_id }}/edit" class="text-indigo-700 hover:text-indigo-900 text-xs">Edit</a>
                                    </td>
                                </tr>
                                {% endfor %}
                                <!-- Totals row -->
                                <tr class="bg-gray-50 font-semibold">
                                    <td colspan="4" class="px-4 py-3 text-right">Totals:</td>
                                    <td class="px-4 py-3 text-right">£{{ "{:,.2f}".format(total_value) }}</td>
                                    <td class="px-4 py-3"></td>
                                    <td class="px-4 py-3 text-right">£{{ "{:,.2f}".format(total_fees) }}</td>
                                    <td class="px-4 py-3"></td>
                                </tr>
                            </tbody>
                        </table>
                        {% else %}
                        <div class="text-center py-10 text-gray-500">No products recorded yet.</div>
                        {% endif %}
                    </div>
                </div>

                <div class="mt-8">
                    <a href="/clients" class="bg-gray-600 text-white px-6 py-3 rounded-lg hover:bg-gray-700">Back to Clients</a>
                </div>
            </div>
        </div>
    </main>
</body>
</html>
        """, client=client, products=products, total_value=total_value, total_fees=total_fees,
           companies=companies, portfolios=portfolios, datetime=datetime)

    except Exception as e:
        logger.exception("Products error")
        return f"Error: {e}", 500


@products_bp.route("/clients/<client_id>/products/<file_id>/edit", methods=["GET", "POST"])
def edit_product(client_id, file_id):
    if "credentials" not in session:
        return redirect(url_for("auth.authorize"))
    try:
        creds = Credentials(**session["credentials"])
        drive = SimpleGoogleDrive(creds)

        # find client
        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c["client_id"] == client_id), None)
        if not client:
            return "Client not found", 404

        # load the product details
        prods = drive.get_client_products(client_id)
        prod = next((p for p in prods if p["file_id"] == file_id), None)
        if not prod:
            return "Product not found", 404

        if request.method == "POST":
            updated = {
                "product_id": prod.get("product_id", ""),
                "company": request.form.get("company", ""),
                "portfolio": request.form.get("portfolio", ""),
                "product_name": request.form.get("product_name", ""),
                "value": request.form.get("value", "0"),
                "charge_pct": request.form.get("charge_pct", "0"),
                "as_of": request.form.get("as_of", prod.get("as_of") or datetime.now().strftime("%Y-%m-%d")),
                "client_id": client_id,
            }
            drive.update_product(file_id, updated)
            return redirect(url_for("products.client_products", client_id=client_id))

        companies, portfolios = drive.get_global_product_options()

        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Edit Product</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <main class="max-w-2xl mx-auto px-6 py-8">
        <h1 class="text-2xl font-bold mb-6">Edit Product — {{ client.display_name }}</h1>
        <form method="POST" class="bg-white shadow rounded p-6 space-y-4">
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">As of</label>
                    <input type="date" name="as_of" value="{{ prod.as_of }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                </div>
                <div></div>
            </div>

            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Company</label>
                <input name="company" value="{{ prod.company }}" list="companies" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                <datalist id="companies">
                    {% for c in companies %}<option value="{{ c }}"></option>{% endfor %}
                </datalist>
            </div>

            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Portfolio</label>
                <input name="portfolio" value="{{ prod.portfolio }}" list="portfolios" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                <datalist id="portfolios">
                    {% for p in portfolios %}<option value="{{ p }}"></option>{% endfor %}
                </datalist>
            </div>

            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Product Name</label>
                <input type="text" name="product_name" value="{{ prod.product_name }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
            </div>

            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Value (£)</label>
                    <input type="number" step="0.01" name="value" value="{{ prod.value }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Annual Charge %</label>
                    <input type="number" step="0.001" name="charge_pct" value="{{ prod.charge_pct }}" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                </div>
            </div>

            <div class="flex justify-between pt-2">
                <a href="/clients/{{ client.client_id }}/products" class="px-6 py-2 border rounded text-gray-700 hover:bg-gray-50">Cancel</a>
                <button class="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Save Changes</button>
            </div>
        </form>
    </main>
</body>
</html>
        """, client=client, prod=prod, companies=companies, portfolios=portfolios)

    except Exception as e:
        logger.exception("Edit product error")
        return f"Error: {e}", 500


@products_bp.route("/products/options")
def products_options():
    """Small helper view to inspect global company/portfolio options."""
    if "credentials" not in session:
        return redirect(url_for("auth.authorize"))
    try:
        creds = Credentials(**session["credentials"])
        drive = SimpleGoogleDrive(creds)
        companies, portfolios = drive.get_global_product_options()
        return {
            "companies": companies,
            "portfolios": portfolios,
            "count_companies": len(companies),
            "count_portfolios": len(portfolios),
        }
    except Exception as e:
        logger.exception("Options error")
        return {"error": str(e)}, 500
