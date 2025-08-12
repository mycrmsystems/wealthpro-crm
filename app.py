"""
WealthPro CRM - Main Application File
FILE 1 of 8 - Upload this as app.py
"""

import os
import logging
from flask import Flask
from routes.auth import auth_bp
from routes.clients import clients_bp
from routes.tasks import tasks_bp
from routes.communications import communications_bp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Configuration
PORT = int(os.environ.get('PORT', 10000))
HOST = '0.0.0.0'

# Register blueprints (route modules)
app.register_blueprint(auth_bp)
app.register_blueprint(clients_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(communications_bp)

# Health check route
@app.route('/health')
def health_check():
    from datetime import datetime
    from flask import jsonify
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'WealthPro CRM'
    })

# Test route
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

if __name__ == '__main__':
    logger.info(f"Starting WealthPro CRM on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)
