import os

path = r'c:\Users\肖媛媛\Desktop\小组项目\teamwork\teamchat\app\blueprints\backend\routes.py'

with open(path, 'rb') as f:
    content = f.read()

# Find the end of the valid code
marker = b"return Response(stream_with_context(generate()), mimetype='text/event-stream')"
idx = content.find(marker)

if idx != -1:
    # Keep content up to the end of the marker line
    # Find the newline after marker
    end_idx = content.find(b'\n', idx)
    if end_idx == -1:
        end_idx = len(content)
    
    clean_content = content[:end_idx+1] # Include the newline
    
    # Dashboard code to append
    dashboard_code = '''
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
                    yield f"data: {json.dumps({'text': chunk.choices[0].delta.content})}\\n\\n"
            yield "data: [DONE]\\n\\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\\n\\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')
'''
    
    with open(path, 'wb') as f:
        f.write(clean_content)
        f.write(b'\n')
        f.write(dashboard_code.encode('utf-8'))
        
    print("Routes file fixed and updated.")

else:
    print("Marker not found, file might be different than expected.")
