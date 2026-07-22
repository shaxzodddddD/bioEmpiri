import os
import json
import hashlib
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ==========================================
# FASTAPI
# ==========================================
app = FastAPI(title="BioEmpire V11.2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# DATABASE (JSON fayl)
# ==========================================
DB_FILE = "database_log.json"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"users": {}}

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"⚠️ DB saqlash xatosi: {e}")
        return False

db = load_db()

# ==========================================
# MODELLAR
# ==========================================
class UserRegister(BaseModel):
    username: str
    email: str
    password: str
    currency: str = "USD"

class UserLogin(BaseModel):
    username: str
    password: str

# ==========================================
# AUTH ENDPOINTLAR
# ==========================================
@app.post("/api/v2/auth/signup")
async def signup(user: UserRegister):
    if user.username in db["users"]:
        raise HTTPException(status_code=400, detail="Bu username allaqachon band.")
    
    for u in db["users"].values():
        if u.get("email") == user.email:
            raise HTTPException(status_code=400, detail="Bu email allaqachon ro'yxatdan o'tgan.")
    
    curr = user.currency.upper()
    if curr not in ["USD", "EUR", "BTC", "SOL"]:
        curr = "USD"
    
    rates = {"USD": 1.0, "EUR": 0.92, "BTC": 0.000015, "SOL": 0.0075}
    initial_balance = 25000.0 * rates.get(curr, 1.0)
    
    db["users"][user.username] = {
        "email": user.email,
        "password_hash": hash_password(user.password),
        "currency": curr,
        "balance": initial_balance,
        "status": "WARNING",
        "health_score": 85.0,
        "avatar": "🧬",
        "registered_at": datetime.now().isoformat()
    }
    save_db(db)
    
    return {
        "status": "success",
        "username": user.username,
        "balance": initial_balance,
        "currency": curr
    }

@app.post("/api/v2/auth/signin")
async def signin(user: UserLogin):
    if user.username not in db["users"]:
        raise HTTPException(status_code=400, detail="Noto'g'ri username yoki parol.")
    
    target = db["users"][user.username]
    if target["password_hash"] != hash_password(user.password):
        raise HTTPException(status_code=400, detail="Noto'g'ri username yoki parol.")
    
    return {
        "status": "success",
        "username": user.username,
        "balance": target["balance"],
        "currency": target["currency"],
        "status_layer": target["status"],
        "health_score": target["health_score"],
        "avatar": target.get("avatar", "🧬")
    }

@app.get("/api/v2/profile/{username}")
async def get_profile(username: str):
    if username not in db["users"]:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
    return db["users"][username]

# ===== HEALTH CHECK =====
@app.get("/health")
async def health():
    return {"status": "ok", "users": len(db["users"])}

# ===== ADMIN: MA'LUMOTLARNI TOZALASH =====
@app.post("/api/v2/admin/clear")
async def clear_database(request: Request):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    ADMIN_USERNAME = "CEO"
    ADMIN_PASSWORD_HASH = hash_password("12345678")
    
    if username != ADMIN_USERNAME or hash_password(password) != ADMIN_PASSWORD_HASH:
        raise HTTPException(status_code=401, detail="Noto'g'ri admin ma'lumotlari.")
    
    db["users"] = {}
    save_db(db)
    return {"status": "success", "message": "Barcha ma'lumotlar tozalandi."}

