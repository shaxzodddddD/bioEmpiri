import os
import json
import random
import asyncio
import hashlib
import httpx
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ==========================================
# GEMINI AI (eski kutubxona, lekin ishlaydi)
# ==========================================
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    print("✅ Gemini AI mavjud (eski versiya)")
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Gemini AI o‘rnatilmagan. `pip install google-generativeai`")

# ==========================================
# KONFIGURATSIYANI YUKLASH
# ==========================================
CONFIG_FILE = "config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
else:
    print("❌ config.json topilmadi! Standart sozlamalar qo‘llaniladi.")
    CONFIG = {
        "ui": {},
        "exchange_rates": {"USD": 1.0},
        "packages": {},
        "departments": [],
        "red_zone_departments": [],
        "ecommerce": {"products": []},
        "chat_price_usd": 49,
        "camera_analysis_price_usd": 150,
        "auto_learning_interval": 120,
        "auto_marketing_interval": 120,
        "auto_ads_optimizer_interval": 60,
        "auto_decision_interval": 300,
        "max_ai_history": 50,
        "ai_autonomy": {},
        "admin": {"username": "CEO", "password_hash": hashlib.sha256("12345678".encode()).hexdigest()},
        "legal": {"terms": "", "privacy": "", "rules": []}
    }

# API kalitlari – muhit o‘zgaruvchilaridan olinadi (Render’da sozlang)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", CONFIG.get("api", {}).get("groq_api_key", ""))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", CONFIG.get("api", {}).get("gemini_api_key", ""))

# Sozlamalar
EXCHANGE_RATES = CONFIG.get("exchange_rates", {"USD": 1.0})
PACKAGES = CONFIG.get("packages", {})
DEPARTMENTS = {d["id"]: d for d in CONFIG.get("departments", [])}
RED_ZONE_DEPARTMENTS = {d["id"]: d for d in CONFIG.get("red_zone_departments", [])}
ECOMMERCE = CONFIG.get("ecommerce", {"products": []})
CHAT_PRICE_USD = CONFIG.get("chat_price_usd", 49)
CAMERA_PRICE_USD = CONFIG.get("camera_analysis_price_usd", 150)
PRIMARY_AI = CONFIG.get("api", {}).get("primary_ai", "gemini")
FALLBACK_AI = CONFIG.get("api", {}).get("fallback_ai", "groq")
GROQ_MODEL = CONFIG.get("api", {}).get("groq_model", "mixtral-8x7b-32768")
GEMINI_MODEL = CONFIG.get("api", {}).get("gemini_model", "gemini-1.5-flash")
GROQ_TEMPERATURE = CONFIG.get("api", {}).get("temperature", 0.7)
GROQ_MAX_TOKENS = CONFIG.get("api", {}).get("max_tokens", 2048)
AUTO_LEARNING_INTERVAL = CONFIG.get("auto_learning_interval", 120)
AUTO_MARKETING_INTERVAL = CONFIG.get("auto_marketing_interval", 120)
AUTO_ADS_OPTIMIZER_INTERVAL = CONFIG.get("auto_ads_optimizer_interval", 60)
AUTO_DECISION_INTERVAL = CONFIG.get("auto_decision_interval", 300)
MAX_AI_HISTORY = CONFIG.get("max_ai_history", 50)
AI_AUTONOMY = CONFIG.get("ai_autonomy", {})
ADMIN_USERNAME = CONFIG.get("admin", {}).get("username", "CEO")
ADMIN_PASSWORD_HASH = CONFIG.get("admin", {}).get("password_hash", hashlib.sha256("12345678".encode()).hexdigest())
LEGAL = CONFIG.get("legal", {})

if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ Gemini API sozlandi")
else:
    print("⚠️ Gemini API sozlanmadi – kalitni tekshiring")

# ==========================================
# MA'LUMOTLAR BAZASI (JSON fayllar)
# ==========================================
DB_FILE = "database_log.json"
BACKUP_FILE = "database_log_backup.json"

