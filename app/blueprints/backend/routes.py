from flask import render_template, session, redirect, url_for, request, jsonify, current_app, Response, stream_with_context

from app.blueprints.backend import backend_bp

from app.models import User, Room, Message, Admin, RoomMember, Friendship, ServerConfig, AIModel, ThirdPartyAPI, Menu, Role

from app.extensions import db

from sqlalchemy import text, func

from functools import wraps

from datetime import datetime

import os

import json

from openai import OpenAI



def admin_required(f):

    @wraps(f)

    def decorated_function(*args, **kwargs):

        if 'admin_id' not in session:

            return redirect(url_for('backend.login'))

        return f(*args, **kwargs)

    return decorated_function



@backend_bp.route("/login", methods=['GET', 'POST'])

def login():

    if request.method == 'POST':

        username = request.form.get('username')

        password = request.form.get('password')

        

        admin = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password):

            session['admin_id'] = admin.id

            session['admin_name'] = admin.username

            return redirect(url_for('backend.backend_index'))

        else:

            return render_template('admin/login.html', error='用户名或密码错误')

            

    return render_template('admin/login.html')



@backend_bp.route("/logout")

def logout():

    session.pop('admin_id', None)

    session.pop('admin_name', None)

    return redirect(url_for('backend.login'))



@backend_bp.context_processor

def inject_menus():

    menus = []

    if 'admin_id' in session:

        admin = Admin.query.get(session['admin_id'])

        if admin:

            if admin.username == 'admin':

                menus = Menu.query.order_by(Menu.order).all()

            else:

                menu_ids = set()

                for role in admin.roles:

                    for menu in role.menus:

                        menu_ids.add(menu.id)

                menus = Menu.query.filter(Menu.id.in_(menu_ids)).order_by(Menu.order).all()

    return dict(menus=menus)



@backend_bp.route("/")

@admin_required

def backend_index():

    user_count = User.query.count()

    room_count = Room.query.filter(Room.code != None).count()

    message_count = Message.query.count()

    

    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()

    

    return render_template('admin/index.html', 

                         user_count=user_count,

                         room_count=room_count,

                         message_count=message_count,

                         recent_users=recent_users)



@backend_bp.route("/users")

@admin_required

def user_list():

    return render_template('admin/user_list.html')



@backend_bp.route("/api/users")

@admin_required

def get_users():

    page = request.args.get('page', 1, type=int)

    limit = request.args.get('limit', 20, type=int)

    

    pagination = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=limit, error_out=False)

    

    users = []

    for u in pagination.items:

        users.append(u.to_dict())

        

    return jsonify({

        'code': 0,

        'msg': '',

        'count': pagination.total,

        'data': users

    })



@backend_bp.route("/api/user/delete", methods=['POST'])

@admin_required

def delete_user():

    data = request.get_json()

    user_id = data.get('id')

    user = User.query.get(user_id)

    if user:

        if user.user_code == 'ai_bot':

             return jsonify({'success': False, 'message': 'AI用户不能删除'})

        db.session.delete(user)

        db.session.commit()

        return jsonify({'success': True})

    return jsonify({'success': False, 'message': '用户不存在'})



@backend_bp.route("/api/user/update", methods=['POST'])

@admin_required

def update_user():

    data = request.get_json()

    id = data.get('id')

    user = User.query.get(id)

    if user:

        user.nickname = data.get('nickname')

        password = data.get('password')

        if password:

            user.set_password(password)

        db.session.commit()

        return jsonify({'success': True})

    return jsonify({'success': False, 'message': '用户不存在'})



@backend_bp.route("/api/user/ban", methods=['POST'])

@admin_required

def ban_user():

    data = request.get_json()

    id = data.get('id')

    ban = data.get('ban')

    user = User.query.get(id)

    if user:

        if user.user_code == 'ai_bot':

             return jsonify({'success': False, 'message': 'AI用户不能封禁'})

        user.is_banned = ban

        db.session.commit()

        return jsonify({'success': True})

    return jsonify({'success': False, 'message': '用户不存在'})





