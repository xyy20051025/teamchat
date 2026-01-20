from flask import render_template, request, session, redirect, url_for, flash, jsonify
from app.blueprints.frontend import frontend_bp
from app.extensions import sock, db
from app.models import User, Message, Room
import json
from datetime import datetime

# Simple in-memory storage for connected clients: ws -> nickname
connected_clients = {}

@frontend_bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # This handles login
        username = request.form.get('nickname') # login.html uses 'nickname' name
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
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
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'success': True, 'message': '注册成功，请登录'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

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
        filename = secure_filename(file.filename)
        # 加上时间戳避免重名
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        file.save(os.path.join(upload_folder, filename))
        
        # 返回相对路径
        url = url_for('static', filename=f'uploads/{filename}')
        return jsonify({'success': True, 'url': url})
        
    return jsonify({'success': False, 'message': '上传失败'})

@frontend_bp.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('frontend.index'))
    return render_template('chat.html', nickname=session['username'])

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
                    elif msg_type == 'message' or msg_type == 'image':
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
                                    msg_type='image' if msg_type == 'image' else 'text',
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
