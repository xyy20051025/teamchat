import os


class AppConfig:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
