
path = r'c:\Users\肖媛媛\Desktop\小组项目\teamwork\teamchat\app\blueprints\backend\routes.py'

with open(path, 'rb') as f:
    content = f.read().decode('utf-8', errors='ignore')

lines = content.split('\n')
final_lines = []
skip_next = False

for i in range(len(lines)):
    if skip_next:
        skip_next = False
        continue
        
    line = lines[i]
    
    # Fix 1: Username exists
    if "if existing:" in line.strip():
        # Look ahead 1 line
        if i+1 < len(lines):
            next_line = lines[i+1]
            if "return jsonify" in next_line and "message" in next_line and "用户名" not in next_line:
                final_lines.append(line)
                final_lines.append("            return jsonify({'success': False, 'message': '用户名已存在'})")
                skip_next = True
                continue

    # Fix 2: Superadmin delete
    if "if admin.username == 'admin':" in line.strip():
         if i+1 < len(lines):
            next_line = lines[i+1]
            if "return jsonify" in next_line and "message" in next_line and "超级管理员" not in next_line:
                final_lines.append(line)
                final_lines.append("            return jsonify({'success': False, 'message': '超级管理员不能删除'})")
                skip_next = True
                continue
            
    final_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(final_lines))
    
print("Fixed routes.py")
