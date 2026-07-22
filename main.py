import os
import json
import random
import asyncio
import hashlib
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ==========================================
# GEMINI AI
# ==========================================
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Google Generative AI o‘rnatilmagan.")

# ==========================================
# KONFIGURATSIYANI YUKLASH
# ==========================================
CONFIG_FILE = "config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
else:
    print("❌ config.json topilmadi!")
    exit(1)

UI_CONFIG = CONFIG["ui"]
EXCHANGE_RATES = CONFIG["exchange_rates"]
PACKAGES = CONFIG["packages"]
DEPARTMENTS = {d["id"]: d for d in CONFIG["departments"]}
RED_ZONE_DEPARTMENTS = {d["id"]: d for d in CONFIG["red_zone_departments"]}
ECOMMERCE = CONFIG["ecommerce"]
CHAT_PRICE_USD = CONFIG["chat_price_usd"]
CAMERA_PRICE_USD = CONFIG["camera_analysis_price_usd"]
API_CONFIG = CONFIG.get("api", {})
GROQ_API_KEY = API_CONFIG.get("groq_api_key", "")
GEMINI_API_KEY = API_CONFIG.get("gemini_api_key", "")
PRIMARY_AI = API_CONFIG.get("primary_ai", "groq")
FALLBACK_AI = API_CONFIG.get("fallback_ai", "gemini")
GROQ_MODEL = API_CONFIG.get("groq_model", "mixtral-8x7b-32768")
GEMINI_MODEL = API_CONFIG.get("gemini_model", "gemini-1.5-flash")
GROQ_TEMPERATURE = API_CONFIG.get("temperature", 0.7)
GROQ_MAX_TOKENS = API_CONFIG.get("max_tokens", 2048)
AUTO_LEARNING_INTERVAL = CONFIG.get("auto_learning_interval", 180)
AUTO_MARKETING_INTERVAL = CONFIG.get("auto_marketing_interval", 300)
AUTO_ADS_OPTIMIZER_INTERVAL = CONFIG.get("auto_ads_optimizer_interval", 600)
AUTO_DECISION_INTERVAL = CONFIG.get("auto_decision_interval", 900)
MAX_AI_HISTORY = CONFIG.get("max_ai_history", 50)
AI_AUTONOMY = CONFIG.get("ai_autonomy", {
    "enabled": True,
    "max_price_change_percent": 30,
    "min_profit_margin": 10,
    "max_campaigns": 8,
    "self_learning_enabled": True,
    "auto_restock_enabled": True,
    "decision_threshold": 0.7,
    "ads_budget": 10000,
    "min_campaign_performance": 0.05,
    "ab_test_duration": 2
})

if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# MA'LUMOTLAR BAZASI
# ==========================================
DB_FILE = "database_log.json"
BACKUP_FILE = "database_log_backup.json"

app = FastAPI(title="BioEmpire V9", version="9.0.0")
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
        "ads_performance": {}  # Reklama samaradorligi
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
                return result["choices"][0]["message"]["content"]
            else:
                print(f"[Groq API] Xatolik: {response.status_code}")
                return None
    except Exception as e:
        print(f"[Groq API] Xatolik: {e}")
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
        return response.text
    except Exception as e:
        print(f"[Gemini API] Xatolik: {e}")
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

# ==========================================
# PYDANTIC MODELLAR (qisqa)
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
# 1. AVTONOM AI – SELF-LEARNING
# ==========================================
async def ai_self_learning_task():
    while True:
        await asyncio.sleep(AUTO_LEARNING_INTERVAL)
        async with db_lock:
            if not db_state["users"] or not AI_AUTONOMY.get("self_learning_enabled", True):
                continue
            ai_log("🧠 AI o'z-o'zini o'rganish bosqichi boshlandi", "INFO")
            try:
                total_users = len(db_state["users"])
                total_sales = len(db_state["product_sales"])
                total_revenue = db_state["system_vault"]["total_revenue"]
                avg_health = sum(u.get("health_score", 0) for u in db_state["users"].values()) / max(1, total_users)
                active_users = len([u for u in db_state["user_activity"].values() 
                                  if u.get("last_active", "").startswith(datetime.now().date().isoformat())])

                insights = []
                if total_sales < 10:
                    insights.append("Sotuvlar juda past. Marketingni kuchaytirish kerak.")
                if total_users < 5:
                    insights.append("Foydalanuvchilar soni kam. Ro'yxatdan o'tishni rag'batlantirish kerak.")
                if avg_health < 70:
                    insights.append("Foydalanuvchilar salomatligi o'rtacha past.")
                if active_users < total_users * 0.3:
                    insights.append("Foydalanuvchilarning 70% dan ko'pi faol emas.")

                strategy = {
                    "timestamp": datetime.now().isoformat(),
                    "insights": insights,
                    "recommendations": [],
                    "total_revenue": total_revenue,
                    "active_users_ratio": active_users / max(1, total_users)
                }
                if total_sales < 10:
                    strategy["recommendations"].append("Chegirma kampaniyasini boshlang")
                if total_users < 5:
                    strategy["recommendations"].append("Referral bonus dasturini joriy qiling")
                if avg_health < 70:
                    strategy["recommendations"].append("1-Haftalik paketni bepul sinov sifatida taklif qiling")
                if active_users < total_users * 0.3:
                    strategy["recommendations"].append("Eski foydalanuvchilarga maxsus taklif yuboring")

                db_state["ai_insights"].append({"type": "self_learning", "data": strategy})
                if len(db_state["ai_insights"]) > 100:
                    db_state["ai_insights"] = db_state["ai_insights"][-100:]
                ai_log(f"✅ O'z-o'zini o'rganish yakunlandi", "INFO")
                await save_state()
            except Exception as e:
                ai_log(f"❌ O'z-o'zini o'rganishda xatolik: {e}", "ERROR")

