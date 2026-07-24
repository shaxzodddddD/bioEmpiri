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
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ==========================================
# GEMINI AI (optional)
# ==========================================
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ==========================================
# CONFIG
# ==========================================
CONFIG_FILE = "config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
else:
    CONFIG = {}

GROQ_API_KEY = os.getenv("GROQ_API_KEY", CONFIG.get("api", {}).get("groq_api_key", ""))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", CONFIG.get("api", {}).get("gemini_api_key", ""))
GEMINI_MODEL = CONFIG.get("api", {}).get("gemini_model", "gemini-1.5-flash")
GROQ_MODEL = CONFIG.get("api", {}).get("groq_model", "mixtral-8x7b-32768")

if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="BioEmpire V13")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# DATABASE (JSON)
# ==========================================
DB_FILE = "database_log.json"
db_lock = asyncio.Lock()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

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

# ==========================================
# AI CALLS
# ==========================================
async def call_groq_api(messages: List[dict]) -> Optional[str]:
    if not GROQ_API_KEY:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": GROQ_MODEL,
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
    response = await call_gemini_api(messages)
    if response:
        return response
    return await call_groq_api(messages)

# ==========================================
# PYDANTIC MODELS
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
# ENDPOINTS
# ==========================================

# ---- ROOT - serve index.html ----
@app.get("/", response_class=HTMLResponse)
@app.head("/", response_class=HTMLResponse)
async def root():
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # Fallback if file missing
        return HTMLResponse("""
        <html><body><h1>🧬 BioEmpire V13</h1>
        <p>Iltimos, <code>templates/index.html</code> faylni joylashtiring.</p>
        <p>Yoki <a href="/api/v2/auth/signup">API</a> dan foydalaning.</p>
        </body></html>
        """, status_code=200)

# ---- AUTH ----
@app.post("/api/v2/auth/signup")
async def signup(user: UserRegister):
    async with db_lock:
        if user.username in db["users"]:
            raise HTTPException(status_code=400, detail="Bu username allaqachon band.")
        # Check email uniqueness
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
            "department": "None",
            "health_score": 85.0,
            "avatar": "🧬",
            "bio": "BioEmpire tizimiga yangi qo'shildim",
            "registered_at": datetime.now().isoformat(),
            "packages": []
        }
        db["system_vault"]["active_users"] = len(db["users"])
        save_db(db)
        # Welcome notification
        notif = generate_notification(user.username, "🎉 Xush kelibsiz! BioEmpire tizimiga muvaffaqiyatli ro'yxatdan o'tdingiz.")
        add_notification(notif)
        return {
            "status": "success",
            "username": user.username,
            "balance": initial_balance,
            "currency": curr
        }

@app.post("/api/v2/auth/signin")
async def signin(user: UserLogin):
    async with db_lock:
        if user.username not in db["users"]:
            raise HTTPException(status_code=400, detail="Noto'g'ri username yoki parol.")
        target = db["users"][user.username]
        if target["password_hash"] != hash_password(user.password):
            raise HTTPException(status_code=400, detail="Noto'g'ri username yoki parol.")
        # Update last activity
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

