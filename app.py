import logging
import os
from flask import Flask, redirect, url_for
from datetime import timedelta

# Blueprints
from routes.auth import auth_bp          # your existing auth (kept)
from routes.clients import clients_bp    # your existing clients (kept)
from routes.tasks import tasks_bp        # updated tasks (restyled)
from routes.products import products_bp  # NEW: products

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
    app.permanent_session_lifetime = timedelta(hours=6)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(products_bp)

    # Root: leave to routes.auth (dashboard) if it already owns "/"
    # If your routes.auth does NOT define "/", uncomment the line below:
    # @app.route("/")
    # def root_redirect():
    #     return redirect(url_for("clients.clients"))

    @app.route("/health")
    def health():
        return {"ok": True, "service": "WealthPro CRM"}

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