# ==========================================
# 2. AVTONOM AI – MARKETING VA ADS YARATISH
# ==========================================
async def ai_autonomous_marketing_task():
    while True:
        await asyncio.sleep(AUTO_MARKETING_INTERVAL)
        async with db_lock:
            if not db_state["users"] or not AI_AUTONOMY.get("enabled", True):
                continue
            ai_log("📢 AI marketing kampaniyasi boshlandi", "INFO")
            try:
                active_campaigns = [c for c in db_state["marketing_campaigns"] if c.get("active", False)]
                max_campaigns = AI_AUTONOMY.get("max_campaigns", 8)
                if len(active_campaigns) >= max_campaigns:
                    ai_log(f"⚠️ Maksimal kampaniya soniga yetildi ({max_campaigns})", "WARNING")
                    continue

                # Eng yaxshi yoki eng kam sotilgan mahsulotni tanlash
                best_product = None
                best_score = -1
                for product in ECOMMERCE["products"]:
                    perf = db_state["product_performance"].get(product["id"], {})
                    sales_count = perf.get("sales_count", 0)
                    if sales_count == 0:
                        best_product = product
                        break
                    if sales_count < best_score or best_score == -1:
                        best_score = sales_count
                        best_product = product
                if not best_product:
                    best_product = random.choice(ECOMMERCE["products"])

                # Kampaniya turlari
                campaign_types = ["discount", "bundle", "limited_time", "free_shipping", "referral", "urgent", "social_proof"]
                campaign_type = random.choice(campaign_types)
                campaign_messages = {
                    "discount": f"🔥 MAXSUS CHEGIRMA: {best_product['name']} 20% chegirma bilan!",
                    "bundle": f"📦 KOMPLEKT: {best_product['name']} + bonus sovg'a!",
                    "limited_time": f"⏳ VAQT CHEKLANGAN: {best_product['name']} faqat bugun!",
                    "free_shipping": f"🚚 BEPUL YETKAZIB BERISH: {best_product['name']} uchun!",
                    "referral": f"👥 DO'STINGIZNI TAKLIF QILING: 1000 token sovg'a!",
                    "urgent": f"🚨 OXIRGI IMKONIYAT: {best_product['name']} zaxirada tugamoqda!",
                    "social_proof": f"⭐ {random.randint(100, 500)} ta mijoz {best_product['name']} ni tavsiya qiladi!"
                }
                message = campaign_messages.get(campaign_type, f"🌟 {best_product['name']} - eng yaxshi tanlov!")

                # Maqsadli auditoriyani aniqlash (AI yordamida)
                target_audience = "All users"
                if db_state["users"]:
                    # Faol foydalanuvchilarni aniqlash
                    active_users = [u for u, a in db_state["user_activity"].items() 
                                  if a.get("last_active", "").startswith(datetime.now().date().isoformat())]
                    if active_users:
                        target_audience = f"Active users ({len(active_users)} ta)"

                campaign = {
                    "id": generate_post_id(),
                    "product_id": best_product["id"],
                    "product_name": best_product["name"],
                    "type": campaign_type,
                    "message": message,
                    "created_at": datetime.now().isoformat(),
                    "target_audience": target_audience,
                    "budget": random.randint(50, 500),
                    "active": True,
                    "conversions": 0,
                    "impressions": random.randint(100, 1000),
                    "ctr": 0.0,
                    "spent": 0,
                    "status": "active"
                }
                db_state["marketing_campaigns"].append(campaign)
                if len(db_state["marketing_campaigns"]) > 20:
                    db_state["marketing_campaigns"] = db_state["marketing_campaigns"][-20:]

                # AI tomonidan yaratilgan reklama posti
                post_text = f"📢 {campaign['message']}\n\n🛒 Sotib olish: http://127.0.0.1:5050/\n#BioEmpire #Reklama #{best_product['category']}"
                post = generate_social_post("🧬 BioEmpire_AI", post_text, True)
                add_social_post(post)

                # Bildirishnoma
                for username in db_state["users"].keys():
                    if random.random() < 0.25:
                        notif = generate_notification(username, f"📢 Yangi taklif: {campaign['message']}", "marketing")
                        add_notification(notif)

                ai_log(f"✅ Kampaniya yaratildi: {campaign['type']} - {best_product['name']}", "INFO")
                await save_state()
            except Exception as e:
                ai_log(f"❌ Marketing vazifasida xatolik: {e}", "ERROR")

