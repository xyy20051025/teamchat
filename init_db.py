from app import create_app
from app.extensions import db
from app.models import User, Room

app = create_app()

with app.app_context():
    db.drop_all() # 重置数据库以应用模型更改
    db.create_all()
    # Create default room if not exists
    if not Room.query.filter_by(name='公共聊天室').first():
        default_room = Room(name='公共聊天室', code='100000')
        db.session.add(default_room)
        db.session.commit()
        print("Created default room.")
    print("Database initialized.")
