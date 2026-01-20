from app import create_app
from app.extensions import db
from app.models import User, Admin
import sqlite3

app = create_app()

with app.app_context():
    # 1. Create Admins table (db.create_all will do this for new tables)
    db.create_all()
    print("Created tables (if not exist).")

    # 2. Add is_banned column to users/rooms if not exists
    # Using raw SQL for SQLite ALTER TABLE
    with db.engine.connect() as conn:
        try:
            conn.execute(db.text("ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT 0"))
            print("Added is_banned column to users table.")
        except Exception as e:
            pass # Ignore if exists

        try:
            conn.execute(db.text("ALTER TABLE rooms ADD COLUMN is_banned BOOLEAN DEFAULT 0"))
            print("Added is_banned column to rooms table.")
        except Exception as e:
            print(f"Column is_banned for rooms might already exist: {e}")

    # 3. Create Indexes for High Performance
    with db.engine.connect() as conn:
        indexes = [
            ("idx_messages_room_id", "messages", "room_id"),
            ("idx_messages_timestamp", "messages", "timestamp"),
            ("idx_room_members_user_id", "room_members", "user_id"),
            ("idx_room_members_room_id", "room_members", "room_id")
        ]
        
        for idx_name, table, column in indexes:
            try:
                conn.execute(db.text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({column})"))
                print(f"Created index {idx_name} on {table}({column})")
            except Exception as e:
                print(f"Error creating index {idx_name}: {e}")

    # 4. Create default admin
    admin = Admin.query.filter_by(username='admin').first()
    if not admin:
        admin = Admin(username='admin')
        admin.set_password('admin888')
        db.session.add(admin)
        db.session.commit()
        print("Created default admin: admin/admin888")
    else:
        print("Admin already exists.")
