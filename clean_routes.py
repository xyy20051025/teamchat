
path = r'c:\Users\肖媛媛\Desktop\小组项目\teamwork\teamchat\app\blueprints\backend\routes.py'

try:
    with open(path, 'rb') as f:
        content = f.read()

    # Remove null bytes
    clean_content = content.replace(b'\x00', b'')

    with open(path, 'wb') as f:
        f.write(clean_content)
        
    print(f"Cleaned {path}")
except Exception as e:
    print(f"Error: {e}")
