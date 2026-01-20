import requests

def test_room_info():
    session = requests.Session()
    
    # 1. Login (or register then login)
    # Try logging in with a known user or create one
    # Assuming 'testuser' exists or register it
    base_url = 'http://10.95.29.130:5000'
    reg_data = {'username': 'testuser_info', 'password': 'password123'}
    try:
        session.post(f'{base_url}/register', json=reg_data)
    except:
        pass
    
    login_data = {'nickname': 'testuser_info', 'password': 'password123'}
    res = session.post(f'{base_url}/', data=login_data)
    
    if res.status_code != 200:
        print("Login failed")
        return

    # 2. Get Room Info for ID 1
    res = session.get(f'{base_url}/api/room/1')
    print(f"Status: {res.status_code}")
    print(f"Response: {res.json()}")

if __name__ == '__main__':
    test_room_info()
