"""
WealthPro CRM - Main Application File
FILE 1 of 8 - Upload this as app.py
"""

import os
import logging
from datetime import datetime
from flask import Flask, jsonify

# Jinja: make undefined safe for format strings
from jinja2.runtime import Undefined

class SafeUndefined(Undefined):
    """Undefined that won't crash when used with format specs like {:,.2f}."""
    def __str__(self):
        return ""
    def __format__(self, spec):
        # If a template tries to do e.g. {{ value|default(0):.2f }} or similar,
        # returning empty string avoids "Unsupported format string for Undefined".
        return ""

# -----------------------------------------------------------------------------
# Flask setup
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Make Jinja tolerant to missing values that are formatted
app.jinja_env.undefined = SafeUndefined

# Optional: a couple of safe filters for templates
@app.template_filter("coalesce")
def coalesce_filter(value, default=""):
    """Return value if it's truthy (and not Undefined), else default."""
    try:
        if value is None:
            return default
        s = str(value)
        return s if s != "" else default
    except Exception:
        return default

@app.template_filter("fmtdate")
def fmtdate_filter(value, fmt="%d %b %Y"):
    """Safely format a date/datetime or date-string; return '' on failure."""
    if not value:
        return ""
    try:
        if isinstance(value, datetime):
            return value.strftime(fmt)
        # try common string formats
        for f in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%fZ"):
            try:
                dt = datetime.strptime(str(value), f)
                return dt.strftime(fmt)
            except Exception:
                continue
        # last resort: just return the original string
        return str(value)
    except Exception:
        return ""

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Blueprints
# -----------------------------------------------------------------------------
from routes.auth import auth_bp
from routes.clients import clients_bp
from routes.tasks import tasks_bp
from routes.communications import communications_bp

# Register blueprints (route modules)
app.register_blueprint(auth_bp)
app.register_blueprint(clients_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(communications_bp)

# -----------------------------------------------------------------------------
# Health check route (polled by Render)
# -----------------------------------------------------------------------------
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'service': 'WealthPro CRM'
    })

# -----------------------------------------------------------------------------
# Test route
# -----------------------------------------------------------------------------
@app.route('/test')
def test():
    from flask import session
    connected = 'credentials' in session
    return f"""
<h1>WealthPro CRM Test</h1>
<p>✅ Flask working</p>
<p>✅ Render deployment successful</p>
<p>🔗 Google Drive connected: {'Yes' if connected else 'No'}</p>
<p><a href="/">Go to Dashboard</a></p>
"""

# -----------------------------------------------------------------------------
# Serve
# -----------------------------------------------------------------------------
PORT = int(os.environ.get('PORT', 10000))
HOST = '0.0.0.0'

if __name__ == '__main__':
    logger.info(f"Starting WealthPro CRM on {HOST}:{PORT}")
    # debug=False is important on Render; the worker is gunicorn in production
    app.run(host=HOST, port=PORT, debug=False)
