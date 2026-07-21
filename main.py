import os
import json
import random
import asyncio
import hashlib
import httpx
import base64
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ==========================================
# GEMINI AI (ixtiyoriy)
# ==========================================
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ==========================================
# KONFIGURATSIYA
# ==========================================
CONFIG_FILE = "config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
else:
    CONFIG = {
        "exchange_rates": {"USD": 1.0, "EUR": 0.92, "BTC": 0.000015, "SOL": 0.0075},
        "chat_price_usd": 49,
        "camera_analysis_price_usd": 150,
        "admin": {"username": "CEO", "password_hash": hashlib.sha256("12345678".encode()).hexdigest()}
    }

EXCHANGE_RATES = CONFIG.get("exchange_rates", {"USD": 1.0})
CHAT_PRICE_USD = CONFIG.get("chat_price_usd", 49)
CAMERA_PRICE_USD = CONFIG.get("camera_analysis_price_usd", 150)
ADMIN_USERNAME = CONFIG.get("admin", {}).get("username", "CEO")
ADMIN_PASSWORD_HASH = CONFIG.get("admin", {}).get("password_hash", hashlib.sha256("12345678".encode()).hexdigest())

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-1.5-flash"

if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="BioEmpire V9.6")
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

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "users": {},
        "social_posts": [],
        "system_vault": {"total_revenue": 0, "active_users": 0},
        "notifications": [],
        "user_activity": {},
        "product_sales": [],
        "ads_performance": {},
        "feed": []
    }

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[DB] Saqlash xatosi: {e}")
        return False

db = load_db()
db_lock = asyncio.Lock()

# ==========================================
# YORDAMCHI FUNKSIYALAR
# ==========================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_post_id() -> str:
    return f"post_{random.randint(10000, 99999)}_{int(datetime.now().timestamp())}"

def generate_social_post(username: str, content: str) -> dict:
    return {
        "id": generate_post_id(),
        "username": username,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "likes": 0,
        "comments": []
    }

def add_social_post(post: dict):
    db["social_posts"].insert(0, post)
    if len(db["social_posts"]) > 100:
        db["social_posts"].pop()
    save_db(db)

def track_user_activity(username: str, action: str, details: dict = None):
    if username not in db["user_activity"]:
        db["user_activity"][username] = {
            "last_active": datetime.now().isoformat(),
            "actions": [],
            "total_spent": 0.0,
            "packages_bought": 0
        }
    db["user_activity"][username]["last_active"] = datetime.now().isoformat()
    db["user_activity"][username]["actions"].append({
        "action": action,
        "timestamp": datetime.now().isoformat(),
        "details": details or {}
    })
    if len(db["user_activity"][username]["actions"]) > 100:
        db["user_activity"][username]["actions"] = db["user_activity"][username]["actions"][-100:]
    save_db(db)

# ==========================================
# AI CALLS
# ==========================================
async def call_gemini_api(messages: List[dict]) -> Optional[str]:
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return None
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        user_message = messages[-1]["content"] if messages else ""
        context = "\n".join([m["content"] for m in messages if m["role"] == "system"])
        full_prompt = f"{context}\n\nFoydalanuvchi: {user_message}" if context else user_message
        response = await asyncio.to_thread(model.generate_content, full_prompt)
        return response.text if response and response.text else None
    except:
        return None

async def call_groq_api(messages: List[dict]) -> Optional[str]:
    if not GROQ_API_KEY:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "mixtral-8x7b-32768",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            return None
    except:
        return None

async def call_ai_api(messages: List[dict]) -> Optional[str]:
    response = await call_gemini_api(messages)
    if response:
        return response
    return await call_groq_api(messages)

# ==========================================
# PYDANTIC MODELLAR
# ==========================================
class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=30)
    email: str
    password: str = Field(..., min_length=6)
    currency: str = "USD"

class UserLogin(BaseModel):
    username: str
    password: str

class SocialPostRequest(BaseModel):
    username: str
    content: str

class LikeRequest(BaseModel):
    username: str
    post_id: str

class CommentRequest(BaseModel):
    username: str
    post_id: str
    comment: str

class AIChatRequest(BaseModel):
    username: str
    message: str

class CameraAnalysisRequest(BaseModel):
    username: str
    department_id: int
    image_data: Optional[str] = None

