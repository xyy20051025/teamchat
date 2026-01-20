
import re
path = r'c:\Users\肖媛媛\Desktop\小组项目\teamwork\teamchat\app\blueprints\backend\routes.py'
restore_path = r'c:\Users\肖媛媛\Desktop\小组项目\teamwork\teamchat\app_routes_restore.py'

with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

marker = "return Response(stream_with_context(generate()), mimetype='text/event-stream')"
indices = [m.start() for m in re.finditer(re.escape(marker), content)]

print(f"Found {len(indices)} markers.")

if len(indices) >= 2:
    # Cut after the 2nd marker (dashboard_ai_report)
    cut_point = indices[1] + len(marker)
    clean_content = content[:cut_point]
    
    with open(restore_path, 'r', encoding='utf-8') as f2:
        restore_content = f2.read()
        
    final_content = clean_content + "\n\n" + restore_content
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(final_content)
    print("Rebuilt routes.py")
else:
    print("Not enough markers found. Aborting.")
