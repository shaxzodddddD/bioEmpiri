import os
import json
import random
import asyncio
import base64
import httpx
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, Depends, File, UploadFile, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey, select, delete, update
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, relationship
from passlib.context import CryptContext
import uvicorn

# ==========================================
# GEMINI (ixtiyoriy)
# ==========================================
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ==========================================
# KONFIG
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-1.5-flash"

if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# BAZA (PostgreSQL / SQLite)
# ==========================================
DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    DATABASE_URL = "sqlite+aiosqlite:///./bioempire.db"
else:
    # Render’da DATABASE_URL postgresql://... bo‘ladi, uni asyncpg ga aylantiramiz
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    elif "postgresql+asyncpg" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

Base = declarative_base()

# ==========================================
# PASSWORD HASH
# ==========================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# ==========================================
# MODELLAR
# ==========================================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(30), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    currency = Column(String(10), default="USD")
    balance = Column(Float, default=25000.0)
    status = Column(String(20), default="WARNING")
    department = Column(String(100), default="None")
    health_score = Column(Float, default=85.0)
    avatar = Column(String(10), default="🧬")
    bio = Column(Text, default="BioEmpire tizimiga yangi qo'shildim")
    full_name = Column(String(100), default="")
    age = Column(Integer, nullable=True)
    gender = Column(String(20), default="")
    phone = Column(String(20), default="")
    address = Column(Text, default="")
    social_links = Column(JSON, default={})
    packages = Column(JSON, default=[])
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

class SocialPost(Base):
    __tablename__ = "social_posts"
    id = Column(String(50), primary_key=True, index=True)
    username = Column(String(30), nullable=False, index=True)
    content = Column(Text, nullable=False)
    timestamp = Column(String(20), nullable=False)
    likes = Column(Integer, default=0)
    comments = Column(JSON, default=[])
    is_ai = Column(Boolean, default=False)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String(50), primary_key=True, index=True)
    username = Column(String(30), nullable=False, index=True)
    message = Column(Text, nullable=False)
    type = Column(String(20), default="info")
    timestamp = Column(DateTime, default=datetime.utcnow)
    read = Column(Boolean, default=False)

class Tournament(Base):
    __tablename__ = "tournaments"
    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(String(20), default="active")
    participants = Column(JSON, default=[])
    scores = Column(JSON, default={})

class CryptoWallet(Base):
    __tablename__ = "crypto_wallets"
    username = Column(String(30), primary_key=True, index=True)
    wallet_address = Column(String(100), nullable=False)

class ProductSale(Base):
    __tablename__ = "product_sales"
    id = Column(String(50), primary_key=True, index=True)
    username = Column(String(30), nullable=False, index=True)
    product_id = Column(String(50), nullable=False)
    product_name = Column(String(100), nullable=False)
    quantity = Column(Integer, default=1)
    total_price = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")
    ordered_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="pending")