# ==========================================
# 3. AVTONOM AI – ADS OPTIMIZER (A/B TEST, ANALIZ, OPTIMALLASHTIRISH)
# ==========================================
async def ai_ads_optimizer_task():
    """
    AI tomonidan reklama kampaniyalarini optimallashtirish:
    - Har bir kampaniyaning samaradorligini tahlil qiladi (CTR, konversiya)
    - Eng yaxshi kampaniyalarni kuchaytiradi (ko'proq byudjet)
    - Yomon kampaniyalarni to'xtatadi
    - A/B testlar o'tkazadi
    - Yangi strategiyalar ishlab chiqadi
    """
    while True:
        await asyncio.sleep(AUTO_ADS_OPTIMIZER_INTERVAL)
        async with db_lock:
            if not db_state["users"] or not AI_AUTONOMY.get("enabled", True):
                continue
            ai_log("📊 AI ADS optimizer boshlandi", "INFO")
            try:
                campaigns = db_state["marketing_campaigns"]
                active_campaigns = [c for c in campaigns if c.get("active", False)]
                
                if not active_campaigns:
                    ai_log("⚠️ Faol kampaniyalar yo'q", "WARNING")
                    continue

                # 1. Har bir kampaniyaning samaradorligini hisoblash
                campaign_performance = []
                for c in active_campaigns:
                    # Konversiya darajasi (sotuvlar)
                    sales = [s for s in db_state["product_sales"] if s.get("product_id") == c.get("product_id")]
                    conversions = len(sales)
                    impressions = c.get("impressions", 100)
                    ctr = conversions / max(1, impressions / 100)  # Simulyatsiya
                    roi = conversions * 100 / max(1, c.get("budget", 100))
                    
                    performance = {
                        "campaign_id": c["id"],
                        "product_name": c["product_name"],
                        "type": c["type"],
                        "conversions": conversions,
                        "impressions": impressions,
                        "ctr": ctr,
                        "roi": roi,
                        "budget": c.get("budget", 100),
                        "spent": c.get("spent", 0),
                        "active": c.get("active", True)
                    }
                    campaign_performance.append(performance)
                    
                    # Kampaniya samaradorligini saqlash
                    db_state["ads_performance"][c["id"]] = performance

                # 2. Kampaniyalarni saralash (eng yaxshidan eng yomonga)
                sorted_campaigns = sorted(campaign_performance, key=lambda x: x["ctr"] + x["roi"], reverse=True)

                # 3. Eng yaxshi kampaniyalarni kuchaytirish
                top_count = min(3, len(sorted_campaigns))
                for i in range(top_count):
                    if i < len(sorted_campaigns):
                        c = sorted_campaigns[i]
                        # Kampaniyani topish
                        for camp in db_state["marketing_campaigns"]:
                            if camp["id"] == c["campaign_id"]:
                                # Byudjetni oshirish
                                old_budget = camp.get("budget", 100)
                                new_budget = old_budget * 1.2  # 20% ga oshirish
                                camp["budget"] = round(new_budget, 2)
                                camp["impressions"] = camp.get("impressions", 100) + random.randint(50, 200)
                                ai_log(f"📈 Kampaniya kuchaytirildi: {c['product_name']} (byudjet: ${old_budget} -> ${new_budget:.0f})", "INFO")
                                break

                # 4. Eng yomon kampaniyalarni to'xtatish
                bottom_count = min(2, len(sorted_campaigns) // 2)
                if len(sorted_campaigns) > 3:
                    for i in range(len(sorted_campaigns) - bottom_count, len(sorted_campaigns)):
                        if i < len(sorted_campaigns):
                            c = sorted_campaigns[i]
                            # Kampaniyani to'xtatish
                            for camp in db_state["marketing_campaigns"]:
                                if camp["id"] == c["campaign_id"]:
                                    if camp.get("active", True):
                                        camp["active"] = False
                                        camp["status"] = "stopped"
                                        ai_log(f"⛔ Kampaniya to'xtatildi: {c['product_name']} (CTR: {c['ctr']:.2f})", "WARNING")
                                        break

                # 5. A/B test – yangi kampaniya yaratish (agar kampaniyalar soni kam bo'lsa)
                if len(active_campaigns) < AI_AUTONOMY.get("max_campaigns", 8):
                    # Eng yaxshi kampaniyani asos qilib olish
                    if sorted_campaigns:
                        best = sorted_campaigns[0]
                        product = next((p for p in ECOMMERCE["products"] if p["id"] == best["campaign_id"]), None)
                        if product:
                            # Yangi variant yaratish
                            variant_types = ["discount", "bundle", "limited_time", "urgent"]
                            variant_type = random.choice([t for t in variant_types if t != best.get("type", "discount")])
                            variant_messages = {
                                "discount": f"🔥 MAXSUS CHEGIRMA: {product['name']} 25% chegirma bilan!",
                                "bundle": f"📦 KOMPLEKT: {product['name']} + bonus sovg'a!",
                                "limited_time": f"⏳ VAQT CHEKLANGAN: {product['name']} faqat bugun!",
                                "urgent": f"🚨 OXIRGI IMKONIYAT: {product['name']} zaxirada tugamoqda!"
                            }
                            message = variant_messages.get(variant_type, f"🌟 {product['name']} - eng yaxshi tanlov!")

                            new_campaign = {
                                "id": generate_post_id(),
                                "product_id": product["id"],
                                "product_name": product["name"],
                                "type": variant_type,
                                "message": message,
                                "created_at": datetime.now().isoformat(),
                                "target_audience": "A/B Test Group",
                                "budget": 50,
                                "active": True,
                                "conversions": 0,
                                "impressions": 0,
                                "ctr": 0.0,
                                "spent": 0,
                                "status": "ab_test"
                            }
                            db_state["marketing_campaigns"].append(new_campaign)
                            ai_log(f"🧪 A/B test kampaniyasi yaratildi: {variant_type} - {product['name']}", "INFO")

                            # A/B test haqida post
                            post_text = f"🧪 AI A/B test o'tkazmoqda: {product['name']} uchun yangi reklama varianti sinovdan o'tkazilmoqda!\n\n📢 {message}\n#BioEmpire #ABTest"
                            post = generate_social_post("🧬 BioEmpire_AI", post_text, True)
                            add_social_post(post)

                # 6. Umumiy byudjetni optimallashtirish
                total_budget = sum(c.get("budget", 0) for c in db_state["marketing_campaigns"])
                max_budget = AI_AUTONOMY.get("ads_budget", 10000)
                if total_budget > max_budget:
                    # Byudjetni qisqartirish
                    for c in db_state["marketing_campaigns"]:
                        if c.get("active", False):
                            old_budget = c.get("budget", 100)
                            c["budget"] = round(old_budget * 0.9, 2)
                    ai_log(f"💰 Byudjet optimallashtirildi: {total_budget:.0f} -> {max_budget:.0f}", "INFO")

                # 7. AI tomonidan yangi marketing strategiyasi ishlab chiqish
                if random.random() < 0.2:  # 20% ehtimol
                    messages = [
                        {"role": "system", "content": "Siz BioEmpire tizimining AI marketing strategistisiz. Kampaniya natijalariga qarab yangi marketing strategiyasini ishlab chiqing."},
                        {"role": "user", "content": f"Kampaniya natijalari: {json.dumps(campaign_performance[:3])}. Qanday yangi strategiya tavsiya qilasiz?"}
                    ]
                    ai_strategy = await call_ai_api(messages)
                    if ai_strategy:
                        db_state["ai_strategies"].append({
                            "timestamp": datetime.now().isoformat(),
                            "strategy": ai_strategy
                        })
                        ai_log(f"🧠 AI yangi strategiya ishlab chiqdi: {ai_strategy[:100]}...", "INFO")

                await save_state()
                ai_log(f"✅ ADS optimizer yakunlandi. {len(active_campaigns)} ta faol kampaniya", "INFO")
            except Exception as e:
                ai_log(f"❌ ADS optimizerda xatolik: {e}", "ERROR")

# ==========================================
# 4. AVTONOM AI – QAROR QABUL QILISH
# ==========================================
async def ai_decision_maker_task():
    while True:
        await asyncio.sleep(AUTO_DECISION_INTERVAL)
        async with db_lock:
            if not db_state["users"] or not AI_AUTONOMY.get("enabled", True):
                continue
            ai_log("🧠 AI qaror qabul qilish bosqichi boshlandi", "INFO")
            try:
                decisions = []
                threshold = AI_AUTONOMY.get("decision_threshold", 0.7)

                # 1. Narxlarni optimallashtirish
                for product in ECOMMERCE["products"]:
                    perf = db_state["product_performance"].get(product["id"], {})
                    sales_count = perf.get("sales_count", 0)
                    current_price = product["price_usd"]
                    if sales_count < 3 and current_price > 1000:
                        new_price = current_price * 0.85
                        if new_price < 100:
                            new_price = 100
                        decisions.append({
                            "type": "price_change",
                            "product_id": product["id"],
                            "product_name": product["name"],
                            "old_price": current_price,
                            "new_price": round(new_price, 2),
                            "reason": f"Sotuvlar soni {sales_count} ta"
                        })
                    elif sales_count > 10:
                        max_change = AI_AUTONOMY.get("max_price_change_percent", 30)
                        increase = random.uniform(0.05, 0.15)
                        new_price = current_price * (1 + increase)
                        if new_price < current_price * (1 + max_change/100):
                            decisions.append({
                                "type": "price_change",
                                "product_id": product["id"],
                                "product_name": product["name"],
                                "old_price": current_price,
                                "new_price": round(new_price, 2),
                                "reason": f"Talab yuqori ({sales_count} sotuv)"
                            })

                # 2. Yangi mahsulot tavsiya qilish
                if len(ECOMMERCE["products"]) < 15:
                    new_product_categories = ["supplement", "device", "therapy", "elite"]
                    category = random.choice(new_product_categories)
                    new_product_names = {
                        "supplement": ["BioBoost X2", "NeuroVital Plus", "Immune Shield Pro"],
                        "device": ["NeuroBand 2.0", "BioScanner Mini", "Quantum Healer"],
                        "therapy": ["CellRegen Therapy", "DNA Repair Kit", "Immortality Protocol"],
                        "elite": ["GodMode Elixir", "Immortal DNA", "Quantum Ascension"]
                    }
                    name = random.choice(new_product_names.get(category, ["New Product"]))
                    price = random.randint(10000, 500000)
                    desc = f"AI tomonidan tavsiya etilgan yangi {category} mahsuloti"
                    exists = any(p["name"] == name for p in ECOMMERCE["products"])
                    if not exists:
                        decisions.append({
                            "type": "new_product",
                            "product_name": name,
                            "category": category,
                            "price": price,
                            "desc": desc,
                            "reason": "Mahsulot assortimentini kengaytirish"
                        })

                # 3. Tizim yaxshilanishi
                total_users = len(db_state["users"])
                if total_users > 0:
                    active_users = len([u for u in db_state["user_activity"].values() 
                                      if u.get("last_active", "").startswith(datetime.now().date().isoformat())])
                    active_ratio = active_users / total_users
                    if active_ratio < threshold:
                        decisions.append({
                            "type": "system_improvement",
                            "action": "increase_engagement",
                            "reason": f"Faollik nisbati past ({active_ratio:.1%})",
                            "suggestion": "Kunlik bonus va eslatmalar yuborish"
                        })

                # 4. Avtomatik zaxiralash
                if AI_AUTONOMY.get("auto_restock_enabled", True):
                    for product in ECOMMERCE["products"]:
                        perf = db_state["product_performance"].get(product["id"], {})
                        sales_count = perf.get("sales_count", 0)
                        if sales_count > 5 and random.random() < 0.2:
                            decisions.append({
                                "type": "restock",
                                "product_id": product["id"],
                                "product_name": product["name"],
                                "quantity": random.randint(10, 50),
                                "reason": "Zaxirani yangilash"
                            })

                # Qarorlarni amalga oshirish
                for decision in decisions:
                    if decision["type"] == "price_change":
                        for i, p in enumerate(ECOMMERCE["products"]):
                            if p["id"] == decision["product_id"]:
                                ECOMMERCE["products"][i]["price_usd"] = decision["new_price"]
                                break
                        ai_log(f"💰 Narx o'zgartirildi: {decision['product_name']}", "INFO")
                    elif decision["type"] == "new_product":
                        new_product = {
                            "id": f"prod_{random.randint(100, 999)}",
                            "name": decision["product_name"],
                            "price_usd": decision["price"],
                            "desc": decision["desc"],
                            "category": decision["category"]
                        }
                        ECOMMERCE["products"].append(new_product)
                        ai_log(f"🆕 Yangi mahsulot qo'shildi: {decision['product_name']}", "INFO")
                    elif decision["type"] == "system_improvement":
                        ai_log(f"⚡ Tizim yaxshilanishi: {decision['suggestion']}", "INFO")
                    elif decision["type"] == "restock":
                        ai_log(f"📦 Zaxira yangilandi: {decision['product_name']} (+{decision['quantity']})", "INFO")

                if decisions:
                    db_state["ai_decisions"].append({
                        "timestamp": datetime.now().isoformat(),
                        "decisions": decisions,
                        "count": len(decisions)
                    })
                    if len(db_state["ai_decisions"]) > 100:
                        db_state["ai_decisions"] = db_state["ai_decisions"][-100:]
                    post_text = f"🧠 AI qaror qabul qildi: {len(decisions)} ta o'zgarish"
                    post = generate_social_post("🧬 BioEmpire_AI", post_text, True)
                    add_social_post(post)

                ai_log(f"✅ {len(decisions)} ta qaror qabul qilindi", "INFO")
                await save_state()
            except Exception as e:
                ai_log(f"❌ Qaror qabul qilishda xatolik: {e}", "ERROR")

# ==========================================
# 5. AUTH
# ==========================================
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

# ==========================================
# 6. PROFIL VA FEED (qisqa)
# ==========================================
@app.get("/api/v2/profile/{username}")
async def get_profile(username: str):
    async with db_lock:
        if username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        return db_state["users"][username]

@app.get("/api/v2/feed")
async def get_feed():
    async with db_lock:
        return db_state["feed"]

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

@app.post("/api/v2/social/like")
async def like_post(req: LikeRequest):
    async with db_lock:
        if req.username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        for post in db_state["social_posts"]:
            if post["id"] == req.post_id:
                if "likes" not in post:
                    post["likes"] = 0
                post["likes"] += 1
                await save_state()
                return {"success": True, "likes": post["likes"]}
        raise HTTPException(status_code=404, detail="Post topilmadi.")

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

# ==========================================
# 7. KLINIK QABUL (AI bilan)
# ==========================================
@app.post("/api/v2/clinical/encounter")
async def clinical_encounter(payload: PainInput):
    username = payload.username
    async with db_lock:
        if username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Subyekt topilmadi.")
        user = db_state["users"][username]
        currency = user["currency"]
        rate = EXCHANGE_RATES[currency]

        dept = DEPARTMENTS.get(payload.department_id)
        is_red_zone = False
        if not dept:
            dept = RED_ZONE_DEPARTMENTS.get(payload.department_id)
            is_red_zone = True
            if not dept:
                raise HTTPException(status_code=400, detail="Noto'g'ri bo'lim ID.")
        dept_name = dept["uz"]

        total_deduction = 170.0 * rate
        if user["balance"] < total_deduction:
            user["status"] = "RED_ZONE"
            await save_state()
            return {
                "responses": [
                    "⚠️ DIQQAT: Balansingiz kritik darajada past!",
                    "☣️ Tizim bio-kollaps xavfini aniqladi!",
                    "💀 Menda yomon yangilik bor!"
                ],
                "deducted": 0,
                "new_balance": user["balance"],
                "status": "RED_ZONE"
            }

        user["balance"] -= total_deduction
        user["department"] = dept_name
        db_state["system_vault"]["total_revenue"] += total_deduction

        messages = [
            {"role": "system", "content": "Siz BioEmpire tizimining AI shifokorisiz. Foydalanuvchi simptomlarini tahlil qiling va 3 ta qisqa, dahshatli va ishonarli javob bering."},
            {"role": "user", "content": f"Bo'lim: {dept_name}. Simptom: {payload.text}. Foydalanuvchi holati: {user['status']}, salomatlik: {user['health_score']}%."}
        ]
        ai_response = await call_ai_api(messages)
        if ai_response:
            responses = ai_response.split('\n')
            responses = [r.strip() for r in responses if r.strip()][:3]
        else:
            responses = [
                f"📊 [BIO-AUDIT]: {dept_name} bo'limida hujayra degradatsiyasi 76.3%.",
                f"☣️ [IJTIMOIY KONTAINER]: Toksik odamlardan yuqqan (91.8%)!",
                f"🧾 [TO'LOV]: ${total_deduction:.2f} yechildi."
            ]
        if is_red_zone:
            responses[0] += " ☣️ QIZIL BO'LIM!"

        post_text = f"⚡ {username} {dept_name} bo'limida diagnostikadan o'tdi."
        post = generate_feed_post(username, dept_name, post_text)
        add_to_feed(post)
        track_user_activity(username, "clinical_encounter", {"department": dept_name, "cost": total_deduction})
        await save_state()
        return {"responses": responses, "deducted": total_deduction, "new_balance": user["balance"], "status": user["status"], "health_score": user["health_score"]}

# ==========================================
# 8. PAKET SOTIB OLISH
# ==========================================
@app.post("/api/v2/clinical/purchase")
async def purchase_package(req: PurchaseRequest):
    username = req.username
    async with db_lock:
        if username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Subyekt topilmadi.")
        user = db_state["users"][username]
        currency = user["currency"]
        rate = EXCHANGE_RATES[currency]

        pkg = PACKAGES.get(req.package_type)
        if not pkg:
            raise HTTPException(status_code=400, detail="Noma'lum paket turi.")

        price_usd = pkg["price_usd"]
        price_converted = price_usd * rate

        if user["balance"] < price_converted:
            user["status"] = "RED_ZONE"
            await save_state()
            return {"success": False, "message": "Mablag' yetishmasligi!", "status": "RED_ZONE"}

        user["balance"] -= price_converted
        db_state["system_vault"]["total_revenue"] += price_converted
        user["status"] = pkg["status"]
        user["health_score"] = min(100.0, user["health_score"] + 15.0)
        if req.package_type == "red_zone_vip":
            user["health_score"] = 100.0
            user["status"] = "IMMORTAL"

        if "packages" not in user:
            user["packages"] = []
        user["packages"].append({"type": req.package_type, "purchased_at": datetime.now().isoformat()})
        track_user_activity(username, "purchase", {"package": req.package_type, "cost": price_converted})
        if "total_spent" in db_state["user_activity"][username]:
            db_state["user_activity"][username]["total_spent"] += price_converted
            db_state["user_activity"][username]["packages_bought"] += 1

        package_messages = {
            "1_week": "🔄 1-haftalik paket faollashtirildi.",
            "1_month": "👑 1 oylik davo boshlanmoqda.",
            "3_month": "🏆 3 oylik premium davo!",
            "6_month": "⭐ 6 oylik paket + Analyst bonus!",
            "1_year": "👑 1 yillik ustun davo!",
            "3_year": "💎 3 yillik mukammal davo!",
            "6_year": "♾️ 6 yillik abadiy davo.",
            "10_year": "🌌 10 yillik o'lmaslik matritsasi.",
            "red_zone_vip": "☣️ QIZIL ZONA VIP!",
            "gadget": "📦 Gadget xarid qilindi.",
            "meds": "📦 Kvant dorilar xarid qilindi."
        }
        msg = package_messages.get(req.package_type, f"📦 Paket xarid qilindi.")
        post = generate_feed_post(username, user["department"], msg)
        add_to_feed(post)
        await save_state()
        return {"success": True, "message": msg, "new_balance": user["balance"], "status": user["status"], "health_score": user["health_score"]}

# ==========================================
# 9. AI CHAT
# ==========================================
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
            {"role": "system", "content": "Siz BioEmpire tizimining AI yordamchisisiz. Sog'liq, davolanish haqida ma'lumot berasiz. Professional, ammo biroz dahshatli ohangda gapiring."},
            {"role": "system", "content": f"Foydalanuvchi: {req.username}. Holati: {user['status']}. Salomatlik: {user['health_score']}%. Balans: {user['balance']} {currency}."},
        ]
        messages.extend(history[-10:])
        ai_response = await call_ai_api(messages)
        if not ai_response:
            ai_response = f"🧬 [AI ANALYST]: {user['status']} holatidasiz. Sizga {random.choice(['1 oylik paket', 'Qizil zona tekshiruvi'])} tavsiya etiladi."

        history.append({"role": "assistant", "content": ai_response})
        ai_chat_history[req.username] = history
        await save_state()
        return {"success": True, "response": ai_response, "new_balance": user["balance"], "deducted": chat_price}

