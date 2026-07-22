import os
import json
import hashlib
import random
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ==========================================
# FASTAPI
# ==========================================
app = FastAPI(title="BioEmpire V11")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# DATABASE (JSON fayl + xotira zaxirasi)
# ==========================================
DB_FILE = "database_log.json"
ADMIN_USERNAME = "CEO"
ADMIN_PASSWORD_HASH = hashlib.sha256("12345678".encode()).hexdigest()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "users" not in data:
                    data["users"] = {}
                return data
        except:
            pass
    return {"users": {}}

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"⚠️ DB faylga saqlash xatosi: {e} – faqat xotirada saqlanadi.")
        return False

db = load_db()
# Xotirada saqlash uchun (fallback)
memory_db = db.copy()

def get_db():
    # Agar fayl mavjud bo'lsa, uni o'qiymiz, aks holda xotiradagi ma'lumotni qaytaramiz
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return memory_db

def update_db(new_data):
    global memory_db
    memory_db = new_data
    save_db(new_data)

# ==========================================
# PYDANTIC MODELLAR
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
# ENDPOINTLAR
# ==========================================

# ROOT – interfeys
@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML

# ===== AUTH =====
@app.post("/api/v2/auth/signup")
async def signup(user: UserRegister):
    current_db = get_db()
    
    # Username mavjudligini tekshirish
    if user.username in current_db["users"]:
        raise HTTPException(status_code=400, detail="Bu username allaqachon band.")
    
    # Email mavjudligini tekshirish
    for u in current_db["users"].values():
        if u.get("email") == user.email:
            raise HTTPException(status_code=400, detail="Bu email allaqachon ro'yxatdan o'tgan.")
    
    # Valyutani aniqlash
    curr = user.currency.upper()
    if curr not in ["USD", "EUR", "BTC", "SOL"]:
        curr = "USD"
    
    # Boshlang'ich balans
    rates = {"USD": 1.0, "EUR": 0.92, "BTC": 0.000015, "SOL": 0.0075}
    initial_balance = 25000.0 * rates.get(curr, 1.0)
    
    # Foydalanuvchini qo'shish
    current_db["users"][user.username] = {
        "email": user.email,
        "password_hash": hash_password(user.password),
        "currency": curr,
        "balance": initial_balance,
        "status": "WARNING",
        "health_score": 85.0,
        "avatar": "🧬",
        "registered_at": datetime.now().isoformat()
    }
    
    # DB ni yangilash
    update_db(current_db)
    
    return {
        "status": "success",
        "username": user.username,
        "balance": initial_balance,
        "currency": curr
    }

@app.post("/api/v2/auth/signin")
async def signin(user: UserLogin):
    current_db = get_db()
    
    if user.username not in current_db["users"]:
        raise HTTPException(status_code=400, detail="Noto'g'ri username yoki parol.")
    
    target = current_db["users"][user.username]
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

# ===== ADMIN: Ma'lumotlarni tozalash =====
@app.post("/api/v2/admin/clear")
async def clear_database(request: Request):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    
    if username != ADMIN_USERNAME or hash_password(password) != ADMIN_PASSWORD_HASH:
        raise HTTPException(status_code=401, detail="Noto'g'ri admin ma'lumotlari.")
    
    # DB ni tozalash
    new_db = {"users": {}}
    update_db(new_db)
    return {"status": "success", "message": "Barcha ma'lumotlar tozalandi."}

# ===== HEALTH CHECK =====
@app.get("/health")
async def health():
    current_db = get_db()
    return {"status": "ok", "users": len(current_db["users"])}

