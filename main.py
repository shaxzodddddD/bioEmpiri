import os
import json
import hashlib
import random
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ==========================================
# FASTAPI
# ==========================================
app = FastAPI(title="BioEmpire V10.1")
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
        print(f"❌ DB saqlash xatosi: {e}")
        return False

db = load_db()

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
# AUTH ENDPOINTLAR
# ==========================================

# RO'YXATDAN O'TISH
@app.post("/api/v2/auth/signup")
async def signup(user: UserRegister):
    # 1. Username mavjudligini tekshirish
    if user.username in db["users"]:
        raise HTTPException(status_code=400, detail="Bu username allaqachon band.")
    
    # 2. Email mavjudligini tekshirish
    for u in db["users"].values():
        if u.get("email") == user.email:
            raise HTTPException(status_code=400, detail="Bu email allaqachon ro'yxatdan o'tgan.")
    
    # 3. Valyutani aniqlash
    curr = user.currency.upper()
    if curr not in ["USD", "EUR", "BTC", "SOL"]:
        curr = "USD"
    
    # 4. Foydalanuvchini qo'shish
    db["users"][user.username] = {
        "email": user.email,
        "password_hash": hash_password(user.password),
        "currency": curr,
        "balance": 25000.0,
        "status": "WARNING",
        "health_score": 85.0,
        "avatar": "🧬",
        "registered_at": datetime.now().isoformat()
    }
    
    # 5. Faylga saqlash
    if not save_db(db):
        raise HTTPException(status_code=500, detail="Ma'lumotlarni saqlashda xatolik.")
    
    return {
        "status": "success",
        "username": user.username,
        "balance": 25000.0,
        "currency": curr
    }

# KIRISH
@app.post("/api/v2/auth/signin")
async def signin(user: UserLogin):
    # 1. Foydalanuvchi mavjudligini tekshirish
    if user.username not in db["users"]:
        raise HTTPException(status_code=400, detail="Noto'g'ri username yoki parol.")
    
    target = db["users"][user.username]
    
    # 2. Parolni tekshirish
    if target["password_hash"] != hash_password(user.password):
        raise HTTPException(status_code=400, detail="Noto'g'ri username yoki parol.")
    
    # 3. Muvaffaqiyatli javob
    return {
        "status": "success",
        "username": user.username,
        "balance": target["balance"],
        "currency": target["currency"],
        "status_layer": target["status"],
        "health_score": target["health_score"],
        "avatar": target.get("avatar", "🧬")
    }

# ==========================================
# HEALTH CHECK
# ==========================================
@app.get("/health")
async def health():
    return {"status": "ok", "users": len(db["users"])}

# ==========================================
# ROOT HTML
# ==========================================
HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧬 BioEmpire V10.1</title>
    <style>
        body { background: #E8F5E9; font-family: 'Segoe UI', system-ui, sans-serif; text-align: center; padding: 50px; }
        .box { background: white; border-radius: 20px; padding: 40px; max-width: 500px; margin: auto; box-shadow: 0 8px 32px rgba(0,40,0,0.08); }
        h1 { color: #2E7D32; }
        .btn { background: #43A047; color: white; padding: 12px 30px; border: none; border-radius: 30px; cursor: pointer; font-size: 16px; display: inline-block; text-decoration: none; }
        .btn:hover { background: #2E7D32; }
        input { display: block; width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 10px; }
        .status { color: #43A047; font-weight: bold; }
    </style>
</head>
<body>
    <div class="box">
        <h1>🧬 BioEmpire V10.1</h1>
        <p class="status">✅ Server ishlamoqda!</p>
        <p>Foydalanuvchilar soni: <strong id="user-count">0</strong></p>
        <hr>
        <h2>🔐 Ro'yxatdan o'tish</h2>
        <input type="text" id="reg-username" placeholder="Username">
        <input type="email" id="reg-email" placeholder="Email">
        <input type="password" id="reg-password" placeholder="Parol">
        <select id="reg-currency">
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
            <option value="BTC">BTC</option>
            <option value="SOL">SOL</option>
        </select>
        <button class="btn" onclick="register()">Ro'yxatdan o'tish</button>
        <div id="reg-result" style="margin-top:10px;"></div>

        <hr>
        <h2>🔑 Kirish</h2>
        <input type="text" id="login-username" placeholder="Username">
        <input type="password" id="login-password" placeholder="Parol">
        <button class="btn" onclick="login()">Kirish</button>
        <div id="login-result" style="margin-top:10px;"></div>
    </div>

    <script>
        async function register() {
            const username = document.getElementById('reg-username').value.trim();
            const email = document.getElementById('reg-email').value.trim();
            const password = document.getElementById('reg-password').value;
            const currency = document.getElementById('reg-currency').value;
            const result = document.getElementById('reg-result');
            result.innerText = '⏳ Yuborilmoqda...';
            try {
                const res = await fetch('/api/v2/auth/signup', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username, email, password, currency})
                });
                const data = await res.json();
                if (res.ok) {
                    result.innerHTML = '✅ <span style="color:green;">Muvaffaqiyatli! Username: ' + data.username + '</span>';
                    loadUserCount();
                } else {
                    result.innerHTML = '❌ <span style="color:red;">' + (data.detail || 'Xatolik') + '</span>';
                }
            } catch(e) {
                result.innerHTML = '❌ <span style="color:red;">Tarmoq xatosi: ' + e.message + '</span>';
            }
        }

        async function login() {
            const username = document.getElementById('login-username').value.trim();
            const password = document.getElementById('login-password').value;
            const result = document.getElementById('login-result');
            result.innerText = '⏳ Yuborilmoqda...';
            try {
                const res = await fetch('/api/v2/auth/signin', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username, password})
                });
                const data = await res.json();
                if (res.ok) {
                    result.innerHTML = '✅ <span style="color:green;">Xush kelibsiz, ' + data.username + '! Balans: $' + data.balance + '</span>';
                } else {
                    result.innerHTML = '❌ <span style="color:red;">' + (data.detail || 'Xatolik') + '</span>';
                }
            } catch(e) {
                result.innerHTML = '❌ <span style="color:red;">Tarmoq xatosi: ' + e.message + '</span>';
            }
        }

        async function loadUserCount() {
            try {
                const res = await fetch('/health');
                const data = await res.json();
                document.getElementById('user-count').innerText = data.users || 0;
            } catch(e) {}
        }
        loadUserCount();
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML

# ==========================================
# SERVER
# ==========================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    print(f"🚀 BioEmpire V10.1 ishga tushdi, port: {port}")
    print(f"📁 Database: {DB_FILE}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
