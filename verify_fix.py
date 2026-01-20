import requests
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_routes():
    print(f"Testing routes on {BASE_URL}...")
    
    # 1. Test /api/public/servers
    try:
        resp = requests.get(f"{BASE_URL}/api/public/servers")
        if resp.status_code == 200:
            print("PASS: /api/public/servers is reachable.")
            print(f"Response: {resp.json()}")
        else:
            print(f"FAIL: /api/public/servers returned {resp.status_code}")
    except Exception as e:
        print(f"FAIL: Could not connect to {BASE_URL}. Is the server running? Error: {e}")
        return

    # 2. Test POST /login (should not be 405 or 404)
    try:
        # We expect a 200 OK (page render) or redirect, but definitely not 404/405
        resp = requests.post(f"{BASE_URL}/login", data={'nickname': 'test', 'password': 'test'})
        if resp.status_code in [200, 302]:
            print(f"PASS: POST /login returned {resp.status_code}")
        else:
            print(f"FAIL: POST /login returned {resp.status_code}")
    except Exception as e:
        print(f"Error testing /login: {e}")

    # 3. Test POST / (should be 405)
    try:
        resp = requests.post(f"{BASE_URL}/", data={'nickname': 'test'})
        if resp.status_code == 405:
            print("PASS: POST / correctly returns 405 Method Not Allowed")
        else:
            print(f"WARN: POST / returned {resp.status_code} (expected 405)")
    except:
        pass

if __name__ == "__main__":
    test_routes()
