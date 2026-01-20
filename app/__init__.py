from flask import Flask

from app.config import AppConfig
from app.blueprints.backend import backend_bp
from app.blueprints.frontend import frontend_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(AppConfig)

    app.register_blueprint(backend_bp, url_prefix="/admin")
    app.register_blueprint(frontend_bp, url_prefix="/portal")

    return app