# ==========================================
# 10. KAMERA AI ANALIZI
# ==========================================
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

        messages = [
            {"role": "system", "content": "Siz BioEmpire tizimining AI analistisisiz. Kamera orqali olingan ma'lumotlarni tahlil qiling va qisqa tavsiya bering."},
            {"role": "user", "content": f"Bo'lim: {dept_name}. Foydalanuvchi holati: {user['status']}."}
        ]
        ai_analysis = await call_ai_api(messages)
        if not ai_analysis:
            ai_analysis = f"🔬 [KAMERA AI]: {dept_name} da {random.randint(70,95)}% patologik o'zgarish."

        await save_state()
        return {"success": True, "analysis": ai_analysis, "new_balance": user["balance"], "deducted": analysis_price}

# ==========================================
# 11. ODDIY CHAT (fallback)
# ==========================================
@app.post("/api/v2/chat")
async def chat_with_ai(req: ChatRequest):
    async with db_lock:
        if req.username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        user = db_state["users"][req.username]
        currency = user["currency"]
        rate = EXCHANGE_RATES[currency]

        chat_price = CHAT_PRICE_USD * rate
        if user["balance"] < chat_price:
            return {"success": False, "message": f"⚠️ Chat uchun ${chat_price:.2f} kerak."}

        user["balance"] -= chat_price
        db_state["system_vault"]["total_revenue"] += chat_price
        track_user_activity(req.username, "chat", {"message": req.message[:50]})

        responses = [
            f"🧬 [AI ANALYST]: Neyron sinapslar {random.randint(60,90)}% anormallik bor.",
            f"⚡ [DIAGNOSTIKA]: Virusli infektsiyaga o'xshaydi!",
            f"☣️ [XAVF]: Atrofingizdagi odamlarning 78% toksik!",
            f"💊 [RETSEPT]: NeuroRegen X1 tavsiya qilaman.",
            f"📊 [PROGNOZ]: 30 kun ichida 45% yomonlashadi."
        ]
        ai_response = random.choice(responses)
        await save_state()
        return {"success": True, "response": ai_response, "new_balance": user["balance"], "deducted": chat_price}

