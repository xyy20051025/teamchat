from flask import render_template, session, redirect, url_for, jsonify, request
from app.blueprints.game import game_bp
from app.models import User, SnakeGameMatch, SnakeGameScore
from app.extensions import db, sock
import random
import string
import json
import threading
import time

# In-memory game state storage
# { room_code: { 'players': {}, 'food': [], 'status': 'waiting', 'type': '1v1' } }
games = {}
game_threads = {}

GRID_W = 40
GRID_H = 30

@game_bp.route('/snake')
def snake_home():
    if 'user_id' not in session:
        return redirect(url_for('frontend.login'))
    return render_template('game/snake.html')

@game_bp.route('/api/snake/create', methods=['POST'])
def create_match():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    data = request.get_json()
    match_type = data.get('type', '1v1') # 1v1, 3v3, pve
    
    # Generate Code
    code = ''.join(random.choices(string.digits, k=6))
    
    # Create DB entry
    match = SnakeGameMatch(
        room_code=code,
        match_type=match_type,
        owner_id=session['user_id']
    )
    db.session.add(match)
    db.session.commit()
    
    # Init in-memory state
    games[code] = {
        'id': match.id,
        'code': code,
        'type': match_type,
        'status': 'waiting',
        'players': {}, 
        'food': [],
        'owner_id': session['user_id']
    }
    
    return jsonify({'success': True, 'room_code': code, 'type': match_type})

@game_bp.route('/api/snake/leaderboard')
def leaderboard():
    scores = SnakeGameScore.query.order_by(SnakeGameScore.score.desc()).limit(10).all()
    data = []
    for s in scores:
        data.append({
            'username': s.user.nickname or s.user.username,
            'score': s.score,
            'avatar': s.user.avatar or '/static/images/default_avatar.svg',
            'date': s.created_at.strftime('%Y-%m-%d')
        })
    return jsonify({'success': True, 'data': data})

class GameThread(threading.Thread):
    def __init__(self, room_code):
        super().__init__()
        self.room_code = room_code
        self.running = True
        self.daemon = True

    def run(self):
        print(f"Game Thread Started: {self.room_code}")
        
        # Countdown Logic
        for i in range(3, 0, -1):
            if not self.running: break
            broadcast(self.room_code, {'type': 'countdown', 'count': i})
            time.sleep(1)
            
        # Send GO signal (count 0 or specific message)
        broadcast(self.room_code, {'type': 'countdown', 'count': 0})
        
        while self.running:
            if self.room_code not in games:
                break
            
            game = games[self.room_code]
            if game['status'] != 'playing':
                time.sleep(1)
                continue
                
            update_game_logic(game)
            broadcast_game_state(self.room_code)
            
            # Check game over
            winner = check_win_condition(game)
            if winner:
                game['status'] = 'finished'
                broadcast(self.room_code, {'type': 'game_over', 'winner': winner})
                save_scores(game)
                self.running = False
                # Remove game after delay? For now just stop loop
                break
                
            time.sleep(0.2) # Game Tick (Moderate Speed)

def update_game_logic(game):
    # 1. Spawn Food if needed
    while len(game['food']) < 3: # Always 3 food items
        fx, fy = random.randint(0, GRID_W-1), random.randint(0, GRID_H-1)
        game['food'].append({'x': fx, 'y': fy})

    # 2. Move AI if PvE
    if game['type'] == 'pve' and 'ai' in game['players']:
        ai = game['players']['ai']
        if ai['alive']:
            # Simple AI: Move to first food
            if game['food']:
                target = game['food'][0]
                dx = target['x'] - ai['x']
                dy = target['y'] - ai['y']
                
                # Simple pathfinding
                new_dir = ai['direction']
                if dx > 0 and ai['direction'] != 'left': new_dir = 'right'
                elif dx < 0 and ai['direction'] != 'right': new_dir = 'left'
                elif dy > 0 and ai['direction'] != 'up': new_dir = 'down'
                elif dy < 0 and ai['direction'] != 'down': new_dir = 'up'
                
                ai['direction'] = new_dir

    # 3. Move Players
    for uid, p in game['players'].items():
        if not p['alive']: continue
        
        # Calculate new head
        head_x, head_y = p['x'], p['y']
        d = p['direction']
        
        if d == 'up': head_y -= 1
        elif d == 'down': head_y += 1
        elif d == 'left': head_x -= 1
        elif d == 'right': head_x += 1
        
        # Wall Collision
        if head_x < 0 or head_x >= GRID_W or head_y < 0 or head_y >= GRID_H:
            p['alive'] = False
            continue

        # Body Collision (Self and Others)
        collision = False
        for other_uid, other_p in game['players'].items():
            if not other_p['alive']: continue
            
            # 3v3 Friendly Fire Check (Can pass through teammates)
            # But still die if hitting self
            if game['type'] == '3v3' and uid != other_uid and p.get('team') == other_p.get('team'):
                continue
                
            for part in other_p['body']:
                if head_x == part['x'] and head_y == part['y']:
                    collision = True
                    break
            if collision: break
            
        if collision:
            p['alive'] = False
            continue

        # Move Body
        p['body'].insert(0, {'x': p['x'], 'y': p['y']})
        
        # Check Food
        ate = False
        for f in game['food']:
            if head_x == f['x'] and head_y == f['y']:
                game['food'].remove(f)
                ate = True
                p['score'] += 10
                # PvE Rule: "没有吃到的一方扣10分" -> AI/Player interaction
                if game['type'] == 'pve':
                    # Find opponent
                    for oid, op in game['players'].items():
                        if oid != uid:
                            op['score'] -= 10
                break
        
        if not ate and p['body']:
            p['body'].pop() # Remove tail
            
        p['x'] = head_x
        p['y'] = head_y

