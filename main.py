import os
import json
import random
import asyncio
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
import httpx
import uvicorn
from passlib.context import CryptContext
from jose import JWTError, jwt

# ---------- KONFIGURATSIYA ----------
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ---------- PAPKALAR VA TEMPLATES (Agar mavjud bo'lmasa yaratamiz) ----------
if not os.path.exists("templates"):
    os.makedirs("templates", exist_ok=True)

# Agar index.html mavjud bo'lmasa, avtomatik yaratamiz
INDEX_HTML_PATH = "templates/index.html"
if not os.path.exists(INDEX_HTML_PATH):
    with open(INDEX_HTML_PATH, "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html>
<head><title>🧬 BioEmpire V13</title></head>
<body>
<h1>🧬 BioEmpire V13</h1>
<p>Tizim ishga tushdi! ✅</p>
<p>Iltimos, to‘liq interfeys uchun <code>templates/index.html</code> ni yangilang.</p>
<a href="/api/v2/auth/signup">Ro'yxatdan o'tish</a> |
<a href="/api/v2/auth/signin">Kirish</a> |
<a href="/api/v2/health/ranking">Salomatlik reytingi</a> |
<a href="/api/v2/system/stats">Statistika</a>
</body>
</html>""")

# ---------- JINJA2 TEMPLATES ----------
templates = Jinja2Templates(directory="templates")

# ---------- DATABASE ----------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")
# SQLite uchun maxsus parametr
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------- JWT & PASSWORD ----------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------- MODELS ----------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    currency = Column(String, default="USD")
    balance = Column(Float, default=25000.0)
    status = Column(String, default="WARNING")
    department = Column(String, default="None")
    health_score = Column(Float, default=85.0)
    avatar = Column(String, default="🧬")
    bio = Column(String, default="BioEmpire tizimiga yangi qo'shildim")
    registered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

# ---------- PYDANTIC ----------
class UserRegister(BaseModel):
    username: str
    email: str
    password: str
    currency: str = "USD"

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# ---------- FASTAPI APP ----------
app = FastAPI(title="BioEmpire V13", version="13.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- JSON DB (boshqa ma'lumotlar uchun) ----------
DB_FILE = "database_log.json"
db_lock = asyncio.Lock()

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
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
        print(f"[DB] xato: {e}")
        return False

db_json = load_db()

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
    db_json["notifications"].insert(0, notification)
    if len(db_json["notifications"]) > 100:
        db_json["notifications"] = db_json["notifications"][:100]
    save_db(db_json)

def track_user_activity(username: str, action: str, details: dict = None):
    if username not in db_json["user_activity"]:
        db_json["user_activity"][username] = {
            "last_active": datetime.now().isoformat(),
            "actions": [],
            "total_spent": 0.0,
            "packages_bought": 0
        }
    db_json["user_activity"][username]["last_active"] = datetime.now().isoformat()
    db_json["user_activity"][username]["actions"].append({
        "action": action,
        "timestamp": datetime.now().isoformat(),
        "details": details or {}
    })
    if len(db_json["user_activity"][username]["actions"]) > 100:
        db_json["user_activity"][username]["actions"] = db_json["user_activity"][username]["actions"][-100:]
    save_db(db_json)

# ---------- AI FUNKSIYALAR ----------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-1.5-flash"
GROQ_MODEL = "mixtral-8x7b-32768"

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except:
    GEMINI_AVAILABLE = False

if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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
    response = await call_gemini_api(messages)
    if response:
        return response
    return await call_groq_api(messages)

# ---------- ROUTERS ----------
@app.get("/", response_class=HTMLResponse)
@app.head("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/index.html", response_class=HTMLResponse)
@app.head("/index.html", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ---------- AUTH ----------
@app.post("/api/v2/auth/signup", response_model=Token)
async def signup(user: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter((User.username == user.username) | (User.email == user.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username yoki email allaqachon band.")
    hashed = get_password_hash(user.password)
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed,
        currency=user.currency
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/v2/auth/signin", response_model=Token)
async def signin(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Noto'g'ri username yoki parol.")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/v2/profile/{username}")
async def get_profile(username: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.username != username:
        raise HTTPException(status_code=403, detail="Faqat o'z profilingizni ko'ra olasiz.")
    return {
        "username": current_user.username,
        "email": current_user.email,
        "balance": current_user.balance,
        "currency": current_user.currency,
        "status": current_user.status,
        "department": current_user.department,
        "health_score": current_user.health_score,
        "avatar": current_user.avatar,
        "bio": current_user.bio,
        "registered_at": current_user.registered_at.isoformat()
    }

# ---------- SOCIAL ----------
@app.get("/api/v2/social/posts")
async def get_social_posts():
    return db_json.get("social_posts", [])

@app.post("/api/v2/social/post")
async def create_social_post(req: dict):
    username = req.get("username")
    content = req.get("content")
    if not username or not content:
        raise HTTPException(400, "Username va content kerak.")
    db_session = SessionLocal()
    user = db_session.query(User).filter(User.username == username).first()
    db_session.close()
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    post = {
        "id": generate_post_id(),
        "username": username,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "likes": 0,
        "comments": []
    }
    db_json["social_posts"].insert(0, post)
    if len(db_json["social_posts"]) > 100:
        db_json["social_posts"] = db_json["social_posts"][:100]
    save_db(db_json)
    track_user_activity(username, "social_post", {"content": content[:50]})
    return post

@app.post("/api/v2/social/like")
async def like_post(req: dict):
    username = req.get("username")
    post_id = req.get("post_id")
    if not username or not post_id:
        raise HTTPException(400, "username va post_id kerak.")
    for post in db_json["social_posts"]:
        if post["id"] == post_id:
            post["likes"] = post.get("likes", 0) + 1
            save_db(db_json)
            track_user_activity(username, "like", {"post_id": post_id})
            return {"success": True, "likes": post["likes"]}
    raise HTTPException(404, "Post topilmadi.")

@app.post("/api/v2/social/comment")
async def comment_post(req: dict):
    username = req.get("username")
    post_id = req.get("post_id")
    comment = req.get("comment")
    if not username or not post_id or not comment:
        raise HTTPException(400, "username, post_id va comment kerak.")
    for post in db_json["social_posts"]:
        if post["id"] == post_id:
            comment_obj = {
                "username": username,
                "text": comment,
                "timestamp": datetime.now().isoformat()
            }
            if "comments" not in post:
                post["comments"] = []
            post["comments"].append(comment_obj)
            save_db(db_json)
            track_user_activity(username, "comment", {"post_id": post_id})
            return {"success": True, "comment": comment_obj}
    raise HTTPException(404, "Post topilmadi.")

# ---------- AI CHAT ----------
@app.post("/api/v2/ai/chat")
async def ai_chat(req: dict):
    username = req.get("username")
    message = req.get("message")
    if not username or not message:
        raise HTTPException(400, "username va message kerak.")
    db_session = SessionLocal()
    user = db_session.query(User).filter(User.username == username).first()
    if not user:
        db_session.close()
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    chat_price = 49.0
    if user.balance < chat_price:
        db_session.close()
        return {"success": False, "message": f"⚠️ ${chat_price:.2f} kerak."}
    user.balance -= chat_price
    db_session.commit()
    db_session.close()
    db_json["system_vault"]["total_revenue"] += chat_price
    save_db(db_json)
    track_user_activity(username, "ai_chat", {"message": message[:50]})
    messages = [
        {"role": "system", "content": "Siz BioEmpire AI shifokorisiz."},
        {"role": "user", "content": message}
    ]
    ai_response = await call_ai_api(messages)
    if not ai_response:
        ai_response = "🧬 Simptomlaringiz virusli infeksiyaga o'xshaydi. 3 kun dam oling."
    return {"success": True, "response": ai_response, "new_balance": user.balance, "deducted": chat_price}

# ---------- CAMERA ----------
@app.post("/api/v2/camera/analyze")
async def camera_analyze(req: dict):
    username = req.get("username")
    image_data = req.get("image_data")
    if not username:
        raise HTTPException(400, "username kerak.")
    db_session = SessionLocal()
    user = db_session.query(User).filter(User.username == username).first()
    if not user:
        db_session.close()
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    analysis_price = 150.0
    if user.balance < analysis_price:
        db_session.close()
        return {"success": False, "message": f"⚠️ ${analysis_price:.2f} kerak."}
    user.balance -= analysis_price
    db_session.commit()
    db_session.close()
    db_json["system_vault"]["total_revenue"] += analysis_price
    save_db(db_json)
    track_user_activity(username, "camera_analysis", {})
    analysis_result = "🔬 Rasm tahlili: Teri toshmasi aniqlangan."
    if image_data and GEMINI_AVAILABLE and GEMINI_API_KEY:
        try:
            image_data = image_data.split(",")[1] if "," in image_data else image_data
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
    return {"success": True, "analysis": analysis_result, "new_balance": user.balance, "deducted": analysis_price}

# ---------- HEALTH RANKING ----------
@app.get("/api/v2/health/ranking")
async def health_ranking(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.health_score.desc()).all()
    return [{"username": u.username, "health_score": u.health_score, "status": u.status, "avatar": u.avatar} for u in users]

# ---------- STATS ----------
@app.get("/api/v2/system/stats")
async def system_stats():
    return {
        "total_revenue": db_json["system_vault"]["total_revenue"],
        "active_users": db_json["system_vault"]["active_users"],
        "total_sales": len(db_json.get("product_sales", [])),
        "total_social_posts": len(db_json.get("social_posts", []))
    }

# ---------- ADS ----------
@app.get("/api/v2/ai/ads-performance")
async def ads_performance():
    return db_json.get("ads_performance", {})

# ---------- NOTIFICATIONS ----------
@app.get("/api/v2/notifications/{username}")
async def get_notifications(username: str):
    return [n for n in db_json.get("notifications", []) if n["username"] == username]

@app.post("/api/v2/notifications/read/{username}")
async def mark_notifications_read(username: str):
    for n in db_json.get("notifications", []):
        if n["username"] == username:
            n["read"] = True
    save_db(db_json)
    return {"success": True}

# ---------- PACKAGES ----------
PACKAGES = {
    "1_week": {"price_usd": 999, "status": "MONITORING", "desc": "1 haftalik asosiy davo"},
    "1_month": {"price_usd": 9999, "status": "OPTIMIZED", "desc": "1 oylik kengaytirilgan davo"},
    "3_month": {"price_usd": 299999, "status": "OPTIMIZED", "desc": "3 oylik premium davo"},
    "6_month": {"price_usd": 599999, "status": "OPTIMIZED", "desc": "6 oylik elita davo"},
    "1_year": {"price_usd": 1199999, "status": "IMMORTAL", "desc": "1 yillik ustun davo"},
    "3_year": {"price_usd": 2999999, "status": "IMMORTAL", "desc": "3 yillik mukammal davo"},
    "6_year": {"price_usd": 5999999, "status": "IMMORTAL", "desc": "6 yillik abadiy davo"},
    "10_year": {"price_usd": 9999999, "status": "IMMORTAL", "desc": "10 yillik o'lmaslik matritsasi"},
    "red_zone_vip": {"price_usd": 99000000, "status": "IMMORTAL", "desc": "QIZIL ZONA VIP"},
    "gadget": {"price_usd": 1200, "status": "MONITORING", "desc": "BCI bilaguzuk"},
    "meds": {"price_usd": 650, "status": "MONITORING", "desc": "Kvant dorilar to'plami"}
}

@app.post("/api/v2/clinical/purchase")
async def purchase_package(req: dict):
    username = req.get("username")
    package_type = req.get("package_type")
    if not username or not package_type:
        raise HTTPException(400, "username va package_type kerak.")
    db_session = SessionLocal()
    user = db_session.query(User).filter(User.username == username).first()
    if not user:
        db_session.close()
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    pkg = PACKAGES.get(package_type)
    if not pkg:
        db_session.close()
        raise HTTPException(400, "Noma'lum paket turi.")
    rates = {"USD": 1.0, "EUR": 0.92, "BTC": 0.000015, "SOL": 0.0075}
    price = pkg["price_usd"] * rates.get(user.currency, 1.0)
    if user.balance < price:
        db_session.close()
        return {"success": False, "message": "Mablag' yetishmasligi!"}
    user.balance -= price
    user.status = pkg["status"]
    user.health_score = min(100, user.health_score + 15)
    if package_type == "red_zone_vip":
        user.health_score = 100
        user.status = "IMMORTAL"
    db_session.commit()
    db_session.close()
    db_json["system_vault"]["total_revenue"] += price
    save_db(db_json)
    track_user_activity(username, "purchase", {"package": package_type, "cost": price})
    return {"success": True, "message": pkg["desc"], "new_balance": user.balance}

# ---------- ADMIN ----------
ADMIN_USERNAME = "CEO"
ADMIN_PASSWORD_HASH = hashlib.sha256("12345678".encode()).hexdigest()

@app.post("/api/v2/admin/login")
async def admin_login(req: dict):
    username = req.get("username")
    password = req.get("password")
    if username == ADMIN_USERNAME and hashlib.sha256(password.encode()).hexdigest() == ADMIN_PASSWORD_HASH:
        return {"success": True, "token": "admin-token"}
    raise HTTPException(401, "Noto'g'ri")

@app.get("/api/v2/admin/dashboard")
async def admin_dashboard(username: str = None, password: str = None):
    if username != ADMIN_USERNAME or hashlib.sha256(password.encode()).hexdigest() != ADMIN_PASSWORD_HASH:
        raise HTTPException(401, "Avtorizatsiya kerak")
    db_session = SessionLocal()
    users = db_session.query(User).count()
    db_session.close()
    return {
        "total_users": users,
        "total_revenue": db_json["system_vault"]["total_revenue"],
        "active_users": db_json["system_vault"]["active_users"],
        "total_sales": len(db_json.get("product_sales", []))
    }

@app.get("/api/v2/legal")
async def get_legal():
    return {
        "terms_of_service": "BioEmpire xizmatlaridan foydalanish shartlari...",
        "privacy_policy": "Shaxsiy ma'lumotlarni himoya qilish siyosati...",
        "rules": [
            "Tizimdan faqat shaxsiy maqsadlarda foydalaning.",
            "Boshqa foydalanuvchilarni haqorat qilmang.",
            "Soxta ma'lumotlar kiritmang.",
            "Tizim tomonidan berilgan tavsiyalar faqat maʼlumot uchun, shifokor maslahatini o'rnini bosa olmaydi."
        ]
    }

# ============================================================
# SERVER
# ============================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    uvicorn.run(app, host="0.0.0.0", port=port)