# Rooms

@backend_bp.route("/rooms")

@admin_required

def room_list():

    return render_template('admin/room_list.html')



@backend_bp.route("/api/rooms")

@admin_required

def get_rooms():

    page = request.args.get('page', 1, type=int)

    limit = request.args.get('limit', 20, type=int)

    

    pagination = Room.query.filter(Room.code != None).order_by(Room.created_at.desc()).paginate(page=page, per_page=limit, error_out=False)

    

    data = []

    for r in pagination.items:

        d = r.to_dict()

        d['owner_name'] = r.owner.nickname if r.owner else 'Unknown'

        data.append(d)

        

    return jsonify({

        'code': 0,

        'msg': '',

        'count': pagination.total,

        'data': data

    })



@backend_bp.route("/api/room/delete", methods=['POST'])

@admin_required

def delete_room():

    data = request.get_json()

    id = data.get('id')

    room = Room.query.get(id)

    if room:

        db.session.delete(room)

        db.session.commit()

        return jsonify({'success': True})

    return jsonify({'success': False})



@backend_bp.route("/api/room/ban", methods=['POST'])

@admin_required

def ban_room():

    data = request.get_json()

    id = data.get('id')

    is_banned = data.get('is_banned')

    room = Room.query.get(id)

    if room:

        room.is_banned = is_banned

        db.session.commit()

        return jsonify({'success': True})

    return jsonify({'success': False})



@backend_bp.route("/api/room/members")

@admin_required

def get_room_members():

    room_id = request.args.get('room_id')

    room = Room.query.get(room_id)

    if not room:

        return jsonify({'code': 1, 'msg': '房间不存在', 'data': []})

    

    data = []

    for member in room.members:

        user = member.user

        data.append({

            'username': user.username,

            'nickname': user.nickname,

            'is_banned': user.is_banned,

            'joined_at': member.joined_at.strftime('%Y-%m-%d %H:%M')

        })

    return jsonify({'code': 0, 'data': data})



@backend_bp.route("/api/room/announcement")

@admin_required

def get_room_announcement():

    room_id = request.args.get('room_id')

    room = Room.query.get(room_id)

    if room:

        return jsonify({'success': True, 'announcement': room.announcement})

    return jsonify({'success': False, 'message': '房间不存在'})



@backend_bp.route("/api/room/announcement/update", methods=['POST'])

@admin_required

def update_room_announcement():

    data = request.get_json()

    id = data.get('id')

    announcement = data.get('announcement')

    room = Room.query.get(id)

    if room:

        room.announcement = announcement

        room.announcement_time = datetime.utcnow()

        db.session.commit()

        return jsonify({'success': True})

    return jsonify({'success': False, 'message': '房间不存在'})



@backend_bp.route("/api/room/messages")

@admin_required

def get_room_messages():

    room_id = request.args.get('room_id')

    page = request.args.get('page', 1, type=int)

    limit = request.args.get('limit', 20, type=int)

    

    pagination = Message.query.filter_by(room_id=room_id).order_by(Message.timestamp.desc()).paginate(page=page, per_page=limit, error_out=False)

    

    return jsonify({

        'code': 0, 

        'msg': '', 

        'count': pagination.total,

        'data': [m.to_dict() for m in pagination.items]

    })



# Files (Messages)

@backend_bp.route("/files")

@admin_required

def file_list():

    return render_template('admin/file_list.html')



@backend_bp.route("/api/files")

@admin_required

def get_files():

    page = request.args.get('page', 1, type=int)

    limit = request.args.get('limit', 20, type=int)

    

    pagination = Message.query.filter(Message.msg_type.in_(['image', 'file', 'audio'])).order_by(Message.timestamp.desc()).paginate(page=page, per_page=limit, error_out=False)

    

    data = []

    for m in pagination.items:

        d = m.to_dict()

        d['sender_name'] = m.sender.nickname if m.sender else 'Unknown'

        d['room_name'] = m.room.name if m.room else 'Unknown'

        data.append(d)

        

    return jsonify({

        'code': 0,

        'msg': '',

        'count': pagination.total,

        'data': data

    })