# ==========================================
# HTML INTERFEYS (RO'YXATDAN O'TISH VA KIRISH)
# ==========================================
HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧬 BioEmpire V11</title>
    <style>
        body { background: #E8F5E9; font-family: 'Segoe UI', system-ui, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .container { background: white; padding: 40px; border-radius: 28px; box-shadow: 0 8px 32px rgba(0,40,0,0.08); width: 100%; max-width: 440px; }
        h1 { color: #2E7D32; text-align: center; }
        .tabs { display: flex; gap: 10px; margin: 20px 0; }
        .tab { flex: 1; padding: 10px; text-align: center; border: 2px solid #ddd; border-radius: 12px; cursor: pointer; font-weight: 600; }
        .tab.active { border-color: #43A047; background: #E8F5E9; color: #2E7D32; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; font-size: 13px; font-weight: 600; color: #333; margin-bottom: 4px; }
        .form-group input, .form-group select { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 10px; font-size: 14px; }
        .btn { width: 100%; padding: 12px; background: #43A047; color: white; border: none; border-radius: 12px; font-size: 16px; font-weight: 700; cursor: pointer; }
        .btn:hover { background: #2E7D32; }
        .result { margin-top: 15px; padding: 10px; border-radius: 10px; display: none; }
        .result.success { background: #E8F5E9; color: #2E7D32; display: block; }
        .result.error { background: #FFEBEE; color: #C62828; display: block; }
        .admin-link { margin-top: 20px; text-align: center; font-size: 12px; color: #888; }
        .admin-link a { color: #43A047; text-decoration: none; }
        .clear-btn { margin-top: 10px; padding: 8px; background: #E53935; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 12px; }
        .clear-btn:hover { background: #C62828; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧬 BioEmpire V11</h1>
        <div class="tabs">
            <div class="tab active" id="tab-signup" onclick="switchTab('signup')">Ro'yxatdan o'tish</div>
            <div class="tab" id="tab-signin" onclick="switchTab('signin')">Kirish</div>
        </div>

        <!-- Ro'yxatdan o'tish -->
        <div id="signup-form">
            <div class="form-group">
                <label>👤 Username</label>
                <input type="text" id="reg-username" placeholder="Bio_User">
            </div>
            <div class="form-group">
                <label>📧 E-mail</label>
                <input type="email" id="reg-email" placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label>🔑 Parol</label>
                <input type="password" id="reg-password" placeholder="••••••••">
            </div>
            <div class="form-group">
                <label>💱 Valyuta</label>
                <select id="reg-currency">
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="BTC">BTC</option>
                    <option value="SOL">SOL</option>
                </select>
            </div>
            <button class="btn" onclick="register()">🚀 Ro'yxatdan o'tish</button>
        </div>

        <!-- Kirish -->
        <div id="signin-form" style="display:none;">
            <div class="form-group">
                <label>👤 Username</label>
                <input type="text" id="login-username" placeholder="Bio_User">
            </div>
            <div class="form-group">
                <label>🔑 Parol</label>
                <input type="password" id="login-password" placeholder="••••••••">
            </div>
            <button class="btn" onclick="login()">🔐 Kirish</button>
        </div>

        <div id="result" class="result"></div>

        <div class="admin-link">
            <a href="#" onclick="clearData()">🗑️ Ma'lumotlarni tozalash (Admin)</a>
            <div style="margin-top:5px; font-size:10px; color:#999;">Admin: CEO / 12345678</div>
        </div>
    </div>

    <script>
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById('tab-' + tab).classList.add('active');
            document.getElementById('signup-form').style.display = tab === 'signup' ? 'block' : 'none';
            document.getElementById('signin-form').style.display = tab === 'signin' ? 'block' : 'none';
            document.getElementById('result').className = 'result';
            document.getElementById('result').innerHTML = '';
        }

        function showResult(message, isSuccess) {
            const el = document.getElementById('result');
            el.className = 'result ' + (isSuccess ? 'success' : 'error');
            el.innerHTML = message;
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
                showResult("❌ Barcha maydonlarni to'ldiring!", false);
                return;
            }

            try {
                const res = await fetch('/api/v2/auth/signin', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                const data = await res.json();
                if (res.ok) {
                    showResult(`✅ Xush kelibsiz, ${data.username}! Balans: $${data.balance}`, true);
                } else {
                    showResult(`❌ ${data.detail || 'Xatolik yuz berdi'}`, false);
                }
            } catch(e) {
                showResult(`❌ Tarmoq xatosi: ${e.message}`, false);
            }
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
    </script>
</body>
</html>
"""

# ==========================================
# SERVER
# ==========================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    print(f"🧬 BioEmpire V11 ishga tushdi, port: {port}")
    print("📁 DB fayl: database_log.json (agar mavjud bo'lmasa, yangi yaratiladi)")
    print("🔐 Admin: CEO / 12345678")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