def check_win_condition(game):
    # 1v1: First to 100 OR Opponent Dead
    if game['type'] == '1v1':
        alive_players = [uid for uid, p in game['players'].items() if p['alive']]
        
        # If someone died
        if len(alive_players) < len(game['players']):
            # If only 1 left, they win
            if len(alive_players) == 1:
                uid = alive_players[0]
                return {'uid': uid, 'name': game['players'][uid]['nickname']}
            # If both died (rare same tick), Draw? Or last one processed? 
            # If 0 alive, maybe random or no winner?
            if len(alive_players) == 0:
                 return {'uid': None, 'name': 'Draw (Both Crashed)'}

        for uid, p in game['players'].items():
            if p['score'] >= 100:
                return {'uid': uid, 'name': p['nickname']}
                
    # PvE: AI or Player 0 score -> Fail (Other wins) OR Death
    elif game['type'] == 'pve':
        # Check Death
        player_id = [k for k in game['players'] if k!='ai'][0]
        player = game['players'][player_id]
        ai = game['players']['ai']
        
        if not player['alive']: return {'uid': 'ai', 'name': ai['nickname']}
        if not ai['alive']: return {'uid': player_id, 'name': player['nickname']}

        # Check Score
        for uid, p in game['players'].items():
            if p['score'] <= 0:
                # Find winner (the other one)
                winner_id = 'ai' if uid != 'ai' else player_id
                winner_name = game['players'][winner_id]['nickname']
                return {'uid': winner_id, 'name': winner_name}
            if p['score'] >= 200: # Cap just in case
                return {'uid': uid, 'name': p['nickname']}

    # 3v3: Team score >= 100 OR All Team Dead
    elif game['type'] == '3v3':
        t1_alive = [p for p in game['players'].values() if p['team'] == 1 and p['alive']]
        t2_alive = [p for p in game['players'].values() if p['team'] == 2 and p['alive']]
        
        if not t1_alive: return {'team': 2, 'name': 'Team 2'}
        if not t2_alive: return {'team': 1, 'name': 'Team 1'}

        t1_score = sum(p['score'] for p in game['players'].values() if p['team'] == 1)
        t2_score = sum(p['score'] for p in game['players'].values() if p['team'] == 2)
        if t1_score >= 100: return {'team': 1, 'name': 'Team 1'}
        if t2_score >= 100: return {'team': 2, 'name': 'Team 2'}
        
    return None

def save_scores(game):
    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            # Update Match Status
            if 'id' in game:
                match = SnakeGameMatch.query.get(game['id'])
                if match:
                    match.status = 'finished'
            
            # Save Scores
            for uid, p in game['players'].items():
                if uid == 'ai': continue
                
                s = SnakeGameScore(
                    user_id=uid,
                    score=p['score'],
                    match_type=game['type']
                )
                db.session.add(s)
            
            db.session.commit()
            print(f"Scores saved for Room {game['code']}")
    except Exception as e:
        print(f"Save Score Error: {e}")