@backend_bp.route("/api/file/delete", methods=['POST'])

@admin_required

def delete_file():

    data = request.get_json()

    id = data.get('id')

    msg = Message.query.get(id)

    if msg:

        db.session.delete(msg)

        db.session.commit()

        return jsonify({'success': True})

    return jsonify({'success': False})



# Servers

@backend_bp.route("/servers")

@admin_required

def server_list():

    return render_template('admin/server_list.html')



@backend_bp.route("/api/servers")

@admin_required

def get_servers():

    configs = ServerConfig.query.all()

    return jsonify({

        'code': 0,

        'msg': '',

        'count': len(configs),

        'data': [c.to_dict() for c in configs]

    })



@backend_bp.route("/api/server/save", methods=['POST'])

@admin_required

def save_server():

    data = request.get_json()

    id = data.get('id')

    if id:

        server = ServerConfig.query.get(id)

        server.name = data.get('name')

        server.ws_url = data.get('ws_url')

    else:

        server = ServerConfig(

            name=data.get('name'),

            ws_url=data.get('ws_url')

        )

        db.session.add(server)

    db.session.commit()

    return jsonify({'success': True})



@backend_bp.route("/api/server/delete", methods=['POST'])

@admin_required

def delete_server():

    data = request.get_json()

    id = data.get('id')

    server = ServerConfig.query.get(id)

    if server:

        db.session.delete(server)

        db.session.commit()

        return jsonify({'success': True})

    return jsonify({'success': False})



# Interfaces

@backend_bp.route("/interfaces")

@admin_required

def interface_list():

    return render_template('admin/interface_list.html')



@backend_bp.route("/api/interfaces")

@admin_required

def get_interfaces():

    page = request.args.get('page', 1, type=int)

    limit = request.args.get('limit', 20, type=int)

    pagination = ThirdPartyAPI.query.paginate(page=page, per_page=limit, error_out=False)

    return jsonify({

        'code': 0, 'msg': '', 'count': pagination.total,

        'data': [item.to_dict() for item in pagination.items]

    })



@backend_bp.route("/api/interface/save", methods=['POST'])

@admin_required

def save_interface():

    data = request.get_json()

    id = data.get('id')

    name = data.get('name')

    command = data.get('command')

    api_url = data.get('api_url')

    api_token = data.get('api_token')



    existing = ThirdPartyAPI.query.filter_by(command=command).first()

    if existing and (not id or int(id) != existing.id):

        return jsonify({'success': False, 'message': '指令已存在'})



    if id:

        api = ThirdPartyAPI.query.get(id)

        if api:

            api.name = name

            api.command = command

            api.api_url = api_url

            api.api_token = api_token

    else:

        api = ThirdPartyAPI(name=name, command=command, api_url=api_url, api_token=api_token)

        db.session.add(api)

    

    db.session.commit()

    return jsonify({'success': True})



@backend_bp.route("/api/interface/delete", methods=['POST'])

@admin_required

def delete_interface():

    data = request.get_json()

    id = data.get('id')

    api = ThirdPartyAPI.query.get(id)

    if api:

        db.session.delete(api)

        db.session.commit()

        return jsonify({'success': True})

    return jsonify({'success': False})



@backend_bp.route("/api/interface/toggle", methods=['POST'])

@admin_required

def toggle_interface():

    data = request.get_json()

    id = data.get('id')

    is_enabled = data.get('is_enabled')

    api = ThirdPartyAPI.query.get(id)

    if api:

        api.is_enabled = is_enabled

        db.session.commit()

        return jsonify({'success': True})

    return jsonify({'success': False})



# AI Models

@backend_bp.route("/ai-models")

@admin_required

def ai_model_list():

    return render_template('admin/ai_model_list.html')



@backend_bp.route("/api/ai-models")

@admin_required