# ==========================================
# HTML (to‘liq interfeys)
# ==========================================
HTML = """<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧬 BioEmpire V9.6</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #E8F5E9; font-family: 'Segoe UI', system-ui, sans-serif; }
        .glass { background: rgba(255,255,255,0.85); backdrop-filter: blur(8px); border: 1px solid rgba(102,187,106,0.3); border-radius: 20px; box-shadow: 0 8px 32px rgba(0,40,0,0.08); }
        .btn-cyber { background: linear-gradient(135deg, #66BB6A, #43A047); border: none; color: white; padding: 10px 24px; border-radius: 12px; cursor: pointer; font-weight: 700; transition: 0.25s; }
        .btn-cyber:hover { transform: translateY(-2px); box-shadow: 0 8px 28px rgba(102,187,106,0.35); }
        .btn-gold { background: linear-gradient(135deg, #FFB300, #F9A825); color: #1B3A1B; }
        .btn-red { background: linear-gradient(135deg, #E53935, #C62828); color: white; }
        .chat-msg { margin-bottom: 8px; padding: 6px 14px; border-radius: 12px; max-width: 90%; }
        .chat-msg.ai { background: rgba(102,187,106,0.08); border-left: 3px solid #66BB6A; }
        .chat-msg.user { background: rgba(255,179,0,0.08); border-right: 3px solid #FFB300; text-align: right; margin-left: auto; }
        #auth-gate { position: fixed; inset: 0; background: rgba(232,245,233,0.97); backdrop-filter: blur(20px); display: flex; align-items: center; justify-content: center; z-index: 99999; }
        .auth-card { background: white; border: 2px solid #66BB6A; border-radius: 28px; padding: 44px 36px; width: 100%; max-width: 440px; }
        .auth-tabs { display: flex; gap: 8px; justify-content: center; margin: 18px 0 22px; }
        .auth-tab { padding: 6px 28px; border-radius: 30px; cursor: pointer; border: 2px solid transparent; font-weight: 700; color: #4A6A4A; }
        .auth-tab.active { border-color: #66BB6A; color: #43A047; background: rgba(102,187,106,0.08); }
        .input-group { margin-bottom: 16px; }
        .input-group label { display: block; font-size: 12px; font-weight: 700; color: #43A047; margin-bottom: 4px; }
        .input-group input, .input-group select { width: 100%; background: #f5faf5; border: 1.5px solid rgba(102,187,106,0.3); padding: 10px 14px; color: #1B3A1B; border-radius: 12px; outline: none; }
        .input-group input:focus { border-color: #66BB6A; box-shadow: 0 0 0 4px rgba(102,187,106,0.1); }
        .sidebar { width: 250px; flex-shrink: 0; background: rgba(255,255,255,0.92); backdrop-filter: blur(12px); border-right: 1px solid rgba(102,187,106,0.3); height: calc(100vh - 68px); overflow-y: auto; padding: 16px 12px; position: sticky; top: 68px; }
        .sidebar-btn { display: flex; align-items: center; gap: 12px; width: 100%; padding: 10px 14px; background: transparent; border: 1px solid transparent; border-radius: 14px; color: #4A6A4A; cursor: pointer; transition: 0.2s; }
        .sidebar-btn:hover { background: rgba(102,187,106,0.06); border-color: rgba(102,187,106,0.3); }
        .sidebar-btn.active { background: rgba(102,187,106,0.1); border-color: #66BB6A; color: #43A047; font-weight: 600; }
        .panel { display: none; animation: fadeSlide 0.3s ease; }
        .panel.active { display: block; }
        @keyframes fadeSlide { 0%{opacity:0;transform:translateY(10px);} 100%{opacity:1;transform:translateY(0);} }
        .chat-terminal { height: 200px; background: #f9fbf9; border: 1px solid rgba(102,187,106,0.3); border-radius: 14px; padding: 12px 16px; overflow-y: auto; }
        .feed-item { background: rgba(255,255,255,0.6); border: 1px solid rgba(102,187,106,0.3); padding: 12px 16px; border-radius: 14px; margin-bottom: 10px; border-left: 4px solid #66BB6A; }
        .feed-item .user { color: #43A047; font-weight: 700; }
        .feed-item .time { color: #4A6A4A; font-size: 11px; float: right; }
        .feed-item .actions { margin-top: 8px; display: flex; gap: 16px; font-size: 13px; color: #4A6A4A; cursor: pointer; }
        .feed-item .actions span:hover { color: #43A047; }
        .package-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 12px; margin-top: 14px; }
        .package-card { background: white; border: 1px solid rgba(255,179,0,0.15); border-radius: 14px; padding: 14px 8px; text-align: center; cursor: pointer; transition: 0.25s; }
        .package-card:hover { border-color: #FFB300; transform: translateY(-4px); box-shadow: 0 8px 24px rgba(255,179,0,0.08); }
        .package-card .pkg-name { font-size: 12px; font-weight: 700; }
        .package-card .pkg-price { color: #FFB300; font-size: 15px; font-weight: 800; }
        .ranking-item { display: flex; align-items: center; gap: 12px; padding: 6px 12px; border-bottom: 1px solid rgba(0,0,0,0.05); }
        .ranking-item .pos { color: #FFB300; font-weight: 700; width: 30px; }
        .notif-badge { position: absolute; top: -6px; right: -8px; background: #E53935; color: white; border-radius: 50%; padding: 0 6px; font-size: 10px; font-weight: 800; min-width: 18px; text-align: center; animation: pulse-badge 1.8s infinite; }
        @keyframes pulse-badge { 0%,100%{transform:scale(1);} 50%{transform:scale(1.15);} }
        .notif-dropdown { position: absolute; right: 0; top: 42px; width: 300px; max-height: 320px; overflow-y: auto; background: white; border: 1px solid rgba(102,187,106,0.3); border-radius: 16px; padding: 14px; display: none; z-index: 200; }
        .notif-dropdown.show { display: block; }
        .notif-item { padding: 8px 10px; border-bottom: 1px solid rgba(0,0,0,0.05); font-size: 13px; }
        .notif-item .time { color: #4A6A4A; font-size: 11px; float: right; }
        .notif-item.unread { border-left: 3px solid #66BB6A; }
        #camera-preview { width: 100%; max-height: 240px; border-radius: 16px; background: #000; object-fit: cover; border: 2px solid rgba(102,187,106,0.3); }
        .voice-indicator { display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #66BB6A; margin-right: 6px; animation: pulse-dot 1s infinite; }
        @keyframes pulse-dot { 0%,100%{opacity:0.4;transform:scale(0.9);} 50%{opacity:1;transform:scale(1.2);} }
        .avatar-lg { width: 52px; height: 52px; border-radius: 50%; background: linear-gradient(135deg, #C8E6C9, #66BB6A); display: flex; align-items: center; justify-content: center; font-size: 28px; border: 2px solid #FFB300; flex-shrink: 0; }
        @media (max-width:1024px) { .sidebar { width: 70px !important; padding: 10px 6px; } .sidebar .btn-text { display: none; } .sidebar .icon { font-size: 24px; width: 100%; text-align: center; } }
        @media (max-width:768px) { .sidebar { display: none; } }
        .status-badge { display: inline-block; padding: 2px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; }
        .status-warning { background: #FFB300; color: #1B3A1B; }
        .status-red { background: #E53935; color: white; }
        .status-optimized { background: #66BB6A; color: white; }
        .status-immortal { background: #FFB300; color: #1B3A1B; }
    </style>
</head>
<body>

<!-- AUTH -->
<div id="auth-gate">
    <div class="auth-card">
        <div class="text-center mb-3"><span class="text-5xl animate-pulse">🧬</span></div>
        <h2 id="auth-title" style="text-align:center;color:#1B3A1B;font-weight:800;">🔐 TIZIMGA ULANISH</h2>
        <div class="auth-tabs">
            <span id="tab-signup" class="auth-tab active" onclick="switchAuth('signup')">Ro'yxatdan o'tish</span>
            <span id="tab-signin" class="auth-tab" onclick="switchAuth('signin')">Kirish</span>
        </div>
        <div id="email-group" class="input-group">
            <label>📧 E-mail</label>
            <input type="email" id="auth-email" placeholder="your@email.com" />
        </div>
        <div class="input-group">
            <label>👤 Username</label>
            <input type="text" id="auth-user" placeholder="Bio_User" />
        </div>
        <div class="input-group">
            <label>🔑 Parol</label>
            <input type="password" id="auth-pass" placeholder="••••••••" />
        </div>
        <div id="currency-group" class="input-group">
            <label>💱 Valyuta</label>
            <select id="auth-curr">
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="BTC">BTC</option>
                <option value="SOL">SOL</option>
            </select>
        </div>
        <button class="btn-cyber w-full" onclick="executeAuth()">🚀 TIZIMNI FAOLASHTIRISH</button>
        <p id="auth-error" class="text-red-500 text-xs mt-3 text-center"></p>
        <div class="text-center mt-3 text-xs text-gray-500">Admin: CEO / parol: 12345678</div>
    </div>
</div>

<!-- DASHBOARD -->
<div id="main-dashboard" style="display:none;">
    <header class="fixed top-0 left-0 w-full z-50 bg-white/90 backdrop-blur-md border-b border-[#66BB6A33] px-4 py-2 flex items-center justify-between">
        <div class="flex items-center gap-3 cursor-pointer" onclick="location.reload()">
            <span class="text-3xl">🧬</span>
            <span class="text-xl font-black text-[#2E7D32]">BioEmpire ∞</span>
        </div>
        <div class="flex items-center gap-4">
            <div class="notif-bell relative" onclick="toggleNotifications()">
                🔔 <span class="notif-badge" id="notif-count">0</span>
                <div class="notif-dropdown" id="notif-dropdown">
                    <div class="font-bold text-[#43A047] text-xs mb-2">📬 Bildirishnomalar</div>
                    <div id="notif-list"></div>
                </div>
            </div>
            <span id="header-user" class="text-xs text-[#43A047] hidden"></span>
            <button id="logout-btn" class="btn-red btn-sm hidden" onclick="logout()">Chiqish</button>
        </div>
    </header>

    <div class="flex pt-[68px]">
        <!-- SIDEBAR -->
        <aside class="sidebar" id="main-sidebar">
            <div class="flex items-center gap-3 p-3 rounded-xl bg-[#F1F8E9] border border-[#66BB6A33] mb-4">
                <div class="avatar-lg" id="sidebar-avatar">🧬</div>
                <div class="flex-1 min-w-0">
                    <div class="font-bold text-sm text-[#1B3A1B] truncate" id="sidebar-username">-</div>
                    <div class="text-xs text-gray-500" id="sidebar-status">WARNING</div>
                </div>
                <div class="text-right">
                    <div class="text-[10px] text-gray-400">Balans</div>
                    <div class="text-sm font-bold text-[#43A047]" id="sidebar-balance">0.00</div>
                </div>
            </div>
            <div class="text-[10px] text-[#43A047] font-bold uppercase tracking-wider mb-2">📋 Bo'limlar</div>
            <div id="sidebar-depts"></div>
            <div class="sidebar-divider border-t border-[#66BB6A33] my-3"></div>
            <button class="sidebar-btn" data-panel="panel-profile" onclick="switchPanel('panel-profile', this)"><span class="icon">👤</span><span class="btn-text">Profil</span></button>
            <button class="sidebar-btn" data-panel="panel-consult" onclick="switchPanel('panel-consult', this)"><span class="icon">🩺</span><span class="btn-text">Konsultatsiya</span></button>
            <button class="sidebar-btn" data-panel="panel-social" onclick="switchPanel('panel-social', this)"><span class="icon">📡</span><span class="btn-text">Ijtimoiy</span><span class="badge" id="feed-badge">0</span></button>
            <button class="sidebar-btn" data-panel="panel-packages" onclick="switchPanel('panel-packages', this)"><span class="icon">📦</span><span class="btn-text">Paketlar</span></button>
            <button class="sidebar-btn" data-panel="panel-stats" onclick="switchPanel('panel-stats', this)"><span class="icon">📊</span><span class="btn-text">Statistika</span></button>
            <button class="sidebar-btn" data-panel="panel-ads" onclick="switchPanel('panel-ads', this)"><span class="icon">📈</span><span class="btn-text">AI ADS</span></button>
            <button class="sidebar-btn" data-panel="panel-admin" onclick="switchPanel('panel-admin', this)"><span class="icon">⚙️</span><span class="btn-text">Admin</span></button>
        </aside>

        <!-- CONTENT -->
        <main class="flex-1 min-w-0 p-4 max-w-full">
            <!-- PANEL: Konsultatsiya -->
            <div id="panel-consult" class="panel active">
                <div class="glass p-5">
                    <h2 class="text-xl font-bold text-[#43A047] mb-3">🩺 AI KONSULTATSIYA</h2>
                    <div class="mb-4">
                        <div class="flex gap-2 flex-wrap">
                            <button class="btn-cyber btn-sm" onclick="startCamera()">📷 Kamerani yoqish</button>
                            <button class="btn-gold btn-sm" onclick="captureAndAnalyze()">🔬 Suratga olib tahlil</button>
                            <button class="btn-red btn-sm" onclick="stopCamera()">⏹ To'xtatish</button>
                        </div>
                        <video id="camera-preview" autoplay playsinline style="display:none;"></video>
                        <div id="camera-placeholder" class="bg-gray-100 rounded-xl p-4 text-center text-gray-400 text-sm border border-dashed border-[#66BB6A33]">Kamera o'chirilgan</div>
                        <div id="camera-result" class="mt-2 text-sm text-[#43A047]"></div>
                    </div>
                    <div class="mb-4">
                        <button class="btn-cyber btn-sm" onclick="startVoice()">🎤 Ovoz bilan gapirish</button>
                        <button class="btn-red btn-sm" onclick="stopVoice()">⏹ To'xtatish</button>
                        <span id="voice-status" class="text-sm text-gray-500"></span>
                        <div id="voice-transcript" class="mt-2 p-3 bg-gray-50 rounded-xl text-sm text-gray-700 min-h-[48px] border border-[#66BB6A33]">Ovoz matni...</div>
                    </div>
                    <div>
                        <div class="chat-terminal" id="consult-chat">
                            <div class="chat-msg ai">Salom! Men AI shifokorman. Simptomlaringizni yozing yoki gapiring.</div>
                        </div>
                        <div class="flex gap-2 mt-3">
                            <input id="consult-input" type="text" placeholder="Xabar yozing..." class="flex-1 bg-white border border-[#66BB6A33] rounded-xl px-4 py-2 text-sm text-[#1B3A1B] outline-none" />
                            <button class="btn-cyber btn-sm" onclick="sendConsult()">Yuborish</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- PANEL: Ijtimoiy tarmoq -->
            <div id="panel-social" class="panel">
                <div class="glass p-5">
                    <h2 class="text-xl font-bold text-[#43A047] mb-3">📡 Ijtimoiy tarmoq</h2>
                    <div class="flex gap-2 mb-4">
                        <input id="social-input" type="text" placeholder="Holatingiz haqida yozing..." class="flex-1 bg-white border border-[#66BB6A33] rounded-xl px-4 py-2 text-sm text-[#1B3A1B] outline-none" />
                        <button class="btn-cyber btn-sm" onclick="createSocialPost()">Yozish</button>
                    </div>
                    <div id="social-feed" class="max-h-[520px] overflow-y-auto"></div>
                </div>
            </div>

            <!-- PANEL: Profil -->
            <div id="panel-profile" class="panel">
                <div class="glass p-5">
                    <h2 class="text-xl font-bold text-[#43A047] mb-3">👤 Profil</h2>
                    <div id="profile-content"></div>
                </div>
            </div>

            <!-- PANEL: Paketlar -->
            <div id="panel-packages" class="panel">
                <div class="glass p-5">
                    <h2 class="text-xl font-bold text-[#FFB300] mb-3">📦 Paketlar</h2>
                    <div class="package-grid" id="package-grid"></div>
                </div>
            </div>

            <!-- PANEL: Statistika -->
            <div id="panel-stats" class="panel">
                <div class="glass p-5">
                    <h2 class="text-xl font-bold text-[#43A047] mb-3">📊 Statistika</h2>
                    <div id="stats-content" class="grid grid-cols-2 md:grid-cols-4 gap-4"></div>
                    <div class="mt-4"><h3 class="text-sm font-bold text-[#43A047]">🏅 Salomatlik reytingi</h3><div id="health-ranking" class="max-h-[200px] overflow-y-auto"></div></div>
                </div>
            </div>

            <!-- PANEL: AI ADS -->
            <div id="panel-ads" class="panel">
                <div class="glass p-5">
                    <h2 class="text-xl font-bold text-[#43A047] mb-3">📈 AI ADS</h2>
                    <div id="ads-performance" class="space-y-2 max-h-[500px] overflow-y-auto"></div>
                    <button class="btn-outline btn-sm mt-3" onclick="loadAdsPerformance()">🔄 Yangilash</button>
                </div>
            </div>

            <!-- PANEL: Admin -->
            <div id="panel-admin" class="panel">
                <div class="glass p-5">
                    <h2 class="text-xl font-bold text-[#FFB300] mb-3">⚙️ Admin</h2>
                    <div class="flex gap-2 mb-4">
                        <input id="admin-user" type="text" placeholder="Admin" value="CEO" class="bg-white border border-[#66BB6A33] rounded-xl px-3 py-1 text-sm outline-none" />
                        <input id="admin-pass" type="password" placeholder="Parol" value="12345678" class="bg-white border border-[#66BB6A33] rounded-xl px-3 py-1 text-sm outline-none" />
                        <button class="btn-cyber btn-sm" onclick="adminLogin()">🔐 Kirish</button>
                    </div>
                    <div id="admin-content" class="hidden">
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4" id="admin-stats-grid"></div>
                        <div id="admin-data" class="mt-3 max-h-[300px] overflow-y-auto text-sm"></div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<script>
// ============================================================
// GLOBAL
// ============================================================
let currentUser = null;
let authMode = 'signup';
let tokenBalance = 100;
let notifCount = 0;
let cameraStream = null;
let cameraActive = false;
let recognition = null;
let voiceActive = false;

// ============================================================
// AUTH
// ============================================================
function switchAuth(mode) {
    authMode = mode;
    document.getElementById('auth-title').innerText = mode === 'signup' ? '🔐 RO\'YXATDAN O\'TISH' : '🔐 KIRISH';
    document.querySelectorAll('.auth-tab').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + mode).classList.add('active');
    document.getElementById('email-group').style.display = mode === 'signup' ? 'block' : 'none';
    document.getElementById('currency-group').style.display = mode === 'signup' ? 'block' : 'none';
}

async function executeAuth() {
    const user = document.getElementById('auth-user').value.trim();
    const pass = document.getElementById('auth-pass').value;
    const email = document.getElementById('auth-email').value.trim();
    const curr = document.getElementById('auth-curr').value;
    const errEl = document.getElementById('auth-error');
    errEl.innerText = '';

    if (!user) { errEl.innerText = "Username kiritilmagan!"; return; }
    if (!pass || pass.length < 6) { errEl.innerText = "Parol kamida 6 belgi!"; return; }
    if (authMode === 'signup' && !email) { errEl.innerText = "Email kiritilmagan!"; return; }

    const url = authMode === 'signup' ? '/api/v2/auth/signup' : '/api/v2/auth/signin';
    const body = authMode === 'signup' ? { username: user, password: pass, email: email, currency: curr } : { username: user, password: pass };

    try {
        const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const data = await res.json();
        if (!res.ok) { errEl.innerText = data.detail || "Server xatosi."; return; }
        if (data.status !== 'success') { errEl.innerText = data.message || "Noma'lum xatolik."; return; }

        currentUser = data.username;
        document.getElementById('auth-gate').style.display = 'none';
        document.getElementById('main-dashboard').style.display = 'block';
        document.getElementById('header-user').innerText = '👤 ' + currentUser;
        document.getElementById('header-user').className = 'text-xs text-[#43A047] block';
        document.getElementById('logout-btn').className = 'btn-red btn-sm block';

        loadProfile();
        loadSocialFeed();
        loadHealthRanking();
        loadStats();
        loadAdsPerformance();
        renderPackages();
        setInterval(loadSocialFeed, 8000);
        setInterval(loadHealthRanking, 15000);
        setInterval(loadAdsPerformance, 30000);
    } catch (e) { errEl.innerText = "Tarmoq xatosi: " + e.message; }
}

function logout() {
    currentUser = null;
    document.getElementById('auth-gate').style.display = 'flex';
    document.getElementById('main-dashboard').style.display = 'none';
    document.getElementById('header-user').className = 'hidden';
    document.getElementById('logout-btn').className = 'hidden';
    if (cameraStream) { cameraStream.getTracks().forEach(t => t.stop()); }
    if (recognition) { recognition.stop(); }
    location.reload();
}

// ============================================================
// PANEL SWITCH
// ============================================================
function switchPanel(panelId, btn) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.getElementById(panelId).classList.add('active');
    document.querySelectorAll('.sidebar-btn[data-panel]').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    if (panelId === 'panel-profile') loadProfile();
    if (panelId === 'panel-social') loadSocialFeed();
    if (panelId === 'panel-stats') { loadStats(); loadHealthRanking(); }
    if (panelId === 'panel-ads') loadAdsPerformance();
    if (panelId === 'panel-packages') renderPackages();
}

// ============================================================
// PROFILE
// ============================================================
async function loadProfile() {
    if (!currentUser) return;
    try {
        const res = await fetch(`/api/v2/profile/${currentUser}`);
        const data = await res.json();
        document.getElementById('sidebar-username').innerText = currentUser;
        document.getElementById('sidebar-balance').innerText = data.balance.toFixed(2);
        document.getElementById('sidebar-status').innerText = data.status;
        document.getElementById('sidebar-avatar').innerText = data.avatar || '🧬';

        const container = document.getElementById('profile-content');
        const statusClass = data.status === 'WARNING' ? 'status-warning' : data.status === 'RED_ZONE' ? 'status-red' : data.status === 'OPTIMIZED' ? 'status-optimized' : 'status-immortal';
        container.innerHTML = `
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="bg-white/70 p-5 rounded-xl border border-[#66BB6A33]">
                    <div class="flex items-center gap-4">
                        <div class="avatar-lg text-4xl">${data.avatar || '🧬'}</div>
                        <div><div class="text-xl font-bold">${currentUser}</div><div class="text-sm text-gray-500">${data.email}</div></div>
                    </div>
                    <div class="mt-4 space-y-1 text-sm">
                        <p><span class="text-gray-500">Holat:</span> <span class="status-badge ${statusClass}">${data.status}</span></p>
                        <p><span class="text-gray-500">Balans:</span> <strong class="text-[#43A047]">${data.balance.toFixed(2)} ${data.currency}</strong></p>
                        <p><span class="text-gray-500">Salomatlik:</span> <strong class="text-[#43A047]">${data.health_score.toFixed(1)}%</strong></p>
                        <p><span class="text-gray-500">Bio:</span> ${data.bio || 'Yo\'q'}</p>
                    </div>
                </div>
                <div class="bg-white/70 p-5 rounded-xl border border-[#66BB6A33]">
                    <h3 class="text-sm font-bold text-[#43A047]">📊 Statistika</h3>
                    <div class="mt-3 space-y-1 text-sm">
                        <p><span class="text-gray-500">Tokenlar:</span> <strong>${tokenBalance}</strong></p>
                    </div>
                </div>
            </div>
        `;
    } catch (e) { console.error(e); }
}

// ============================================================
// SOCIAL FEED
// ============================================================
async function loadSocialFeed() {
    try {
        const res = await fetch('/api/v2/social/posts');
        const posts = await res.json();
        const container = document.getElementById('social-feed');
        container.innerHTML = '';
        document.getElementById('feed-badge').innerText = posts.length;
        posts.forEach(p => {
            const div = document.createElement('div');
            div.className = 'feed-item';
            div.innerHTML = `
                <div><span class="user">@${p.username}</span> <span class="time">${p.timestamp}</span></div>
                <div>${p.content}</div>
                <div class="actions">
                    <span onclick="likePost('${p.id}')">❤️ ${p.likes || 0}</span>
                    <span onclick="commentPost('${p.id}')">💬 ${p.comments ? p.comments.length : 0}</span>
                </div>
            `;
            container.appendChild(div);
        });
    } catch (e) {}
}

async function createSocialPost() {
    const input = document.getElementById('social-input');
    if (!input.value.trim() || !currentUser) return;
    try {
        const res = await fetch('/api/v2/social/post', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: currentUser, content: input.value })
        });
        if (res.ok) {
            input.value = '';
            loadSocialFeed();
        }
    } catch (e) { alert('Xatolik: ' + e.message); }
}

async function likePost(pid) {
    if (!currentUser) return;
    try {
        await fetch('/api/v2/social/like', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: currentUser, post_id: pid })
        });
        loadSocialFeed();
    } catch (e) {}
}

async function commentPost(pid) {
    if (!currentUser) return;
    const comment = prompt('Komment:');
    if (!comment) return;
    try {
        await fetch('/api/v2/social/comment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: currentUser, post_id: pid, comment: comment })
        });
        loadSocialFeed();
    } catch (e) { alert(e.message); }
}

// ============================================================
// CONSULTATION
// ============================================================
async function sendConsult() {
    const input = document.getElementById('consult-input');
    const msg = input.value.trim();
    if (!msg || !currentUser) return;
    if (tokenBalance < 3) { alert('Token yetarli emas!'); return; }
    tokenBalance -= 3;
    const box = document.getElementById('consult-chat');
    box.innerHTML += `<div class="chat-msg user">${msg}</div>`;
    input.value = '';
    box.scrollTop = box.scrollHeight;

    try {
        const res = await fetch('/api/v2/ai/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: currentUser, message: msg })
        });
        const data = await res.json();
        if (data.success) {
            box.innerHTML += `<div class="chat-msg ai">${data.response}</div>`;
            loadProfile();
        } else {
            box.innerHTML += `<div class="chat-msg warning">${data.message}</div>`;
        }
    } catch (e) { box.innerHTML += `<div class="chat-msg warning">${e.message}</div>`; }
    box.scrollTop = box.scrollHeight;
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && document.activeElement?.id === 'consult-input') sendConsult();
    if (e.key === 'Enter' && document.activeElement?.id === 'social-input') createSocialPost();
});

// Camera
async function startCamera() {
    try {
        const video = document.getElementById('camera-preview');
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
        cameraStream = stream;
        video.srcObject = stream;
        video.style.display = 'block';
        document.getElementById('camera-placeholder').style.display = 'none';
        cameraActive = true;
    } catch (err) { alert('Kamera yoqish xatosi: ' + err.message); }
}

function stopCamera() {
    if (cameraStream) { cameraStream.getTracks().forEach(t => t.stop()); cameraStream = null; }
    document.getElementById('camera-preview').style.display = 'none';
    document.getElementById('camera-placeholder').style.display = 'block';
    cameraActive = false;
}

async function captureAndAnalyze() {
    if (!currentUser) return;
    const video = document.getElementById('camera-preview');
    if (!cameraActive || video.style.display === 'none') { alert('Kamerani yoqing!'); return; }
    if (tokenBalance < 10) { alert('Token yetarli emas! (10 token)'); return; }
    tokenBalance -= 10;

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const base64 = canvas.toDataURL('image/jpeg');

    const result = document.getElementById('camera-result');
    result.innerText = '⏳ Tahlil...';
    try {
        const res = await fetch('/api/v2/camera/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: currentUser, department_id: 1, image_data: base64 })
        });
        const data = await res.json();
        if (data.success) { result.innerText = '🔬 ' + data.analysis; loadProfile(); }
        else { result.innerText = '❌ ' + data.message; }
    } catch (e) { result.innerText = '❌ ' + e.message; }
}

// Voice
function startVoice() {
    if (!('webkitSpeechRecognition' in window)) { alert('Brauzer ovozni qo‘llab-quvvatlamaydi'); return; }
    if (voiceActive) { stopVoice(); return; }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.lang = 'uz-UZ';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onstart = () => {
        voiceActive = true;
        document.getElementById('voice-status').innerHTML = '<span class="voice-indicator"></span> Aytishni boshlang...';
    };
    recognition.onresult = (event) => {
        let final = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) final += event.results[i][0].transcript;
        }
        if (final) {
            document.getElementById('voice-transcript').innerText = final;
            document.getElementById('consult-input').value = final;
            sendConsult();
        }
    };
    recognition.onerror = (e) => { console.error(e); stopVoice(); };
    recognition.start();
}

function stopVoice() {
    if (recognition) { recognition.stop(); recognition = null; }
    voiceActive = false;
    document.getElementById('voice-status').innerHTML = '';
}

// ============================================================
// HEALTH RANKING
// ============================================================
async function loadHealthRanking() {
    try {
        const res = await fetch('/api/v2/health/ranking');
        const data = await res.json();
        const container = document.getElementById('health-ranking');
        container.innerHTML = '';
        data.slice(0, 10).forEach((item, idx) => {
            const div = document.createElement('div');
            div.className = 'ranking-item';
            div.innerHTML = `<span class="pos">${idx+1}</span><span>${item.avatar || '🧬'}</span><span class="name">${item.username}</span><span class="score">${item.health_score}%</span>`;
            container.appendChild(div);
        });
    } catch (e) {}
}

// ============================================================
// STATS
// ============================================================
async function loadStats() {
    try {
        const res = await fetch('/api/v2/system/stats');
        const data = await res.json();
        const container = document.getElementById('stats-content');
        container.innerHTML = `
            <div class="bg-white p-4 rounded-xl text-center shadow"><div class="text-2xl font-bold text-[#43A047]">$${data.total_revenue || 0}</div><div class="text-xs text-gray-500">Daromad</div></div>
            <div class="bg-white p-4 rounded-xl text-center shadow"><div class="text-2xl font-bold text-[#43A047]">${data.active_users || 0}</div><div class="text-xs text-gray-500">Aktiv</div></div>
            <div class="bg-white p-4 rounded-xl text-center shadow"><div class="text-2xl font-bold text-[#FFB300]">${data.total_sales || 0}</div><div class="text-xs text-gray-500">Sotuv</div></div>
            <div class="bg-white p-4 rounded-xl text-center shadow"><div class="text-2xl font-bold text-[#43A047]">${data.total_social_posts || 0}</div><div class="text-xs text-gray-500">Post</div></div>
        `;
    } catch (e) {}
}

// ============================================================
// ADS
// ============================================================
async function loadAdsPerformance() {
    try {
        const res = await fetch('/api/v2/ai/ads-performance');
        const data = await res.json();
        const container = document.getElementById('ads-performance');
        container.innerHTML = '<div class="text-gray-400 text-sm">Hozircha kampaniya yo\'q</div>';
    } catch (e) {}
}

// ============================================================
// PACKAGES
// ============================================================
function renderPackages() {
    const container = document.getElementById('package-grid');
    container.innerHTML = `
        <div class="package-card"><div class="pkg-name">1 Haftalik</div><div class="pkg-price">$999</div></div>
        <div class="package-card"><div class="pkg-name">1 Oylik</div><div class="pkg-price">$9,999</div></div>
        <div class="package-card"><div class="pkg-name">3 Oylik</div><div class="pkg-price">$299,999</div></div>
        <div class="package-card"><div class="pkg-name">1 Yillik</div><div class="pkg-price">$1,199,999</div></div>
    `;
}

// ============================================================
// ADMIN
// ============================================================
async function adminLogin() {
    const user = document.getElementById('admin-user').value.trim();
    const pass = document.getElementById('admin-pass').value.trim();
    if (!user || !pass) { alert('Admin ma\'lumotlarini kiriting!'); return; }
    try {
        const res = await fetch('/api/v2/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: user, password: pass })
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('admin-content').classList.remove('hidden');
            adminLoadDashboard();
        } else { alert('Noto\'g\'ri admin ma\'lumotlari'); }
    } catch (e) { alert(e.message); }
}

async function adminLoadDashboard() {
    try {
        const res = await fetch(`/api/v2/admin/dashboard?username=CEO&password=12345678`);
        const data = await res.json();
        const grid = document.getElementById('admin-stats-grid');
        grid.innerHTML = `
            <div class="bg-white p-4 rounded-xl text-center"><div class="text-2xl font-bold">${data.total_users || 0}</div><div class="text-xs text-gray-500">Foydalanuvchilar</div></div>
            <div class="bg-white p-4 rounded-xl text-center"><div class="text-2xl font-bold text-[#FFB300]">$${data.total_revenue || 0}</div><div class="text-xs text-gray-500">Daromad</div></div>
        `;
        document.getElementById('admin-data').innerHTML = `<pre class="text-xs">${JSON.stringify(data, null, 2)}</pre>`;
    } catch (e) {}
}
</script>
</body>
</html>"""

