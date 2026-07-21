import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# Ma'lumotlar bazasi fayli
DB_FILE = "database_log.json"

DEFAULT_STATE = {
    "products": [
        {"id": "p1", "name": "Minimalist T-Shirt", "price": 29.99, "stock": 50, "sales": 12},
        {"id": "p2", "name": "Oversized Hoodie", "price": 59.99, "stock": 30, "sales": 8}
    ],
    "ai_decisions": [],
    "logs": []
}

def load_state() -> Dict[str, Any]:
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_STATE, f, indent=4)
        return DEFAULT_STATE
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_STATE

async def save_state():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db_state, f, indent=4)

db_state = load_state()

# FastAPI ilovasini yaratish
app = FastAPI(title="AlterEgo Core Engine")

# CORS sozlamalari (Frontend ulanishi uchun)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bosh sahifaga kirganda index.html faylini ko'rsatish
@app.get("/", response_class=HTMLResponse)
async def get_index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>❌ Backend muvaffaqiyatli ishlayapti, lekin index.html fayli serverda topilmadi!</h1>"

@app.get("/api/products")
async def get_products():
    return db_state["products"]

# WebSocket ulanish nuqtasi
@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        # Ulanish amalga oshganda boshlang'ich ma'lumotni yuborish
        await websocket.send_json({"event": "INITIAL_STATE", "data": {"products": db_state["products"]}})
        while True:
            # Ulanishni ochiq ushlab turish uchun xabarlarni kutish
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    import uvicorn
    # Render muhiti uchun dinamik port sozlamasi
    port = int(os.getenv("PORT", 1111))
    uvicorn.run("main:app", host="0.0.0.0", port=port)