def get_ai_models():

    page = request.args.get('page', 1, type=int)

    limit = request.args.get('limit', 20, type=int)

    pagination = AIModel.query.paginate(page=page, per_page=limit, error_out=False)

    return jsonify({

        'code': 0, 'msg': '', 'count': pagination.total,

        'data': [m.to_dict() for m in pagination.items]

    })



@backend_bp.route("/api/ai-model/save", methods=['POST'])

@admin_required

def save_ai_model():

    data = request.get_json()

    id = data.get('id')

    if id:

        model = AIModel.query.get(id)

        model.name = data.get('name')

        model.model_name = data.get('model_name')

        model.api_url = data.get('api_url')

        model.api_key = data.get('api_key')

        if data.get('is_default'):

            AIModel.query.update({AIModel.is_default: False})

            model.is_default = True

    else:

        if data.get('is_default'):

             AIModel.query.update({AIModel.is_default: False})

        model = AIModel(

            name=data.get('name'),

            model_name=data.get('model_name'),

            api_url=data.get('api_url'),

            api_key=data.get('api_key'),

            is_default=data.get('is_default', False)

        )

        db.session.add(model)

    db.session.commit()

    return jsonify({'success': True})



@backend_bp.route("/api/ai-model/delete", methods=['POST'])

@admin_required

def delete_ai_model():

    data = request.get_json()

    id = data.get('id')

    model = AIModel.query.get(id)

    if model:

        db.session.delete(model)

        db.session.commit()

        return jsonify({'success': True})

    return jsonify({'success': False})



@backend_bp.route("/api/ai-model/toggle", methods=['POST'])

@admin_required

def toggle_ai_model():

    data = request.get_json()

    id = data.get('id')

    is_enabled = data.get('is_enabled')

    model = AIModel.query.get(id)

    if model:

        model.is_enabled = is_enabled

        db.session.commit()

        return jsonify({'success': True})

    return jsonify({'success': False})



@backend_bp.route("/api/ai-model/set-default", methods=['POST'])

@admin_required

def set_default_ai_model():

    data = request.get_json()

    id = data.get('id')

    

    # Unset all

    AIModel.query.update({AIModel.is_default: False})

    

    # Set target

    model = AIModel.query.get(id)

    if model:

        model.is_default = True

        db.session.commit()

        return jsonify({'success': True})

    

    db.session.commit() # Commit the unset all if target not found (though unlikely UI flow)

    return jsonify({'success': False, 'message': '模型不存在'})



@backend_bp.route("/api/ai-model/test", methods=['POST'])

@admin_required

def test_ai_model():

    data = request.get_json()

    model_id = data.get('id')

    message = data.get('message')

    

    model = AIModel.query.get(model_id)

    if not model:

        def error_generator():

            yield f"data: {json.dumps({'error': '模型不存在'}, ensure_ascii=False)}\n\n"

        return Response(stream_with_context(error_generator()), mimetype='text/event-stream')



    client = OpenAI(api_key=model.api_key, base_url=model.api_url)



    def generate():

        try:

            stream = client.chat.completions.create(

                model=model.model_name,

                messages=[{"role": "user", "content": message}],

                stream=True

            )

            for chunk in stream:

                content = chunk.choices[0].delta.content

                if content:

                    yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"

        except Exception as e:

            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"



    return Response(stream_with_context(generate()), mimetype='text/event-stream')



# Dashboard
@backend_bp.route("/dashboard")
@admin_required
def dashboard():
    return render_template('admin/dashboard.html')

