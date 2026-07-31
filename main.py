import os
import json
import random
import asyncio
import hashlib
import base64
import httpx
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ---------- KONFIGURATSIYANI YUKLASH ----------
CONFIG_FILE = "config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
else:
    CONFIG = {}

# ---------- UI ----------
UI_CONFIG = CONFIG.get("ui", {})

# ---------- API KALITLARI ----------
API_CONFIG = CONFIG.get("api", {})
GROQ_API_KEY = os.getenv("GROQ_API_KEY", API_CONFIG.get("groq_api_key", ""))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", API_CONFIG.get("gemini_api_key", ""))
GEMINI_MODEL = API_CONFIG.get("gemini_model", "gemini-1.5-flash")
GROQ_MODEL = API_CONFIG.get("groq_model", "mixtral-8x7b-32768")
PRIMARY_AI = API_CONFIG.get("primary_ai", "gemini")
GROQ_TEMPERATURE = API_CONFIG.get("temperature", 0.7)
GROQ_MAX_TOKENS = API_CONFIG.get("max_tokens", 2048)

# ---------- EXCHANGE RATES ----------
EXCHANGE_RATES = CONFIG.get("exchange_rates", {"USD": 1.0, "EUR": 0.92, "BTC": 0.000015, "SOL": 0.0075})

# ---------- PAKETLAR ----------
PACKAGES = CONFIG.get("packages", {})

# ---------- DEPARTAMENLAR ----------
DEPARTMENTS = {d["id"]: d for d in CONFIG.get("departments", [])}
RED_ZONE_DEPARTMENTS = {d["id"]: d for d in CONFIG.get("red_zone_departments", [])}

# ---------- E-COMMERCE ----------
ECOMMERCE = CONFIG.get("ecommerce", {"products": []})

# ---------- NARXLAR ----------
CHAT_PRICE_USD = CONFIG.get("chat_price_usd", 49)
CAMERA_PRICE_USD = CONFIG.get("camera_analysis_price_usd", 150)

# ---------- AVTONOM AI ----------
AI_AUTONOMY = CONFIG.get("ai_autonomy", {})
AUTO_LEARNING_INTERVAL = CONFIG.get("auto_learning_interval", 120)
AUTO_MARKETING_INTERVAL = CONFIG.get("auto_marketing_interval", 120)
AUTO_ADS_OPTIMIZER_INTERVAL = CONFIG.get("auto_ads_optimizer_interval", 60)
AUTO_DECISION_INTERVAL = CONFIG.get("auto_decision_interval", 300)
MAX_AI_HISTORY = CONFIG.get("max_ai_history", 50)

# ---------- ADMIN ----------
ADMIN = CONFIG.get("admin", {})
ADMIN_USERNAME = ADMIN.get("username", "CEO")
ADMIN_PASSWORD_HASH = ADMIN.get("password_hash", hashlib.sha256("12345678".encode()).hexdigest())

# ---------- LEGAL ----------
LEGAL = CONFIG.get("legal", {})

# ---------- GEMINI ----------
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ Gemini sozlandi")
else:
    print("⚠️ Gemini sozlanmadi – GEMINI_API_KEY ni qo'shing")

