from flask import Flask, render_template_string, request, redirect, url_for, session
import hashlib, json, os, random

app = Flask(__name__)
app.secret_key = "openfront_secret_CHANGE_IN_PROD"

# ================== CONFIG ==================
USERS_FILE = "openfront_users.json"
SAVES_DIR = "openfront_saves"
os.makedirs(SAVES_DIR, exist_ok=True)

# ================== DATA ==================
seigneurs = [
    {"nom": "Baron Noir", "unites": ["Archer", "Fantassin"], "recompense": 200, "niveau": 3},
    {"nom": "Comte Sanglant", "unites": ["Chevalier", "Mage"], "recompense": 400, "niveau": 5},
    {"nom": "Duc des Ombres", "unites": ["Dragon", "Paladin"], "recompense": 800, "niveau": 8},
    {"nom": "Roi Maudit", "unites": ["Titan", "Archimage"], "recompense": 1500, "niveau": 12},
    {"nom": "Empereur du Chaos", "unites": ["Démon", "Ange Noir"], "recompense": 5000, "niveau": 20}
]

unite_stats = {
    "Archer": {"pv": 80, "attaque": 25, "rarete": "Commun"},
    "Fantassin": {"pv": 100, "attaque": 20, "rarete": "Commun"},
    "Chevalier": {"pv": 120, "attaque": 35, "rarete": "Rare"},
    "Mage": {"pv": 90, "attaque": 40, "rarete": "Rare"},
    "Dragon": {"pv": 150, "attaque": 50, "rarete": "Épique"},
    "Paladin": {"pv": 140, "attaque": 45, "rarete": "Épique"},
    "Titan": {"pv": 180, "attaque": 55, "rarete": "Légendaire"},
    "Archimage": {"pv": 130, "attaque": 60, "rarete": "Légendaire"},
    "Démon": {"pv": 200, "attaque": 65, "rarete": "Mythique"},
    "Ange Noir": {"pv": 170, "attaque": 70, "rarete": "Mythique"}
}

PRIX_VENTE = {"Commun": 50, "Rare": 150, "Épique": 400, "Légendaire": 900, "Mythique": 2000}
BONUS_ATK = {"Commun": 0, "Rare": 5, "Épique": 10, "Légendaire": 20, "Mythique": 30}
MAX_ARMEE = 6

LANGUES = {
    "fr": {"welcome": "Bienvenue {nom}", "login": "Connexion", "register": "S'inscrire", 
           "menu": "Royaume", "fight": "⚔️ Conquête", "recruit": "🎲 Recruter (60 or)",
           "army": "🛡️ Armée", "sell": "💰 Vendre", "heal": "❤️ Soigner (40 or)",
           "save": "💾 Sauvegarder", "quit": "🚪 Quitter", "back": "← Retour",
           "gold": "Or", "progress": "Seigneurs vaincus", "choose_unit": "Choisis ton unité",
           "attack": "Attaquer", "heal_action": "Soigner", "victory": "🏆 VICTOIRE", "defeat": "💀 Défaite"},
    "en": {"welcome": "Welcome {nom}", "login": "Login", "register": "Register",
           "menu": "Kingdom", "fight": "⚔️ Conquest", "recruit": "🎲 Recruit (60 gold)",
           "army": "🛡️ Army", "sell": "💰 Sell", "heal": "❤️ Heal (40 gold)",
           "save": "💾 Save", "quit": "🚪 Quit", "back": "← Back",
           "gold": "Gold", "progress": "Lords defeated", "choose_unit": "Choose unit",
           "attack": "Attack", "heal_action": "Heal", "victory": "🏆 VICTORY", "defeat": "💀 DEFEAT"}
}

# ================== UTILS ==================
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def load_users():
    return json.load(open(USERS_FILE, encoding='utf-8')) if os.path.exists(USERS_FILE) else {}

