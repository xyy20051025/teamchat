from flask import Flask

from app.config import AppConfig
from app.extensions import sock, db
from app.blueprints.backend import backend_bp
from app.blueprints.frontend import frontend_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(AppConfig)
    
    sock.init_app(app)
    db.init_app(app)

    app.register_blueprint(backend_bp, url_prefix="/admin")
    app.register_blueprint(frontend_bp, url_prefix="/")

    return app