class MarketingCampaign(Base):
    __tablename__ = "marketing_campaigns"
    id = Column(String(50), primary_key=True, index=True)
    product_id = Column(String(50), nullable=False)
    product_name = Column(String(100), nullable=False)
    type = Column(String(30), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    target_audience = Column(Text, default="All users")
    budget = Column(Float, default=100.0)
    active = Column(Boolean, default=True)
    conversions = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    ctr = Column(Float, default=0.0)
    spent = Column(Float, default=0.0)
    status = Column(String(20), default="active")

class AdsPerformance(Base):
    __tablename__ = "ads_performance"
    campaign_id = Column(String(50), primary_key=True, index=True)
    product_name = Column(String(100), nullable=False)
    type = Column(String(30), nullable=False)
    conversions = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    ctr = Column(Float, default=0.0)
    roi = Column(Float, default=0.0)
    budget = Column(Float, default=100.0)
    spent = Column(Float, default=0.0)
    active = Column(Boolean, default=True)

class AILog(Base):
    __tablename__ = "ai_logs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String(10), default="INFO")
    message = Column(Text, nullable=False)

class Follow(Base):
    __tablename__ = "follows"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    follower = Column(String(30), nullable=False, index=True)
    following = Column(String(30), nullable=False, index=True)

class CEOIdea(Base):
    __tablename__ = "ceo_ideas"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    content = Column(Text, nullable=False)

# ==========================================
# DEPENDENCY
# ==========================================
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

# ==========================================
# YORDAMCHI FUNKSIYALAR
# ==========================================
def generate_post_id():
    return f"post_{random.randint(10000,99999)}_{int(datetime.now().timestamp())}"

def generate_notification_id():
    return f"notif_{random.randint(10000,99999)}_{int(datetime.now().timestamp())}"

def generate_tournament_id():
    return f"tournament_{random.randint(1000,9999)}"

# ==========================================
# FASTAPI
# ==========================================
app = FastAPI(title="BioEmpire V12")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# WEBSOCKET
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
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except:
                pass

manager = ConnectionManager()

# ==========================================
# AI CALLS
# ==========================================
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
            resp = await client.post(url, headers=headers, json=data)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
    except:
        pass
    return None

async def call_gemini_api(messages: List[dict]) -> Optional[str]:
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return None
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        user_msg = messages[-1]["content"] if messages else ""
        context = "\n".join([m["content"] for m in messages if m["role"] == "system"])
        full_prompt = f"{context}\n\nFoydalanuvchi: {user_msg}" if context else user_msg
        response = await asyncio.to_thread(model.generate_content, full_prompt)
        return response.text if response and response.text else None
    except:
        return None

async def call_ai_api(messages: List[dict]) -> Optional[str]:
    resp = await call_gemini_api(messages)
    if resp:
        return resp
    return await call_groq_api(messages)

# ==========================================
# PYDANTIC MODELLAR
# ==========================================
class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=30)
    email: EmailStr
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

class ProductOrderRequest(BaseModel):
    username: str
    product_id: str
    quantity: int = 1

class VirtualDoctorRequest(BaseModel):
    username: str
    symptoms: str
    level: str = "doctor"

class EmailReport(BaseModel):
    username: str
    email: str

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
# ENDPOINTLAR
# ==========================================

# ===== ROOT =====
@app.get("/", response_class=HTMLResponse)
@app.head("/", response_class=HTMLResponse)
async def root():
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTML

