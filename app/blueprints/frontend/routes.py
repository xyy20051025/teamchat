from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify, Response, stream_with_context
from app.extensions import db, sock
from app.models import User, Room, RoomMember, Friendship, Message, AIModel, ServerConfig
from sqlalchemy import or_
from datetime import datetime
from werkzeug.utils import secure_filename
import json
import os
import threading
import time
from openai import OpenAI
import random
import string
from app.blueprints.frontend import frontend_bp

# Global dictionary to store connected clients: {ws: nickname}
connected_clients = {}

@frontend_bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('frontend.chat'))
    return redirect(url_for('frontend.login'))

@frontend_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nickname = request.form.get('nickname')
        password = request.form.get('password')
        
        user = User.query.filter(or_(User.username == nickname, User.user_code == nickname)).first()
        
        if user and user.check_password(password):
            if user.is_banned:
                flash('该账号已被封禁', 'danger')
                return redirect(url_for('frontend.login'))
                
            session['user_id'] = user.id
            session['nickname'] = user.nickname or user.username
            session['is_admin'] = False
            
            # Check if admin
            from app.models import Admin
            admin = Admin.query.filter_by(username=user.username).first()
            if admin:
                 session['is_admin'] = True
                 
            # Store configured WS server if selected (simulated for now)
            ws_server = request.form.get('ws_server')
            if ws_server:
                session['ws_server'] = ws_server
                
            return redirect(url_for('frontend.chat'))
        else:
            flash('用户名或密码错误', 'danger')
            
    return render_template('login.html')

@frontend_bp.route('/api/public/servers')
def get_public_servers():
    servers = ServerConfig.query.all()
    return jsonify({
        'success': True,
        'data': [s.to_dict() for s in servers]
    })

@frontend_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username')
        password = data.get('password')
        # confirm_password only in form, maybe frontend check is enough or add check here
        
        if User.query.filter_by(username=username).first():
            if request.is_json:
                return jsonify({'success': False, 'message': '用户名已存在'})
            flash('用户名已存在', 'danger')
            return redirect(url_for('frontend.login')) # Register is part of login page now
            
        # Generate unique 6 digit code
        while True:
            code = ''.join(random.choices(string.digits, k=6))
            if not User.query.filter_by(user_code=code).first():
                break
                
        user = User(username=username, user_code=code, nickname=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        if request.is_json:
             return jsonify({'success': True, 'message': f'注册成功！您的用户编码是: {code}，请牢记。'})

        flash(f'注册成功！您的用户编码是: {code}，请牢记。', 'success')
        return redirect(url_for('frontend.login'))
        
    return redirect(url_for('frontend.login'))

@frontend_bp.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('frontend.login'))
        
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('frontend.login'))
        
    return render_template('chat.html', user=user, ws_server=session.get('ws_server'))

@frontend_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('frontend.login'))

# API Routes for Chat Data
@frontend_bp.route('/api/rooms')
def get_rooms():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    # Get joined rooms
    memberships = RoomMember.query.filter_by(user_id=user_id).all()
    rooms_data = []
    
    # Always include public room if exists, or create it? 
    # Logic: User should be added to public room on creation/login if not there.
    # For now, just return what they are in.
    
    for m in memberships:
        room = Room.query.get(m.room_id)
        if room:
            rooms_data.append({
                'id': room.id,
                'name': room.name,
                'code': room.code,
                'type': 'group',
                'unread': 0 # TODO: Implement unread count
            })
            
    return jsonify({'success': True, 'data': rooms_data})

@frontend_bp.route('/api/friends')
def get_friends():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    user_id = session['user_id']
    
    # Get accepted friendships
    friends = Friendship.query.filter(
        ((Friendship.user_id == user_id) | (Friendship.friend_id == user_id)),
        Friendship.status == 'accepted'
    ).all()
    
    friends_data = []
    for f in friends:
        friend_user = f.friend if f.user_id == user_id else f.user
        friends_data.append({
            'id': friend_user.id,
            'username': friend_user.username,
            'nickname': friend_user.nickname,
            'avatar': friend_user.avatar or '/static/images/default_avatar.svg',
            'status': 'offline' # WebSocket status would be better
        })
        
    return jsonify({'success': True, 'data': friends_data})

