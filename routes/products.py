# routes/products.py

import logging
from flask import Blueprint, render_template_string, request, redirect, url_for, session
from google.oauth2.credentials import Credentials
from models.google_drive import SimpleGoogleDrive

logger = logging.getLogger(__name__)
products_bp = Blueprint("products", __name__)


def _require_creds():
    if "credentials" not in session:
        return None
    return Credentials(**session["credentials"])


@products_bp.route("/clients/<client_id>/products", methods=["GET", "POST"])
def client_products(client_id):
    """Add/list/edit client's products; remember companies/portfolios globally."""
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))

    try:
        drive = SimpleGoogleDrive(creds)
        # Find client for display name
        clients = drive.get_clients_enhanced()
        client = next((c for c in clients if c["client_id"] == client_id), None)
        if not client:
            return "Client not found", 404

        # Load products + catalog
        products = drive.get_client_products(client_id)
        catalog = drive.get_products_catalog()
        companies = catalog.get("companies", [])
        portfolios = catalog.get("portfolios", [])

        if request.method == "POST":
            # Add or edit a product
            mode = (request.form.get("mode") or "add").lower()
            idx = request.form.get("index", "")
            company = (request.form.get("company") or "").strip()
            portfolio = (request.form.get("portfolio") or "").strip()
            value = request.form.get("value") or "0"
            charge_pct = request.form.get("charge_pct") or "0"

            try:
                value_f = float(value)
            except Exception:
                value_f = 0.0
            try:
                charge_f = float(charge_pct)
            except Exception:
                charge_f = 0.0

            entry = {
                "company": company,
                "portfolio": portfolio,
                "value": value_f,
                "charge_pct": charge_f,
            }

            if mode == "edit" and idx.isdigit():
                i = int(idx)
                if 0 <= i < len(products):
                    products[i] = entry
            else:
                products.append(entry)

            # Update picklists
            drive.update_products_catalog(
                companies=[company] if company else [],
                portfolios=[portfolio] if portfolio else [],
            )
            # Save
            drive.save_client_products(client_id, products)
            return redirect(url_for("products.client_products", client_id=client_id))

        # Totals
        total_value = round(sum(p.get("value", 0) for p in products), 2)
        total_fee = round(sum((p.get("value", 0) * p.get("charge_pct", 0) / 100.0) for p in products), 2)

        return render_template_string(
            """
<!DOCTYPE html>
<html>
<head>
    <title>WealthPro CRM - Products</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: "Inter", sans-serif; }
        .gradient-wealth { background: linear-gradient(135deg, #1a365d 0%, #2563eb 100%); }
        .card { @apply bg-white rounded-lg shadow; }
        .label { @apply block text-sm font-medium text-gray-700 mb-1; }
        .input { @apply w-full px-3 py-2 border border-gray-300 rounded-md; }
        .select { @apply w-full px-3 py-2 border border-gray-300 rounded-md; }
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
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold">Products: {{ client.display_name }}</h1>
            <p class="text-gray-600 mt-2">Record and track investments & pensions. Saved to Google Drive → Products/products.json</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Add / Edit Product Form (styled like Communications) -->
            <div class="lg:col-span-1">
                <div class="card p-6">
                    <h3 class="text-lg font-semibold mb-4">Add / Edit Product</h3>
                    <form method="POST" class="space-y-4">
                        <input type="hidden" name="mode" id="modeField" value="add">
                        <input type="hidden" name="index" id="indexField" value="">

                        <div>
                            <label class="label">Company *</label>
                            <input list="companies" name="company" class="input" required placeholder="e.g., Aviva, Fidelity">
                            <datalist id="companies">
                                {% for c in companies %}
                                <option value="{{ c }}"></option>
                                {% endfor %}
                            </datalist>
                        </div>

                        <div>
                            <label class="label">Portfolio *</label>
                            <input list="portfolios" name="portfolio" class="input" required placeholder="e.g., Balanced, Growth">
                            <datalist id="portfolios">
                                {% for p in portfolios %}
                                <option value="{{ p }}"></option>
                                {% endfor %}
                            </datalist>
                        </div>

                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="label">Value (£) *</label>
                                <input type="number" step="0.01" name="value" class="input" required>
                            </div>
                            <div>
                                <label class="label">Charge (%)</label>
                                <input type="number" step="0.01" name="charge_pct" class="input" placeholder="e.g., 1.00">
                            </div>
                        </div>

                        <button class="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                            Save Product
                        </button>
                    </form>
                </div>
            </div>

            <!-- Products List -->
            <div class="lg:col-span-2">
                <div class="card">
                    <div class="p-6 border-b">
                        <h3 class="text-lg font-semibold">Current Products</h3>
                    </div>
                    <div class="p-6">
                        {% if products %}
                        <div class="overflow-x-auto">
                            <table class="min-w-full">
                                <thead>
                                    <tr class="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">
                                        <th class="px-4 py-2">Company</th>
                                        <th class="px-4 py-2">Portfolio</th>
                                        <th class="px-4 py-2">Value (£)</th>
                                        <th class="px-4 py-2">Charge (%)</th>
                                        <th class="px-4 py-2">Annual Revenue (£)</th>
                                        <th class="px-4 py-2">Actions</th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-gray-200 bg-white">
                                    {% for p in products %}
                                    <tr>
                                        <td class="px-4 py-2">{{ p.company }}</td>
                                        <td class="px-4 py-2">{{ p.portfolio }}</td>
                                        <td class="px-4 py-2">£{{ "{:,.2f}".format(p.value or 0) }}</td>
                                        <td class="px-4 py-2">{{ "{:.2f}".format(p.charge_pct or 0) }}%</td>
                                        <td class="px-4 py-2">
                                            £{{ "{:,.2f}".format((p.value or 0) * (p.charge_pct or 0) / 100.0) }}
                                        </td>
                                        <td class="px-4 py-2 space-x-2">
                                            <button onclick="editItem({{ loop.index0 }}, '{{ p.company|e }}', '{{ p.portfolio|e }}', '{{ p.value }}', '{{ p.charge_pct }}')" class="text-indigo-700 hover:text-indigo-900 text-sm">Edit</button>
                                            <a href="/clients/{{ client.client_id }}/products/{{ loop.index0 }}/delete" class="text-red-700 hover:text-red-900 text-sm">Delete</a>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                                <tfoot class="bg-gray-50">
                                    <tr>
                                        <td class="px-4 py-3 font-semibold" colspan="2">Totals</td>
                                        <td class="px-4 py-3 font-semibold">£{{ "{:,.2f}".format(total_value) }}</td>
                                        <td class="px-4 py-3"></td>
                                        <td class="px-4 py-3 font-semibold">£{{ "{:,.2f}".format(total_fee) }}</td>
                                        <td class="px-4 py-3"></td>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>
                        {% else %}
                        <p class="text-gray-500">No products recorded yet.</p>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>

        <div class="mt-8">
            <a href="/clients" class="bg-gray-600 text-white px-6 py-3 rounded-lg hover:bg-gray-700">
                Back to Clients
            </a>
        </div>
    </main>

    <script>
    function editItem(index, company, portfolio, value, charge) {
        document.getElementById('modeField').value = 'edit';
        document.getElementById('indexField').value = index;
        const form = document.forms[0];
        form.company.value = company;
        form.portfolio.value = portfolio;
        form.value.value = value;
        form.charge_pct.value = charge;
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    </script>
</body>
</html>
            """,
            client=client,
            products=products,
            companies=companies,
            portfolios=portfolios,
            total_value=total_value,
            total_fee=total_fee,
        )

    except Exception as e:
        logger.exception("Products error")
        return f"Error: {e}", 500


@products_bp.route("/clients/<client_id>/products/<int:index>/delete")
def delete_product(client_id, index: int):
    creds = _require_creds()
    if not creds:
        return redirect(url_for("auth.authorize"))
    try:
        drive = SimpleGoogleDrive(creds)
        products = drive.get_client_products(client_id)
        if 0 <= index < len(products):
            products.pop(index)
            drive.save_client_products(client_id, products)
        return redirect(url_for("products.client_products", client_id=client_id))
    except Exception as e:
        logger.exception("Delete product error")
        return f"Error: {e}", 500
