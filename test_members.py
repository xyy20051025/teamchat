import requests

def test_members():
    base_url = 'http://10.95.29.130:5000'
    session = requests.Session()
    
    # 1. Login
    login_data = {'nickname': 'testuser_info', 'password': 'password123'}
    # Try login, if fails try register then login
    res = session.post(f'{base_url}/', data=login_data)
    
    if res.status_code != 200 or '登录' in res.text: # If login page returned, login failed
        print("Login failed, trying to register...")
        reg_data = {'username': 'testuser_info', 'password': 'password123'}
        session.post(f'{base_url}/register', json=reg_data)
        res = session.post(f'{base_url}/', data=login_data)
        
    if res.status_code != 200:
        print("Login failed completely")
        return

    print("Login successful")

    # Join Group 1
    join_res = session.post(f'{base_url}/api/group/join', json={'room_id': 1})
    print(f"Join: {join_res.json()}")

    # 2. Get Members for Room 1
    res = session.get(f'{base_url}/api/room/1/members')
    print(f"Status: {res.status_code}")
    print(f"Response: {res.json()}")

if __name__ == '__main__':
    test_members()