# ==========================================
# HTML (TO'LIQ INTERFEYS)
# ==========================================
HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧬 BioEmpire V11.2</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #E8F5E9; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; display: flex; justify-content: center; align-items: center; }
        .container { background: white; padding: 40px; border-radius: 28px; box-shadow: 0 8px 32px rgba(0,40,0,0.08); width: 100%; max-width: 440px; }
        h1 { color: #2E7D32; text-align: center; margin-bottom: 10px; }
        .subtitle { text-align: center; color: #666; margin-bottom: 20px; }
        input, select { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ccc; border-radius: 12px; font-size: 14px; }
        button { width: 100%; padding: 14px; background: #43A047; color: white; border: none; border-radius: 12px; font-weight: 700; font-size: 16px; cursor: pointer; transition: 0.3s; }
        button:hover { background: #2E7D32; transform: scale(1.02); }
        .tabs { display: flex; gap: 10px; margin: 20px 0; }
        .tab { flex: 1; padding: 12px; text-align: center; border: 2px solid #ddd; border-radius: 12px; cursor: pointer; font-weight: 600; transition: 0.3s; }
        .tab.active { border-color: #43A047; background: #E8F5E9; color: #2E7D32; }
        .tab:hover { background: #f0f0f0; }
        .result { margin-top: 15px; padding: 12px; border-radius: 12px; display: none; }
        .result.success { background: #E8F5E9; color: #2E7D32; display: block; }
        .result.error { background: #FFEBEE; color: #C62828; display: block; }
        .dashboard { display: none; }
        .dashboard .info { background: #f5f5f5; padding: 15px; border-radius: 12px; margin: 10px 0; }
        .dashboard .info span { font-weight: bold; color: #2E7D32; }
        .logout-btn { background: #E53935; margin-top: 10px; }
        .logout-btn:hover { background: #C62828; }
        .admin-link { margin-top: 15px; text-align: center; font-size: 13px; color: #888; }
        .admin-link a { color: #43A047; text-decoration: none; cursor: pointer; }
        .clear-btn { background: #E53935; padding: 8px; font-size: 13px; margin-top: 5px; }
    </style>
</head>
<body>
<div id="auth-container" class="container">
    <h1>🧬 BioEmpire V11.2</h1>
    <div class="subtitle">🔐 Tizimga ulanish</div>

    <div class="tabs">
        <div class="tab active" id="tab-signup" onclick="switchTab('signup')">Ro'yxatdan o'tish</div>
        <div class="tab" id="tab-signin" onclick="switchTab('signin')">Kirish</div>
    </div>

    <!-- Signup -->
    <div id="signup-form">
        <input type="text" id="reg-username" placeholder="👤 Username">
        <input type="email" id="reg-email" placeholder="📧 Email">
        <input type="password" id="reg-password" placeholder="🔑 Parol (min 6)">
        <select id="reg-currency">
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
            <option value="BTC">BTC</option>
            <option value="SOL">SOL</option>
        </select>
        <button onclick="register()">🚀 Ro'yxatdan o'tish</button>
    </div>

    <!-- Signin -->
    <div id="signin-form" style="display:none;">
        <input type="text" id="login-username" placeholder="👤 Username">
        <input type="password" id="login-password" placeholder="🔑 Parol">
        <button onclick="login()">🔐 Kirish</button>
    </div>

    <div id="result" class="result"></div>

    <div class="admin-link">
        <a onclick="clearData()">🗑️ Ma'lumotlarni tozalash (Admin)</a>
        <div style="font-size:11px; color:#999;">CEO / 12345678</div>
    </div>
</div>

<!-- DASHBOARD -->
<div id="dashboard-container" class="container" style="display:none;">
    <h1>🧬 BioEmpire</h1>
    <div class="subtitle">👤 Xush kelibsiz, <span id="dash-username"></span>!</div>
    <div class="info">
        <p>💵 Balans: <span id="dash-balance">0</span> <span id="dash-currency">USD</span></p>
        <p>📊 Holat: <span id="dash-status">WARNING</span></p>
        <p>❤️ Salomatlik: <span id="dash-health">85%</span></p>
        <p>🧬 Avatar: <span id="dash-avatar">🧬</span></p>
    </div>
    <button class="logout-btn" onclick="logout()">🚪 Chiqish</button>
</div>

<script>
let currentUser = null;

function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + tab).classList.add('active');
    document.getElementById('signup-form').style.display = tab === 'signup' ? 'block' : 'none';
    document.getElementById('signin-form').style.display = tab === 'signin' ? 'block' : 'none';
    document.getElementById('result').className = 'result';
    document.getElementById('result').textContent = '';
}

function showResult(msg, isSuccess) {
    const r = document.getElementById('result');
    r.className = 'result ' + (isSuccess ? 'success' : 'error');
    r.textContent = msg;
}

async function register() {
    const username = document.getElementById('reg-username').value.trim();
    const email = document.getElementById('reg-email').value.trim();
    const password = document.getElementById('reg-password').value;
    const currency = document.getElementById('reg-currency').value;

    if (!username || !email || !password) {
        showResult("❌ Barcha maydonlarni to'ldiring!", false);
        return;
    }
    if (password.length < 6) {
        showResult("❌ Parol kamida 6 belgi bo'lishi kerak!", false);
        return;
    }

    try {
        const res = await fetch('/api/v2/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password, currency })
        });
        const data = await res.json();
        if (res.ok) {
            showResult(`✅ Muvaffaqiyatli! Username: ${data.username}, Balans: $${data.balance}`, true);
            // Avtomatik kirish
            await autoLogin(username, password);
        } else {
            showResult(`❌ ${data.detail || 'Xatolik yuz berdi'}`, false);
        }
    } catch(e) {
        showResult(`❌ Tarmoq xatosi: ${e.message}`, false);
    }
}

async function login() {
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;

    if (!username || !password) {
        showResult("❌ Username va parolni kiriting!", false);
        return;
    }
    await autoLogin(username, password);
}

async function autoLogin(username, password) {
    try {
        const res = await fetch('/api/v2/auth/signin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (res.ok) {
            currentUser = data;
            showDashboard(data);
        } else {
            showResult(`❌ ${data.detail || 'Kirish xatosi'}`, false);
        }
    } catch(e) {
        showResult(`❌ Tarmoq xatosi: ${e.message}`, false);
    }
}

function showDashboard(user) {
    document.getElementById('auth-container').style.display = 'none';
    document.getElementById('dashboard-container').style.display = 'block';
    document.getElementById('dash-username').textContent = user.username;
    document.getElementById('dash-balance').textContent = user.balance.toFixed(2);
    document.getElementById('dash-currency').textContent = user.currency;
    document.getElementById('dash-status').textContent = user.status_layer || 'WARNING';
    document.getElementById('dash-health').textContent = (user.health_score || 85) + '%';
    document.getElementById('dash-avatar').textContent = user.avatar || '🧬';
}

function logout() {
    currentUser = null;
    document.getElementById('dashboard-container').style.display = 'none';
    document.getElementById('auth-container').style.display = 'block';
    document.getElementById('login-username').value = '';
    document.getElementById('login-password').value = '';
    document.getElementById('result').className = 'result';
    document.getElementById('result').textContent = '';
}

async function clearData() {
    if (!confirm("Barcha ma'lumotlarni tozalashni xohlaysizmi? Bu amalni qaytarib bo'lmaydi!")) return;
    const username = prompt("Admin username (CEO):");
    if (username !== "CEO") { alert("Noto'g'ri username"); return; }
    const password = prompt("Admin parol:");
    if (!password) return;

    try {
        const res = await fetch('/api/v2/admin/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (res.ok) {
            alert("✅ " + data.message);
            location.reload();
        } else {
            alert("❌ " + (data.detail || "Xatolik"));
        }
    } catch(e) {
        alert("❌ " + e.message);
    }
}

// Ro'yxatdan o'tgandan keyin avtomatik kirish uchun
// Agar localStorage da foydalanuvchi bo'lsa, avtomatik kirish
window.onload = function() {
    // Agar oldin login qilingan bo'lsa, saqlab qo'yamiz
    // Hozircha oddiy, hech narsa
};
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML

# ==========================================
# STATIK FAYL XIZMATI (agar index.html alohida bo'lsa)
# ==========================================
from fastapi.responses import FileResponse
import os

if os.path.exists("templates/index.html"):
    @app.get("/old", response_class=HTMLResponse)
    async def old_index():
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return f.read()

# ==========================================
# SERVER
# ==========================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    print(f"🧬 BioEmpire V11.2 ishga tushdi, port: {port}")
    print(f"📁 DB fayl: {DB_FILE}")
    print("🔐 Admin: CEO / 12345678")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
