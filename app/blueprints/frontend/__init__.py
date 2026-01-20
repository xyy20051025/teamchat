from flask import Blueprint

frontend_bp = Blueprint("frontend", __name__)

from app.blueprints.frontend import routes