# ---- PROFILE ----
@app.get("/api/v2/profile/{username}")
async def get_profile(username: str):
    async with db_lock:
        if username not in db["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        return db["users"][username]

# ---- SOCIAL ----
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

# ---- AI CHAT ----
@app.post("/api/v2/ai/chat")
async def ai_chat(req: AIChatRequest):
    async with db_lock:
        if req.username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        user = db["users"][req.username]
        # Deduct tokens/balance (simulated)
        chat_price = 49.0
        rates = {"USD": 1.0, "EUR": 0.92, "BTC": 0.000015, "SOL": 0.0075}
        price = chat_price * rates.get(user["currency"], 1.0)
        if user["balance"] < price:
            return {"success": False, "message": f"⚠️ AI chat uchun ${price:.2f} kerak."}
        user["balance"] -= price
        db["system_vault"]["total_revenue"] += price
        save_db(db)
        track_user_activity(req.username, "ai_chat", {"message": req.message[:50]})

        # Call AI
        messages = [
            {"role": "system", "content": "Siz BioEmpire AI shifokorisiz. Kasalliklar haqida batafsil ma'lumot bering va davolash usullarini tavsiya qiling."},
            {"role": "user", "content": req.message}
        ]
        ai_response = await call_ai_api(messages)
        if not ai_response:
            # Fallback
            fallbacks = [
                "🧬 Sizning simptomlaringiz virusli infeksiyaga o'xshaydi. 3 kun dam oling va ko'p suv iching.",
                "🩺 Tahlillar natijasiga ko'ra, immun tizim zaifligi aniqlangan. ImmunoBoost Pro tavsiya etiladi.",
                "💊 Simptomlaringiz allergik reaksiyaga o'xshaydi. Antigistamin preparatlarini qabul qiling.",
                "🧫 Sizda bakterial infeksiya belgilari bor. Antibiotik kursi kerak bo'lishi mumkin.",
                "⚡ Nerv tizimingizda stress belgilari aniqlangan. Meditatsiya va dam olish tavsiya etiladi."
            ]
            ai_response = random.choice(fallbacks)

        return {"success": True, "response": ai_response, "new_balance": user["balance"], "deducted": price}

# ---- CAMERA ----
@app.post("/api/v2/camera/analyze")
async def camera_analyze(req: CameraAnalysisRequest):
    async with db_lock:
        if req.username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        user = db["users"][req.username]
        analysis_price = 150.0
        rates = {"USD": 1.0, "EUR": 0.92, "BTC": 0.000015, "SOL": 0.0075}
        price = analysis_price * rates.get(user["currency"], 1.0)
        if user["balance"] < price:
            return {"success": False, "message": f"⚠️ Kamera analizi uchun ${price:.2f} kerak."}
        user["balance"] -= price
        db["system_vault"]["total_revenue"] += price
        save_db(db)
        track_user_activity(req.username, "camera_analysis", {"department_id": req.department_id})

        analysis_result = "🔬 Rasm tahlili: Teri toshmasi aniqlangan. Dermatologga murojaat qilish tavsiya etiladi."

        if req.image_data and GEMINI_AVAILABLE and GEMINI_API_KEY:
            try:
                image_data = req.image_data.split(",")[1] if "," in req.image_data else req.image_data
                image_bytes = base64.b64decode(image_data)
                model = genai.GenerativeModel(GEMINI_MODEL)
                response = await asyncio.to_thread(
                    model.generate_content,
                    ["Ushbu rasmni tahlil qiling va diagnostik tavsiya bering.", {"mime_type": "image/jpeg", "data": image_bytes}]
                )
                if response and response.text:
                    analysis_result = "🔬 " + response.text
            except Exception as e:
                analysis_result = f"🔬 Rasm tahlilida xatolik: {e}"
        else:
            # Fallback to text AI
            messages = [
                {"role": "system", "content": "Siz BioEmpire AI analistisisiz. Rasm tahlili natijasini berasiz."},
                {"role": "user", "content": "Rasmda teri toshmasi ko'rinadi. Diagnostika bering."}
            ]
            ai_resp = await call_ai_api(messages)
            if ai_resp:
                analysis_result = "🔬 " + ai_resp

        return {"success": True, "analysis": analysis_result, "new_balance": user["balance"], "deducted": price}

# ---- HEALTH RANKING ----
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

# ---- STATS ----
@app.get("/api/v2/system/stats")
async def system_stats():
    return {
        "total_revenue": db["system_vault"]["total_revenue"],
        "active_users": db["system_vault"]["active_users"],
        "total_sales": len(db.get("product_sales", [])),
        "total_social_posts": len(db.get("social_posts", []))
    }

# ---- ADS PERFORMANCE ----
@app.get("/api/v2/ai/ads-performance")
async def ads_performance():
    return db.get("ads_performance", {})

# ---- NOTIFICATIONS ----
@app.get("/api/v2/notifications/{username}")
async def get_notifications(username: str):
    async with db_lock:
        if username not in db["users"]:
            raise HTTPException(404, "Foydalanuvchi topilmadi.")
        # Return only this user's notifications
        user_notifs = [n for n in db.get("notifications", []) if n["username"] == username]
        return user_notifs

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

# ---- ADMIN ----
ADMIN_USERNAME = "CEO"
ADMIN_PASSWORD_HASH = hash_password("12345678")

@app.post("/api/v2/admin/login")
async def admin_login(request: Request):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    if username == ADMIN_USERNAME and hash_password(password) == ADMIN_PASSWORD_HASH:
        return {"success": True, "token": "admin-token"}
    raise HTTPException(401, "Noto'g'ri admin ma'lumotlari")

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
# BACKGROUND TASKS (Optional)
# ==========================================
# These can be enabled as needed; for simplicity, we skip.

# ==========================================
# SERVER
# ==========================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    print(f"🧬 BioEmpire V13 ishga tushdi, port: {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