@sock.route('/ws/game/snake')
def snake_socket(ws):
    user_id = session.get('user_id')
    if not user_id:
        ws.close()
        return

    current_room = None
    
    try:
        while True:
            data = ws.receive()
            if not data: break
            
            msg = json.loads(data)
            msg_type = msg.get('type')
            
            if msg_type == 'join':
                code = msg.get('code')
                if code in games:
                    current_room = code
                    game = games[code]
                    
                    # Logic for teams/slots
                    real_players_vals = [p for uid, p in game['players'].items() if uid != 'ai']
                    count = len(real_players_vals)
                    
                    team1_count = len([p for p in real_players_vals if p['team'] == 1])
                    team2_count = len([p for p in real_players_vals if p['team'] == 2])
                    
                    max_players = 6 if game['type'] == '3v3' else 2
                    if game['type'] == 'pve': max_players = 1
                    
                    if count >= max_players:
                        ws.send(json.dumps({'type': 'error', 'message': 'Room full'}))
                        continue

                    # Assign team to balance numbers (Alternating 1 -> 2 -> 1...)
                    if team1_count <= team2_count:
                        team = 1
                    else:
                        team = 2
                        
                    # Enforce 3v3 team limit
                    if game['type'] == '3v3':
                        if team1_count >= 3: team = 2
                        if team2_count >= 3: team = 1
                    
                    # Add Player
                    px, py = random.randint(5, GRID_W-5), random.randint(5, GRID_H-5)
                    game['players'][user_id] = {
                        'ws': ws,
                        'x': px, 
                        'y': py, 
                        'score': 0 if game['type'] != 'pve' else 100,
                        'team': team,
                        'alive': True,
                        'direction': 'right',
                        'body': [{'x': px-1, 'y': py}, {'x': px-2, 'y': py}],
                        'nickname': session.get('nickname', 'Unknown'),
                        'avatar': User.query.get(user_id).avatar
                    }
                    
                    # If PvE, add AI if not present
                    if game['type'] == 'pve' and 'ai' not in game['players']:
                         ax, ay = random.randint(5, GRID_W-5), random.randint(5, GRID_H-5)
                         game['players']['ai'] = {
                            'ws': None, # No WS for AI
                            'x': ax,
                            'y': ay,
                            'score': 100,
                            'team': 2,
                            'alive': True,
                            'direction': 'left',
                            'body': [{'x': ax+1, 'y': ay}, {'x': ax+2, 'y': ay}],
                            'nickname': 'AI Bot',
                            'avatar': '/static/images/default_avatar.svg'
                        }
                    
                    broadcast_game_state(code)
                else:
                    ws.send(json.dumps({'type': 'error', 'message': 'Room not found'}))

            elif msg_type == 'input':
                if current_room and user_id in games[current_room]['players']:
                    games[current_room]['players'][user_id]['direction'] = msg.get('direction')
                    
            elif msg_type == 'start':
                 if current_room and games[current_room]['owner_id'] == user_id:
                     game = games[current_room]
                     if game['status'] == 'waiting':
                         # Check Player Count
                         player_count = len([p for uid, p in game['players'].items() if uid != 'ai'])
                         if game['type'] == '1v1' and player_count < 2:
                             ws.send(json.dumps({'type': 'error', 'message': '人数不足，需要2人才能开始'}))
                             continue
                         if game['type'] == '3v3' and player_count < 6:
                             ws.send(json.dumps({'type': 'error', 'message': '人数不足，需要6人才能开始'}))
                             continue

                         game['status'] = 'playing'
                         # Force state update to switch screens immediately
                         broadcast_game_state(current_room)
                         # Start Thread
                         if current_room not in game_threads:
                             t = GameThread(current_room)
                             game_threads[current_room] = t
                             t.start()
                             
            elif msg_type == 'chat':
                 if current_room:
                     broadcast(current_room, {
                         'type': 'chat',
                         'user': session.get('nickname'),
                         'content': msg.get('content')
                     })

    except Exception as e:
        print(f"Game WS Error: {e}")
    finally:
        if current_room and user_id in games[current_room]['players']:
            del games[current_room]['players'][user_id]
            # If room empty, thread handles cleanup eventually
            broadcast_game_state(current_room)

def broadcast_game_state(room_code):
    if room_code not in games: return
    game = games[room_code]
    
    players_data = {}
    for uid, p in game['players'].items():
        players_data[uid] = {k:v for k,v in p.items() if k != 'ws'}
        
    msg = json.dumps({
        'type': 'state',
        'players': players_data,
        'food': game['food'],
        'status': game['status'],
        'mode': game['type'],
        'owner_id': game['owner_id']
    })
    
    to_remove = []
    for uid, p in game['players'].items():
        if p.get('ws'):
            try:
                p['ws'].send(msg)
            except:
                to_remove.append(uid)
            
    for uid in to_remove:
        del game['players'][uid]

def broadcast(room_code, data):
    if room_code not in games: return
    msg = json.dumps(data)
    for p in games[room_code]['players'].values():
        if p.get('ws'):
            try:
                p['ws'].send(msg)
            except:
                pass