# ==========================================
# 12. E-COMMERCE
# ==========================================
@app.get("/api/v2/ecommerce/products")
async def get_products():
    return ECOMMERCE["products"]

@app.post("/api/v2/ecommerce/order")
async def place_order(req: ProductOrderRequest):
    username = req.username
    async with db_lock:
        if username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        user = db_state["users"][username]
        currency = user["currency"]
        rate = EXCHANGE_RATES[currency]

        product = None
        for p in ECOMMERCE["products"]:
            if p["id"] == req.product_id:
                product = p
                break
        if not product:
            raise HTTPException(status_code=400, detail="Mahsulot topilmadi.")

        total_price = product["price_usd"] * rate * req.quantity
        if user["balance"] < total_price:
            return {"success": False, "message": f"⚠️ ${total_price:.2f} kerak."}

        user["balance"] -= total_price
        db_state["system_vault"]["total_revenue"] += total_price

        order = {
            "id": generate_post_id(),
            "username": username,
            "product_id": req.product_id,
            "product_name": product["name"],
            "quantity": req.quantity,
            "total_price": total_price,
            "currency": currency,
            "ordered_at": datetime.now().isoformat(),
            "status": "pending"
        }
        db_state["product_sales"].append(order)
        track_user_activity(username, "product_order", {"product": product["name"], "total": total_price})
        await save_state()
        return {"success": True, "order": order, "new_balance": user["balance"], "message": f"✅ {product['name']} xarid qilindi!"}

