import requests
import json

BASE_URL = "http://10.95.29.130:5000"

def test_login_issue():
    # 1. Register a user
    username = "testuser"
    password = "password123"
    print(f"Registering with username='{username}'...")
    resp = requests.post(f"{BASE_URL}/register", json={'username': username, 'password': password})
    print(f"Register response: {resp.json()}")
    
    if not resp.json().get('success'):
        print("Registration failed (maybe already exists), trying login...")

    # 2. Login with original username (should success)
    s = requests.Session()
    print(f"Logging in with username='{username}'...")
    resp = s.post(f"{BASE_URL}/", data={'nickname': username, 'password': password})
    if "趣唠 - 聊天" in resp.text or "chat-container" in resp.text:
        print("Login with username SUCCESS")
    else:
        print("Login with username FAILED")
        print(f"URL: {resp.url}")
        print(f"Content snippet: {resp.text[:500]}")
        return

    # 3. Change nickname
    new_nickname = "CoolGuy"
    print(f"Changing nickname to '{new_nickname}'...")
    # Need to access /api/me via the session
    # First we need to verify we are actually logged in. The redirect might have happened.
    # Requests automatically follows redirects for POST? Yes, by default.
    
    resp = s.post(f"{BASE_URL}/api/me", json={'nickname': new_nickname})
    print(f"Change nickname response: {resp.json()}")

    # 4. Logout (clear session)
    s.cookies.clear()
    
    # 5. Try login with NEW nickname (should fail if my hypothesis is correct)
    print(f"Attempting login with new nickname='{new_nickname}'...")
    resp = s.post(f"{BASE_URL}/", data={'nickname': new_nickname, 'password': password})
    if "趣唠 - 聊天" in resp.text or "chat-container" in resp.text:
        print("Login with NEW nickname SUCCESS (Unexpected)")
    else:
        print("Login with NEW nickname FAILED (Expected)")

    # 6. Try login with user_code (not implemented yet, but good to test if we want to add it)
    # We need to get the user code first.
    # Log in again with username
    s.post(f"{BASE_URL}/", data={'nickname': username, 'password': password})
    resp = s.get(f"{BASE_URL}/api/me")
    user_data = resp.json().get('data')
    user_code = user_data.get('user_code')
    print(f"User code is {user_code}")
    s.cookies.clear()

    print(f"Attempting login with user_code='{user_code}'...")
    resp = s.post(f"{BASE_URL}/", data={'nickname': user_code, 'password': password})
    if "趣唠 - 聊天" in resp.text or "chat-container" in resp.text:
        print("Login with user_code SUCCESS")
    else:
        print("Login with user_code FAILED")

if __name__ == "__main__":
    test_login_issue()
