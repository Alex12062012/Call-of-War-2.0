from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import hashlib, json, os, random
from collections import deque

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'openfront_dev_key_CHANGE_IN_PROD')

# ================== CONFIG ==================
USERS_FILE = "strategy_users.json"
SAVES_DIR = "strategy_saves"
os.makedirs(SAVES_DIR, exist_ok=True)

MAP_SIZE = 40  # Réduit pour de meilleures perfs
CELL_SIZE = 16  # Plus gros pour mieux voir
COLORS = ["#FF0000", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E2", "#F8B739", "#52BE80"]
BOT_NAMES = ["Empire Rouge", "Royaume Bleu", "Nation Verte", "Alliance Jaune", "Confédération Violette", 
             "Coalition Orange", "Fédération Rose", "Union Turquoise", "République Cyan", "Ligue Magenta"]

# ================== UTILS ==================
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def load_users():
    try:
        return json.load(open(USERS_FILE, encoding='utf-8')) if os.path.exists(USERS_FILE) else {}
    except:
        return {}

def save_users(u):
    try:
        json.dump(u, open(USERS_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    except:
        pass

def generate_map():
    """Génère une carte avec terrain"""
    terrain = [[0 for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
    
    # Génération par clusters plus denses
    num_continents = random.randint(4, 7)
    for _ in range(num_continents):
        cx, cy = random.randint(5, MAP_SIZE-5), random.randint(5, MAP_SIZE-5)
        size = random.randint(6, 12)
        
        for x in range(max(0, cx-size), min(MAP_SIZE, cx+size)):
            for y in range(max(0, cy-size), min(MAP_SIZE, cy+size)):
                dist = ((x-cx)**2 + (y-cy)**2)**0.5
                if dist < size and random.random() > 0.15:
                    terrain[y][x] = 1
    
    return terrain

def init_game(username):
    """Initialise une nouvelle partie"""
    terrain = generate_map()
    land_positions = [(x, y) for y in range(MAP_SIZE) for x in range(MAP_SIZE) if terrain[y][x] == 1]
    
    if len(land_positions) < 11:
        return init_game(username)  # Régénérer si pas assez de terre
    
    random.shuffle(land_positions)
    
    players = []
    ownership = [[-1 for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
    cities = {}
    troops_per_cell = {}  # Troupes par case
    
    # Player humain (ID 0)
    px, py = land_positions.pop()
    players.append({
        "id": 0,
        "name": username,
        "color": "#FF0000",
        "gold": 500,
        "is_bot": False
    })
    ownership[py][px] = 0
    troops_per_cell[f"{px},{py}"] = 100
    
    # 5 Bots (réduit pour meilleures perfs)
    for i in range(5):
        if not land_positions:
            break
        bx, by = land_positions.pop()
        players.append({
            "id": i+1,
            "name": BOT_NAMES[i],
            "color": COLORS[i],
            "gold": 500,
            "is_bot": True
        })
        ownership[by][bx] = i+1
        troops_per_cell[f"{bx},{by}"] = 100
    
    return {
        "terrain": terrain,
        "ownership": ownership,
        "players": players,
        "cities": cities,
        "troops": troops_per_cell,
        "turn": 0,
        "history": []
    }

def get_neighbors(x, y):
    neighbors = []
    for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
        nx, ny = x + dx, y + dy
        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE:
            neighbors.append((nx, ny))
    return neighbors

def get_player_territories(game, player_id):
    """Retourne les territoires d'un joueur (optimisé)"""
    territories = []
    for y in range(MAP_SIZE):
        for x in range(MAP_SIZE):
            if game['ownership'][y][x] == player_id:
                territories.append((x, y))
    return territories

def get_total_troops(game, player_id):
    """Compte les troupes totales d'un joueur"""
    total = 0
    for y in range(MAP_SIZE):
        for x in range(MAP_SIZE):
            if game['ownership'][y][x] == player_id:
                key = f"{x},{y}"
                total += game['troops'].get(key, 0)
    return total

def bot_ai(game, bot_id):
    """IA des bots - améliorée"""
    bot = game['players'][bot_id]
    my_territories = get_player_territories(game, bot_id)
    
    if not my_territories:
        return
    
    # Revenus
    bot['gold'] += len(my_territories) * 2
    
    # Produire des troupes sur chaque territoire
    for x, y in my_territories:
        key = f"{x},{y}"
        game['troops'][key] = game['troops'].get(key, 0) + 2
        
        # Bonus ville
        if key in game['cities'] and game['cities'][key]['owner'] == bot_id:
            game['troops'][key] += 10
    
    # Construire une ville (10% chance)
    if bot['gold'] >= 300 and random.random() < 0.1 and my_territories:
        cx, cy = random.choice(my_territories)
        city_key = f"{cx},{cy}"
        if city_key not in game['cities']:
            game['cities'][city_key] = {"owner": bot_id}
            bot['gold'] -= 300
            return
    
    # Attaquer
    for cx, cy in my_territories:
        my_troops = game['troops'].get(f"{cx},{cy}", 0)
        
        if my_troops < 50:
            continue
        
        for nx, ny in get_neighbors(cx, cy):
            enemy_id = game['ownership'][ny][nx]
            
            if enemy_id == -1 and game['terrain'][ny][nx] == 1:
                # Conquête neutre
                enemy_troops = 20
            elif enemy_id != -1 and enemy_id != bot_id:
                enemy_troops = game['troops'].get(f"{nx},{ny}", 0)
            else:
                continue
            
            # Attaquer si on a 1.5x plus de troupes
            if my_troops > enemy_troops * 1.5:
                attack_troops = int(my_troops * 0.6)
                perform_attack(game, bot_id, cx, cy, nx, ny, attack_troops)
                return

def perform_attack(game, attacker_id, fx, fy, tx, ty, troops):
    """Combat amélioré - plus équilibré"""
    defender_id = game['ownership'][ty][tx]
    from_key = f"{fx},{fy}"
    to_key = f"{tx},{ty}"
    
    attacker_troops = min(troops, game['troops'].get(from_key, 0))
    defender_troops = game['troops'].get(to_key, 20 if defender_id == -1 else 0)
    
    # Combat
    attack_power = attacker_troops * random.uniform(0.9, 1.1)
    defense_power = defender_troops * random.uniform(1.3, 1.6)  # Bonus défenseur
    
    if attack_power > defense_power:
        # Victoire
        game['ownership'][ty][tx] = attacker_id
        game['troops'][from_key] = max(0, game['troops'].get(from_key, 0) - int(attacker_troops * 0.4))
        game['troops'][to_key] = int(attacker_troops * 0.6)
        
        # Supprimer ville ennemie
        if to_key in game['cities'] and game['cities'][to_key]['owner'] != attacker_id:
            del game['cities'][to_key]
        
        attacker_name = game['players'][attacker_id]['name']
        game['history'].append(f"⚔️ {attacker_name} conquiert ({tx},{ty})")
    else:
        # Défaite
        game['troops'][from_key] = max(0, game['troops'].get(from_key, 0) - int(attacker_troops * 0.7))
        if defender_id != -1:
            game['troops'][to_key] = max(10, int(defender_troops * 0.7))

def load_game(user):
    try:
        f = os.path.join(SAVES_DIR, f"{user}_game.json")
        if os.path.exists(f):
            return json.load(open(f, encoding='utf-8'))
    except:
        pass
    return init_game(user)

def save_game_to_file(user, data):
    try:
        f = os.path.join(SAVES_DIR, f"{user}_game.json")
        json.dump(data, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    except:
        pass

# ================== STYLES ==================
BASE_STYLE = """
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Segoe UI', Tahoma, sans-serif;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    color: white;
    overflow: hidden;
}
.container { display: flex; height: 100vh; }
.sidebar {
    width: 320px;
    background: rgba(0,0,0,0.7);
    padding: 20px;
    overflow-y: auto;
}
.map-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    overflow: auto;
}
.game-map {
    display: grid;
    grid-template-columns: repeat(""" + str(MAP_SIZE) + f""", {CELL_SIZE}px);
    gap: 1px;
    border: 3px solid #fff;
    background: #000;
}}
.cell {{
    width: {CELL_SIZE}px;
    height: {CELL_SIZE}px;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
}}
.cell:hover {{
    transform: scale(1.2);
    z-index: 10;
    box-shadow: 0 0 10px white;
}}
.cell.city::after {{
    content: '🏰';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 10px;
}}
.btn {{
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    padding: 12px 20px;
    border-radius: 8px;
    cursor: pointer;
    width: 100%;
    margin: 5px 0;
    font-size: 0.95em;
    transition: all 0.2s;
}}
.btn:hover {{ opacity: 0.9; transform: translateY(-2px); }}
.stat {{
    background: rgba(255,255,255,0.15);
    padding: 12px;
    border-radius: 8px;
    margin: 10px 0;
}}
.player-item {{
    padding: 10px;
    margin: 5px 0;
    border-radius: 6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.9em;
}}
h2 {{ font-size: 1.2em; margin: 15px 0 10px 0; }}
.modal {{
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: #1a1a2e;
    padding: 30px;
    border-radius: 12px;
    border: 2px solid #667eea;
    z-index: 1000;
    min-width: 400px;
}}
.overlay {{
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.85);
    z-index: 999;
}}
.history {{
    background: rgba(0,0,0,0.3);
    padding: 10px;
    border-radius: 6px;
    max-height: 150px;
    overflow-y: auto;
    font-size: 0.85em;
}}
.history p {{ margin: 3px 0; }}
.troop-count {{
    position: absolute;
    bottom: 2px;
    right: 2px;
    font-size: 8px;
    font-weight: bold;
    color: white;
    text-shadow: 0 0 2px black;
}}
</style>
"""

# ================== ROUTES ==================
@app.route("/")
def home():
    return render_template_string(BASE_STYLE + """
    <body><div class="container" style="align-items:center;justify-content:center;flex-direction:column;">
        <h1 style="font-size:3em;margin-bottom:20px;">🎮 OpenFront Strategy</h1>
        <p style="font-size:1.2em;margin:20px 0;">Jeu de conquête territoriale</p>
        <a href="{{url_for('login_page')}}"><button class="btn" style="width:300px;">🚀 Commencer</button></a>
    </div></body>
    """)

@app.route("/login", methods=["GET", "POST"])
def login_page():
    msg = ""
    if request.method == "POST":
        user, pw = request.form["username"], request.form["password"]
        users = load_users()
        if user in users and users[user]["password"] == hash_pw(pw):
            session['username'] = user
            return redirect(url_for("game"))
        msg = "❌ Identifiants invalides"
    
    return render_template_string(BASE_STYLE + """
    <body><div class="container" style="align-items:center;justify-content:center;flex-direction:column;">
        <h1>🔐 Connexion</h1>
        {% if msg %}<p style="color:#ff6b6b;margin:10px 0;">{{msg}}</p>{% endif %}
        <form method="post" style="width:300px;">
            <input name="username" placeholder="Nom d'utilisateur" required 
                   style="width:100%;padding:12px;margin:10px 0;border-radius:8px;border:none;">
            <input name="password" type="password" placeholder="Mot de passe" required
                   style="width:100%;padding:12px;margin:10px 0;border-radius:8px;border:none;">
            <button class="btn" type="submit">Se connecter</button>
        </form>
        <a href="{{url_for('signup_page')}}"><button class="btn" style="width:300px;background:#f5576c;">Créer un compte</button></a>
    </div></body>
    """, msg=msg)

@app.route("/signup", methods=["GET", "POST"])
def signup_page():
    msg = ""
    if request.method == "POST":
        user, pw = request.form["username"], request.form["password"]
        users = load_users()
        if user in users:
            msg = "❌ Utilisateur existe déjà"
        else:
            users[user] = {"password": hash_pw(pw)}
            save_users(users)
            return redirect(url_for("login_page"))
    
    return render_template_string(BASE_STYLE + """
    <body><div class="container" style="align-items:center;justify-content:center;flex-direction:column;">
        <h1>📝 Inscription</h1>
        {% if msg %}<p style="color:#ff6b6b;margin:10px 0;">{{msg}}</p>{% endif %}
        <form method="post" style="width:300px;">
            <input name="username" placeholder="Nom d'utilisateur" required
                   style="width:100%;padding:12px;margin:10px 0;border-radius:8px;border:none;">
            <input name="password" type="password" placeholder="Mot de passe" required
                   style="width:100%;padding:12px;margin:10px 0;border-radius:8px;border:none;">
            <button class="btn" type="submit">S'inscrire</button>
        </form>
    </div></body>
    """, msg=msg)

@app.route("/game")
def game():
    if 'username' not in session:
        return redirect(url_for("login_page"))
    
    game_state = load_game(session['username'])
    player = game_state['players'][0]
    
    # Générer la carte
    map_html = ""
    for y in range(MAP_SIZE):
        for x in range(MAP_SIZE):
            terrain_type = "sea" if game_state['terrain'][y][x] == 0 else "land"
            owner = game_state['ownership'][y][x]
            color = game_state['players'][owner]['color'] if owner != -1 else ("#1e3a8a" if terrain_type == "sea" else "#22c55e")
            
            city_class = "city" if f"{x},{y}" in game_state['cities'] else ""
            troops = game_state['troops'].get(f"{x},{y}", 0)
            troop_display = f'<span class="troop-count">{troops}</span>' if owner != -1 and troops > 0 else ""
            
            # Afficher le nom du joueur sur son territoire principal
            label = ""
            if owner == 0 and (x, y) == get_player_territories(game_state, 0)[0]:
                label = f'<div style="position:absolute;top:-18px;left:50%;transform:translateX(-50%);white-space:nowrap;font-size:10px;font-weight:bold;color:white;text-shadow:0 0 3px black;">{player["name"]}</div>'
            
            map_html += f'<div class="cell {terrain_type} {city_class}" style="background-color:{color};position:relative;" onclick="selectCell({x},{y})">{troop_display}{label}</div>'
    
    # Classement
    players_sorted = sorted(game_state['players'], key=lambda p: len(get_player_territories(game_state, p['id'])), reverse=True)
    
    # Historique
    history_html = "<br>".join(game_state['history'][-6:])
    
    return render_template_string(BASE_STYLE + """
    <body>
    <div class="container">
        <div class="sidebar">
            <h1 style="font-size:1.5em;margin-bottom:15px;">⚔️ OpenFront</h1>
            
            <div class="stat">
                <strong>{{player['name']}}</strong><br>
                💰 Or: {{player['gold']}}<br>
                🏴 Territoires: {{territories}}<br>
                🪖 Troupes totales: {{total_troops}}
            </div>
            
            <button class="btn" onclick="nextTurn()">▶️ Terminer mon tour</button>
            <button class="btn" onclick="location.reload()">🔄 Rafraîchir</button>
            <button class="btn" onclick="location.href='/save'" style="background:#22c55e;">💾 Sauvegarder</button>
            <button class="btn" onclick="location.href='/new_game'" style="background:#f5576c;">🆕 Nouvelle partie</button>
            
            <h2>🏆 Classement</h2>
            {% for p in players_sorted %}
            <div class="player-item" style="background-color:{{p['color']}}33;border-left:4px solid {{p['color']}};">
                <span>{{p['name']}}</span>
                <span>{{p['territories']}} 🏴</span>
            </div>
            {% endfor %}
            
            <h2>📜 Historique (Tour {{game_state['turn']}})</h2>
            <div class="history">
                {{history_html|safe}}
            </div>
            
            <h2>ℹ️ Instructions</h2>
            <p style="font-size:0.85em;line-height:1.4;">
                • Cliquez sur vos territoires → menu<br>
                • Cliquez sur territoires adjacents → attaque<br>
                • Villes: +10 troupes/tour (300 or)<br>
                • +2 troupes/territoire/tour<br>
                • +2 or/territoire/tour
            </p>
        </div>
        
        <div class="map-container">
            <div class="game-map">
                {{map_html|safe}}
            </div>
        </div>
    </div>
    
    <script>
    function selectCell(x, y) {
        fetch('/api/select', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({x: x, y: y})
        })
        .then(r => r.json())
        .then(data => {
            if (data.action === 'build_menu') {
                showBuildMenu(x, y, data);
            } else if (data.action === 'attack_menu') {
                showAttackMenu(x, y, data);
            }
            if (data.message) alert(data.message);
        });
    }
    
    function showBuildMenu(x, y, data) {
        let html = `
            <div class="overlay" onclick="closeModal()"></div>
            <div class="modal">
                <h2>🏗️ Case (${x},${y})</h2>
                <p>🪖 Troupes ici: ${data.troops}<br>💰 Or: ${data.player_gold}</p>
                <button class="btn" onclick="buildCity(${x},${y})">🏰 Construire ville (300 or)</button>
                <button class="btn" onclick="closeModal()" style="background:#95a5a6;">Annuler</button>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', html);
    }
    
    function showAttackMenu(x, y, data) {
        let html = `
            <div class="overlay" onclick="closeModal()"></div>
            <div class="modal">
                <h2>⚔️ Attaquer (${x},${y})</h2>
                <p>Défenseur: ${data.defender_troops} troupes<br>Vos troupes sur (${data.from_x},${data.from_y}): ${data.my_troops}</p>
                <input type="number" id="attackTroops" value="${Math.min(data.my_troops, 50)}" min="1" max="${data.my_troops}" 
                       style="width:100%;padding:10px;margin:10px 0;border-radius:8px;border:none;color:black;">
                <button class="btn" onclick="attack(${data.from_x},${data.from_y},${x},${y}, document.getElementById('attackTroops').value)">
                    ⚔️ Attaquer
                </button>
                <button class="btn" onclick="closeModal()" style="background:#95a5a6;">Annuler</button>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', html);
    }
    
    function buildCity(x, y) {
        fetch('/api/build_city', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({x: x, y: y})
        })
        .then(r => r.json())
        .then(data => {
            alert(data.message);
            if (data.success) location.reload();
            else closeModal();
        });
    }
    
    function attack(fx, fy, tx, ty, troops) {
        fetch('/api/attack', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({fx: fx, fy: fy, tx: tx, ty: ty, troops: parseInt(troops)})
        })
        .then(r => r.json())
        .then(data => {
            alert(data.message);
            location.reload();
        });
    }
    
    function nextTurn() {
        if (!confirm('Terminer votre tour ? Les bots vont jouer.')) return;
        fetch('/api/next_turn', {method: 'POST'})
        .then(r => r.json())
        .then(data => {
            alert(data.message);
            location.reload();
        });
    }
    
    function closeModal() {
        document.querySelector('.overlay')?.remove();
        document.querySelector('.modal')?.remove();
    }
    </script>
    </body>
    """, map_html=map_html, player=player, game_state=game_state, players_sorted=[{**p, 'territories': len(get_player_territories(game_state, p['id']))} for p in players_sorted],
         territories=len(get_player_territories(game_state, 0)), total_troops=get_total_troops(game_state, 0), history_html=history_html)

@app.route("/api/select", methods=["POST"])
def api_select():
    data = request.json
    x, y = data['x'], data['y']
    game = load_game(session['username'])
    owner = game['ownership'][y][x]
    
    if owner == 0:
        return jsonify({
            "action": "build_menu",
            "troops": game['troops'].get(f"{x},{y}", 0),
            "player_gold": game['players'][0]['gold']
        })
    elif owner != 0 and owner != -1:
        # Vérifier territoire adjacent
        for nx, ny in get_neighbors(x, y):
            if game['ownership'][ny][nx] == 0:
                return jsonify({
                    "action": "attack_menu",
                    "from_x": nx,
                    "from_y": ny,
                    "my_troops": game['troops'].get(f"{nx},{ny}", 0),
                    "defender_troops": game['troops'].get(f"{x},{y}", 0)
                })
        return jsonify({"message": "❌ Pas de territoire adjacent !"})
    elif owner == -1 and game['terrain'][y][x] == 1:
        # Territoire neutre
        for nx, ny in get_neighbors(x, y):
            if game['ownership'][ny][nx] == 0:
                return jsonify({
                    "action": "attack_menu",
                    "from_x": nx,
                    "from_y": ny,
                    "my_troops": game['troops'].get(f"{nx},{ny}", 0),
                    "defender_troops": 20
                })
        return jsonify({"message": "❌ Pas de territoire adjacent !"})
    
    return jsonify({"message": "❌ Mer - non conquérable"})

@app.route("/api/build_city", methods=["POST"])
def api_build_city():
    data = request.json
    x, y = data['x'], data['y']
    game = load_game(session['username'])
    player = game['players'][0]
    
    city_key = f"{x},{y}"
    if city_key in game['cities']:
        return jsonify({"success": False, "message": "❌ Ville déjà construite !"})
    
    if player['gold'] < 300:
        return jsonify({"success": False, "message": "❌ Pas assez d'or (300 requis)"})
    
    player['gold'] -= 300
    game['cities'][city_key] = {"owner": 0}
    game['history'].append(f"🏰 {player['name']} construit une ville en ({x},{y})")
    save_game_to_file(session['username'], game)
    
    return jsonify({"success": True, "message": "✅ Ville construite !"})

@app.route("/api/attack", methods=["POST"])
def api_attack():
    data = request.json
    fx, fy, tx, ty, troops = data['fx'], data['fy'], data['tx'], data['ty'], data['troops']
    
    game = load_game(session['username'])
    perform_attack(game, 0, fx, fy, tx, ty, troops)
    save_game_to_file(session['username'], game)
    
    return jsonify({"message": "⚔️ Attaque lancée !"})

@app.route("/api/next_turn", methods=["POST"])
def api_next_turn():
    game = load_game(session['username'])
    game['turn'] += 1
    
    # Tour du joueur (revenus)
    my_territories = get_player_territories(game, 0)
    game['players'][0]['gold'] += len(my_territories) * 2
    
    for x, y in my_territories:
        key = f"{x},{y}"
        game['troops'][key] = game['troops'].get(key, 0) + 2
        
        # Bonus ville
        if key in game['cities'] and game['cities'][key]['owner'] == 0:
            game['troops'][key] += 10
    
    # Tours des bots (FIX MAJEUR)
    for i in range(1, len(game['players'])):
        if game['players'][i]['is_bot']:
            bot_ai(game, i)
    
    # Limiter l'historique
    game['history'] = game['history'][-20:]
    
    save_game_to_file(session['username'], game)
    return jsonify({"message": f"✅ Tour {game['turn']} terminé ! Les bots ont joué."})

@app.route("/save")
def save():
    if 'username' not in session:
        return redirect(url_for("login_page"))
    
    game = load_game(session['username'])
    save_game_to_file(session['username'], game)
    return redirect(url_for("game"))

@app.route("/new_game")
def new_game():
    if 'username' in session:
        new_game_state = init_game(session['username'])
        save_game_to_file(session['username'], new_game_state)
    return redirect(url_for("game"))

@app.route("/quit")
def quit():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