@frontend_bp.route('/api/room/<int:room_id>/messages')
def get_room_messages(room_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    # Check membership
    is_member = RoomMember.query.filter_by(user_id=session['user_id'], room_id=room_id).first()
    if not is_member:
        return jsonify({'success': False, 'message': 'Not a member'}), 403
        
    messages = Message.query.filter_by(room_id=room_id).order_by(Message.timestamp.asc()).all()
    
    return jsonify({'success': True, 'data': [m.to_dict() for m in messages]})

@frontend_bp.route('/api/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'})
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'})
        
    if file:
        filename = file.filename
        # Save to static/uploads
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        # Generate safe filename
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        safe_filename = f"{timestamp}_{filename}"
        file.save(os.path.join(upload_folder, safe_filename))
        
        url = url_for('static', filename=f'uploads/{safe_filename}')
        return jsonify({'success': True, 'url': url, 'filename': filename})

@frontend_bp.route('/api/friend/request', methods=['POST'])
def send_friend_request():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    data = request.get_json()
    user_code = data.get('user_code')
    
    target_user = User.query.filter_by(user_code=user_code).first()
    if not target_user:
        return jsonify({'success': False, 'message': '用户不存在'})
        
    if target_user.id == session['user_id']:
        return jsonify({'success': False, 'message': '不能添加自己为好友'})
        
    # Check if already friends
    existing = Friendship.query.filter(
        ((Friendship.user_id == session['user_id']) & (Friendship.friend_id == target_user.id)) |
        ((Friendship.user_id == target_user.id) & (Friendship.friend_id == session['user_id']))
    ).first()
    
    if existing:
        if existing.status == 'accepted':
            return jsonify({'success': False, 'message': '已经是好友了'})
        elif existing.status == 'pending':
            return jsonify({'success': False, 'message': '好友请求已发送，请等待通过'})
            
    # Create request
    friendship = Friendship(user_id=session['user_id'], friend_id=target_user.id, status='pending')
    db.session.add(friendship)
    db.session.commit()
    
    # Notify target user via WebSocket
    sender = User.query.get(session['user_id'])
    send_personal_message(target_user.nickname, {
        'type': 'friend_request',
        'message': f'{sender.nickname} 请求添加你为好友'
    })
    
    return jsonify({'success': True, 'message': '好友请求已发送'})

@frontend_bp.route('/api/friend/requests')
def get_friend_requests():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    requests = Friendship.query.filter_by(friend_id=session['user_id'], status='pending').all()
    data = []
    for r in requests:
        data.append({
            'id': r.id,
            'user_id': r.user.id,
            'nickname': r.user.nickname,
            'avatar': r.user.avatar or '/static/images/default_avatar.svg',
            'time': r.created_at.strftime('%Y-%m-%d %H:%M')
        })
    return jsonify({'success': True, 'data': data})

@frontend_bp.route('/api/friend/handle', methods=['POST'])
def handle_friend_request():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    data = request.get_json()
    request_id = data.get('id')
    action = data.get('action') # accept, reject
    
    friendship = Friendship.query.get(request_id)
    if not friendship or friendship.friend_id != session['user_id']:
        return jsonify({'success': False, 'message': '请求不存在'})
        
    if action == 'accept':
        friendship.status = 'accepted'
        db.session.commit()
        return jsonify({'success': True, 'message': '已同意'})
    elif action == 'reject':
        db.session.delete(friendship)
        db.session.commit()
        return jsonify({'success': True, 'message': '已拒绝'})
        
    return jsonify({'success': False, 'message': '未知操作'})

@frontend_bp.route('/api/group/create', methods=['POST'])
def create_group():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return jsonify({'success': False, 'message': '请输入群名称'})
        
    # Generate code
    while True:
        code = ''.join(random.choices(string.digits, k=6))
        if not Room.query.filter_by(code=code).first():
            break
            
    room = Room(name=name, code=code, owner_id=session['user_id'])
    db.session.add(room)
    db.session.commit()
    
    # Add owner as member
    member = RoomMember(user_id=session['user_id'], room_id=room.id)
    db.session.add(member)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '创建成功', 'room': {'id': room.id, 'name': room.name, 'code': code}})

@frontend_bp.route('/api/group/join', methods=['POST'])
def join_group():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    data = request.get_json()
    room_id = data.get('room_id')
    code = data.get('code')
    
    room = None
    if room_id:
        room = Room.query.get(room_id)
    elif code:
        room = Room.query.filter_by(code=code).first()
        
    if not room:
        return jsonify({'success': False, 'message': '群组不存在'})
        
    existing = RoomMember.query.filter_by(user_id=session['user_id'], room_id=room.id).first()
    if existing:
        return jsonify({'success': True, 'message': '已在群组中', 'room_id': room.id})
        
    member = RoomMember(user_id=session['user_id'], room_id=room.id)
    db.session.add(member)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '加入成功', 'room_id': room.id})