# ==========================================
# ENDPOINTLAR
# ==========================================
@app.get("/", response_class=HTMLResponse)
@app.head("/", response_class=HTMLResponse)
async def root():
    return HTML

# AUTH – RO'YXATDAN O'TISH (TO'LIQ ISHLAYDI)
@app.post("/api/v2/auth/signup")
async def signup(user: UserRegister):
    async with db_lock:
        # 1. Username mavjudligini tekshirish
        if user.username in db["users"]:
            raise HTTPException(status_code=400, detail="Bu username allaqachon band.")
        
        # 2. Valyutani aniqlash
        curr = user.currency.upper()
        if curr not in EXCHANGE_RATES:
            curr = "USD"
        
        # 3. Boshlang'ich balans
        initial_balance = 25000.0 * EXCHANGE_RATES[curr]
        
        # 4. Foydalanuvchini qo'shish
        db["users"][user.username] = {
            "email": user.email,
            "password_hash": hash_password(user.password),
            "currency": curr,
            "balance": initial_balance,
            "status": "WARNING",
            "department": "None",
            "health_score": 85.0,
            "last_purchase": None,
            "packages": [],
            "avatar": "🧬",
            "bio": "BioEmpire tizimiga yangi qo'shildim",
            "full_name": "",
            "age": None,
            "gender": "",
            "phone": "",
            "address": "",
            "social_links": {},
            "registered_at": datetime.now().isoformat()
        }
        
        # 5. Aktiv foydalanuvchilar sonini yangilash
        db["system_vault"]["active_users"] = len(db["users"])
        
        # 6. Faylga saqlash
        success = save_db(db)
        if not success:
            raise HTTPException(status_code=500, detail="Ma'lumotlarni saqlashda xatolik.")
        
        return {
            "status": "success",
            "username": user.username,
            "balance": initial_balance,
            "currency": curr
        }