@backend_bp.route("/api/dashboard/data")
@admin_required
def get_dashboard_data():
    # 1. Basic Stats
    total_users = User.query.count()
    total_rooms = Room.query.count()
    
    today = datetime.utcnow().date()
    today_start = datetime(today.year, today.month, today.day)
    
    today_messages = Message.query.filter(Message.timestamp >= today_start).count()
    
    # Active users today
    active_users_count = db.session.query(func.count(func.distinct(Message.user_id))).filter(Message.timestamp >= today_start, Message.user_id.isnot(None)).scalar()
    
    # 2. Charts Data
    # Room Member Distribution (Top 5 rooms)
    top_rooms = db.session.query(Room.name, func.count(RoomMember.id)).join(RoomMember).group_by(Room.id).order_by(func.count(RoomMember.id).desc()).limit(5).all()
    room_stats = [{'name': r[0], 'value': r[1]} for r in top_rooms]
    
    # Message Trend (Last 7 days) - Simplified for now (just hours of today or similar)
    # Let's do messages per hour for today
    msgs_by_hour = db.session.query(func.strftime('%H', Message.timestamp), func.count(Message.id)).filter(Message.timestamp >= today_start).group_by(func.strftime('%H', Message.timestamp)).all()
    # Fill gaps
    hours = [f"{i:02d}" for i in range(24)]
    msg_counts = {h: 0 for h in hours}
    for h, count in msgs_by_hour:
        msg_counts[h] = count
    
    line_chart_data = {'categories': hours, 'data': [msg_counts[h] for h in hours]}

    # 3. Warnings (Simple keyword filter on recent messages)
    keywords = ['fuck', 'shit', 'die', 'hack', 'stupid', 'admin', 'root', 'error', 'fail', 'warning'] # Example keywords
    recent_msgs = Message.query.order_by(Message.timestamp.desc()).limit(100).all()
    warnings = []
    for m in recent_msgs:
        if m.content and any(k in m.content.lower() for k in keywords):
            warnings.append({
                'user': m.user.nickname if m.user else 'Unknown',
                'content': m.content[:20] + '...' if len(m.content) > 20 else m.content,
                'room': m.room.name,
                'time': m.timestamp.strftime('%H:%M:%S'),
                'level': 'High' 
            })
    
    # 4. Room Activity List
    active_rooms_query = db.session.query(Room.name, func.count(Message.id)).join(Message).filter(Message.timestamp >= today_start).group_by(Room.id).order_by(func.count(Message.id).desc()).limit(10).all()
    active_rooms = [{'name': r[0], 'msg_count': r[1]} for r in active_rooms_query]

    return jsonify({
        'stats': {
            'total_users': total_users,
            'total_rooms': total_rooms,
            'today_messages': today_messages,
            'active_users': active_users_count or 0
        },
        'charts': {
            'room_distribution': room_stats,
            'message_trend': line_chart_data
        },
        'warnings': warnings[:5], # Top 5 recent
        'active_rooms': active_rooms
    })

@backend_bp.route("/api/dashboard/ai-report")
@admin_required
def dashboard_ai_report():
    total_users = User.query.count()
    today = datetime.utcnow().date()
    today_start = datetime(today.year, today.month, today.day)
    today_msgs = Message.query.filter(Message.timestamp >= today_start).count()
    active_users = db.session.query(func.count(func.distinct(Message.user_id))).filter(Message.timestamp >= today_start, Message.user_id.isnot(None)).scalar() or 0
    
    prompt = f"""
    You are the 'TeamChat Sentinel', an AI system monitor for a sci-fi dashboard.
    Current System Status:
    - Users: {total_users}
    - Messages Today: {today_msgs}
    - Active Users Today: {active_users}
    - Date: {today}
    
    Analyze this data.
    1. If activity is low, suggest initialization protocols.
    2. If high, praise system load capacity.
    3. Generate a "System Status Report" (max 80 words) formatted with HTML (use <span style="color:#00ff00"> for good, #ff0000 for alert).
    4. Style it like a futuristic computer log.
    """
    
    def generate():
        client = OpenAI(
            api_key=current_app.config.get('OPENAI_API_KEY'),
            base_url=current_app.config.get('OPENAI_BASE_URL')
        )
        
        # Determine model
        model_name = "gpt-3.5-turbo" 
        default_model = AIModel.query.filter_by(is_default=True).first()
        if default_model:
            model_name = default_model.model_name
            
        try:
            stream = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": prompt}],
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield f"data: {json.dumps({'text': chunk.choices[0].delta.content})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