app = FastAPI(title="BioEmpire V13", version="13.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- BAZA (database_log.json) ----------
DB_FILE = "database_log.json"
BACKUP_FILE = "database_log_backup.json"
db_lock = asyncio.Lock()

def hash_password(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()

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
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[DB] xato: {e}")
        return False

db = load_db()

def generate_post_id():
    return f"post_{random.randint(10000, 99999)}_{int(datetime.now().timestamp())}"

def generate_notification(username: str, message: str, type: str = "info") -> dict:
    return {
        "id": generate_post_id(),
        "username": username,
        "message": message,
        "type": type,
        "timestamp": datetime.now().isoformat(),
        "read": False
    }

def add_notification(notification: dict):
    db["notifications"].insert(0, notification)
    if len(db["notifications"]) > 100:
        db["notifications"] = db["notifications"][:100]
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

# ---------- AI CHAQIRUVLARI ----------
async def call_groq_api(messages: List[dict]) -> Optional[str]:
    if not GROQ_API_KEY:
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
            r = await client.post(url, headers=headers, json=data)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            return None
    except:
        return None

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

async def call_ai_api(messages: List[dict]) -> Optional[str]:
    if PRIMARY_AI == "gemini":
        response = await call_gemini_api(messages)
        if response:
            return response
        return await call_groq_api(messages)
    else:
        response = await call_groq_api(messages)
        if response:
            return response
        return await call_gemini_api(messages)

# ---------- PYDANTIC MODELLAR ----------
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

class PurchaseRequest(BaseModel):
    username: str
    package_type: str

# ---------- HTML (fayldan o‘qish, bo‘lmasa fallback) ----------
def get_html():
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return """
        <!DOCTYPE html>
        <html>
        <head><title>🧬 BioEmpire V13</title></head>
        <body style="font-family:sans-serif;background:#E8F5E9;padding:40px;text-align:center;">
            <h1>🧬 BioEmpire V13</h1>
            <p>Iltimos, <code>templates/index.html</code> faylni joylashtiring.</p>
            <p>Yoki quyidagi havolalardan foydalaning:</p>
            <ul style="list-style:none;padding:0;">
                <li><a href="/api/v2/auth/signup">Ro'yxatdan o'tish</a></li>
                <li><a href="/api/v2/auth/signin">Kirish</a></li>
                <li><a href="/api/v2/health/ranking">Salomatlik reytingi</a></li>
                <li><a href="/api/v2/system/stats">Statistika</a></li>
            </ul>
        </body>
        </html>
        """

# ============================================================
# ENDPOINTLAR
# ============================================================
@app.get("/", response_class=HTMLResponse)
@app.head("/", response_class=HTMLResponse)
async def root():
    return get_html()

@app.get("/index.html", response_class=HTMLResponse)
@app.head("/index.html", response_class=HTMLResponse)
async def index_html():
    return get_html()

# ---------- AUTH ----------
@app.post("/api/v2/auth/signup")
async def signup(user: UserRegister):
    async with db_lock:
        if user.username in db["users"]:
            raise HTTPException(400, "Bu username allaqachon band.")
        for u in db["users"].values():
            if u.get("email") == user.email:
                raise HTTPException(400, "Bu email allaqachon ro'yxatdan o'tgan.")
        curr = user.currency.upper()
        if curr not in EXCHANGE_RATES:
            curr = "USD"
        initial_balance = 25000.0 * EXCHANGE_RATES.get(curr, 1.0)
        db["users"][user.username] = {
            "email": user.email,
            "password_hash": hash_password(user.password),
            "currency": curr,
            "balance": initial_balance,
            "status": "WARNING",
            "department": "None",
            "health_score": 85.0,
            "avatar": "🧬",
            "bio": "BioEmpire tizimiga yangi qo'shildim",
            "registered_at": datetime.now().isoformat(),
            "packages": []
        }
        db["system_vault"]["active_users"] = len(db["users"])
        save_db(db)
        add_notification(generate_notification(user.username, "🎉 Xush kelibsiz!"))
        return {"status": "success", "username": user.username, "balance": initial_balance, "currency": curr}

@app.post("/api/v2/auth/signin")
async def signin(user: UserLogin):
    async with db_lock:
        if user.username not in db["users"]:
            raise HTTPException(400, "Noto'g'ri username yoki parol.")
        target = db["users"][user.username]
        if target["password_hash"] != hash_password(user.password):
            raise HTTPException(400, "Noto'g'ri username yoki parol.")
        track_user_activity(user.username, "signin")
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
    async with db_lock:
        if username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        return db["users"][username]

# ---------- SOCIAL ----------
@app.get("/api/v2/social/posts")
async def get_social_posts():
    return db.get("social_posts", [])

@app.post("/api/v2/social/post")
async def create_social_post(req: SocialPostRequest):
    async with db_lock:
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
        if len(db["social_posts"]) > 100:
            db["social_posts"] = db["social_posts"][:100]
        save_db(db)
        track_user_activity(req.username, "social_post", {"content": req.content[:50]})
        return post

@app.post("/api/v2/social/like")
async def like_post(req: LikeRequest):
    async with db_lock:
        if req.username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        for post in db["social_posts"]:
            if post["id"] == req.post_id:
                post["likes"] = post.get("likes", 0) + 1
                save_db(db)
                track_user_activity(req.username, "like", {"post_id": req.post_id})
                return {"success": True, "likes": post["likes"]}
        raise HTTPException(404, "Post topilmadi.")

@app.post("/api/v2/social/comment")
async def comment_post(req: CommentRequest):
    async with db_lock:
        if req.username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        for post in db["social_posts"]:
            if post["id"] == req.post_id:
                comment_obj = {
                    "username": req.username,
                    "text": req.comment,
                    "timestamp": datetime.now().isoformat()
                }
                if "comments" not in post:
                    post["comments"] = []
                post["comments"].append(comment_obj)
                save_db(db)
                track_user_activity(req.username, "comment", {"post_id": req.post_id})
                return {"success": True, "comment": comment_obj}
        raise HTTPException(404, "Post topilmadi.")

# ---------- AI CHAT ----------
@app.post("/api/v2/ai/chat")
async def ai_chat(req: AIChatRequest):
    async with db_lock:
        if req.username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        user = db["users"][req.username]
        chat_price = CHAT_PRICE_USD * EXCHANGE_RATES.get(user["currency"], 1.0)
        if user["balance"] < chat_price:
            return {"success": False, "message": f"⚠️ ${chat_price:.2f} kerak."}
        user["balance"] -= chat_price
        db["system_vault"]["total_revenue"] += chat_price
        save_db(db)
        track_user_activity(req.username, "ai_chat", {"message": req.message[:50]})
        messages = [
            {"role": "system", "content": "Siz BioEmpire AI shifokorisiz."},
            {"role": "user", "content": req.message}
        ]
        ai_response = await call_ai_api(messages)
        if not ai_response:
            ai_response = "🧬 Simptomlaringiz virusli infeksiyaga o'xshaydi. 3 kun dam oling."
        return {"success": True, "response": ai_response, "new_balance": user["balance"], "deducted": chat_price}

# ---------- CAMERA ----------
@app.post("/api/v2/camera/analyze")
async def camera_analyze(req: CameraAnalysisRequest):
    async with db_lock:
        if req.username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        user = db["users"][req.username]
        analysis_price = CAMERA_PRICE_USD * EXCHANGE_RATES.get(user["currency"], 1.0)
        if user["balance"] < analysis_price:
            return {"success": False, "message": f"⚠️ ${analysis_price:.2f} kerak."}
        user["balance"] -= analysis_price
        db["system_vault"]["total_revenue"] += analysis_price
        save_db(db)
        track_user_activity(req.username, "camera_analysis", {"department_id": req.department_id})
        analysis_result = "🔬 Rasm tahlili: Teri toshmasi aniqlangan."
        if req.image_data and GEMINI_AVAILABLE and GEMINI_API_KEY:
            try:
                image_data = req.image_data.split(",")[1] if "," in req.image_data else req.image_data
                image_bytes = base64.b64decode(image_data)
                model = genai.GenerativeModel(GEMINI_MODEL)
                response = await asyncio.to_thread(
                    model.generate_content,
                    ["Ushbu rasmni tahlil qiling.", {"mime_type": "image/jpeg", "data": image_bytes}]
                )
                if response and response.text:
                    analysis_result = "🔬 " + response.text
            except Exception as e:
                analysis_result = f"🔬 Xatolik: {e}"
        return {"success": True, "analysis": analysis_result, "new_balance": user["balance"], "deducted": analysis_price}

# ---------- HEALTH RANKING ----------
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

# ---------- STATS ----------
@app.get("/api/v2/system/stats")
async def system_stats():
    return {
        "total_revenue": db["system_vault"]["total_revenue"],
        "active_users": db["system_vault"]["active_users"],
        "total_sales": len(db.get("product_sales", [])),
        "total_social_posts": len(db.get("social_posts", []))
    }

# ---------- ADS ----------
@app.get("/api/v2/ai/ads-performance")
async def ads_performance():
    return db.get("ads_performance", {})

# ---------- NOTIFICATIONS ----------
@app.get("/api/v2/notifications/{username}")
async def get_notifications(username: str):
    async with db_lock:
        if username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        return [n for n in db.get("notifications", []) if n["username"] == username]

@app.post("/api/v2/notifications/read/{username}")
async def mark_notifications_read(username: str):
    async with db_lock:
        if username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        for n in db["notifications"]:
            if n["username"] == username:
                n["read"] = True
        save_db(db)
        return {"success": True}

# ---------- PACKAGE PURCHASE ----------
@app.post("/api/v2/clinical/purchase")
async def purchase_package(req: PurchaseRequest):
    async with db_lock:
        if req.username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        user = db["users"][req.username]
        pkg = PACKAGES.get(req.package_type)
        if not pkg:
            raise HTTPException(400, "Noma'lum paket turi.")
        price = pkg["price_usd"] * EXCHANGE_RATES.get(user["currency"], 1.0)
        if user["balance"] < price:
            return {"success": False, "message": "Mablag' yetishmasligi!"}
        user["balance"] -= price
        db["system_vault"]["total_revenue"] += price
        user["status"] = pkg["status"]
        user["health_score"] = min(100, user["health_score"] + 15)
        if req.package_type == "red_zone_vip":
            user["health_score"] = 100
            user["status"] = "IMMORTAL"
        if "packages" not in user:
            user["packages"] = []
        user["packages"].append({"type": req.package_type, "purchased_at": datetime.now().isoformat()})
        track_user_activity(req.username, "purchase", {"package": req.package_type, "cost": price})
        save_db(db)
        return {"success": True, "message": f"{pkg['desc']}", "new_balance": user["balance"]}

# ---------- ADMIN ----------
@app.post("/api/v2/admin/login")
async def admin_login(request: Request):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    if username == ADMIN_USERNAME and hash_password(password) == ADMIN_PASSWORD_HASH:
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

# ---------- LEGAL ----------
@app.get("/api/v2/legal")
async def get_legal():
    return LEGAL

# ============================================================
# SERVER
# ============================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    uvicorn.run(app, host="0.0.0.0", port=port)
