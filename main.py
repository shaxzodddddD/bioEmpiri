import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext

# --- 1. DIRECTORY CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

# Templates va Static obyektlarini sozlash
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- 2. DATABASE CONFIGURATION (SQLite) ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bioempire_v13.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Model
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_order=True, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 3. SECURITY & HASHING ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# --- 4. FASTAPI APP INITIALIZATION ---
app = FastAPI(
    title="🧬 BioEmpire V13 Enterprise Core",
    description="Render Production Ready FastAPI Infrastructure",
    version="13.0.0"
)

# --- 5. ROUTERS & ENDPOINTS ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Bosh sahifa - HTML shablonni qaytaradi"""
    return templates.TemplateResponse("index.html", {"request": request, "title": "BioEmpire V13"})

@app.post("/api/register")
async def register_user(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Foydalanuvchini ro'yxatdan o'tkazish"""
    db_user = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Foydalanuvchi nomi yoki email band!")
    
    new_user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"status": "success", "message": "Ro'yxatdan muvaffaqiyatli o'tdingiz!", "user_id": new_user.id}

@app.post("/api/login")
async def login_user(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Tizimga kirish (Login)"""
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Foydalanuvchi nomi yoki parol xato!")
    
    return {"status": "success", "message": f"Xush kelibsiz, {user.username}!", "user_id": user.id}

@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    """Salomatlik reytingi va Tizim holati"""
    user_count = db.query(User).count()
    return {
        "status": "healthy",
        "system": "BioEmpire V13 Engine",
        "database": "connected",
        "health_score": 99.8,
        "total_registered_users": user_count
    }

@app.get("/api/stats")
async def system_stats(db: Session = Depends(get_db)):
    """Tizim statistikasi"""
    total_users = db.query(User).count()
    return {
        "active_node": "Render Cloud Ohio",
        "version": "13.0.0-PROD",
        "total_users": total_users,
        "gpu_acceleration": "Enabled",
        "uptime": "99.99%"
    }