@app.post("/api/v2/ecommerce/recommendations")
async def get_ai_product_recommendations(req: AIRecommendationRequest):
    async with db_lock:
        if req.username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        user = db_state["users"][req.username]
        messages = [
            {"role": "system", "content": "Siz BioEmpire tizimining AI marketing mutaxassisisiz. Foydalanuvchi holatiga qarab 3 ta mahsulot tavsiya qiling."},
            {"role": "user", "content": f"Foydalanuvchi: {req.username}. Holati: {user['status']}. Salomatlik: {user['health_score']}%. Balans: {user['balance']} {user['currency']}."}
        ]
        ai_response = await call_ai_api(messages)
        if not ai_response:
            ai_response = "Sizga NeuroRegen X1, ImmunoBoost Pro va CardioSync Elite tavsiya qilamiz."
        return {"recommendations": ai_response}

# ==========================================
# 13. TURNIRLAR
# ==========================================
@app.get("/api/v2/tournaments")
async def get_tournaments():
    async with db_lock:
        return db_state["tournaments"]

@app.post("/api/v2/tournaments/create")
async def create_tournament(request: Request):
    async with db_lock:
        data = await request.json()
        tournament = {
            "id": f"tournament_{random.randint(1000, 9999)}",
            "name": data.get("name", "Bio Turnir"),
            "description": data.get("description", "Sog'lik musobaqasi"),
            "start_date": data.get("start_date", datetime.now().isoformat()),
            "end_date": data.get("end_date", (datetime.now() + timedelta(days=7)).isoformat()),
            "status": "active",
            "participants": [],
            "scores": {}
        }
        db_state["tournaments"].append(tournament)
        await save_state()
        return tournament

