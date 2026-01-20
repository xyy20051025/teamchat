from flask import Flask
from flask_compress import Compress
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.config import AppConfig
from app.extensions import sock, db
from app.blueprints.backend import backend_bp
from app.blueprints.frontend import frontend_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(AppConfig)
    
    # Enable Gzip compression
    Compress(app)
    
    sock.init_app(app)
    db.init_app(app)

    # Enable Write-Ahead Logging (WAL) for SQLite to improve concurrency
    if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    app.register_blueprint(backend_bp, url_prefix="/admin")
    app.register_blueprint(frontend_bp, url_prefix="/")

    return app