app = FastAPI(title="BioEmpire V9.4", version="9.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
db_lock = asyncio.Lock()
ai_chat_history = {}

# ==========================================
# MA'LUMOTLARNI YUKLASH / SAQLASH
# ==========================================
def load_initial_state() -> dict:
    default_state = {
        "users": {},
        "feed": [],
        "social_posts": [],
        "system_vault": {"total_revenue": 0.0, "active_users": 0},
        "likes": {},
        "health_rankings": {},
        "notifications": [],
        "user_activity": {},
        "tournaments": [],
        "crypto_wallets": {},
        "product_sales": [],
        "ai_decisions": [],
        "ai_insights": [],
        "ai_strategies": [],
        "marketing_campaigns": [],
        "price_history": {},
        "product_performance": {},
        "ai_logs": [],
        "ai_self_improvements": [],
        "ads_performance": {},
        "comments": {},
        "follows": {},
        "ceo_ideas": []
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key in default_state:
                    if key not in data:
                        data[key] = default_state[key]
                return data
        except Exception:
            return default_state
    return default_state

db_state = load_initial_state()

def sync_save_to_disk():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db_state, f, indent=4, ensure_ascii=False)
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(db_state, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[ERROR] Diskka yozishda xatolik: {e}")
        return False

async def save_state():
    await asyncio.to_thread(sync_save_to_disk)

# ==========================================
# WEBSOCKET MANAGER
# ==========================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# ==========================================
# AI API CALLS
# ==========================================
async def call_groq_api(messages: List[dict]) -> Optional[str]:
    if not GROQ_API_KEY:
        print("[Groq] API kaliti yo'q")
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": GROQ_TEMPERATURE,
        "max_tokens": GROQ_MAX_TOKENS
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print(f"[Groq] Javob olindi: {content[:50]}...")
                return content
            else:
                print(f"[Groq] Xatolik {response.status_code}: {response.text}")
                return None
    except Exception as e:
        print(f"[Groq] Xatolik: {e}")
        return None

async def call_gemini_api(messages: List[dict]) -> Optional[str]:
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        print("[Gemini] API kaliti yo'q yoki kutubxona mavjud emas")
        return None
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        user_message = messages[-1]["content"] if messages else ""
        context = "\n".join([m["content"] for m in messages if m["role"] == "system"])
        full_prompt = f"{context}\n\nFoydalanuvchi: {user_message}" if context else user_message
        response = await asyncio.to_thread(model.generate_content, full_prompt)
        if response and response.text:
            print(f"[Gemini] Javob olindi: {response.text[:50]}...")
            return response.text
        else:
            print("[Gemini] Javob bo'sh")
            return None
    except Exception as e:
        print(f"[Gemini] Xatolik: {e}")
        return None

async def call_ai_api(messages: List[dict]) -> Optional[str]:
    if PRIMARY_AI == "gemini":
        response = await call_gemini_api(messages)
        if response:
            return response
        print("[AI] Gemini ishlamadi, Groq ga o'tilmoqda")
        return await call_groq_api(messages)
    else:
        response = await call_groq_api(messages)
        if response:
            return response
        print("[AI] Groq ishlamadi, Gemini ga o'tilmoqda")
        return await call_gemini_api(messages)

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

class PainInput(BaseModel):
    username: str
    department_id: int
    text: str

class PurchaseRequest(BaseModel):
    username: str
    package_type: str

class ChatRequest(BaseModel):
    username: str
    message: str

class CameraAnalysisRequest(BaseModel):
    username: str
    department_id: int
    image_data: Optional[str] = None

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

class FollowRequest(BaseModel):
    username: str
    target: str

class TournamentJoin(BaseModel):
    username: str
    tournament_id: str

class TournamentScore(BaseModel):
    username: str
    tournament_id: str
    score: float

class CryptoConnect(BaseModel):
    username: str
    wallet_address: str

class CryptoPay(BaseModel):
    username: str
    amount: float
    currency: str = "USD"

class EmailReport(BaseModel):
    username: str
    email: str

class VirtualDoctorRequest(BaseModel):
    username: str
    symptoms: str
    level: str = "doctor"

class ProductOrderRequest(BaseModel):
    username: str
    product_id: str
    quantity: int = 1

class AIChatRequest(BaseModel):
    username: str
    message: str
    context: Optional[str] = None

class AIRecommendationRequest(BaseModel):
    username: str
    context: str

class ProfileUpdate(BaseModel):
    username: str
    full_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None
    social_links: Optional[dict] = None

# ==========================================
# YORDAMCHI FUNKSIYALAR
# ==========================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_post_id() -> str:
    return f"post_{random.randint(10000, 99999)}_{int(datetime.now().timestamp())}"

def generate_feed_post(username: str, department_name: str, text: str) -> dict:
    return {
        "id": generate_post_id(),
        "username": username,
        "text": text,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "likes": 0,
        "type": "feed"
    }

def generate_social_post(username: str, content: str, is_ai: bool = False) -> dict:
    return {
        "id": generate_post_id(),
        "username": "🧬 BioEmpire_AI" if is_ai else username,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "likes": random.randint(5, 50) if is_ai else 0,
        "comments": [],
        "is_ai": is_ai
    }

def generate_notification(username: str, message: str, type: str = "info") -> dict:
    return {
        "id": generate_post_id(),
        "username": username,
        "message": message,
        "type": type,
        "timestamp": datetime.now().isoformat(),
        "read": False
    }

def add_to_feed(post: dict):
    db_state["feed"].insert(0, post)
    if len(db_state["feed"]) > 50:
        db_state["feed"].pop()

def add_social_post(post: dict):
    db_state["social_posts"].insert(0, post)
    if len(db_state["social_posts"]) > 100:
        db_state["social_posts"].pop()

def add_notification(notification: dict):
    db_state["notifications"].insert(0, notification)
    if len(db_state["notifications"]) > 100:
        db_state["notifications"].pop()

def track_user_activity(username: str, action: str, details: dict = None):
    if username not in db_state["user_activity"]:
        db_state["user_activity"][username] = {
            "last_active": datetime.now().isoformat(),
            "actions": [],
            "total_spent": 0.0,
            "packages_bought": 0
        }
    activity = db_state["user_activity"][username]
    activity["last_active"] = datetime.now().isoformat()
    activity["actions"].append({
        "action": action,
        "timestamp": datetime.now().isoformat(),
        "details": details or {}
    })
    if len(activity["actions"]) > 100:
        activity["actions"] = activity["actions"][-100:]

def ai_log(message: str, level: str = "INFO"):
    db_state["ai_logs"].append({
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message
    })
    if len(db_state["ai_logs"]) > 500:
        db_state["ai_logs"] = db_state["ai_logs"][-500:]

# ==========================================
# AVTONOM AI TASKS (qisqa – to‘liq versiya avvalgi xabarlarda)
# ==========================================
# ... (qoldirilgan, lekin ishlatish mumkin)

# ==========================================
# ENDPOINTLAR (qisqartirilgan – to‘liq avvalgi xabarlarda)
# ==========================================

# Auth
@app.post("/api/v2/auth/signup")
async def signup(user: UserRegister):
    async with db_lock:
        if user.username in db_state["users"]:
            raise HTTPException(status_code=400, detail="Bu username allaqachon band.")
        curr = user.currency.upper()
        if curr not in EXCHANGE_RATES:
            curr = "USD"
        initial_balance = 25000.0 * EXCHANGE_RATES[curr]
        db_state["users"][user.username] = {
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
        db_state["system_vault"]["active_users"] = len(db_state["users"])
        welcome_post = generate_social_post(user.username, f"🌟 Salom hammaga! Men {user.username}, BioEmpire tizimiga endi qo'shildim!", False)
        welcome_post["likes"] = random.randint(5, 30)
        add_social_post(welcome_post)
        track_user_activity(user.username, "signup")
        await save_state()
        return {"status": "success", "username": user.username, "balance": initial_balance, "currency": curr}

@app.post("/api/v2/auth/signin")
async def signin(user: UserLogin):
    async with db_lock:
        if user.username not in db_state["users"]:
            raise HTTPException(status_code=400, detail="Noto'g'ri username yoki parol.")
        target = db_state["users"][user.username]
        if target["password_hash"] != hash_password(user.password):
            raise HTTPException(status_code=400, detail="Noto'g'ri username yoki parol.")
        track_user_activity(user.username, "signin")
        await save_state()
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

# Profile
@app.get("/api/v2/profile/{username}")
async def get_profile(username: str):
    async with db_lock:
        if username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        return db_state["users"][username]

@app.post("/api/v2/profile/update")
async def update_profile(req: ProfileUpdate):
    async with db_lock:
        if req.username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        user = db_state["users"][req.username]
        for key, value in req.dict(exclude_unset=True).items():
            if key != "username" and value is not None:
                user[key] = value
        await save_state()
        return {"success": True, "profile": user}

# Social
@app.get("/api/v2/social/posts")
async def get_social_posts():
    async with db_lock:
        return db_state["social_posts"]

@app.post("/api/v2/social/post")
async def create_social_post(req: SocialPostRequest):
    async with db_lock:
        if req.username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        post = generate_social_post(req.username, req.content, False)
        add_social_post(post)
        track_user_activity(req.username, "social_post", {"content": req.content[:50]})
        await save_state()
        await manager.broadcast({"type": "new_post", "post": post})
        return post

# AI Chat
@app.post("/api/v2/ai/chat")
async def ai_chat(req: AIChatRequest):
    async with db_lock:
        if req.username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        user = db_state["users"][req.username]
        currency = user["currency"]
        rate = EXCHANGE_RATES[currency]

        chat_price = CHAT_PRICE_USD * rate
        if user["balance"] < chat_price:
            return {"success": False, "message": f"⚠️ AI chat uchun ${chat_price:.2f} kerak."}

        user["balance"] -= chat_price
        db_state["system_vault"]["total_revenue"] += chat_price
        track_user_activity(req.username, "ai_chat", {"message": req.message[:50]})

        if req.username not in ai_chat_history:
            ai_chat_history[req.username] = []
        history = ai_chat_history[req.username]
        history.append({"role": "user", "content": req.message})
        if len(history) > MAX_AI_HISTORY:
            history = history[-MAX_AI_HISTORY:]

        messages = [
            {"role": "system", "content": "Siz BioEmpire tizimining AI shifokorisiz. Sog'liq, davolanish va turli kasalliklar haqida batafsil ma'lumot berasiz. Professional, ammo biroz dahshatli ohangda gapiring."},
            {"role": "system", "content": f"Foydalanuvchi: {req.username}. Holati: {user['status']}. Salomatlik: {user['health_score']}%. Balans: {user['balance']} {currency}."},
        ]
        messages.extend(history[-10:])
        ai_response = await call_ai_api(messages)
        if not ai_response:
            ai_response = "Kechirasiz, AI hozir javob bera olmadi. Iltimos, keyinroq urinib ko'ring."

        history.append({"role": "assistant", "content": ai_response})
        ai_chat_history[req.username] = history
        await save_state()
        return {"success": True, "response": ai_response, "new_balance": user["balance"], "deducted": chat_price}

# Camera
@app.post("/api/v2/camera/analyze")
async def camera_analyze(req: CameraAnalysisRequest):
    async with db_lock:
        if req.username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        user = db_state["users"][req.username]
        currency = user["currency"]
        rate = EXCHANGE_RATES[currency]

        analysis_price = CAMERA_PRICE_USD * rate
        if user["balance"] < analysis_price:
            return {"success": False, "message": f"⚠️ Kamera analizi uchun ${analysis_price:.2f} kerak."}

        user["balance"] -= analysis_price
        db_state["system_vault"]["total_revenue"] += analysis_price

        dept = DEPARTMENTS.get(req.department_id) or RED_ZONE_DEPARTMENTS.get(req.department_id)
        dept_name = dept["uz"] if dept else "Noma'lum"
        track_user_activity(req.username, "camera_analysis", {"department": dept_name})

        analysis_result = ""
        if req.image_data and GEMINI_AVAILABLE and GEMINI_API_KEY:
            try:
                image_bytes = base64.b64decode(req.image_data.split(",")[1] if "," in req.image_data else req.image_data)
                model = genai.GenerativeModel(GEMINI_MODEL)
                response = await asyncio.to_thread(
                    model.generate_content,
                    ["Ushbu rasmni tahlil qiling va BioEmpire bo'limi uchun diagnostik tavsiya bering.", 
                     {"mime_type": "image/jpeg", "data": image_bytes}]
                )
                analysis_result = response.text if response and response.text else "Rasm tahlili natija bermadi."
            except Exception as e:
                analysis_result = f"Rasm tahlilida xatolik: {e}"
        else:
            if not req.image_data:
                analysis_result = "Rasm yuklanmagan."
            else:
                analysis_result = "Gemini Vision ishlamayapti, matnli AI dan foydalaniladi."

        if not analysis_result or "xatolik" in analysis_result.lower():
            messages = [
                {"role": "system", "content": "Siz BioEmpire tizimining AI analistisisiz. Kamera orqali olingan ma'lumotlarni tahlil qiling va qisqa tavsiya bering."},
                {"role": "user", "content": f"Bo'lim: {dept_name}. Foydalanuvchi holati: {user['status']}. Rasm tahlili natijasi: {analysis_result}"}
            ]
            ai_response = await call_ai_api(messages)
            if ai_response:
                analysis_result = ai_response
            else:
                analysis_result = f"🔬 [KAMERA AI]: {dept_name} da {random.randint(70,95)}% patologik o'zgarish."

        await save_state()
        return {"success": True, "analysis": analysis_result, "new_balance": user["balance"], "deducted": analysis_price}

# Health Ranking
@app.get("/api/v2/health/ranking")
async def get_health_ranking():
    async with db_lock:
        ranking = []
        for username, user in db_state["users"].items():
            ranking.append({
                "username": username,
                "health_score": user.get("health_score", 0),
                "status": user.get("status", "WARNING"),
                "avatar": user.get("avatar", "🧬")
            })
        ranking.sort(key=lambda x: x["health_score"], reverse=True)
        return ranking

# Notifications
@app.get("/api/v2/notifications/{username}")
async def get_notifications(username: str):
    async with db_lock:
        if username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        return [n for n in db_state["notifications"] if n["username"] == username][:20]

@app.post("/api/v2/notifications/read/{username}")
async def mark_notifications_read(username: str):
    async with db_lock:
        if username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        for n in db_state["notifications"]:
            if n["username"] == username:
                n["read"] = True
        await save_state()
        return {"success": True}

# AI ADS Performance
@app.get("/api/v2/ai/ads-performance")
async def ads_performance():
    async with db_lock:
        return db_state["ads_performance"]

# Stats
@app.get("/api/v2/system/stats")
async def get_system_stats():
    async with db_lock:
        return {
            "total_revenue": db_state["system_vault"]["total_revenue"],
            "active_users": db_state["system_vault"]["active_users"],
            "total_feed_posts": len(db_state["feed"]),
            "total_social_posts": len(db_state["social_posts"]),
            "total_notifications": len(db_state["notifications"]),
            "total_sales": len(db_state["product_sales"]),
            "total_tournaments": len(db_state["tournaments"]),
            "active_campaigns": len([c for c in db_state["marketing_campaigns"] if c.get("active", False)])
        }

# Admin
@app.post("/api/v2/admin/login")
async def admin_login(request: Request):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    if username == ADMIN_USERNAME and hash_password(password) == ADMIN_PASSWORD_HASH:
        return {"success": True, "token": "admin-token"}
    raise HTTPException(status_code=401, detail="Noto'g'ri admin ma'lumotlari")

@app.get("/api/v2/admin/dashboard")
async def admin_dashboard(username: str = None, password: str = None):
    if not (username == ADMIN_USERNAME and hash_password(password) == ADMIN_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Avtorizatsiya kerak")
    async with db_lock:
        return {
            "total_users": len(db_state["users"]),
            "total_revenue": db_state["system_vault"]["total_revenue"],
            "active_users": db_state["system_vault"]["active_users"],
            "total_sales": len(db_state["product_sales"]),
            "active_campaigns": len([c for c in db_state["marketing_campaigns"] if c.get("active", False)]),
            "ai_logs": db_state["ai_logs"][-50:],
            "ads_performance": db_state["ads_performance"],
            "recent_decisions": db_state["ai_decisions"][-10:]
        }

# CEO Dashboard
@app.get("/api/v2/ceo/dashboard")
async def ceo_dashboard(username: str = None, password: str = None):
    if not (username == ADMIN_USERNAME and hash_password(password) == ADMIN_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Faqat CEO uchun")
    async with db_lock:
        return {
            "insights": db_state.get("ceo_ideas", [])[-5:],
            "ai_status": {
                "gemini_available": GEMINI_AVAILABLE,
                "groq_configured": bool(GROQ_API_KEY),
                "primary_ai": PRIMARY_AI
            },
            "system_stats": {
                "total_revenue": db_state["system_vault"]["total_revenue"],
                "active_users": db_state["system_vault"]["active_users"],
                "total_sales": len(db_state["product_sales"])
            }
        }

# ==========================================
# ROOT – HTML (fayl + embedded)
# ==========================================
def get_html_content() -> str:
    """HTML ni fayldan o‘qiydi, topilmasa ichki HTML ni qaytaradi"""
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # Embedded HTML – to‘liq versiya (quyida keltirilgan)
        return """
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8"><title>🧬 BioEmpire</title>
        <style>body{background:#E8F5E9;font-family:sans-serif;text-align:center;padding:50px;color:#1B3A1B;}
        .glass{background:white;border-radius:20px;padding:30px;max-width:800px;margin:auto;box-shadow:0 8px 32px rgba(0,40,0,0.1);}
        h1{color:#43A047;} .btn{background:#66BB6A;border:none;color:white;padding:12px 30px;border-radius:30px;cursor:pointer;font-size:16px;}
        .btn:hover{background:#43A047;}</style></head>
        <body><div class="glass"><h1>🧬 BioEmpire V9.4</h1>
        <p>AI tizimi ishga tushdi! 🚀</p>
        <p><b>Admin:</b> CEO / 12345678</p>
        <button class="btn" onclick="location.href='/api/v2/health/ranking'">Salomatlik reytingi</button>
        <button class="btn" onclick="location.href='/api/v2/system/stats'">Statistika</button>
        <p style="margin-top:20px;font-size:14px;color:#4A6A4A;">Agar to‘liq interfeysni ko‘rmasangiz, <code>templates/index.html</code> faylni yarating.</p>
        </div></body></html>
        """

@app.get("/", response_class=HTMLResponse)
@app.head("/", response_class=HTMLResponse)
async def root():
    return get_html_content()

# ==========================================
# WEBSOCKET
# ==========================================
@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ==========================================
# STARTUP
# ==========================================
@app.on_event("startup")
async def startup_event():
    print("🚀 BioEmpire V9.4 ishga tushdi!")

# ==========================================
# SERVER – Render uchun
# ==========================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