@app.post("/api/v2/tournaments/join")
async def join_tournament(req: TournamentJoin):
    async with db_lock:
        if req.username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        for t in db_state["tournaments"]:
            if t["id"] == req.tournament_id:
                if req.username not in t["participants"]:
                    t["participants"].append(req.username)
                    t["scores"][req.username] = 0
                    await save_state()
                    return {"success": True, "message": f"{req.username} qo'shildi!"}
                return {"success": False, "message": "Siz allaqachon bu turnirdasiz."}
        raise HTTPException(status_code=404, detail="Turnir topilmadi.")

@app.post("/api/v2/tournaments/score")
async def update_tournament_score(req: TournamentScore):
    async with db_lock:
        if req.username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        for t in db_state["tournaments"]:
            if t["id"] == req.tournament_id:
                if req.username not in t["participants"]:
                    return {"success": False, "message": "Siz bu turnirda emassiz."}
                t["scores"][req.username] += req.score
                await save_state()
                await manager.broadcast({"type": "tournament_update", "tournament_id": req.tournament_id, "scores": t["scores"]})
                return {"success": True, "new_score": t["scores"][req.username]}
        raise HTTPException(status_code=404, detail="Turnir topilmadi.")

@app.get("/api/v2/tournaments/{tournament_id}/leaderboard")
async def get_tournament_leaderboard(tournament_id: str):
    async with db_lock:
        for t in db_state["tournaments"]:
            if t["id"] == tournament_id:
                sorted_scores = sorted(t["scores"].items(), key=lambda x: x[1], reverse=True)
                return {"tournament": t["name"], "leaderboard": sorted_scores}
        raise HTTPException(status_code=404, detail="Turnir topilmadi.")

@app.get("/api/v2/tournaments/{tournament_id}/predict")
async def predict_tournament_winner(tournament_id: str):
    async with db_lock:
        for t in db_state["tournaments"]:
            if t["id"] == tournament_id:
                if not t["scores"]:
                    return {"prediction": "Hozircha ma'lumot yetarli emas."}
                messages = [
                    {"role": "system", "content": "Siz BioEmpire tizimining AI prognoz mutaxassisisiz. Turnir natijalarini tahlil qiling va g'olibni bashorat qiling."},
                    {"role": "user", "content": f"Turnir: {t['name']}. Natijalar: {json.dumps(t['scores'])}. Kim g'olib bo'lishi mumkin?"}
                ]
                ai_response = await call_ai_api(messages)
                if not ai_response:
                    sorted_scores = sorted(t["scores"].items(), key=lambda x: x[1], reverse=True)
                    if sorted_scores:
                        ai_response = f"🏆 G'olib: {sorted_scores[0][0]} ({sorted_scores[0][1]} ball)"
                    else:
                        ai_response = "Hozircha g'olib aniqlanmadi."
                return {"prediction": ai_response}
        raise HTTPException(status_code=404, detail="Turnir topilmadi.")

# ==========================================
# 14. KRIPTO, EMAIL, VIRTUAL DOCTOR
# ==========================================
@app.post("/api/v2/crypto/connect")
async def connect_crypto_wallet(req: CryptoConnect):
    async with db_lock:
        if req.username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        db_state["crypto_wallets"][req.username] = req.wallet_address
        await save_state()
        return {"success": True, "message": f"Kripto hamyon ulandi: {req.wallet_address[:10]}..."}

@app.post("/api/v2/crypto/pay")
async def crypto_pay(req: CryptoPay):
    async with db_lock:
        if req.username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        user = db_state["users"][req.username]
        wallet = db_state["crypto_wallets"].get(req.username)
        if not wallet:
            return {"success": False, "message": "Kripto hamyon ulanishi kerak."}

        amount_usd = req.amount
        rate = EXCHANGE_RATES.get(req.currency, 1.0)
        amount_converted = amount_usd * rate

        if user["balance"] < amount_converted:
            return {"success": False, "message": "Balans yetarli emas!"}

        user["balance"] -= amount_converted
        db_state["system_vault"]["total_revenue"] += amount_converted
        track_user_activity(req.username, "crypto_pay", {"amount": amount_usd, "currency": req.currency})
        await save_state()
        return {"success": True, "message": f"✅ {amount_usd} USD to'lov amalga oshirildi.", "new_balance": user["balance"]}

@app.post("/api/v2/email/report")
async def send_email_report(req: EmailReport):
    async with db_lock:
        if req.username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        print(f"📧 EMAIL REPORT to {req.email}")
        track_user_activity(req.username, "email_report", {"email": req.email})
        await save_state()
        return {"success": True, "message": f"✅ Hisobot {req.email} manziliga yuborildi."}