# AI Analysis
@backend_bp.route("/ai-analysis")
@admin_required
def ai_analysis():
    return render_template('admin/ai_analysis.html')

@backend_bp.route("/api/ai-analysis/chat", methods=['POST'])
@admin_required
def ai_analysis_chat():
    data = request.get_json()
    user_message = data.get('message')
    
    # Get DB Schema
    inspector = db.inspect(db.engine)
    table_names = inspector.get_table_names()
    schema_info = []
    for table in table_names:
        columns = inspector.get_columns(table)
        col_strs = [f"{col['name']} ({col['type']})" for col in columns]
        schema_info.append(f"Table {table}: {', '.join(col_strs)}")
        # Foreign keys
        try:
            fks = inspector.get_foreign_keys(table)
            for fk in fks:
                schema_info.append(f"  FK {table}.{fk['constrained_columns'][0]} -> {fk['referred_table']}.{fk['referred_columns'][0]}")
        except:
            pass
            
    schema_str = "\n".join(schema_info)
    
    system_prompt = f"""You are an expert Data Analyst for the TeamChat application.
    Database Schema (SQLite):
    {schema_str}
    
    Rules:
    1. You can execute SQL queries to answer user questions.
    2. ONLY execute SELECT statements. INSERT, UPDATE, DELETE, DROP are strictly PROHIBITED.
    3. If the user asks for data analysis, query the data first, then summarize it.
    4. Use Markdown for formatting tables and lists.
    5. Be concise and professional.
    """
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "execute_sql",
                "description": "Execute a SQL SELECT query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The SQL query to execute (SELECT only)"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    def generate():
        client = OpenAI(
            api_key=current_app.config.get('OPENAI_API_KEY'),
            base_url=current_app.config.get('OPENAI_BASE_URL')
        )
        
        # Determine model
        model_name = "gpt-3.5-turbo" 
        default_model = AIModel.query.filter_by(is_default=True).first()
        if default_model:
            model_name = default_model.model_name
            
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        try:
            # Report status: Analyzing
            yield f"data: {json.dumps({'status': 'analyzing', 'message': '正在分析您的意图...'}, ensure_ascii=False)}\n\n"

            # 1. First call: Check for intent/tool usage (non-streaming)
            completion = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=False
            )
            
            message = completion.choices[0].message
            
            if message.tool_calls:
                messages.append(message) # Append assistant's intent
                
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "execute_sql":
                        try:
                            args = json.loads(tool_call.function.arguments)
                            query = args.get("query")
                            
                            # Report status: Executing SQL
                            yield f"data: {json.dumps({'status': 'executing', 'message': f'正在执行查询: {query}'}, ensure_ascii=False)}\n\n"

                            if not query.lower().strip().startswith("select"):
                                result = "Error: Only SELECT queries are allowed."
                            else:
                                result_proxy = db.session.execute(text(query))
                                keys = result_proxy.keys()
                                result_list = [dict(zip(keys, row)) for row in result_proxy]
                                result = json.dumps(result_list, default=str, ensure_ascii=False)
                        except Exception as e:
                            result = f"SQL Error: {str(e)}"
                        
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": "execute_sql",
                            "content": result
                        })
                
                # Report status: Generating Response
                yield f"data: {json.dumps({'status': 'generating', 'message': '正在整理数据并生成报告...'}, ensure_ascii=False)}\n\n"

                # 2. Second call: Stream the interpretation
                stream = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    stream=True
                )
                for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
            
            else:
                # No tool call, return content
                content = message.content
                yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"

        except Exception as e:
            print(f"AI Analysis Error: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


# Menus
@backend_bp.route("/menus")
@admin_required
def menu_list():
    return render_template('admin/menu_list.html')

@backend_bp.route("/api/menus")
@admin_required
def get_menus():
    menus = Menu.query.order_by(Menu.order).all()
    return jsonify({
        'code': 0, 'msg': '', 'count': len(menus),
        'data': [m.to_dict() for m in menus]
    })

@backend_bp.route("/api/menu/save", methods=['POST'])
@admin_required
def save_menu():
    data = request.get_json()
    id = data.get('id')
    
    if id:
        menu = Menu.query.get(id)
        if menu:
            menu.name = data.get('name')
            menu.url = data.get('url')
            menu.icon = data.get('icon')
            menu.order = data.get('order', 0)
    else:
        menu = Menu(
            name=data.get('name'),
            url=data.get('url'),
            icon=data.get('icon'),
            order=data.get('order', 0)
        )
        db.session.add(menu)
    
    db.session.commit()
    return jsonify({'success': True})

@backend_bp.route("/api/menu/delete", methods=['POST'])
@admin_required
def delete_menu():
    data = request.get_json()
    id = data.get('id')
    menu = Menu.query.get(id)
    if menu:
        db.session.delete(menu)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

# Roles
@backend_bp.route("/roles")
@admin_required
def role_list():
    return render_template('admin/role_list.html')

@backend_bp.route("/api/roles")
@admin_required
def get_roles():
    roles = Role.query.all()
    return jsonify({
        'code': 0, 'msg': '', 'count': len(roles),
        'data': [r.to_dict() for r in roles]
    })

@backend_bp.route("/api/role/save", methods=['POST'])
@admin_required
def save_role():
    data = request.get_json()
    id = data.get('id')
    name = data.get('name')
    menu_ids = data.get('menu_ids', [])
    
    if id:
        role = Role.query.get(id)
        if role:
            role.name = name
    else:
        role = Role(name=name)
        db.session.add(role)
    
    # Update menus
    if role:
        # Clear existing menus
        role.menus = []
        # Add new menus
        if menu_ids:
            menus = Menu.query.filter(Menu.id.in_(menu_ids)).all()
            role.menus = menus
            
    db.session.commit()
    return jsonify({'success': True})

@backend_bp.route("/api/role/delete", methods=['POST'])
@admin_required
def delete_role():
    data = request.get_json()
    id = data.get('id')
    role = Role.query.get(id)
    if role:
        db.session.delete(role)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@backend_bp.route("/api/role/menus")
@admin_required
def get_role_menus():
    role_id = request.args.get('role_id')
    role = Role.query.get(role_id)
    if role:
        return jsonify({'success': True, 'menu_ids': [m.id for m in role.menus]})
    return jsonify({'success': False, 'menu_ids': []})

# Admins
@backend_bp.route("/admins")
@admin_required
def admin_list():
    return render_template('admin/admin_list.html')

@backend_bp.route("/api/admins")
@admin_required
def get_admins():
    admins = Admin.query.all()
    data = []
    for a in admins:
        d = a.to_dict()
        d['role_ids'] = [r.id for r in a.roles]
        data.append(d)
    return jsonify({
        'code': 0, 'msg': '', 'count': len(admins),
        'data': data
    })

@backend_bp.route("/api/admin/save", methods=['POST'])
@admin_required
def save_admin():
    data = request.get_json()
    id = data.get('id')
    username = data.get('username')
    password = data.get('password')
    role_ids = data.get('role_ids', [])
    
    if id:
        admin = Admin.query.get(id)
        if admin:
            admin.username = username
            if password:
                admin.set_password(password)
    else:
        existing = Admin.query.filter_by(username=username).first()
        if existing:
            return jsonify({'success': False, 'message': '用户名已存在'})
        admin = Admin(username=username)
        admin.set_password(password)
        db.session.add(admin)
        
    # Update roles
    if admin:
        admin.roles = []
        if role_ids:
            roles = Role.query.filter(Role.id.in_(role_ids)).all()
            admin.roles = roles
            
    db.session.commit()
    return jsonify({'success': True})

@backend_bp.route("/api/admin/delete", methods=['POST'])
@admin_required
def delete_admin():
    data = request.get_json()
    id = data.get('id')
    admin = Admin.query.get(id)
    if admin:
        if admin.username == 'admin':
            return jsonify({'success': False, 'message': '超级管理员不能删除'})
        db.session.delete(admin)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})
