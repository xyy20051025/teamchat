from app import create_app
from app.extensions import db
from app.models import User, Room

app = create_app()

with app.app_context():
    db.create_all()
    # Create default room if not exists
    if not Room.query.filter_by(name='公共聊天室').first():
        default_room = Room(name='公共聊天室')
        db.session.add(default_room)
        db.session.commit()
        print("Created default room.")
    print("Database initialized.")
