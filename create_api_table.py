from app import create_app
from app.extensions import db
from app.models import ThirdPartyAPI

app = create_app()

with app.app_context():
    db.create_all()
    print("ThirdPartyAPI table created (if not existed).")
