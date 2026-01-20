from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Drop tables if they exist
    with db.engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS role_menus"))
        conn.execute(text("DROP TABLE IF EXISTS roles"))
        conn.execute(text("DROP TABLE IF EXISTS menus"))
        conn.commit()
    print("Dropped menus, roles, role_menus tables.")