# AUTH – KIRISH (TO'LIQ ISHLAYDI)
@app.post("/api/v2/auth/signin")
async def signin(user: UserLogin):
    async with db_lock:
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
            "department": target["department"],
            "health_score": target["health_score"],
            "avatar": target.get("avatar", "🧬"),
            "bio": target.get("bio", "")
        }

# ==========================================
# BOSHQA ENDPOINTLAR
# ==========================================
@app.get("/api/v2/profile/{username}")
async def get_profile(username: str):
    async with db_lock:
        if username not in db["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        return db["users"][username]

@app.get("/api/v2/social/posts")
async def social_posts():
    return db["social_posts"]

@app.post("/api/v2/social/post")
async def create_post(req: SocialPostRequest):
    async with db_lock:
        if req.username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        post = generate_social_post(req.username, req.content)
        add_social_post(post)
        return post

@app.post("/api/v2/social/like")
async def like(req: LikeRequest):
    async with db_lock:
        for post in db["social_posts"]:
            if post["id"] == req.post_id:
                post["likes"] = post.get("likes", 0) + 1
                save_db(db)
                return {"success": True, "likes": post["likes"]}
        raise HTTPException(404, "Post topilmadi.")

@app.post("/api/v2/social/comment")
async def comment(req: CommentRequest):
    async with db_lock:
        for post in db["social_posts"]:
            if post["id"] == req.post_id:
                if "comments" not in post:
                    post["comments"] = []
                comment_obj = {
                    "username": req.username,
                    "text": req.comment,
                    "timestamp": datetime.now().isoformat()
                }
                post["comments"].append(comment_obj)
                save_db(db)
                return {"success": True, "comment": comment_obj}
        raise HTTPException(404, "Post topilmadi.")

@app.post("/api/v2/ai/chat")
async def ai_chat(req: AIChatRequest):
    async with db_lock:
        if req.username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        user = db["users"][req.username]
        currency = user["currency"]
        rate = EXCHANGE_RATES[currency]
        chat_price = CHAT_PRICE_USD * rate
        if user["balance"] < chat_price:
            return {"success": False, "message": f"⚠️ AI chat uchun ${chat_price:.2f} kerak."}
        user["balance"] -= chat_price
        db["system_vault"]["total_revenue"] += chat_price
        save_db(db)

        messages = [
            {"role": "system", "content": "Siz BioEmpire AI shifokorisiz. Kasalliklar haqida batafsil ma'lumot bering."},
            {"role": "user", "content": req.message}
        ]
        ai_response = await call_ai_api(messages)
        if not ai_response:
            ai_response = "AI hozir javob bera olmadi. Keyinroq urinib ko'ring."

        return {"success": True, "response": ai_response, "new_balance": user["balance"], "deducted": chat_price}

@app.post("/api/v2/camera/analyze")
async def camera_analyze(req: CameraAnalysisRequest):
    async with db_lock:
        if req.username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        user = db["users"][req.username]
        currency = user["currency"]
        rate = EXCHANGE_RATES[currency]
        analysis_price = CAMERA_PRICE_USD * rate
        if user["balance"] < analysis_price:
            return {"success": False, "message": f"⚠️ Kamera analizi uchun ${analysis_price:.2f} kerak."}
        user["balance"] -= analysis_price
        db["system_vault"]["total_revenue"] += analysis_price
        save_db(db)

        analysis_result = "Rasm tahlili bajarilmadi."
        if req.image_data and GEMINI_AVAILABLE and GEMINI_API_KEY:
            try:
                image_bytes = base64.b64decode(req.image_data.split(",")[1] if "," in req.image_data else req.image_data)
                model = genai.GenerativeModel(GEMINI_MODEL)
                response = await asyncio.to_thread(
                    model.generate_content,
                    ["Ushbu rasmni tahlil qiling va diagnostik tavsiya bering.", {"mime_type": "image/jpeg", "data": image_bytes}]
                )
                if response and response.text:
                    analysis_result = response.text
            except Exception as e:
                analysis_result = f"Xatolik: {e}"

        if not analysis_result or "xatolik" in analysis_result.lower():
            messages = [{"role": "system", "content": "Siz AI analistisisiz."}, {"role": "user", "content": f"Rasm tahlili: {analysis_result}"}]
            ai_response = await call_ai_api(messages)
            if ai_response:
                analysis_result = ai_response

        return {"success": True, "analysis": analysis_result, "new_balance": user["balance"], "deducted": analysis_price}

@app.get("/api/v2/health/ranking")
async def health_ranking():
    async with db_lock:
        ranking = []
        for username, user in db["users"].items():
            ranking.append({
                "username": username,
                "health_score": user.get("health_score", 0),
                "status": user.get("status", "WARNING"),
                "avatar": user.get("avatar", "🧬")
            })
        ranking.sort(key=lambda x: x["health_score"], reverse=True)
        return ranking

@app.get("/api/v2/system/stats")
async def system_stats():
    return {
        "total_revenue": db["system_vault"]["total_revenue"],
        "active_users": db["system_vault"]["active_users"],
        "total_sales": len(db.get("product_sales", [])),
        "total_social_posts": len(db["social_posts"])
    }

@app.get("/api/v2/ai/ads-performance")
async def ads_performance():
    return db["ads_performance"]

@app.post("/api/v2/admin/login")
async def admin_login(request: Request):
    data = await request.json()
    if data.get("username") == ADMIN_USERNAME and hash_password(data.get("password", "")) == ADMIN_PASSWORD_HASH:
        return {"success": True, "token": "admin-token"}
    raise HTTPException(401, "Noto'g'ri")

@app.get("/api/v2/admin/dashboard")
async def admin_dashboard(username: str = None, password: str = None):
    if username != ADMIN_USERNAME or hash_password(password or "") != ADMIN_PASSWORD_HASH:
        raise HTTPException(401, "Avtorizatsiya kerak")
    return {
        "total_users": len(db["users"]),
        "total_revenue": db["system_vault"]["total_revenue"],
        "active_users": db["system_vault"]["active_users"],
        "total_sales": len(db.get("product_sales", []))
    }

# ==========================================
# SERVER
# ==========================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
