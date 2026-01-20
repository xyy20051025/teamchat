from flask import render_template, request, session, redirect, url_for, flash, jsonify
from app.blueprints.frontend import frontend_bp
from app.extensions import sock, db
from app.models import User, Message, Room, Friendship, RoomMember
import json
import random
import string
from datetime import datetime

# Simple in-memory storage for connected clients: ws -> nickname
connected_clients = {}

def generate_user_code():
    """生成唯一的6位数字编码"""
    while True:
        code = ''.join(random.choices(string.digits, k=6))
        if not User.query.filter_by(user_code=code).first():
            return code

def generate_room_code():
    """生成唯一的6位数字群号"""
    while True:
        code = ''.join(random.choices(string.digits, k=6))
        if not Room.query.filter_by(code=code).first():
            return code

@frontend_bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # This handles login
        login_id = request.form.get('nickname') # login.html uses 'nickname' name
        password = request.form.get('password')
        
        # Support login by username or user_code
        user = User.query.filter(
            (User.username == login_id) | (User.user_code == login_id)
        ).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('frontend.chat'))
        else:
            # Pass error to template (need to update login.html to show it)
            return render_template('login.html', error='用户名或密码错误')
            
    return render_template('login.html')

@frontend_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
        
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': '用户名已存在'})
        
    try:
        user_code = generate_user_code()
        # 默认头像和昵称
        new_user = User(
            username=username, 
            user_code=user_code,
            nickname=username,
            avatar=f'https://api.dicebear.com/7.x/avataaars/svg?seed={username}'
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'success': True, 'message': '注册成功，请登录'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@frontend_bp.route('/api/me', methods=['GET', 'POST'])
def my_profile():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401
    
    user = User.query.get(session['user_id'])
    if request.method == 'GET':
        return jsonify({'success': True, 'data': user.to_dict()})
    
    data = request.get_json()
    if 'nickname' in data:
        user.nickname = data['nickname']
        # 同时更新 session 中的 username (虽然这里叫 username 但其实通常用作显示)
        # 如果系统严格区分 username(登录名) 和 nickname(显示名)，则无需更新 session['username']
        # 但考虑到 chat.html 用的是 session['username'] 或者 nickname 变量，
        # 我们最好保持一致。
        # 注意：User.username 是登录名，User.nickname 是显示名。
        # session['username'] 存的是 User.username。
        # 前端显示应该优先用 User.nickname。
        
    if 'avatar' in data:
        user.avatar = data['avatar']
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': '更新成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@frontend_bp.route('/api/user/search', methods=['GET'])
def search_user():
    code = request.args.get('code')
    if not code:
        return jsonify({'success': False, 'message': '请输入用户编码'})
    
    user = User.query.filter_by(user_code=code).first()
    if user:
        return jsonify({'success': True, 'data': {
            'id': user.id, # 前端可能需要 ID 来发送请求
            'username': user.username,
            'nickname': user.nickname,
            'avatar': user.avatar,
            'user_code': user.user_code
        }})
    return jsonify({'success': False, 'message': '用户不存在'})

@frontend_bp.route('/api/friend/request', methods=['POST'])
def send_friend_request():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401
        
    data = request.get_json()
    target_code = data.get('user_code')
    
    target_user = User.query.filter_by(user_code=target_code).first()
    if not target_user:
        return jsonify({'success': False, 'message': '用户不存在'})
        
    if target_user.id == session['user_id']:
        return jsonify({'success': False, 'message': '不能添加自己为好友'})
        
    # Check if request already exists
    existing = Friendship.query.filter(
        ((Friendship.user_id == session['user_id']) & (Friendship.friend_id == target_user.id)) |
        ((Friendship.user_id == target_user.id) & (Friendship.friend_id == session['user_id']))
    ).first()
    
    if existing:
        if existing.status == 'accepted':
             return jsonify({'success': False, 'message': '你们已经是好友了'})
        return jsonify({'success': False, 'message': '好友请求已发送或正在处理中'})
        
    new_friendship = Friendship(user_id=session['user_id'], friend_id=target_user.id, status='pending')
    db.session.add(new_friendship)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '好友请求已发送'})

