# app.py
import os
import logging
from datetime import datetime
from flask import Flask, jsonify
from jinja2.runtime import Undefined

# -----------------------------
# SafeUndefined for Jinja (won't crash on missing keys/attrs)
# -----------------------------
class SafeUndefined(Undefined):
    def _fail_with_undefined_error(self, *args, **kwargs):
        return ""
    __add__ = __radd__ = __mul__ = __rmul__ = __div__ = __rdiv__ = __truediv__ = __rtruediv__ = (
        __floordiv__
    ) = __rfloordiv__ = __mod__ = __rmod__ = __pos__ = __neg__ = __call__ = __getitem__ = (
        __getattr__
    ) = _fail_with_undefined_error

# -----------------------------
# App factory
# -----------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

# Jinja: use SafeUndefined
app.jinja_env.undefined = SafeUndefined

# -----------------------------
# Template filters (kept from your original)
# -----------------------------
def coalesce(*args):
    """Return first non-empty/non-None value."""
    for a in args:
        if a not in (None, "", [], {}, ()):
            return a
    return ""

def fmtdate(value, in_fmt="%Y-%m-%d", out_fmt="%d %b %Y"):
    """Format date strings safely."""
    try:
        if not value:
            return ""
        if isinstance(value, datetime):
            return value.strftime(out_fmt)
        dt = datetime.strptime(str(value), in_fmt)
        return dt.strftime(out_fmt)
    except Exception:
        return str(value or "")

app.add_template_filter(coalesce, "coalesce")
app.add_template_filter(fmtdate, "fmtdate")

# -----------------------------
# Logging (kept)
# -----------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(levelname)s:%(name)s:%(message)s",
)
logger = logging.getLogger(__name__)

# -----------------------------
# Blueprints (existing)
# -----------------------------
from routes.auth import auth_bp
from routes.clients import clients_bp
from routes.tasks import tasks_bp
from routes.communications import communications_bp

# -----------------------------
# NEW Blueprints (add these)
# -----------------------------
from routes.portfolio import portfolio_bp
from routes.client_details import client_details_bp

# -----------------------------
# Register blueprints
# -----------------------------
app.register_blueprint(auth_bp)
app.register_blueprint(clients_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(communications_bp)

# New ones
app.register_blueprint(portfolio_bp)
app.register_blueprint(client_details_bp)

# -----------------------------
# Health & test routes (kept)
# -----------------------------
@app.route("/health")
def health():
    return jsonify(status="ok", service="wealthpro-crm", time=datetime.utcnow().isoformat() + "Z")

@app.route("/test")
def test():
    return "OK"

# -----------------------------
# Local dev entrypoint (kept)
# -----------------------------
if __name__ == "__main__":
    # For local development only (Render uses gunicorn)
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
