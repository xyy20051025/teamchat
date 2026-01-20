
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