@frontend_bp.route('/api/user/avatar', methods=['POST'])
def update_avatar():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
        
    if 'avatar' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'}), 400
        
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'}), 400
        
    if file:
        filename = secure_filename(file.filename)
        # Unique filename
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        new_filename = f"{timestamp}_{filename}"
        
        # Ensure directory exists
        upload_folder = os.path.join(current_app.static_folder, 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        file_path = os.path.join(upload_folder, new_filename)
        file.save(file_path)
        
        # Update user avatar URL
        avatar_url = f"/static/uploads/{new_filename}"
        user.avatar = avatar_url
        db.session.commit()
        
        return jsonify({'success': True, 'avatar_url': avatar_url})
        
    return jsonify({'success': False, 'message': 'Upload failed'}), 500

@frontend_bp.route('/api/chat/ai_stream')
def stream_ai_chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'No query provided'}), 400
        
    # Find default active model
    model = AIModel.query.filter_by(is_active=True, is_default=True).first()
    if not model:
        def generate_error():
            yield f"data: {json.dumps({'error': '未配置默认AI模型'}, ensure_ascii=False)}\n\n"
        return Response(stream_with_context(generate_error()), mimetype='text/event-stream')
        
    def generate():
        try:
            client = OpenAI(
                api_key=model.api_key,
                base_url=model.api_url
            )
            
            messages = []
            if model.prompt:
                messages.append({"role": "system", "content": model.prompt})
                
            messages.append({"role": "user", "content": query})
            
            stream = client.chat.completions.create(
                model=model.model_name,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True}
            )
            
            accumulated_usage = 0
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                
                if hasattr(chunk, 'usage') and chunk.usage:
                     accumulated_usage = chunk.usage.total_tokens

            if accumulated_usage > 0:
                model.token_usage += accumulated_usage
                db.session.commit()
                     
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            print(f"AI Chat Stream Error: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

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
                        # Save to public room
                        room = Room.query.filter_by(name='公共聊天室').first()
                        if room:
                            room.announcement = content
                            room.announcement_time = datetime.now()
                            db.session.commit()
                            
                            broadcast_message({
                                'type': 'announcement',
                                'content': content,
                                'time': room.announcement_time.strftime('%Y-%m-%d %H:%M')
                            })

                    elif msg_type in ['message', 'image', 'file']:
                        # Validate session/user
                        # Since WebSocket is long-lived, we might not have request context with session every time?
                        # Flask-Sock runs in app context. request.session might be available if cookie is sent.
                        # But for safety, let's rely on the user info sent in message or mapped in connected_clients.
                        
                        nickname = connected_clients.get(ws)
                        if not nickname or nickname == "Anonymous":
                            continue
                            
                        # Save message to DB
                        room_id = msg_data.get('room_id')
                        if room_id:
                            # WebSocket doesn't share session context easily in all setups, but Flask-Sock might.
                            # Let's try to find user by nickname (fallback)
                            user = User.query.filter((User.nickname == nickname) | (User.username == nickname)).first()
                            
                            room = Room.query.get(room_id)
                            
                            if user and room:
                                # Check membership
                                is_member = RoomMember.query.filter_by(user_id=user.id, room_id=room.id).first()
                                if not is_member:
                                    continue

                                msg_entry = Message(
                                    content=msg_data.get('content'),
                                    msg_type=msg_type,
                                    user_id=user.id,
                                    room_id=room.id,
                                    timestamp=datetime.now()
                                )
                                if msg_type == 'file':
                                    msg_entry.filename = msg_data.get('filename')
                                    
                                db.session.add(msg_entry)
                                db.session.commit()
                                
                                # Prepare data for broadcast
                                msg_data['user'] = nickname # Display name
                                msg_data['avatar'] = user.avatar or '/static/images/default_avatar.svg'
                                msg_data['nickname'] = user.nickname or user.username
                                msg_data['room_id'] = room_id
                                
                                # Broadcast to room members only
                                broadcast_room_message(room_id, msg_data)
                                
                                # Check for AI command
                                content = msg_data.get('content', '')
                                trigger = None
                                if content.startswith('@趣冰'):
                                    trigger = '@趣冰'
                                elif content.startswith('@趣聊小助手'):
                                    trigger = '@趣聊小助手'
                                    
                                if msg_type == 'message' and trigger:
                                    query = content.replace(trigger, '', 1).strip()
                                    if query:
                                        # Use current_app._get_current_object() to pass app context
                                        app = current_app._get_current_object()
                                        threading.Thread(target=handle_ai_response_ws, args=(app, query, room_id, msg_data['nickname'])).start()
                                


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

def broadcast_room_message(room_id, data):
    msg = json.dumps(data)
    dead_clients = set()
    
    # 获取该房间的所有成员ID
    room_members = [m.user_id for m in RoomMember.query.filter_by(room_id=room_id).all()]
    
    for client, nickname in connected_clients.items():
        try:
            # 找到 client 对应的 user_id
            # 这里效率较低，实际生产环境应该在 connected_clients 里存 user_id
            user = User.query.filter((User.nickname == nickname) | (User.username == nickname)).first()
            if user and user.id in room_members:
                client.send(msg)
        except:
            dead_clients.add(client)
    
    for client in dead_clients:
        if client in connected_clients:
            connected_clients.pop(client)

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

def send_personal_message(target_nickname, data):
    """发送私聊/系统消息给指定用户"""
    print(f"DEBUG: Sending personal message to '{target_nickname}'. Connected: {list(connected_clients.values())}")
    msg = json.dumps(data)
    dead_clients = set()
    sent = False
    
    for client, nickname in connected_clients.items():
        if nickname == target_nickname:
            try:
                client.send(msg)
                sent = True
            except:
                dead_clients.add(client)
    
    for client in dead_clients:
        if client in connected_clients:
            connected_clients.pop(client)
            
    if not sent:
        print(f"DEBUG: Failed to send to '{target_nickname}'. User not found in connected clients.")
        
    return sent

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

def handle_ai_response_ws(app, query, room_id, user_nickname=None):
    with app.app_context():
        try:
            # 1. Find default model
            model = AIModel.query.filter_by(is_active=True, is_default=True).first()
            if not model:
                broadcast_room_message(room_id, {
                    'type': 'message',
                    'user': '系统',
                    'nickname': '系统',
                    'avatar': '/static/images/system_avatar.svg',
                    'content': '系统提示：后台未配置可用的AI模型引擎，暂时无法为您提供智能回复服务。',
                    'room_id': room_id,
                    'msg_type': 'system'
                })
                return

            # 2. Prepare Streaming
            msg_id = f'ai-msg-{int(time.time()*1000)}'
            avatar = '/static/images/default_avatar.svg'
            timestamp = datetime.now().strftime('%H:%M')
            
            # Broadcast Start
            broadcast_room_message(room_id, {
                'type': 'ai_stream_start',
                'id': msg_id,
                'user': '趣聊小助手',
                'nickname': '趣聊小助手',
                'avatar': avatar,
                'time': timestamp,
                'room_id': room_id
            })
            
            # 3. Call OpenAI
            client = OpenAI(
                api_key=model.api_key,
                base_url=model.api_url
            )
            
            messages = []
            if model.prompt:
                messages.append({"role": "system", "content": model.prompt})
            messages.append({"role": "user", "content": query})
            
            stream = client.chat.completions.create(
                model=model.model_name,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True}
            )
            
            mention_text = f"@{user_nickname} " if user_nickname else ""
            full_content = mention_text
            
            # Send mention first if exists
            if mention_text:
                broadcast_room_message(room_id, {
                    'type': 'ai_stream_chunk',
                    'id': msg_id,
                    'content': mention_text,
                    'room_id': room_id
                })
            
            accumulated_usage = 0
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    broadcast_room_message(room_id, {
                        'type': 'ai_stream_chunk',
                        'id': msg_id,
                        'content': content,
                        'room_id': room_id
                    })
                
                if hasattr(chunk, 'usage') and chunk.usage:
                    accumulated_usage = chunk.usage.total_tokens

            # 4. Save Usage
            if accumulated_usage > 0:
                model.token_usage += accumulated_usage
                db.session.commit()
                
            # 5. Broadcast Done
            broadcast_room_message(room_id, {
                'type': 'ai_stream_done',
                'id': msg_id,
                'room_id': room_id
            })
            
            # 6. Save Message to DB
            if full_content:
                msg_entry = Message(
                    content=full_content,
                    msg_type='ai',
                    user_id=None, # System/AI
                    room_id=room_id,
                    timestamp=datetime.now()
                )
                db.session.add(msg_entry)
                db.session.commit()
                
        except Exception as e:
            print(f"AI Stream Error: {e}")
            broadcast_room_message(room_id, {
                'type': 'message', # Fallback to normal message for error
                'user': '趣聊小助手',
                'nickname': '趣聊小助手',
                'content': f'AI服务暂时不可用: {str(e)}',
                'room_id': room_id,
                'msg_type': 'ai',
                'avatar': '/static/images/default_avatar.svg'
            })