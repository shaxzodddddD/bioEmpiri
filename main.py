import os
import json
import hashlib
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="BioEmpire V11.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class UserRegister(BaseModel):
    username: str
    email: str
    password: str
    currency: str = "USD"

class UserLogin(BaseModel):
    username: str
    password: str

# ===== AUTH ENDPOINTLAR =====
@app.post("/api/v2/auth/signup")
async def signup(user: UserRegister):
    # Username mavjudligini tekshirish
    if user.username in db["users"]:
        raise HTTPException(status_code=400, detail="Bu username allaqachon band.")
    
    # Email mavjudligini tekshirish
    for u in db["users"].values():
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
    db["users"][user.username] = {
        "email": user.email,
        "password_hash": hash_password(user.password),
        "currency": curr,
        "balance": initial_balance,
        "registered_at": datetime.now().isoformat()
    }
    
    # Faylga saqlash
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
        "currency": target["currency"]
    }

# ===== HEALTH CHECK =====
@app.get("/health")
async def health():
    return {"status": "ok", "users": len(db["users"])}

# ==========================================
# HTML INTERFEYS
# ==========================================
HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧬 BioEmpire V11.1</title>
    <style>
        body { background: #E8F5E9; font-family: 'Segoe UI', system-ui, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .container { background: white; padding: 40px; border-radius: 28px; box-shadow: 0 8px 32px rgba(0,40,0,0.08); width: 100%; max-width: 400px; }
        h1 { color: #2E7D32; text-align: center; }
        input, select { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ccc; border-radius: 10px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #43A047; color: white; border: none; border-radius: 12px; font-weight: 700; cursor: pointer; }
        button:hover { background: #2E7D32; }
        .result { margin-top: 10px; padding: 10px; border-radius: 10px; }
        .success { background: #E8F5E9; color: #2E7D32; }
        .error { background: #FFEBEE; color: #C62828; }
        hr { margin: 20px 0; }
    </style>
</head>
<body>
<div class="container">
    <h1>🧬 BioEmpire V11.1</h1>
    
    <h3>🔐 Ro'yxatdan o'tish</h3>
    <input id="reg-user" placeholder="👤 Username">
    <input id="reg-email" placeholder="📧 Email">
    <input id="reg-pass" type="password" placeholder="🔑 Parol (min 6 belgi)">
    <select id="reg-curr">
        <option value="USD">USD</option>
        <option value="EUR">EUR</option>
        <option value="BTC">BTC</option>
        <option value="SOL">SOL</option>
    </select>
    <button onclick="register()">🚀 Ro'yxatdan o'tish</button>
    
    <hr>
    
    <h3>🔑 Kirish</h3>
    <input id="login-user" placeholder="👤 Username">
    <input id="login-pass" type="password" placeholder="🔑 Parol">
    <button onclick="login()">🔐 Kirish</button>
    
    <div id="result" class="result"></div>
</div>

<script>
function showResult(msg, isSuccess) {
    const r = document.getElementById('result');
    r.className = 'result ' + (isSuccess ? 'success' : 'error');
    r.textContent = msg;
}

async function register() {
    const username = document.getElementById('reg-user').value.trim();
    const email = document.getElementById('reg-email').value.trim();
    const password = document.getElementById('reg-pass').value;
    const currency = document.getElementById('reg-curr').value;
    
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
    const username = document.getElementById('login-user').value.trim();
    const password = document.getElementById('login-pass').value;
    
    if (!username || !password) {
        showResult("❌ Username va parolni kiriting!", false);
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
    print(f"🧬 BioEmpire V11.1 ishga tushdi, port: {port}")
    print(f"📁 DB fayl: {DB_FILE}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