@frontend_bp.route('/api/group/create', methods=['POST'])
def create_group():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'}), 401
        
    data = request.get_json()
    group_name = data.get('name')
    
    if not group_name:
        return jsonify({'success': False, 'message': '请输入群聊名称'})
        
    try:
        room_code = generate_room_code()
        new_room = Room(
            name=group_name,
            code=room_code,
            owner_id=session['user_id']
        )
        db.session.add(new_room)
        db.session.flush() # Get ID before committing
        
        # Add creator as member
        member = RoomMember(user_id=session['user_id'], room_id=new_room.id)
        db.session.add(member)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': '群聊创建成功',
            'data': {
                'id': new_room.id,
                'name': new_room.name,
                'code': new_room.code
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@frontend_bp.route('/api/search_add', methods=['POST'])
def search_and_add():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'}), 401
        
    data = request.get_json()
    code = data.get('code')
    
    if not code:
        return jsonify({'success': False, 'message': '请输入编码'})
        
    # Check if it's a User
    user = User.query.filter_by(user_code=code).first()
    if user:
        # Check if it's self
        if user.id == session['user_id']:
             return jsonify({'success': False, 'message': '不能添加自己'})
             
        # Check existing friendship
        friendship = Friendship.query.filter(
            ((Friendship.user_id == session['user_id']) & (Friendship.friend_id == user.id)) |
            ((Friendship.user_id == user.id) & (Friendship.friend_id == session['user_id']))
        ).first()
        
        status = 'none'
        if friendship:
            status = friendship.status
            
        return jsonify({
            'success': True,
            'type': 'user',
            'data': {
                'id': user.id,
                'username': user.username,
                'nickname': user.nickname,
                'avatar': user.avatar,
                'status': status
            }
        })

    # Check if it's a Room
    room = Room.query.filter_by(code=code).first()
    if room:
        # Check if already a member
        is_member = RoomMember.query.filter_by(
            user_id=session['user_id'],
            room_id=room.id
        ).first() is not None
        
        return jsonify({
            'success': True,
            'type': 'group',
            'data': {
                'id': room.id,
                'name': room.name,
                'code': room.code,
                'is_member': is_member
            }
        })
        
    return jsonify({'success': False, 'message': '未找到对应用户或群聊'})

@frontend_bp.route('/api/group/join', methods=['POST'])
def join_group():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'}), 401
        
    data = request.get_json()
    room_id = data.get('room_id')
    
    if not room_id:
        return jsonify({'success': False, 'message': '参数错误'})
        
    room = Room.query.get(room_id)
    if not room:
        return jsonify({'success': False, 'message': '群聊不存在'})
        
    # Check if already member
    if RoomMember.query.filter_by(user_id=session['user_id'], room_id=room_id).first():
        return jsonify({'success': False, 'message': '你已经是该群成员'})
        
    try:
        member = RoomMember(user_id=session['user_id'], room_id=room_id)
        db.session.add(member)
        db.session.commit()
        return jsonify({'success': True, 'message': '加入群聊成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@frontend_bp.route('/api/room/<int:room_id>', methods=['GET'])
def get_room_info(room_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'}), 401
    
    room = Room.query.get(room_id)
    if not room:
        return jsonify({'success': False, 'message': '群聊不存在'})
        
    # Check if member (optional, but good for privacy)
    # For now, allow viewing info if it's public or if member
    # Assuming all rooms are "searchable" so info is public-ish
    
    member_count = room.members.count()
    
    return jsonify({
        'success': True,
        'data': {
            'id': room.id,
            'name': room.name,
            'code': room.code,
            'created_at': room.created_at.strftime('%Y-%m-%d'),
            'announcement': room.announcement,
            'member_count': member_count
        }
    })

@frontend_bp.route('/api/room/<int:room_id>/members', methods=['GET'])
def get_room_members(room_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'}), 401
    
    room = Room.query.get(room_id)
    if not room:
        return jsonify({'success': False, 'message': '群聊不存在'})
        
    members_data = []
    for member in room.members:
        user = member.user
        members_data.append({
            'id': user.id,
            'nickname': user.nickname or user.username,
            'username': user.username,
            'avatar': user.avatar or f'https://api.dicebear.com/7.x/avataaars/svg?seed={user.username}',
            'role': 'owner' if room.owner_id == user.id else 'member'
        })
        
    return jsonify({
        'success': True, 
        'data': members_data
    })

import os
from werkzeug.utils import secure_filename
from flask import current_app

@frontend_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
        
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有文件部分'})
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'})
        
    if file:
        original_filename = secure_filename(file.filename)
        # 加上时间戳避免重名
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{original_filename}"
        
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        file.save(os.path.join(upload_folder, filename))
        
        # 返回相对路径和原始文件名
        url = url_for('static', filename=f'uploads/{filename}')
        return jsonify({
            'success': True, 
            'url': url,
            'filename': original_filename, # 返回原始文件名用于显示
            'is_image': file.content_type.startswith('image/')
        })
        
    return jsonify({'success': False, 'message': '上传失败'})

@frontend_bp.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('frontend.index'))
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('frontend.index'))
    return render_template('chat.html', user=user, nickname=user.nickname)

@sock.route('/ws')
def websocket(ws):
    # Initial connection - wait for join message to map nickname
    connected_clients[ws] = "Anonymous"
    try:
        while True:
            data = ws.receive()
            if data:
                try:
                    msg_data = json.loads(data)
                    msg_type = msg_data.get('type')
                    
                    if msg_type == 'join':
                        # Update nickname mapping
                        nickname = msg_data.get('user')
                        connected_clients[ws] = nickname
                        # Broadcast join message
                        broadcast_message(msg_data)
                        # Broadcast updated user list
                        broadcast_user_list()
                        
                        # Send current announcement to the new user
                        room = Room.query.filter_by(name='公共聊天室').first()
                        if room and room.announcement:
                            ws.send(json.dumps({
                                'type': 'announcement',
                                'content': room.announcement,
                                'time': room.announcement_time.strftime('%Y-%m-%d %H:%M') if room.announcement_time else ''
                            }))

                    elif msg_type == 'update_announcement':
                        content = msg_data.get('content')
                        room = Room.query.filter_by(name='公共聊天室').first()
                        if room:
                            room.announcement = content
                            room.announcement_time = datetime.now()
                            db.session.commit()
                            
                            # Broadcast announcement to all
                            broadcast_message({
                                'type': 'announcement',
                                'content': content,
                                'time': room.announcement_time.strftime('%Y-%m-%d %H:%M')
                            })

                    elif msg_type == 'message' or msg_type == 'image' or msg_type == 'file':
                        # Ensure user is set correctly
                        username = connected_clients.get(ws, "Anonymous")
                        msg_data['user'] = username
                        
                        # Save to DB
                        try:
                            user = User.query.filter_by(username=username).first()
                            room = Room.query.filter_by(name='公共聊天室').first()
                            if user and room:
                                msg_entry = Message(
                                    content=msg_data.get('content'),
                                    msg_type=msg_type, # 'text', 'image', or 'file'
                                    user_id=user.id,
                                    room_id=room.id,
                                    timestamp=datetime.now()
                                )
                                db.session.add(msg_entry)
                                db.session.commit()
                        except Exception as e:
                            print(f"Error saving message: {e}")

                        broadcast_message(msg_data)
                    else:
                        broadcast_message(msg_data)
                except Exception as e:
                    print(f"Error processing message: {e}")
    except Exception:
        pass
    finally:
        if ws in connected_clients:
            nickname = connected_clients.pop(ws)
            # Broadcast leave message
            if nickname and nickname != "Anonymous":
                leave_msg = {'type': 'leave', 'user': nickname}
                broadcast_message(leave_msg)
                broadcast_user_list()

def broadcast_message(data):
    msg = json.dumps(data)
    dead_clients = set()
    for client in connected_clients:
        try:
            client.send(msg)
        except:
            dead_clients.add(client)
    
    for client in dead_clients:
        if client in connected_clients:
            connected_clients.pop(client)

def broadcast_user_list():
    # Filter out anonymous or None
    users = [name for name in connected_clients.values() if name and name != "Anonymous"]
    msg = json.dumps({'type': 'user_list', 'users': users})
    dead_clients = set()
    for client in connected_clients:
        try:
            client.send(msg)
        except:
            dead_clients.add(client)
            
    for client in dead_clients:
        if client in connected_clients:
            connected_clients.pop(client)
