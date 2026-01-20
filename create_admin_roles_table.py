from app import create_app, db
from app.models import admin_roles

app = create_app()

def create_table():
    with app.app_context():
        # Create specific table
        try:
            admin_roles.create(db.engine)
            print("admin_roles table created successfully.")
        except Exception as e:
            print(f"Error creating table: {e}")
            # If it fails because it exists, that's fine.
            
if __name__ == "__main__":
    create_table()
