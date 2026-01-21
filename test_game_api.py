import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"

def test_game_creation():
    session = requests.Session()
    
    # 1. Login
    print("Logging in...")
    try:
        login_resp = session.post(f"{BASE_URL}/login", data={
            'nickname': 'test_user', 
            'password': 'password',
            'ws_server': ''
        })
        if login_resp.status_code != 200:
            # Maybe redirect?
            if login_resp.history:
                print("Login redirected to", login_resp.url)
            else:
                print(f"Login failed: {login_resp.status_code}")
                # Try to continue anyway if we got a cookie
    except Exception as e:
        print(f"Login error: {e}")
        return

    # 2. Create Game
    print("Creating game...")
    start_time = time.time()
    try:
        resp = session.post(f"{BASE_URL}/game/api/snake/create", 
                           json={'type': '1v1'},
                           timeout=5)
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"Request took {duration:.2f} seconds")
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success'):
                print(f"PASS: Game created successfully. Room Code: {data.get('room_code')}")
            else:
                print(f"FAIL: Game creation returned success=False. Msg: {data.get('message')}")
        else:
            print(f"FAIL: HTTP {resp.status_code} - {resp.text}")
            
    except requests.exceptions.Timeout:
        print("FAIL: Request timed out!")
    except Exception as e:
        print(f"FAIL: Error creating game: {e}")

if __name__ == "__main__":
    test_game_creation()