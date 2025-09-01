# app.py
import os
import logging
from datetime import datetime
from flask import Flask, jsonify

# -----------------------------
# Create app
# -----------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")

# Secret key (required for session/OAuth)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# Reasonable defaults
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB uploads
app.config["JSON_SORT_KEYS"] = False

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(levelname)s:%(name)s:%(message)s",
)
logger = logging.getLogger(__name__)

# -----------------------------
# Jinja helpers (optional)
# -----------------------------
def _fmt_currency(value):
    try:
        return f"£{float(value):,.2f}"
    except Exception:
        return value

def _fmt_date(value, fmt="%Y-%m-%d"):
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime(fmt)
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").strftime(fmt)
    except Exception:
        return str(value)

app.jinja_env.filters["currency"] = _fmt_currency
app.jinja_env.filters["datefmt"] = _fmt_date

# -----------------------------
# Blueprints
# -----------------------------
# NOTE:
# - We import and register *only*; routes remain defined in their own files.
# - Do not change any route paths here—this preserves existing behavior.

# Auth / Dashboard
from routes.auth import bp as auth_bp
app.register_blueprint(auth_bp)

# Clients (profile, folders link, archive/restore, details, etc.)
try:
    from routes.clients import clients_bp
    app.register_blueprint(clients_bp)
except Exception as e:
    logger.warning(f"clients blueprint not loaded: {e}")

# Tasks (ongoing/completed, CRUD)
try:
    from routes.tasks import tasks_bp
    app.register_blueprint(tasks_bp)
except Exception as e:
    logger.warning(f"tasks blueprint not loaded: {e}")

# Products (formerly Portfolio) – per-client products, totals, AUM sync
try:
    from routes.products import products_bp
    app.register_blueprint(products_bp)
except Exception as e:
    logger.warning(f"products blueprint not loaded: {e}")

# Reviews (annual review creation, agenda/valuation docs)
try:
    from routes.reviews import reviews_bp
    app.register_blueprint(reviews_bp)
except Exception as e:
    logger.warning(f"reviews blueprint not loaded: {e}")

# Files / Drive helpers (optional)
try:
    from routes.files import files_bp
    app.register_blueprint(files_bp)
except Exception as e:
    logger.warning(f"files blueprint not loaded: {e}")

# (If you had a communications blueprint before and fully removed it,
# do NOT import/register it here. This keeps it deleted across the app.)

# -----------------------------
# Health check
# -----------------------------
@app.route("/health")
def health():
    return jsonify(
        status="ok",
        now=datetime.utcnow().isoformat() + "Z",
        service="WealthPro CRM",
    )

# -----------------------------
# Error handlers (simple)
# -----------------------------
@app.errorhandler(404)
def not_found(err):
    return (
        "<h1>404 - Not Found</h1><p>The page you requested does not exist.</p>",
        404,
    )

@app.errorhandler(500)
def internal_error(err):
    logger.error(f"500 error: {err}")
    return (
        "<h1>500 - Server Error</h1><p>Something went wrong. Please try again.</p>",
        500,
    )

# -----------------------------
# Gunicorn entry point
# -----------------------------
if __name__ == "__main__":
    # Local dev server
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