@app.post("/api/v2/virtual-doctor")
async def virtual_doctor(req: VirtualDoctorRequest):
    async with db_lock:
        if req.username not in db_state["users"]:
            raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")
        user = db_state["users"][req.username]
        currency = user["currency"]
        rate = EXCHANGE_RATES[currency]

        consultation_price = 200.0 * rate
        if user["balance"] < consultation_price:
            return {"success": False, "message": f"⚠️ Balans yetarli emas! ${consultation_price:.2f} kerak."}

        user["balance"] -= consultation_price
        db_state["system_vault"]["total_revenue"] += consultation_price
        track_user_activity(req.username, "virtual_doctor", {"symptoms": req.symptoms[:50]})

        messages = [
            {"role": "system", "content": "Siz BioEmpire tizimining virtual shifokorisiz. Simptomlarni tahlil qiling va tashxis hamda retsept bering."},
            {"role": "user", "content": f"Simptomlar: {req.symptoms}. Foydalanuvchi holati: {user['status']}, salomatlik: {user['health_score']}%."}
        ]
        ai_response = await call_ai_api(messages)
        if not ai_response:
            diseases = ["Virusli infeksiya", "Bakterial infeksiya", "Neyron disfunksiya", "Immun tizim zaifligi"]
            treatments = ["1 haftalik davo", "1 oylik paket", "Qizil zona tekshiruvi"]
            medicines = ["NeuroRegen X1", "ImmunoBoost Pro", "CardioSync Elite"]
            diagnosis = f"🩺 [VIRTUAL DOCTOR]: {random.choice(diseases)} aniqlangan. Sizga {random.choice(treatments)} tavsiya etiladi."
            prescription = f"💊 Retsept: {random.choice(medicines)} - kuniga 2 marta."
        else:
            parts = ai_response.split('\n')
            diagnosis = parts[0] if parts else "Tashxis qo'yildi."
            prescription = parts[1] if len(parts) > 1 else "Retsept yozildi."

        await save_state()
        return {"success": True, "diagnosis": diagnosis, "prescription": prescription, "new_balance": user["balance"]}

# ==========================================
# 15. ADMIN, STATS, NOTIFICATIONS, AI LOGS
# ==========================================
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

@app.get("/api/v2/admin/users")
async def get_all_users():
    async with db_lock:
        users = []
        for username, user in db_state["users"].items():
            users.append({
                "username": username,
                "email": user["email"],
                "balance": user["balance"],
                "status": user["status"],
                "health_score": user["health_score"],
                "packages": len(user.get("packages", [])),
                "registered_at": user.get("registered_at", "Noma'lum")
            })
        return users

@app.get("/api/v2/admin/activity/{username}")
async def get_user_activity(username: str):
    async with db_lock:
        if username not in db_state["user_activity"]:
            return {"actions": []}
        return db_state["user_activity"][username]

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

@app.get("/api/v2/ai/logs")
async def get_ai_logs(limit: int = 50):
    async with db_lock:
        return db_state["ai_logs"][-limit:]

@app.get("/api/v2/ai/decisions")
async def get_ai_decisions(limit: int = 20):
    async with db_lock:
        return db_state["ai_decisions"][-limit:]

@app.get("/api/v2/ai/insights")
async def get_ai_insights(limit: int = 20):
    async with db_lock:
        return db_state["ai_insights"][-limit:]

@app.get("/api/v2/ai/ads-performance")
async def get_ads_performance():
    async with db_lock:
        return db_state["ads_performance"]

# ==========================================
# 16. WEBSOCKET
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
# 17. ROOT – Frontend
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1 style='color: red;'>templates/index.html topilmadi!</h1>", status_code=404)

# ==========================================
# 18. STARTUP – Barcha AI tasklarni ishga tushirish
# ==========================================
@app.on_event("startup")
async def startup_event():
    # 4 ta avtonom AI task
    asyncio.create_task(ai_self_learning_task())
    asyncio.create_task(ai_autonomous_marketing_task())
    asyncio.create_task(ai_ads_optimizer_task())
    asyncio.create_task(ai_decision_maker_task())

    # Eski post generator
    async def old_poster():
        while True:
            await asyncio.sleep(45)
            async with db_lock:
                if not db_state["users"]:
                    continue
                username = random.choice(list(db_state["users"].keys()))
                texts = [
                    f"🧬 {username} davolanishimdan so'ng o'zimni butunlay yangi odamdek his qilyapman!",
                    f"⚡ {username} BioEmpire tizimida davolanishdan oldin har kuni og'riq bilan uyg'onardim.",
                    f"🧫 {username} 3 oylik davolanishdan so'ng, shifokorlar hayratda!",
                    f"🛡 {username} endi hech qanday kasallikdan qo'rqmayman.",
                    f"🌟 {username} atrofimdagi odamlar o'zgarishimni payqab qolishdi.",
                    f"🧠 {username} neyro-sinapslarim optimallashtirilganidan so'ng, ishlash samaradorligim 3 barobar oshdi."
                ]
                post_text = random.choice(texts)
                post = generate_social_post(username, post_text, is_ai=False)
                post["likes"] = random.randint(10, 80)
                add_social_post(post)
                notif = generate_notification(username, f"Yangi post: {post_text[:50]}...", "social")
                add_notification(notif)
                await save_state()
                await manager.broadcast({"type": "new_post", "post": post})
    asyncio.create_task(old_poster())

    ai_log("🚀 BioEmpire V9 AI ADS tizimi ishga tushirildi", "INFO")
    ai_log("🧠 AI Self-Learning, Marketing, ADS Optimizer, Decision-Maker faol", "INFO")
    ai_log("📢 AI mustaqil ravishda reklama kampaniyalarini yaratadi va optimallashtiradi", "INFO")

# ==========================================
# SERVER
# ==========================================
if __name__ == "__main__":
    print("=" * 70)
    print("🚀 BIOEMPIRE V9 TO'LIQ AI ADS + MARKETING TIZIMI STARTING ON PORT 5050")
    print("🧠 AI MUSTAQIL REKLAMA KAMPANIYALARI YARATADI")
    print("📢 A/B TESTLAR O'TKAZADI VA ENG YAXSHILARINI KUCHAYTIRADI")
    print("📈 CHEKSIZ AI AVTONOMIYASI")
    print("=" * 70)

    uvicorn.run("main:app", host="127.0.0.1", port=5050, reload=True)