# ===== AUTH =====
@app.post("/api/v2/auth/signup")
async def signup(user: UserRegister, db: AsyncSession = Depends(get_db)):
    # username tekshirish
    stmt = select(User).where(User.username == user.username)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(400, "Bu username allaqachon band.")
    # email tekshirish
    stmt = select(User).where(User.email == user.email)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(400, "Bu email allaqachon ro'yxatdan o'tgan.")
    
    curr = user.currency.upper()
    if curr not in ["USD", "EUR", "BTC", "SOL"]:
        curr = "USD"
    rates = {"USD": 1.0, "EUR": 0.92, "BTC": 0.000015, "SOL": 0.0075}
    initial_balance = 25000.0 * rates.get(curr, 1.0)
    
    new_user = User(
        username=user.username,
        email=user.email,
        password_hash=hash_password(user.password),
        currency=curr,
        balance=initial_balance
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return {"status": "success", "username": new_user.username, "balance": new_user.balance, "currency": new_user.currency}

@app.post("/api/v2/auth/signin")
async def signin(user: UserLogin, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.username == user.username)
    res = await db.execute(stmt)
    db_user = res.scalar_one_or_none()
    if not db_user:
        raise HTTPException(400, "Noto'g'ri username yoki parol.")
    if not verify_password(user.password, db_user.password_hash):
        raise HTTPException(400, "Noto'g'ri username yoki parol.")
    return {
        "status": "success",
        "username": db_user.username,
        "balance": db_user.balance,
        "currency": db_user.currency,
        "status_layer": db_user.status,
        "department": db_user.department,
        "health_score": db_user.health_score,
        "avatar": db_user.avatar,
        "bio": db_user.bio
    }

# ===== PROFILE =====
@app.get("/api/v2/profile/{username}")
async def get_profile(username: str, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.username == username)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    return {
        "username": user.username,
        "email": user.email,
        "balance": user.balance,
        "currency": user.currency,
        "status": user.status,
        "department": user.department,
        "health_score": user.health_score,
        "avatar": user.avatar,
        "bio": user.bio,
        "full_name": user.full_name,
        "age": user.age,
        "gender": user.gender,
        "phone": user.phone,
        "address": user.address,
        "social_links": user.social_links,
        "packages": user.packages,
        "registered_at": user.registered_at.isoformat() if user.registered_at else None
    }

@app.post("/api/v2/profile/update")
async def update_profile(req: ProfileUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.username == req.username)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    update_data = req.dict(exclude_unset=True, exclude={"username"})
    for key, value in update_data.items():
        if value is not None:
            setattr(user, key, value)
    await db.commit()
    return {"success": True}

# ===== SOCIAL =====
@app.get("/api/v2/social/posts")
async def get_social_posts(db: AsyncSession = Depends(get_db)):
    stmt = select(SocialPost).order_by(SocialPost.timestamp.desc()).limit(100)
    res = await db.execute(stmt)
    posts = res.scalars().all()
    return [{"id": p.id, "username": p.username, "content": p.content, "timestamp": p.timestamp, "likes": p.likes, "comments": p.comments, "is_ai": p.is_ai} for p in posts]

@app.post("/api/v2/social/post")
async def create_social_post(req: SocialPostRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.username == req.username)
    res = await db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    post = SocialPost(
        id=generate_post_id(),
        username=req.username,
        content=req.content,
        timestamp=datetime.now().strftime("%H:%M:%S"),
        likes=0,
        comments=[],
        is_ai=False
    )
    db.add(post)
    await db.commit()
    await manager.broadcast({"type": "new_post", "post": {"id": post.id, "username": post.username, "content": post.content, "timestamp": post.timestamp, "likes": post.likes, "comments": post.comments}})
    return {"id": post.id, "username": post.username, "content": post.content, "timestamp": post.timestamp, "likes": post.likes, "comments": post.comments}

@app.post("/api/v2/social/like")
async def like_post(req: LikeRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(SocialPost).where(SocialPost.id == req.post_id)
    res = await db.execute(stmt)
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post topilmadi.")
    post.likes += 1
    await db.commit()
    return {"success": True, "likes": post.likes}

@app.post("/api/v2/social/comment")
async def comment_post(req: CommentRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(SocialPost).where(SocialPost.id == req.post_id)
    res = await db.execute(stmt)
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post topilmadi.")
    comments = post.comments or []
    comments.append({"username": req.username, "text": req.comment, "timestamp": datetime.now().isoformat()})
    post.comments = comments
    await db.commit()
    return {"success": True, "comment": comments[-1]}

@app.post("/api/v2/social/repost")
async def repost_post(req: LikeRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(SocialPost).where(SocialPost.id == req.post_id)
    res = await db.execute(stmt)
    original = res.scalar_one_or_none()
    if not original:
        raise HTTPException(404, "Post topilmadi.")
    new_post = SocialPost(
        id=generate_post_id(),
        username=req.username,
        content=f"🔁 Repost: {original.content}",
        timestamp=datetime.now().strftime("%H:%M:%S"),
        likes=0,
        comments=[],
        is_ai=False
    )
    db.add(new_post)
    await db.commit()
    return {"success": True, "repost": {"id": new_post.id, "username": new_post.username, "content": new_post.content, "timestamp": new_post.timestamp}}

@app.post("/api/v2/social/follow")
async def follow_user(req: FollowRequest, db: AsyncSession = Depends(get_db)):
    if req.username == req.target:
        return {"success": False, "message": "O'zingizni kuzata olmaysiz."}
    stmt = select(User).where(User.username.in_([req.username, req.target]))
    res = await db.execute(stmt)
    users = res.scalars().all()
    if len(users) != 2:
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    stmt = select(Follow).where(Follow.follower == req.username, Follow.following == req.target)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        return {"success": False, "message": "Siz allaqachon bu foydalanuvchini kuzatasiz."}
    follow = Follow(follower=req.username, following=req.target)
    db.add(follow)
    await db.commit()
    return {"success": True, "message": f"{req.target} ni kuzatish boshlandi."}

# ===== NOTIFICATIONS =====
@app.get("/api/v2/notifications/{username}")
async def get_notifications(username: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Notification).where(Notification.username == username).order_by(Notification.timestamp.desc()).limit(20)
    res = await db.execute(stmt)
    notifs = res.scalars().all()
    return [{"id": n.id, "message": n.message, "type": n.type, "timestamp": n.timestamp.isoformat(), "read": n.read} for n in notifs]

@app.post("/api/v2/notifications/read/{username}")
async def mark_notifications_read(username: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Notification).where(Notification.username == username, Notification.read == False)
    res = await db.execute(stmt)
    notifs = res.scalars().all()
    for n in notifs:
        n.read = True
    await db.commit()
    return {"success": True}

# ===== AI CHAT =====
@app.post("/api/v2/ai/chat")
async def ai_chat(req: AIChatRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.username == req.username)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    chat_price = 49.0
    rate = {"USD": 1.0, "EUR": 0.92, "BTC": 0.000015, "SOL": 0.0075}
    price = chat_price * rate.get(user.currency, 1.0)
    if user.balance < price:
        return {"success": False, "message": f"⚠️ AI chat uchun ${price:.2f} kerak."}
    user.balance -= price
    await db.commit()
    messages = [{"role": "system", "content": "Siz BioEmpire AI shifokorisiz."}, {"role": "user", "content": req.message}]
    ai_response = await call_ai_api(messages)
    if not ai_response:
        ai_response = "🧬 Simptomlaringiz virusli infeksiyaga o'xshaydi. 3 kun dam oling va ko'p suv iching."
    return {"success": True, "response": ai_response, "new_balance": user.balance, "deducted": price}

# ===== CAMERA =====
@app.post("/api/v2/camera/analyze")
async def camera_analyze(req: CameraAnalysisRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.username == req.username)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi.")
    price = 150.0 * {"USD":1.0, "EUR":0.92, "BTC":0.000015, "SOL":0.0075}.get(user.currency, 1.0)
    if user.balance < price:
        return {"success": False, "message": f"⚠️ Kamera analizi uchun ${price:.2f} kerak."}
    user.balance -= price
    await db.commit()
    analysis = "🔬 Rasm tahlili: Teri toshmasi aniqlangan. Dermatologga murojaat qilish tavsiya etiladi."
    if req.image_data and GEMINI_AVAILABLE and GEMINI_API_KEY:
        try:
            img_data = req.image_data.split(",")[1] if "," in req.image_data else req.image_data
            img_bytes = base64.b64decode(img_data)
            model = genai.GenerativeModel(GEMINI_MODEL)
            resp = await asyncio.to_thread(
                model.generate_content,
                ["Ushbu rasmni tahlil qiling va diagnostik tavsiya bering.", {"mime_type": "image/jpeg", "data": img_bytes}]
            )
            if resp and resp.text:
                analysis = "🔬 " + resp.text
        except Exception as e:
            analysis = f"🔬 Rasm tahlilida xatolik: {e}"
    return {"success": True, "analysis": analysis, "new_balance": user.balance, "deducted": price}

# ===== HEALTH RANKING =====
@app.get("/api/v2/health/ranking")
async def get_health_ranking(db: AsyncSession = Depends(get_db)):
    stmt = select(User).order_by(User.health_score.desc())
    res = await db.execute(stmt)
    users = res.scalars().all()
    return [{"username": u.username, "health_score": u.health_score, "status": u.status, "avatar": u.avatar} for u in users]

# ===== STATS =====
@app.get("/api/v2/system/stats")
async def get_system_stats(db: AsyncSession = Depends(get_db)):
    stmt = select(User)
    res = await db.execute(stmt)
    users = res.scalars().all()
    total_users = len(users)
    stmt2 = select(ProductSale)
    res2 = await db.execute(stmt2)
    sales = res2.scalars().all()
    total_revenue = sum(s.total_price for s in sales) if sales else 0.0
    active_users = len([u for u in users if u.last_active and (datetime.utcnow() - u.last_active) < timedelta(days=1)])
    stmt3 = select(SocialPost)
    res3 = await db.execute(stmt3)
    total_posts = len(res3.scalars().all())
    return {
        "total_revenue": total_revenue,
        "active_users": active_users,
        "total_sales": len(sales),
        "total_social_posts": total_posts
    }

# ===== AI ADS =====
@app.get("/api/v2/ai/ads-performance")
async def get_ads_performance(db: AsyncSession = Depends(get_db)):
    stmt = select(AdsPerformance)
    res = await db.execute(stmt)
    ads = res.scalars().all()
    return {a.campaign_id: {"product_name": a.product_name, "type": a.type, "conversions": a.conversions, "impressions": a.impressions, "ctr": a.ctr, "roi": a.roi, "budget": a.budget, "spent": a.spent, "active": a.active} for a in ads}

# ===== ADMIN =====
ADMIN_USERNAME = "CEO"
ADMIN_PASSWORD_HASH = hash_password("12345678")

@app.post("/api/v2/admin/login")
async def admin_login(request: Request):
    data = await request.json()
    if data.get("username") == ADMIN_USERNAME and verify_password(data.get("password", ""), ADMIN_PASSWORD_HASH):
        return {"success": True, "token": "admin-token"}
    raise HTTPException(401, "Noto'g'ri admin ma'lumotlari")

@app.get("/api/v2/admin/dashboard")
async def admin_dashboard(username: str = None, password: str = None, db: AsyncSession = Depends(get_db)):
    if username != ADMIN_USERNAME or not verify_password(password or "", ADMIN_PASSWORD_HASH):
        raise HTTPException(401, "Avtorizatsiya kerak")
    stmt = select(User)
    res = await db.execute(stmt)
    users = res.scalars().all()
    stmt2 = select(ProductSale)
    res2 = await db.execute(stmt2)
    sales = res2.scalars().all()
    total_revenue = sum(s.total_price for s in sales) if sales else 0.0
    return {
        "total_users": len(users),
        "total_revenue": total_revenue,
        "active_users": len([u for u in users if u.last_active and (datetime.utcnow() - u.last_active) < timedelta(days=1)]),
        "total_sales": len(sales)
    }

# ===== CEO =====
@app.get("/api/v2/ceo/dashboard")
async def ceo_dashboard(username: str = None, password: str = None, db: AsyncSession = Depends(get_db)):
    if username != ADMIN_USERNAME or not verify_password(password or "", ADMIN_PASSWORD_HASH):
        raise HTTPException(401, "Faqat CEO uchun")
    stmt = select(CEOIdea).order_by(CEOIdea.timestamp.desc()).limit(5)
    res = await db.execute(stmt)
    ideas = res.scalars().all()
    return {"insights": [{"timestamp": i.timestamp.isoformat(), "content": i.content} for i in ideas]}

# ===== WEBSOCKET =====
@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ==========================================
# STARTUP – TABELLARNI YARATISH
# ==========================================
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Baza jadvallari yaratildi.")
    print("🚀 BioEmpire V12 ishga tushdi!")

# ==========================================
# HTML (FALLBACK)
# ==========================================
HTML = """<!DOCTYPE html>
<html><body><h1>🧬 BioEmpire V12</h1><p>Ro'yxatdan o'tish ixtiyoriy, o'ng tomonda.</p></body></html>
"""

# ==========================================
# SERVER
# ==========================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
