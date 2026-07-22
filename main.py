# main.py
import os
import json
import hashlib
import random
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database file
DB_FILE = "database_log.json"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

db = load_db()

# Models
from pydantic import BaseModel

class UserRegister(BaseModel):
    username: str
    email: str
    password: str
    currency: str = "USD"

class UserLogin(BaseModel):
    username: str
    password: str

# Auth endpoints
@app.post("/api/v2/auth/signup")
async def signup(user: UserRegister):
    if user.username in db["users"]:
        raise HTTPException(400, "Username already exists")
    for u in db["users"].values():
        if u.get("email") == user.email:
            raise HTTPException(400, "Email already registered")
    db["users"][user.username] = {
        "email": user.email,
        "password_hash": hash_password(user.password),
        "currency": user.currency,
        "balance": 25000.0,
        "status": "WARNING",
        "health_score": 85.0,
        "registered_at": datetime.now().isoformat()
    }
    save_db(db)
    return {"status": "success", "username": user.username, "balance": 25000.0, "currency": user.currency}

@app.post("/api/v2/auth/signin")
async def signin(user: UserLogin):
    if user.username not in db["users"]:
        raise HTTPException(400, "Invalid username or password")
    target = db["users"][user.username]
    if target["password_hash"] != hash_password(user.password):
        raise HTTPException(400, "Invalid username or password")
    return {
        "status": "success",
        "username": user.username,
        "balance": target["balance"],
        "currency": target["currency"],
        "status_layer": target["status"],
        "health_score": target["health_score"],
        "avatar": "🧬"
    }

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}

# Root HTML (minimal)
HTML = """
<!DOCTYPE html>
<html>
<head><title>BioEmpire</title></head>
<body style="background:#E8F5E9;font-family:sans-serif;text-align:center;padding:50px;">
    <h1>🧬 BioEmpire V10.0</h1>
    <p>Server ishlamoqda! ✅</p>
    <p>Admin: CEO / 12345678</p>
    <p><a href="/health" style="color:#43A047;">/health</a></p>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
