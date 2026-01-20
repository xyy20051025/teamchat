from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Check if column exists
        with db.engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(ai_models)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'is_default' not in columns:
                print("Adding is_default column to ai_models table...")
                conn.execute(text("ALTER TABLE ai_models ADD COLUMN is_default BOOLEAN DEFAULT 0"))
                conn.commit()
                print("Column added successfully.")
            else:
                print("Column is_default already exists.")
    except Exception as e:
        print(f"Error: {e}")