def save_users(u):
    json.dump(u, open(USERS_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

def load_game(user):
    if not user:
        return {"or": 200, "armee": [], "seigneur_actuel": 0}
    f = os.path.join(SAVES_DIR, f"{user}.json")
    return json.load(open(f, encoding='utf-8')) if os.path.exists(f) else {"or": 200, "armee": [], "seigneur_actuel": 0}

def save_game(user, data):
    json.dump(data, open(os.path.join(SAVES_DIR, f"{user}.json"), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

def get_state():
    if 'username' not in session:
        return {"or": 200, "armee": [], "seigneur_actuel": 0}
    if 'game_state' not in session:
        session['game_state'] = load_game(session.get('username', ''))
    return session['game_state']

def update_state(updates):
    state = get_state()
    state.update(updates)
    session['game_state'] = state
    session.modified = True

# ================== STYLES ==================
BASE_STYLE = """
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Segoe UI', Tahoma, sans-serif;
    background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
    min-height: 100vh;
    padding: 20px;
}
.container {
    max-width: 900px;
    margin: 0 auto;
    background: rgba(255, 255, 255, 0.95);
    border-radius: 20px;
    padding: 40px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.4);
}
h1 { color: #2c3e50; margin-bottom: 20px; text-align: center; }
.btn {
    background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
    color: white;
    border: none;
    padding: 15px 30px;
    font-size: 1.1em;
    border-radius: 10px;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    margin: 5px;
    transition: transform 0.2s;
}
.btn:hover { transform: translateY(-3px); }
.btn-secondary { background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); }
.stat { text-align: center; margin: 20px 0; font-size: 1.3em; color: #555; }
.unit-card {
    background: white;
    border-radius: 15px;
    padding: 20px;
    margin: 10px 0;
    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    border-left: 5px solid #e74c3c;
}
.health-bar {
    background: #ddd;
    height: 20px;
    border-radius: 10px;
    overflow: hidden;
    margin: 10px 0;
}
.health-fill {
    background: linear-gradient(90deg, #e74c3c 0%, #c0392b 100%);
    height: 100%;
    transition: width 0.3s;
}
input {
    width: 100%;
    padding: 15px;
    margin: 10px 0;
    border: 2px solid #ddd;
    border-radius: 10px;
    font-size: 1em;
}
.msg {
    padding: 15px;
    border-radius: 10px;
    margin: 15px 0;
    text-align: center;
    font-weight: bold;
}
.msg-success { background: #d4edda; color: #155724; }
.msg-error { background: #f8d7da; color: #721c24; }
.rarity-Commun { border-left-color: #95a5a6; }
.rarity-Rare { border-left-color: #3498db; }
.rarity-Épique { border-left-color: #9b59b6; }
.rarity-Légendaire { border-left-color: #f39c12; }
.rarity-Mythique { border-left-color: #e74c3c; }
</style>
"""

# ================== ROUTES ==================
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        session["lang"] = request.form["lang"]
        return redirect(url_for("login_page"))
    
    return render_template_string(BASE_STYLE + """
    <body><div class="container" style="text-align:center;">
        <h1>⚔️ Kingdom Conquest</h1>
        <p style="font-size:1.2em;margin:20px 0;">Choisir la langue / Choose language</p>
        <form method="post">
            <button class="btn" name="lang" value="fr">🇫🇷 Français</button>
            <button class="btn" name="lang" value="en">🇬🇧 English</button>
        </form>
    </div></body>
    """)

@app.route("/login", methods=["GET", "POST"])
def login_page():
    lang = session.get("lang", "fr")
    T = LANGUES[lang]
    msg = ""
    
    if request.method == "POST":
        user, pw = request.form["username"], request.form["password"]
        users = load_users()
        if user in users and users[user]["password"] == hash_pw(pw):
            session['username'] = user
            session['game_state'] = load_game(user)
            return redirect(url_for("menu"))
        msg = "❌ Identifiants invalides"
    
    return render_template_string(BASE_STYLE + """
    <body><div class="container">
        <h1>🏰 {{T['login']}}</h1>
        {% if msg %}<p class="msg msg-error">{{msg}}</p>{% endif %}
        <form method="post">
            <input name="username" placeholder="Nom d'utilisateur" required>
            <input name="password" type="password" placeholder="Mot de passe" required>
            <button class="btn" type="submit">{{T['login']}}</button>
        </form>
        <a href="{{url_for('signup_page')}}"><button class="btn btn-secondary">{{T['register']}}</button></a>
    </div></body>
    """, T=T, msg=msg)

@app.route("/signup", methods=["GET", "POST"])
def signup_page():
    lang = session.get("lang", "fr")
    T = LANGUES[lang]
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
    <body><div class="container">
        <h1>📝 {{T['register']}}</h1>
        {% if msg %}<p class="msg msg-error">{{msg}}</p>{% endif %}
        <form method="post">
            <input name="username" placeholder="Nom d'utilisateur" required>
            <input name="password" type="password" placeholder="Mot de passe" required>
            <button class="btn btn-secondary" type="submit">{{T['register']}}</button>
        </form>
    </div></body>
    """, T=T, msg=msg)

@app.route("/menu")
def menu():
    if 'username' not in session:
        return redirect(url_for("login_page"))
    
    lang = session.get("lang", "fr")
    T = LANGUES[lang]
    state = get_state()
    current_lord = seigneurs[state['seigneur_actuel']]['nom'] if state['seigneur_actuel'] < len(seigneurs) else "✅ Tous vaincus"
    
    return render_template_string(BASE_STYLE + """
    <body><div class="container">
        <h1>🏰 {{T['menu']}}</h1>
        <div class="stat">
            💰 {{state['or']}} {{T['gold']}} | 🏆 {{state['seigneur_actuel']}}/{{seigneurs|length}} | 🛡️ {{state['armee']|length}}/{{MAX_ARMEE}}
        </div>
        <p style="text-align:center;background:#e74c3c;color:white;padding:10px;border-radius:10px;margin:20px 0;">
            ⚔️ Prochain adversaire: {{current_lord}}
        </p>
        <div style="text-align:center;">
            <a href="{{url_for('fight')}}"><button class="btn">{{T['fight']}}</button></a>
            <a href="{{url_for('recruit')}}"><button class="btn">{{T['recruit']}}</button></a>
            <a href="{{url_for('army_page')}}"><button class="btn">{{T['army']}}</button></a>
            <a href="{{url_for('sell')}}"><button class="btn">{{T['sell']}}</button></a>
            <a href="{{url_for('heal_army')}}"><button class="btn">{{T['heal']}}</button></a>
            <a href="{{url_for('save')}}"><button class="btn">{{T['save']}}</button></a>
            <a href="{{url_for('quit')}}"><button class="btn btn-secondary">{{T['quit']}}</button></a>
        </div>
    </div></body>
    """, T=T, state=state, current_lord=current_lord, seigneurs=seigneurs, MAX_ARMEE=MAX_ARMEE)

@app.route("/recruit", methods=["GET", "POST"])
def recruit():
    if 'username' not in session:
        return redirect(url_for("login_page"))
    
    lang = session.get("lang", "fr")
    T = LANGUES[lang]
    state = get_state()
    msg = ""
    new_unit = None
    
    if request.method == "POST":
        if state['or'] < 60:
            msg = "❌ Pas assez d'or (60 requis)"
        elif len(state['armee']) >= MAX_ARMEE:
            msg = "⚠️ Armée complète (max 6 unités)"
        else:
            state['or'] -= 60
            t = random.randint(1, 100)
            if t <= 50:
                nom = random.choice(["Archer", "Fantassin"])
            elif t <= 70:
                nom = random.choice(["Chevalier", "Mage"])
            elif t <= 85:
                nom = random.choice(["Dragon", "Paladin"])
            elif t <= 95:
                nom = random.choice(["Titan", "Archimage"])
            else:
                nom = random.choice(["Démon", "Ange Noir"])
            
            stats = unite_stats[nom]
            new_unit = {"nom": nom, "pv": stats["pv"], "pv_max": stats["pv"], 
                       "attaque": stats["attaque"] + BONUS_ATK[stats["rarete"]], 
                       "rarete": stats["rarete"], "niveau": 1}
            state['armee'].append(new_unit)
            update_state(state)
            msg = f"✨ Recruté: {nom} ({stats['rarete']}) !"
    
    return render_template_string(BASE_STYLE + """
    <body><div class="container">
        <h1>🎲 {{T['recruit']}}</h1>
        <div class="stat">💰 {{state['or']}} {{T['gold']}}</div>
        {% if msg %}<p class="msg {{'msg-success' if new_unit else 'msg-error'}}">{{msg}}</p>{% endif %}
        {% if new_unit %}
        <div class="unit-card rarity-{{new_unit['rarete']}}" style="text-align:center;">
            <h2>{{new_unit['nom']}}</h2>
            <p style="color:#e74c3c;font-weight:bold;">{{new_unit['rarete']}} | Niv.{{new_unit['niveau']}}</p>
            <p>❤️ {{new_unit['pv']}} HP | ⚔️ {{new_unit['attaque']}} ATK</p>
        </div>
        {% endif %}
        <form method="post" style="text-align:center;margin:20px 0;">
            <button class="btn" type="submit">Recruter une unité (60 or)</button>
        </form>
        <div style="background:#ecf0f1;padding:15px;border-radius:10px;margin:20px 0;">
            <h3 style="color:#2c3e50;">Taux de recrutement:</h3>
            <p>50% - Commun (Archer, Fantassin)</p>
            <p>20% - Rare (Chevalier, Mage)</p>
            <p>15% - Épique (Dragon, Paladin)</p>
            <p>10% - Légendaire (Titan, Archimage)</p>
            <p>5% - Mythique (Démon, Ange Noir)</p>
        </div>
        <a href="{{url_for('menu')}}"><button class="btn btn-secondary">{{T['back']}}</button></a>
    </div></body>
    """, T=T, state=state, msg=msg, new_unit=new_unit)

@app.route("/army")
def army_page():
    if 'username' not in session:
        return redirect(url_for("login_page"))
    
    lang = session.get("lang", "fr")
    T = LANGUES[lang]
    state = get_state()
    
    return render_template_string(BASE_STYLE + """
    <body><div class="container">
        <h1>🛡️ {{T['army']}}</h1>
        {% if state['armee'] %}
            {% for u in state['armee'] %}
            <div class="unit-card rarity-{{u['rarete']}}">
                <h3>{{u['nom']}} <span style="color:#e74c3c;">Niv.{{u['niveau']}}</span></h3>
                <p style="color:#7f8c8d;">{{u['rarete']}}</p>
                <div class="health-bar">
                    <div class="health-fill" style="width:{{(u['pv']/u['pv_max']*100)|int}}%;"></div>
                </div>
                <p>❤️ {{u['pv']}}/{{u['pv_max']}} HP | ⚔️ {{u['attaque']}} ATK</p>
            </div>
            {% endfor %}
        {% else %}
            <p style="text-align:center;color:#999;margin:40px 0;">Aucune unité dans l'armée</p>
        {% endif %}
        <a href="{{url_for('menu')}}"><button class="btn btn-secondary">{{T['back']}}</button></a>
    </div></body>
    """, T=T, state=state)

@app.route("/sell", methods=["GET", "POST"])
def sell():
    if 'username' not in session:
        return redirect(url_for("login_page"))
    
    lang = session.get("lang", "fr")
    T = LANGUES[lang]
    state = get_state()
    msg = ""
    
    if request.method == "POST" and state['armee']:
        idx = int(request.form["index"])
        if 0 <= idx < len(state['armee']):
            unit = state['armee'].pop(idx)
            prix = PRIX_VENTE[unit['rarete']]
            state['or'] += prix
            update_state(state)
            msg = f"💰 {unit['nom']} vendu pour {prix} or"
    
    return render_template_string(BASE_STYLE + """
    <body><div class="container">
        <h1>💰 {{T['sell']}}</h1>
        <div class="stat">💰 {{state['or']}} {{T['gold']}}</div>
        {% if msg %}<p class="msg msg-success">{{msg}}</p>{% endif %}
        {% if state['armee'] %}
            <form method="post">
                {% for i in range(state['armee']|length) %}
                {% set u = state['armee'][i] %}
                <div class="unit-card rarity-{{u['rarete']}}" style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <strong>{{u['nom']}}</strong> Niv.{{u['niveau']}} ({{u['rarete']}})
                    </div>
                    <button class="btn" name="index" value="{{i}}" type="submit">Vendre {{PRIX_VENTE[u['rarete']]}} or</button>
                </div>
                {% endfor %}
            </form>
        {% else %}
            <p style="text-align:center;color:#999;margin:40px 0;">Aucune unité</p>
        {% endif %}
        <a href="{{url_for('menu')}}"><button class="btn btn-secondary">{{T['back']}}</button></a>
    </div></body>
    """, T=T, state=state, msg=msg, PRIX_VENTE=PRIX_VENTE)

@app.route("/heal_army", methods=["GET", "POST"])
def heal_army():
    if 'username' not in session:
        return redirect(url_for("login_page"))
    
    lang = session.get("lang", "fr")
    T = LANGUES[lang]
    state = get_state()
    msg = ""
    
    if request.method == "POST":
        if state['or'] < 40:
            msg = "❌ Pas assez d'or (40 requis)"
        else:
            state['or'] -= 40
            for u in state['armee']:
                u['pv'] = u['pv_max']
            update_state(state)
            msg = "✨ Armée soignée !"
    
    return render_template_string(BASE_STYLE + """
    <body><div class="container">
        <h1>❤️ {{T['heal']}}</h1>
        <div class="stat">💰 {{state['or']}} {{T['gold']}}</div>
        {% if msg %}<p class="msg {{'msg-success' if '✨' in msg else 'msg-error'}}">{{msg}}</p>{% endif %}
        <form method="post" style="text-align:center;margin:20px 0;">
            <button class="btn" type="submit">Soigner toute l'armée (40 or)</button>
        </form>
        <a href="{{url_for('menu')}}"><button class="btn btn-secondary">{{T['back']}}</button></a>
    </div></body>
    """, T=T, state=state, msg=msg)

@app.route("/fight", methods=["GET", "POST"])
def fight():
    if 'username' not in session:
        return redirect(url_for("login_page"))
    
    lang = session.get("lang", "fr")
    T = LANGUES[lang]
    state = get_state()
    
    if state['seigneur_actuel'] >= len(seigneurs):
        return render_template_string(BASE_STYLE + """
        <body><div class="container">
            <h1>🎊 VICTOIRE TOTALE !</h1>
            <p style="text-align:center;font-size:1.5em;margin:40px 0;">Tous les seigneurs sont vaincus ! Vous êtes le maître du royaume !</p>
            <a href="{{url_for('menu')}}"><button class="btn">{{T['back']}}</button></a>
        </div></body>
        """, T=T)
    
    seigneur = seigneurs[state['seigneur_actuel']]
    available = [u for u in state['armee'] if u['pv'] > 0]
    
    if not available:
        return render_template_string(BASE_STYLE + """
        <body><div class="container">
            <h1>❌ Aucune unité disponible</h1>
            <p style="text-align:center;margin:20px 0;">Soigne ton armée avant de combattre !</p>
            <a href="{{url_for('menu')}}"><button class="btn">{{T['back']}}</button></a>
        </div></body>
        """, T=T)
    
    if request.method == "POST" and 'unit_idx' not in session:
        idx = int(request.form['unit_idx'])
        count = 0
        for i, u in enumerate(state['armee']):
            if u['pv'] > 0:
                if count == idx:
                    session['unit_collection_idx'] = i
                    break
                count += 1
        
        session['enemy_unit'] = random.choice(seigneur['unites'])
        stats = unite_stats[session['enemy_unit']]
        session['enemy_pv'] = stats['pv'] + (seigneur['niveau'] * 15)
        session['enemy_pv_max'] = session['enemy_pv']
        session['enemy_atk'] = stats['attaque'] + (seigneur['niveau'] * 3)
        session['combat_log'] = []
        session.modified = True
        return redirect(url_for('fight_action'))
    
    return render_template_string(BASE_STYLE + """
    <body><div class="container">
        <h1>⚔️ Affronter {{seigneur['nom']}}</h1>
        <p style="text-align:center;margin:20px 0;font-size:1.2em;">Niveau {{seigneur['niveau']}} | Récompense: {{seigneur['recompense']}} or</p>
        <h2>{{T['choose_unit']}}</h2>
        <form method="post">
            {% for i in range(available|length) %}
            {% set u = available[i] %}
            <div class="unit-card rarity-{{u['rarete']}}" style="cursor:pointer;">
                <button class="btn" name="unit_idx" value="{{i}}" type="submit" style="width:100%;text-align:left;">
                    <strong>{{u['nom']}}</strong> Niv.{{u['niveau']}} | ❤️ {{u['pv']}}/{{u['pv_max']}} | ⚔️ {{u['attaque']}}
                </button>
            </div>
            {% endfor %}
        </form>
        <a href="{{url_for('menu')}}"><button class="btn btn-secondary">{{T['back']}}</button></a>
    </div></body>
    """, T=T, seigneur=seigneur, available=available)

@app.route("/fight_action", methods=["GET", "POST"])
def fight_action():
    if 'username' not in session or 'unit_collection_idx' not in session:
        return redirect(url_for("fight"))
    
    lang = session.get("lang", "fr")
    T = LANGUES[lang]
    state = get_state()
    seigneur = seigneurs[state['seigneur_actuel']]
    unit = state['armee'][session['unit_collection_idx']]
    
    if request.method == "POST":
        action = request.form['action']
        log = session.get('combat_log', [])
        
        if action == "attack":
            dmg = random.randint(unit['attaque']-8, unit['attaque']+8)
            if random.randint(1,100) <= 20:
                dmg = int(dmg * 1.8)
                log.append(f"💥 {unit['nom']} COUP CRITIQUE: -{dmg}")
            else:
                log.append(f"⚔️ {unit['nom']}: -{dmg}")
            session['enemy_pv'] = max(0, session['enemy_pv'] - dmg)
        elif action == "heal":
            heal = int(unit['pv_max'] * 0.5)
            unit['pv'] = min(unit['pv_max'], unit['pv'] + heal)
            log.append(f"💚 {unit['nom']}: +{heal} HP")
        
        if session['enemy_pv'] > 0:
            if random.randint(1,100) <= 25:
                heal = int(session['enemy_pv_max'] * 0.4)
                session['enemy_pv'] = min(session['enemy_pv_max'], session['enemy_pv'] + heal)
                log.append(f"💚 {session['enemy_unit']}: +{heal} HP")
            else:
                dmg = random.randint(session['enemy_atk']-8, session['enemy_atk']+8)
                if random.randint(1,100) <= 20:
                    dmg = int(dmg * 1.8)
                    log.append(f"⚡ {session['enemy_unit']} COUP CRITIQUE: -{dmg}")
                else:
                    log.append(f"🔥 {session['enemy_unit']}: -{dmg}")
                unit['pv'] = max(0, unit['pv'] - dmg)
        
        session['combat_log'] = log[-6:]
        session.modified = True
        update_state(state)
        
        if unit['pv'] <= 0 or session['enemy_pv'] <= 0:
            return redirect(url_for('fight_result'))
    
    return render_template_string(BASE_STYLE + """
    <body><div class="container">
        <h1>⚔️ Combat vs {{seigneur['nom']}}</h1>
        <div class="stat">
            💰 {{state['or']}} or | Ennemi: {{session['enemy_unit']}} ({{session['enemy_pv']}}/{{session['enemy_pv_max']}} HP)
        </div>
        <div class="unit-card rarity-{{unit['rarete']}}">
            <h3>{{unit['nom']}} (Niv.{{unit['niveau']}})</h3>
            <div class="health-bar">
                <div class="health-fill" style="width:{{(unit['pv']/unit['pv_max']*100)|int}}%;"></div>
            </div>
            <p>❤️ {{unit['pv']}}/{{unit['pv_max']}} HP | ⚔️ {{unit['attaque']}} ATK</p>
        </div>
        <div style="background:#ecf0f1;padding:15px;border-radius:10px;margin:20px 0;">
            <h3 style="color:#2c3e50;">📜 Journal de combat:</h3>
            {% for entry in session.get('combat_log', []) %}
                <p style="margin:5px 0;">{{entry}}</p>
            {% endfor %}
        </div>
        <form method="post" style="text-align:center;">
            <button class="btn" name="action" value="attack" type="submit">{{T['attack']}}</button>
            <button class="btn btn-secondary" name="action" value="heal" type="submit">{{T['heal_action']}}</button>
        </form>
        <a href="{{url_for('menu')}}"><button class="btn" style="background:#95a5a6;">Abandonner</button></a>
    </div></body>
    """, T=T, seigneur=seigneur, unit=unit, session=session, state=state)

@app.route("/fight_result")
def fight_result():
    if 'username' not in session or 'unit_collection_idx' not in session:
        return redirect(url_for("fight"))
    
    lang = session.get("lang", "fr")
    T = LANGUES[lang]
    state = get_state()
    seigneur = seigneurs[state['seigneur_actuel']]
    unit = state['armee'][session['unit_collection_idx']]
    
    won = session['enemy_pv'] <= 0
    if won:
        state['or'] += seigneur['recompense']
        state['seigneur_actuel'] += 1
        unit['niveau'] += 1
        unit['attaque'] += 5
        unit['pv_max'] += 20
        unit['pv'] = unit['pv_max']
        msg = f"{T['victory']} +{seigneur['recompense']} or ! {unit['nom']} monte au niveau {unit['niveau']} !"
        cls = "msg-success"
    else:
        msg = T['defeat']
        cls = "msg-error"
    
    update_state(state)
    
    # Clean up session
    keys_to_clear = ['unit_collection_idx', 'enemy_unit', 'enemy_pv', 'enemy_pv_max', 'enemy_atk', 'combat_log']
    for k in keys_to_clear:
        session.pop(k, None)
    session.modified = True
    
    return render_template_string(BASE_STYLE + """
    <body><div class="container">
        <h1>{% if won %}{{T['victory']}}{% else %}{{T['defeat']}}{% endif %}</h1>
        <p class="msg {{cls}}">{{msg}}</p>
        <div class="unit-card rarity-{{unit['rarete']}}">
            <h3>{{unit['nom']}}</h3>
            <p>❤️ {{unit['pv']}}/{{unit['pv_max']}} HP | ⚔️ {{unit['attaque']}} ATK | ⭐ Niveau {{unit['niveau']}}</p>
        </div>
        {% if won and state['seigneur_actuel'] < seigneurs|length %}
        <p style="text-align:center;margin:20px 0;font-size:1.1em;">
            Prochain adversaire: <strong>{{seigneurs[state['seigneur_actuel']]['nom']}}</strong> (Niveau {{seigneurs[state['seigneur_actuel']]['niveau']}})
        </p>
        {% endif %}
        <a href="{{url_for('menu')}}"><button class="btn">{{T['menu']}}</button></a>
    </div></body>
    """, T=T, won=won, msg=msg, cls=cls, unit=unit, state=state, seigneurs=seigneurs)

@app.route("/save")
def save():
    if 'username' not in session:
        return redirect(url_for("login_page"))
    save_game(session['username'], get_state())
    return redirect(url_for("menu"))

@app.route("/quit")
def quit():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
