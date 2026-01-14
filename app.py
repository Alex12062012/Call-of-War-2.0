from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import hashlib, json, os, random
from collections import deque

app = Flask(__name__)
app.secret_key = "openfront_strategy_CHANGE_IN_PROD"

# ================== CONFIG ==================
USERS_FILE = "strategy_users.json"
SAVES_DIR = "strategy_saves"
os.makedirs(SAVES_DIR, exist_ok=True)

MAP_SIZE = 50
COLORS = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E2", "#F8B739", "#52BE80"]
BOT_NAMES = ["Empire Rouge", "Royaume Bleu", "Nation Verte", "Alliance Jaune", "Confédération Violette", 
             "Coalition Orange", "Fédération Rose", "Union Turquoise", "République Cyan", "Ligue Magenta"]

# ================== UTILS ==================
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def load_users():
    return json.load(open(USERS_FILE, encoding='utf-8')) if os.path.exists(USERS_FILE) else {}

def save_users(u):
    json.dump(u, open(USERS_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

def generate_map():
    """Génère une carte 50x50 avec terrain (0=mer, 1=terre) en utilisant perlin-like"""
    terrain = [[0 for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
    
    # Génération simple par clusters
    num_continents = random.randint(3, 6)
    for _ in range(num_continents):
        cx, cy = random.randint(5, MAP_SIZE-5), random.randint(5, MAP_SIZE-5)
        size = random.randint(8, 15)
        
        for x in range(max(0, cx-size), min(MAP_SIZE, cx+size)):
            for y in range(max(0, cy-size), min(MAP_SIZE, cy+size)):
                dist = ((x-cx)**2 + (y-cy)**2)**0.5
                if dist < size and random.random() > 0.2:
                    terrain[y][x] = 1
    
    return terrain

def init_game():
    """Initialise une nouvelle partie"""
    terrain = generate_map()
    
    # Trouver des positions de spawn sur terre
    land_positions = [(x, y) for y in range(MAP_SIZE) for x in range(MAP_SIZE) if terrain[y][x] == 1]
    random.shuffle(land_positions)
    
    players = []
    ownership = [[-1 for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
    cities = {}
    
    # Player humain (ID 0)
    if land_positions:
        px, py = land_positions.pop()
        players.append({
            "id": 0,
            "name": session.get('username', 'Joueur'),
            "color": "#FF0000",
            "troops": 1000,
            "gold": 500,
            "is_bot": False,
            "territory_count": 1
        })
        ownership[py][px] = 0
    
    # 10 Bots
    for i in range(10):
        if not land_positions:
            break
        bx, by = land_positions.pop()
        players.append({
            "id": i+1,
            "name": BOT_NAMES[i],
            "color": COLORS[i],
            "troops": 1000,
            "gold": 500,
            "is_bot": True,
            "territory_count": 1,
            "last_action": 0
        })
        ownership[by][bx] = i+1
    
    return {
        "terrain": terrain,
        "ownership": ownership,
        "players": players,
        "cities": cities,
        "turn": 0,
        "selected_cell": None
    }

def get_neighbors(x, y):
    """Retourne les voisins d'une cellule"""
    neighbors = []
    for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
        nx, ny = x + dx, y + dy
        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE:
            neighbors.append((nx, ny))
    return neighbors

def count_territory(game, player_id):
    """Compte le territoire d'un joueur"""
    count = 0
    for row in game['ownership']:
        count += sum(1 for cell in row if cell == player_id)
    return count

def bot_ai(game, bot_id):
    """IA des bots - stratégie simple mais efficace"""
    bot = game['players'][bot_id]
    ownership = game['ownership']
    terrain = game['terrain']
    
    # Gagner des troupes par tour (1 par territoire)
    bot['territory_count'] = count_territory(game, bot_id)
    bot['troops'] += bot['territory_count']
    bot['gold'] += bot['territory_count'] // 10
    
    # Stratégie: expansion intelligente
    my_cells = [(x, y) for y in range(MAP_SIZE) for x in range(MAP_SIZE) if ownership[y][x] == bot_id]
    
    if not my_cells:
        return
    
    # 1. Construire des villes sur les cases stratégiques (20% de chance)
    if bot['gold'] >= 300 and random.random() < 0.2:
        strategic_cells = [c for c in my_cells if len([n for n in get_neighbors(*c) if ownership[n[1]][n[0]] != bot_id]) >= 2]
        if strategic_cells:
            city_pos = random.choice(strategic_cells)
            city_key = f"{city_pos[0]},{city_pos[1]}"
            if city_key not in game['cities']:
                game['cities'][city_key] = {"owner": bot_id, "level": 1}
                bot['gold'] -= 300
                bot['troops'] += 100
                return
    
    # 2. Attaquer les territoires adjacents faibles
    targets = []
    for cx, cy in my_cells:
        for nx, ny in get_neighbors(cx, cy):
            target_owner = ownership[ny][nx]
            if target_owner != bot_id and target_owner != -1:
                # Vérifier si on peut attaquer
                target_troops = game['players'][target_owner]['troops']
                if bot['troops'] > target_troops * 0.3:  # On attaque si on a 30% de leurs troupes
                    targets.append((nx, ny, target_owner, cx, cy))
    
    if targets and bot['troops'] > 200:
        # Attaquer la cible la plus faible
        targets.sort(key=lambda t: game['players'][t[2]]['troops'])
        tx, ty, target_id, fx, fy = targets[0]
        
        # Vérifier si on doit envoyer un bateau
        use_boat = terrain[fy][fx] == 1 and terrain[ty][tx] == 1 and not are_connected_by_land(game, fx, fy, tx, ty)
        
        attack_troops = min(bot['troops'] // 2, 300)
        if use_boat and bot['gold'] >= 50:
            bot['gold'] -= 50
            perform_attack(game, bot_id, fx, fy, tx, ty, attack_troops)
        elif not use_boat:
            perform_attack(game, bot_id, fx, fy, tx, ty, attack_troops)
    
    # 3. Expansion sur territoires neutres
    elif bot['troops'] > 100:
        neutral_targets = []
        for cx, cy in my_cells:
            for nx, ny in get_neighbors(cx, cy):
                if ownership[ny][nx] == -1 and terrain[ny][nx] == 1:
                    neutral_targets.append((nx, ny, cx, cy))
        
        if neutral_targets:
            tx, ty, fx, fy = random.choice(neutral_targets)
            ownership[ty][tx] = bot_id
            bot['troops'] -= 50

def are_connected_by_land(game, x1, y1, x2, y2):
    """BFS pour vérifier si deux cases terrestres sont connectées"""
    if game['terrain'][y1][x1] == 0 or game['terrain'][y2][x2] == 0:
        return False
    
    visited = set()
    queue = deque([(x1, y1)])
    visited.add((x1, y1))
    
    while queue:
        x, y = queue.popleft()
        if x == x2 and y == y2:
            return True
        
        for nx, ny in get_neighbors(x, y):
            if (nx, ny) not in visited and game['terrain'][ny][nx] == 1:
                visited.add((nx, ny))
                queue.append((nx, ny))
    
    return False

def perform_attack(game, attacker_id, fx, fy, tx, ty, troops):
    """Effectue une attaque"""
    defender_id = game['ownership'][ty][tx]
    attacker = game['players'][attacker_id]
    
    if defender_id == -1:
        # Territoire neutre
        game['ownership'][ty][tx] = attacker_id
        attacker['troops'] -= min(troops, attacker['troops'])
    else:
        # Combat
        defender = game['players'][defender_id]
        
        # Ratio de victoire basé sur les troupes
        attack_power = min(troops, attacker['troops'])
        defense_power = defender['troops'] * 0.3  # Le défenseur a un bonus
        
        if attack_power > defense_power:
            # Victoire de l'attaquant
            game['ownership'][ty][tx] = attacker_id
            attacker['troops'] -= int(attack_power * 0.7)
            defender['troops'] -= int(defense_power * 0.5)
            
            # Supprimer la ville si elle existe
            city_key = f"{tx},{ty}"
            if city_key in game['cities']:
                del game['cities'][city_key]
        else:
            # Victoire du défenseur
            attacker['troops'] -= int(attack_power * 0.8)
            defender['troops'] -= int(attack_power * 0.3)

def load_game(user):
    if not user:
        return init_game()
    f = os.path.join(SAVES_DIR, f"{user}_strategy.json")
    return json.load(open(f, encoding='utf-8')) if os.path.exists(f) else init_game()

def save_game(user, data):
    json.dump(data, open(os.path.join(SAVES_DIR, f"{user}_strategy.json"), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

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
.container {
    display: flex;
    height: 100vh;
}
.sidebar {
    width: 300px;
    background: rgba(0,0,0,0.5);
    padding: 20px;
    overflow-y: auto;
}
.map-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
}
.game-map {
    display: grid;
    grid-template-columns: repeat(50, 12px);
    gap: 0;
    border: 2px solid #fff;
    background: #000;
}
.cell {
    width: 12px;
    height: 12px;
    border: 1px solid rgba(255,255,255,0.1);
    cursor: pointer;
    transition: all 0.2s;
}
.cell:hover {
    transform: scale(1.3);
    z-index: 10;
    border: 2px solid white;
}
.cell.sea { background: #1e3a8a; }
.cell.land { background: #22c55e; }
.cell.city {
    background-image: radial-gradient(circle, #ffd700 0%, transparent 70%);
}
.btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 5px;
    cursor: pointer;
    width: 100%;
    margin: 5px 0;
    font-size: 0.9em;
}
.btn:hover { opacity: 0.8; }
.btn:disabled { opacity: 0.3; cursor: not-allowed; }
.stat {
    background: rgba(255,255,255,0.1);
    padding: 10px;
    border-radius: 5px;
    margin: 10px 0;
}
.player-item {
    padding: 8px;
    margin: 5px 0;
    border-radius: 5px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
h2 { font-size: 1.2em; margin: 15px 0 10px 0; }
.modal {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: #1a1a2e;
    padding: 30px;
    border-radius: 10px;
    border: 2px solid #667eea;
    z-index: 1000;
    min-width: 400px;
}
.overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.8);
    z-index: 999;
}
</style>
"""

# ================== ROUTES ==================
@app.route("/")
def home():
    return render_template_string(BASE_STYLE + """
    <body><div class="container" style="align-items:center;justify-content:center;flex-direction:column;">
        <h1 style="font-size:3em;margin-bottom:20px;">🎮 OpenFront Strategy</h1>
        <p style="font-size:1.2em;margin:20px 0;">Jeu de stratégie en temps réel - Conquête territoriale</p>
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
                   style="width:100%;padding:10px;margin:10px 0;border-radius:5px;border:none;">
            <input name="password" type="password" placeholder="Mot de passe" required
                   style="width:100%;padding:10px;margin:10px 0;border-radius:5px;border:none;">
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
                   style="width:100%;padding:10px;margin:10px 0;border-radius:5px;border:none;">
            <input name="password" type="password" placeholder="Mot de passe" required
                   style="width:100%;padding:10px;margin:10px 0;border-radius:5px;border:none;">
            <button class="btn" type="submit">S'inscrire</button>
        </form>
    </div></body>
    """, msg=msg)

@app.route("/game")
def game():
    if 'username' not in session:
        return redirect(url_for("login_page"))
    
    if 'game_state' not in session:
        session['game_state'] = init_game()
        session.modified = True
    
    game_state = session['game_state']
    player = game_state['players'][0]
    
    # Générer la carte HTML
    map_html = ""
    for y in range(MAP_SIZE):
        for x in range(MAP_SIZE):
            terrain_type = "sea" if game_state['terrain'][y][x] == 0 else "land"
            owner = game_state['ownership'][y][x]
            color = game_state['players'][owner]['color'] if owner != -1 else ("#1e3a8a" if terrain_type == "sea" else "#22c55e")
            
            city_class = ""
            city_key = f"{x},{y}"
            if city_key in game_state['cities']:
                city_class = "city"
            
            map_html += f'<div class="cell {terrain_type} {city_class}" style="background-color:{color};" onclick="selectCell({x},{y})"></div>'
    
    # Classement des joueurs
    players_sorted = sorted(game_state['players'], key=lambda p: count_territory(game_state, p['id']), reverse=True)
    
    return render_template_string(BASE_STYLE + """
    <body>
    <div class="container">
        <div class="sidebar">
            <h1 style="font-size:1.5em;margin-bottom:20px;">⚔️ OpenFront</h1>
            
            <div class="stat">
                <strong>{{player['name']}}</strong><br>
                🪖 Troupes: {{player['troops']}}<br>
                💰 Or: {{player['gold']}}<br>
                🏴 Territoires: {{player['territory_count']}}
            </div>
            
            <button class="btn" onclick="nextTurn()">▶️ Tour suivant</button>
            <button class="btn" onclick="location.reload()">🔄 Rafraîchir</button>
            <button class="btn" onclick="location.href='/save'" style="background:#22c55e;">💾 Sauvegarder</button>
            <button class="btn" onclick="location.href='/new_game'" style="background:#f5576c;">🆕 Nouvelle partie</button>
            
            <h2>🏆 Classement</h2>
            {% for p in players_sorted[:5] %}
            <div class="player-item" style="background-color:{{p['color']}}33;border-left:4px solid {{p['color']}};">
                <span>{{p['name']}}</span>
                <span>{{count_territory(game_state, p['id'])}} 🏴</span>
            </div>
            {% endfor %}
            
            <h2>ℹ️ Instructions</h2>
            <p style="font-size:0.85em;line-height:1.4;">
                • Cliquez sur vos territoires pour construire<br>
                • Cliquez sur territoires ennemis pour attaquer<br>
                • Villes: +100 troupes (300 or)<br>
                • Bateaux: traverser la mer (50 or)<br>
                • +1 troupe/territoire par tour
            </p>
        </div>
        
        <div class="map-container">
            <div class="game-map">
                {{map_html|safe}}
            </div>
        </div>
    </div>
    
    <script>
    let selectedCell = null;
    
    function selectCell(x, y) {
        fetch('/api/select', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({x: x, y: y})
        })
        .then(r => r.json())
        .then(data => {
            if (data.action) {
                if (data.action === 'build_menu') {
                    showBuildMenu(x, y, data);
                } else if (data.action === 'attack_menu') {
                    showAttackMenu(x, y, data);
                }
            }
            if (data.message) alert(data.message);
        });
    }
    
    function showBuildMenu(x, y, data) {
        let html = `
            <div class="overlay" onclick="this.nextElementSibling.remove();this.remove();"></div>
            <div class="modal">
                <h2>🏗️ Construire sur (${x},${y})</h2>
                <p>Troupes: ${data.player_troops} | Or: ${data.player_gold}</p>
                <button class="btn" onclick="buildCity(${x},${y})">🏰 Ville (300 or → +100 troupes)</button>
                <button class="btn" onclick="closeModal()" style="background:#f5576c;">Annuler</button>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', html);
    }
    
    function showAttackMenu(x, y, data) {
        let boatText = data.need_boat ? ' + 🚢 Bateau (50 or)' : '';
        let html = `
            <div class="overlay" onclick="this.nextElementSibling.remove();this.remove();"></div>
            <div class="modal">
                <h2>⚔️ Attaquer (${x},${y})</h2>
                <p>Défenseur: ${data.defender_name} (${data.defender_troops} troupes)</p>
                <p>Vos troupes: ${data.player_troops}</p>
                <input type="number" id="attackTroops" value="100" min="1" max="${data.player_troops}" 
                       style="width:100%;padding:10px;margin:10px 0;border-radius:5px;border:none;">
                <button class="btn" onclick="attack(${x},${y}, document.getElementById('attackTroops').value, ${data.need_boat})">
                    ⚔️ Attaquer${boatText}
                </button>
                <button class="btn" onclick="closeModal()" style="background:#f5576c;">Annuler</button>
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
    
    function attack(x, y, troops, needBoat) {
        fetch('/api/attack', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({x: x, y: y, troops: parseInt(troops), need_boat: needBoat})
        })
        .then(r => r.json())
        .then(data => {
            alert(data.message);
            location.reload();
        });
    }
    
    function nextTurn() {
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
    """, map_html=map_html, player=player, game_state=game_state, 
         players_sorted=players_sorted, count_territory=count_territory)

@app.route("/api/select", methods=["POST"])
def api_select():
    data = request.json
    x, y = data['x'], data['y']
    game = session['game_state']
    owner = game['ownership'][y][x]
    player = game['players'][0]
    
    if owner == 0:  # Notre territoire
        return jsonify({
            "action": "build_menu",
            "player_troops": player['troops'],
            "player_gold": player['gold']
        })
    elif owner != -1:  # Territoire ennemi
        defender = game['players'][owner]
        
        # Vérifier si on a un territoire adjacent
        has_adjacent = False
        for nx, ny in get_neighbors(x, y):
            if game['ownership'][ny][nx] == 0:
                has_adjacent = True
                # Vérifier si on a besoin d'un bateau
                need_boat = game['terrain'][ny][nx] == 1 and game['terrain'][y][x] == 1 and not are_connected_by_land(game, nx, ny, x, y)
                break
        
        if not has_adjacent:
            return jsonify({"message": "Pas de territoire adjacent pour attaquer !"})
        
        return jsonify({
            "action": "attack_menu",
            "defender_name": defender['name'],
            "defender_troops": defender['troops'],
            "player_troops": player['troops'],
            "need_boat": need_boat
        })
    
    return jsonify({"message": "Territoire neutre - utilisez l'attaque depuis un territoire adjacent"})

@app.route("/api/build_city", methods=["POST"])
def api_build_city():
    data = request.json
    x, y = data['x'], data['y']
    game = session['game_state']
    player = game['players'][0]
    
    city_key = f"{x},{y}"
    if city_key in game['cities']:
        return jsonify({"success": False, "message": "❌ Ville déjà construite ici !"})
    
    if player['gold'] < 300:
        return jsonify({"success": False, "message": "❌ Pas assez d'or (300 requis)"})
    
    player['gold'] -= 300
    player['troops'] += 100
    game['cities'][city_key] = {"owner": 0, "level": 1}
    session.modified = True
    
    return jsonify({"success": True, "message": "✅ Ville construite ! +100 troupes"})

@app.route("/api/attack", methods=["POST"])
def api_attack():
    data = request.json
    x, y = data['x'], data['y']
    troops = data['troops']
    need_boat = data['need_boat']
    
    game = session['game_state']
    player = game['players'][0]
    
    if troops > player['troops']:
        return jsonify({"message": "❌ Pas assez de troupes !"})
    
    if need_boat and player['gold'] < 50:
        return jsonify({"message": "❌ Pas assez d'or pour le bateau (50 requis)"})
    
    if need_boat:
        player['gold'] -= 50
    
    # Trouver notre territoire adjacent
    from_x, from_y = None, None
    for nx, ny in get_neighbors(x, y):
        if game['ownership'][ny][nx] == 0:
            from_x, from_y = nx, ny
            break
    
    perform_attack(game, 0, from_x, from_y, x, y, troops)
    session.modified = True
    
    return jsonify({"message": "⚔️ Attaque effectuée !"})

@app.route("/api/next_turn", methods=["POST"])
def api_next_turn():
    game = session['game_state']
    game['turn'] += 1
    
    # Tour du joueur
    player = game['players'][0]
    player['territory_count'] = count_territory(game, 0)
    player['troops'] += player['territory_count']
    player['gold'] += player['territory_count'] // 10
