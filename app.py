# app.py

import os
import logging
from flask import Flask

# Existing blueprints you already have
from routes.auth import auth_bp
from routes.clients import clients_bp

# New / updated blueprints
from routes.tasks import tasks_bp
from routes.products import products_bp

logging.basicConfig(level=logging.INFO)

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(products_bp)

    # Health
    @app.route("/health")
    def health():
        return {"ok": True}

    return app

app = create_app()
