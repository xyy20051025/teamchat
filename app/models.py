from datetime import datetime
from app.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    nickname = db.Column(db.String(64)) # 显示名称
    user_code = db.Column(db.String(10), unique=True, nullable=False) # 数字编码
    avatar = db.Column(db.String(256)) # 头像URL
    password_hash = db.Column(db.String(128))
    is_banned = db.Column(db.Boolean, default=False) # 是否封禁
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'nickname': self.nickname or self.username,
            'user_code': self.user_code,
            'avatar': self.avatar or '/static/images/default_avatar.svg',
            'is_banned': self.is_banned,
            'created_at': self.created_at.isoformat()
        }

class Friendship(db.Model):
    __tablename__ = 'friendships'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='friend_requests_sent')
    friend = db.relationship('User', foreign_keys=[friend_id], backref='friend_requests_received')

class Room(db.Model):
    __tablename__ = 'rooms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False) # Remove unique=True to allow same name groups
    code = db.Column(db.String(10), unique=True, nullable=True) # Room code for searching
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    announcement = db.Column(db.Text, nullable=True)
    announcement_time = db.Column(db.DateTime, nullable=True)
    is_banned = db.Column(db.Boolean, default=False) # 是否封禁

    owner = db.relationship('User', foreign_keys=[owner_id])

class RoomMember(db.Model):
    __tablename__ = 'room_members'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False, index=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('room_memberships', lazy='dynamic'))
    room = db.relationship('Room', backref=db.backref('members', lazy='dynamic'))


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    msg_type = db.Column(db.String(20), default='text') # text, image, system
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # nullable for system messages
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False, index=True)
    
    user = db.relationship('User', backref=db.backref('messages', lazy=True))
    room = db.relationship('Room', backref=db.backref('messages', lazy=True))

    def to_dict(self):
        user_name = 'System'
        if self.user:
            user_name = self.user.nickname or self.user.username
        elif self.msg_type == 'ai':
            user_name = '趣唠AI'
            
        return {
            'id': self.id,
            'content': self.content,
            'msg_type': self.msg_type,
            'timestamp': self.timestamp.strftime('%H:%M'), # 简化时间格式
            'user': user_name,
            'avatar': self.user.avatar if self.user else ('/static/images/default_avatar.svg' if self.msg_type == 'ai' else ''),
            'room': self.room.name
        }

class ServerConfig(db.Model):
    __tablename__ = 'server_configs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False) # Server name/description
    ws_url = db.Column(db.String(256), nullable=False) # WS Address: ws://ip:port or wss://domain
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'ws_url': self.ws_url,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }

class AIModel(db.Model):
    __tablename__ = 'ai_models'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False) # Display Name
    api_url = db.Column(db.String(256), nullable=False)
    api_key = db.Column(db.String(256), nullable=False)
    model_name = db.Column(db.String(128), nullable=False) # Model ID/Name used in API
    prompt = db.Column(db.Text, nullable=True) # System prompt
    token_usage = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'api_url': self.api_url,
            'api_key': self.api_key, # In prod, maybe mask this
            'model_name': self.model_name,
            'prompt': self.prompt,
            'token_usage': self.token_usage,
            'is_active': self.is_active,
            'is_default': self.is_default,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }

class ThirdPartyAPI(db.Model):
    __tablename__ = 'third_party_apis'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    command = db.Column(db.String(64), nullable=False, unique=True) # e.g. @天气
    api_url = db.Column(db.String(256), nullable=False)
    api_token = db.Column(db.String(256), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'command': self.command,
            'api_url': self.api_url,
            'api_token': self.api_token,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }

role_menus = db.Table('role_menus',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('menu_id', db.Integer, db.ForeignKey('menus.id'), primary_key=True)
)

admin_roles = db.Table('admin_roles',
    db.Column('admin_id', db.Integer, db.ForeignKey('admins.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
)

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    menus = db.relationship('Menu', secondary=role_menus, lazy='subquery',
        backref=db.backref('roles', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'menus': [m.to_dict() for m in self.menus],
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }

class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    
    roles = db.relationship('Role', secondary=admin_roles, lazy='subquery',
        backref=db.backref('admins', lazy=True))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'roles': [r.to_dict() for r in self.roles]
        }

class Menu(db.Model):
    __tablename__ = 'menus'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    icon = db.Column(db.String(64), default='') # layui icon class
    url = db.Column(db.String(128), default='#') # endpoint or url
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'icon': self.icon,
            'url': self.url,
            'order': self.order
        }

class SnakeGameMatch(db.Model):
    __tablename__ = 'snake_game_matches'
    id = db.Column(db.Integer, primary_key=True)
    room_code = db.Column(db.String(10), unique=True, nullable=False)
    match_type = db.Column(db.String(10), default='1v1') # 1v1, 3v3, pve
    status = db.Column(db.String(20), default='waiting') # waiting, playing, finished
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SnakeGameScore(db.Model):
    __tablename__ = 'snake_game_scores'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    match_type = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='game_scores')
