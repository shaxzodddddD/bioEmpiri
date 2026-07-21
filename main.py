import os
import json
import random
import asyncio
import hashlib
import httpx
import base64
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# -------------------- GEMINI --------------------
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# -------------------- CONFIG --------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-1.5-flash"

if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# -------------------- DATABASE --------------------
DB_FILE = "database_log.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "users": {},
        "social_posts": [],
        "system_vault": {"total_revenue": 0, "active_users": 0},
        "notifications": [],
        "user_activity": {},
        "product_sales": [],
        "ai_logs": [],
        "ads_performance": {}
    }

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

db = load_db()

# -------------------- HELPERS --------------------
def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def generate_post_id():
    return f"post_{random.randint(10000,99999)}_{int(datetime.now().timestamp())}"

# -------------------- PYDANTIC MODELS --------------------
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

# -------------------- AI CALLS --------------------
async def call_ai_api(messages: List[dict]) -> Optional[str]:
    # Gemini
    if GEMINI_AVAILABLE and GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel(GEMINI_MODEL)
            prompt = "\n".join([m["content"] for m in messages])
            response = await asyncio.to_thread(model.generate_content, prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            print("Gemini error:", e)
    # Groq
    if GROQ_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                    json={"model": "mixtral-8x7b-32768", "messages": messages, "temperature": 0.7, "max_tokens": 2048}
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print("Groq error:", e)
    return None

# -------------------- HTML (to'liq) --------------------
HTML_PAGE = """<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧬 BioEmpire</title>
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

<div id="main-dashboard" style="display:none;">
    <header class="fixed top-0 left-0 w-full z-50 bg-white/90 backdrop-blur-md border-b border-[#66BB6A33] px-4 py-2 flex items-center justify-between">
        <div class="flex items-center gap-3 cursor-pointer" onclick="location.reload()">
            <span class="text-3xl">🧬</span>
            <span class="text-xl font-black text-[#2E7D32]">BioEmpire ∞</span>
        </div>
        <div class="flex items-center gap-4">
            <span id="header-user" class="text-xs text-[#43A047] hidden"></span>
            <button id="logout-btn" class="btn-red btn-sm hidden" onclick="logout()">Chiqish</button>
        </div>
    </header>

    <div class="flex pt-[68px]">
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
            <button class="sidebar-btn active" data-panel="panel-consult" onclick="switchPanel('panel-consult', this)"><span class="icon">🩺</span><span class="btn-text">Konsultatsiya</span></button>
            <button class="sidebar-btn" data-panel="panel-social" onclick="switchPanel('panel-social', this)"><span class="icon">📡</span><span class="btn-text">Ijtimoiy</span></button>
            <button class="sidebar-btn" data-panel="panel-profile" onclick="switchPanel('panel-profile', this)"><span class="icon">👤</span><span class="btn-text">Profil</span></button>
            <button class="sidebar-btn" data-panel="panel-packages" onclick="switchPanel('panel-packages', this)"><span class="icon">📦</span><span class="btn-text">Paketlar</span></button>
            <button class="sidebar-btn" data-panel="panel-stats" onclick="switchPanel('panel-stats', this)"><span class="icon">📊</span><span class="btn-text">Statistika</span></button>
            <button class="sidebar-btn" data-panel="panel-admin" onclick="switchPanel('panel-admin', this)"><span class="icon">⚙️</span><span class="btn-text">Admin</span></button>
        </aside>

        <main class="flex-1 min-w-0 p-4 max-w-full">
            <div id="panel-consult" class="panel active">
                <div class="glass p-5">
                    <h2 class="text-xl font-bold text-[#43A047] mb-3">🩺 AI KONSULTATSIYA</h2>
                    <div class="mb-4">
                        <button class="btn-cyber btn-sm" onclick="startCamera()">📷 Kamerani yoqish</button>
                        <button class="btn-gold btn-sm" onclick="captureAndAnalyze()">🔬 Suratga olib tahlil</button>
                        <button class="btn-red btn-sm" onclick="stopCamera()">⏹ To'xtatish</button>
                        <video id="camera-preview" autoplay playsinline style="display:none;"></video>
                        <div id="camera-placeholder" class="bg-gray-100 rounded-xl p-4 text-center text-gray-400 text-sm border border-dashed border-[#66BB6A33]">Kamera o'chirilgan</div>
                        <div id="camera-result" class="mt-2 text-sm text-[#43A047]"></div>
                    </div>
                    <div>
                        <div class="chat-terminal" id="consult-chat">
                            <div class="chat-msg ai">Salom! Men AI shifokorman. Simptomlaringizni yozing.</div>
                        </div>
                        <div class="flex gap-2 mt-3">
                            <input id="consult-input" type="text" placeholder="Xabar yozing..." class="flex-1 bg-white border border-[#66BB6A33] rounded-xl px-4 py-2 text-sm text-[#1B3A1B] outline-none" />
                            <button class="btn-cyber btn-sm" onclick="sendConsult()">Yuborish</button>
                        </div>
                    </div>
                </div>
            </div>

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

            <div id="panel-profile" class="panel">
                <div class="glass p-5">
                    <h2 class="text-xl font-bold text-[#43A047] mb-3">👤 Profil</h2>
                    <div id="profile-content"></div>
                </div>
            </div>

            <div id="panel-packages" class="panel">
                <div class="glass p-5">
                    <h2 class="text-xl font-bold text-[#FFB300] mb-3">📦 Paketlar</h2>
                    <div class="package-grid" id="package-grid"></div>
                </div>
            </div>

            <div id="panel-stats" class="panel">
                <div class="glass p-5">
                    <h2 class="text-xl font-bold text-[#43A047] mb-3">📊 Statistika</h2>
                    <div id="stats-content"></div>
                    <div class="mt-4"><h3 class="text-sm font-bold text-[#43A047]">🏅 Salomatlik reytingi</h3><div id="health-ranking"></div></div>
                </div>
            </div>

            <div id="panel-admin" class="panel">
                <div class="glass p-5">
                    <h2 class="text-xl font-bold text-[#FFB300] mb-3">⚙️ Admin</h2>
                    <div class="flex gap-2 mb-4">
                        <input id="admin-user" type="text" placeholder="Admin" value="CEO" class="bg-white border border-[#66BB6A33] rounded-xl px-3 py-1 text-sm outline-none" />
                        <input id="admin-pass" type="password" placeholder="Parol" value="12345678" class="bg-white border border-[#66BB6A33] rounded-xl px-3 py-1 text-sm outline-none" />
                        <button class="btn-cyber btn-sm" onclick="adminLogin()">🔐 Kirish</button>
                    </div>
                    <div id="admin-content" class="hidden">
                        <div id="admin-stats-grid" class="grid grid-cols-2 gap-3 mb-4"></div>
                        <div id="admin-data" class="mt-3 max-h-[300px] overflow-y-auto text-sm"></div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<script>
let currentUser = null;
let authMode = 'signup';
let tokenBalance = 100;
let cameraStream = null;
let cameraActive = false;

// Auth
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
        renderPackages();
    } catch (e) { errEl.innerText = "Tarmoq xatosi: " + e.message; }
}

function logout() {
    currentUser = null;
    location.reload();
}

function switchPanel(panelId, btn) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.getElementById(panelId).classList.add('active');
    document.querySelectorAll('.sidebar-btn[data-panel]').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    if (panelId === 'panel-profile') loadProfile();
    if (panelId === 'panel-social') loadSocialFeed();
    if (panelId === 'panel-stats') { loadStats(); loadHealthRanking(); }
}

async function loadProfile() {
    if (!currentUser) return;
    try {
        const res = await fetch(`/api/v2/profile/${currentUser}`);
        const data = await res.json();
        document.getElementById('sidebar-username').innerText = currentUser;
        document.getElementById('sidebar-balance').innerText = data.balance.toFixed(2);
        document.getElementById('sidebar-status').innerText = data.status;
        document.getElementById('sidebar-avatar').innerText = data.avatar || '🧬';
        document.getElementById('profile-content').innerHTML = `
            <div class="bg-white/70 p-5 rounded-xl border border-[#66BB6A33]">
                <div class="flex items-center gap-4">
                    <div class="avatar-lg text-4xl">${data.avatar || '🧬'}</div>
                    <div><div class="text-xl font-bold">${currentUser}</div><div class="text-sm text-gray-500">${data.email}</div></div>
                </div>
                <div class="mt-4 space-y-1 text-sm">
                    <p><span class="text-gray-500">Holat:</span> <span class="status-badge status-warning">${data.status}</span></p>
                    <p><span class="text-gray-500">Balans:</span> <strong class="text-[#43A047]">${data.balance.toFixed(2)} ${data.currency}</strong></p>
                    <p><span class="text-gray-500">Salomatlik:</span> <strong class="text-[#43A047]">${data.health_score}%</strong></p>
                </div>
            </div>
        `;
    } catch (e) { console.error(e); }
}

async function loadSocialFeed() {
    try {
        const res = await fetch('/api/v2/social/posts');
        const posts = await res.json();
        const container = document.getElementById('social-feed');
        container.innerHTML = '';
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
        await fetch('/api/v2/social/post', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: currentUser, content: input.value })
        });
        input.value = '';
        loadSocialFeed();
    } catch (e) { alert('Xatolik: ' + e.message); }
}

async function likePost(pid) {
    if (!currentUser) return;
    try {
        await fetch('/api/v2/social/like', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: currentUser, post_id: pid }) });
        loadSocialFeed();
    } catch (e) {}
}

async function commentPost(pid) {
    if (!currentUser) return;
    const comment = prompt('Komment:');
    if (!comment) return;
    try {
        await fetch('/api/v2/social/comment', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: currentUser, post_id: pid, comment: comment }) });
        loadSocialFeed();
    } catch (e) { alert(e.message); }
}

async function sendConsult() {
    const input = document.getElementById('consult-input');
    const msg = input.value.trim();
    if (!msg || !currentUser) return;
    const box = document.getElementById('consult-chat');
    box.innerHTML += `<div class="chat-msg user">${msg}</div>`;
    input.value = '';
    try {
        const res = await fetch('/api/v2/ai/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: currentUser, message: msg })
        });
        const data = await res.json();
        if (data.success) {
            box.innerHTML += `<div class="chat-msg ai">${data.response}</div>`;
        } else {
            box.innerHTML += `<div class="chat-msg warning">${data.message}</div>`;
        }
    } catch (e) { box.innerHTML += `<div class="chat-msg warning">${e.message}</div>`; }
    box.scrollTop = box.scrollHeight;
}

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
        if (data.success) { result.innerText = '🔬 ' + data.analysis; }
        else { result.innerText = '❌ ' + data.message; }
    } catch (e) { result.innerText = '❌ ' + e.message; }
}

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

async function loadStats() {
    try {
        const res = await fetch('/api/v2/system/stats');
        const data = await res.json();
        const container = document.getElementById('stats-content');
        container.innerHTML = `
            <div class="grid grid-cols-2 gap-4">
                <div class="bg-white p-4 rounded-xl text-center shadow"><div class="text-2xl font-bold text-[#43A047]">$${data.total_revenue || 0}</div><div class="text-xs text-gray-500">Daromad</div></div>
                <div class="bg-white p-4 rounded-xl text-center shadow"><div class="text-2xl font-bold text-[#43A047]">${data.active_users || 0}</div><div class="text-xs text-gray-500">Aktiv</div></div>
            </div>
        `;
    } catch (e) {}
}

function renderPackages() {
    const container = document.getElementById('package-grid');
    container.innerHTML = `
        <div class="package-card"><div class="pkg-name">1 Haftalik</div><div class="pkg-price">$999</div></div>
        <div class="package-card"><div class="pkg-name">1 Oylik</div><div class="pkg-price">$9,999</div></div>
        <div class="package-card"><div class="pkg-name">1 Yillik</div><div class="pkg-price">$1,199,999</div></div>
    `;
}

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
        document.getElementById('admin-stats-grid').innerHTML = `
            <div class="bg-white p-4 rounded-xl text-center"><div class="text-2xl font-bold">${data.total_users || 0}</div><div class="text-xs text-gray-500">Foydalanuvchilar</div></div>
            <div class="bg-white p-4 rounded-xl text-center"><div class="text-2xl font-bold text-[#FFB300]">$${data.total_revenue || 0}</div><div class="text-xs text-gray-500">Daromad</div></div>
        `;
        document.getElementById('admin-data').innerHTML = `<pre class="text-xs">${JSON.stringify(data, null, 2)}</pre>`;
    } catch (e) {}
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && document.activeElement?.id === 'consult-input') sendConsult();
});
</script>
</body>
</html>"""

# ==========================================
# ENDPOINTS
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_PAGE

@app.post("/api/v2/auth/signup")
async def signup(user: UserRegister):
    if user.username in db["users"]:
        raise HTTPException(400, "Bu username allaqachon band.")
    currency = user.currency.upper()
    if currency not in ["USD", "EUR", "BTC", "SOL"]:
        currency = "USD"
    initial_balance = 25000.0  # USD
    db["users"][user.username] = {
        "email": user.email,
        "password_hash": hash_password(user.password),
        "currency": currency,
        "balance": initial_balance,
        "status": "WARNING",
        "department": "None",
        "health_score": 85.0,
        "avatar": "🧬",
        "bio": "BioEmpire tizimiga yangi qo'shildim",
        "registered_at": datetime.now().isoformat()
    }
    db["system_vault"]["active_users"] = len(db["users"])
    save_db(db)
    return {"status": "success", "username": user.username, "balance": initial_balance, "currency": currency}

@app.post("/api/v2/auth/signin")
async def signin(user: UserLogin):
    if user.username not in db["users"]:
        raise HTTPException(400, "Noto'g'ri username yoki parol.")
    target = db["users"][user.username]
    if target["password_hash"] != hash_password(user.password):
        raise HTTPException(400, "Noto'g'ri username yoki parol.")
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

@app.get("/api/v2/profile/{username}")
async def get_profile(username: str):
    if username not in db["users"]:
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    return db["users"][username]

@app.get("/api/v2/social/posts")
async def social_posts():
    return db["social_posts"]

@app.post("/api/v2/social/post")
async def create_post(req: SocialPostRequest):
    if req.username not in db["users"]:
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    post = {
        "id": generate_post_id(),
        "username": req.username,
        "content": req.content,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "likes": 0,
        "comments": []
    }
    db["social_posts"].insert(0, post)
    save_db(db)
    return post

@app.post("/api/v2/social/like")
async def like(req: LikeRequest):
    for post in db["social_posts"]:
        if post["id"] == req.post_id:
            post["likes"] = post.get("likes", 0) + 1
            save_db(db)
            return {"success": True, "likes": post["likes"]}
    raise HTTPException(404, "Post topilmadi.")

@app.post("/api/v2/social/comment")
async def comment(req: CommentRequest):
    for post in db["social_posts"]:
        if post["id"] == req.post_id:
            if "comments" not in post:
                post["comments"] = []
            post["comments"].append({
                "username": req.username,
                "text": req.comment,
                "timestamp": datetime.now().isoformat()
            })
            save_db(db)
            return {"success": True, "comment": post["comments"][-1]}
    raise HTTPException(404, "Post topilmadi.")

@app.post("/api/v2/ai/chat")
async def ai_chat(req: AIChatRequest):
    if req.username not in db["users"]:
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    user = db["users"][req.username]
    messages = [
        {"role": "system", "content": "Siz BioEmpire AI shifokorisiz. Kasalliklar, davolanish va sog'liq haqida maslahat bering."},
        {"role": "user", "content": req.message}
    ]
    ai_response = await call_ai_api(messages)
    if not ai_response:
        ai_response = "Kechirasiz, AI hozir javob bera olmadi. Iltimos, keyinroq urinib ko'ring."
    return {"success": True, "response": ai_response}

@app.post("/api/v2/camera/analyze")
async def camera_analyze(req: CameraAnalysisRequest):
    analysis = "Rasm tahlili: Hech narsa aniqlanmadi."
    if req.image_data and GEMINI_AVAILABLE and GEMINI_API_KEY:
        try:
            image_bytes = base64.b64decode(req.image_data.split(",")[1])
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = await asyncio.to_thread(
                model.generate_content,
                ["Ushbu rasmni tahlil qiling va diagnostik tavsiya bering.", {"mime_type": "image/jpeg", "data": image_bytes}]
            )
            if response and response.text:
                analysis = response.text
        except Exception as e:
            analysis = f"Rasm tahlilida xatolik: {e}"
    return {"success": True, "analysis": analysis}

@app.get("/api/v2/health/ranking")
async def health_ranking():
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

@app.post("/api/v2/admin/login")
async def admin_login(request: Request):
    data = await request.json()
    if data.get("username") == "CEO" and hash_password(data.get("password", "")) == hash_password("12345678"):
        return {"success": True, "token": "admin-token"}
    raise HTTPException(401, "Noto'g'ri")

@app.get("/api/v2/admin/dashboard")
async def admin_dashboard(username: str = None, password: str = None):
    if username != "CEO" or hash_password(password or "") != hash_password("12345678"):
        raise HTTPException(401, "Avtorizatsiya kerak")
    return {
        "total_users": len(db["users"]),
        "total_revenue": db["system_vault"]["total_revenue"],
        "active_users": db["system_vault"]["active_users"]
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
