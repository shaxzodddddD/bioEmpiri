import os
import json
import random
import asyncio
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
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

# ---------- PAPKALAR VA TEMPLATES ----------
# Agar templates papkasi mavjud bo'lmasa, yaratamiz
if not os.path.exists("templates"):
    os.makedirs("templates", exist_ok=True)

# Agar index.html mavjud bo'lmasa, avtomatik yaratamiz
INDEX_HTML_PATH = "templates/index.html"
if not os.path.exists(INDEX_HTML_PATH):
    with open(INDEX_HTML_PATH, "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧬 BioEmpire V13</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#E8F5E9;font-family:'Segoe UI',system-ui,sans-serif;margin:0;}
        .glass{background:rgba(255,255,255,0.85);backdrop-filter:blur(8px);border:1px solid rgba(102,187,106,0.3);border-radius:20px;box-shadow:0 8px 32px rgba(0,40,0,0.08);padding:20px;}
        .btn{display:inline-block;padding:8px 20px;border:none;border-radius:12px;font-weight:700;cursor:pointer;transition:0.25s;font-size:14px;}
        .btn-primary{background:linear-gradient(135deg,#66BB6A,#43A047);color:#fff;box-shadow:0 4px 16px rgba(102,187,106,0.25);}
        .btn-gold{background:linear-gradient(135deg,#FFB300,#F9A825);color:#1B3A1B;box-shadow:0 4px 16px rgba(255,179,0,0.25);}
        .btn-red{background:linear-gradient(135deg,#E53935,#C62828);color:#fff;}
        .btn-sm{padding:6px 16px;font-size:12px;border-radius:10px;}
        .btn-xs{padding:4px 12px;font-size:11px;border-radius:8px;}
        #auth-modal{position:fixed;inset:0;background:rgba(0,0,0,0.5);backdrop-filter:blur(8px);display:none;align-items:center;justify-content:center;z-index:99999;}
        #auth-modal.show{display:flex;}
        .auth-card{background:#fff;border-radius:28px;padding:36px 32px;width:100%;max-width:420px;box-shadow:0 20px 60px rgba(0,0,0,0.2);max-height:90vh;overflow-y:auto;}
        .auth-card h2{text-align:center;font-size:22px;font-weight:800;color:#1B3A1B;}
        .auth-card .close-modal{float:right;font-size:28px;cursor:pointer;background:none;border:none;color:#4A6A4A;}
        .auth-card .close-modal:hover{color:#E53935;}
        .auth-tabs{display:flex;gap:8px;justify-content:center;margin:16px 0 20px;}
        .auth-tab{padding:6px 24px;border-radius:30px;cursor:pointer;border:2px solid transparent;font-weight:700;color:#4A6A4A;background:none;font-size:14px;}
        .auth-tab.active{border-color:#66BB6A;color:#43A047;background:rgba(102,187,106,0.08);}
        .input-group{margin-bottom:14px;}
        .input-group label{display:block;font-size:12px;font-weight:700;color:#43A047;margin-bottom:4px;}
        .input-group input,.input-group select{width:100%;background:#f5faf5;border:1.5px solid rgba(102,187,106,0.3);padding:10px 14px;color:#1B3A1B;border-radius:12px;outline:none;font-size:14px;}
        .input-group input:focus,.input-group select:focus{border-color:#66BB6A;box-shadow:0 0 0 4px rgba(102,187,106,0.1);}
        .auth-error{color:#E53935;font-size:12px;margin-top:8px;text-align:center;}
        header{background:rgba(255,255,255,0.95);backdrop-filter:blur(12px);border-bottom:1px solid rgba(102,187,106,0.3);padding:10px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:1000;flex-wrap:wrap;gap:10px;}
        .logo{font-size:24px;font-weight:900;color:#43A047;display:flex;align-items:center;gap:8px;cursor:pointer;}
        .logo span{font-size:28px;}
        .auth-section{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}
        .auth-section .auth-buttons{display:flex;gap:8px;}
        .auth-section .user-info{display:flex;align-items:center;gap:10px;}
        .user-avatar{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#66BB6A,#43A047);display:flex;align-items:center;justify-content:center;font-size:18px;border:2px solid #FFB300;flex-shrink:0;}
        .user-name{font-weight:600;font-size:14px;color:#1B3A1B;}
        .user-balance{font-size:13px;color:#43A047;font-weight:700;}
        .sidebar{width:240px;flex-shrink:0;background:rgba(255,255,255,0.92);backdrop-filter:blur(12px);border-right:1px solid rgba(102,187,106,0.3);height:calc(100vh - 72px);overflow-y:auto;padding:16px 12px;position:sticky;top:72px;}
        .sidebar-btn{display:flex;align-items:center;gap:12px;width:100%;padding:10px 14px;background:transparent;border:1px solid transparent;border-radius:14px;color:#4A6A4A;cursor:pointer;transition:0.2s;font-size:14px;font-weight:500;margin-bottom:2px;}
        .sidebar-btn:hover{background:rgba(102,187,106,0.06);border-color:rgba(102,187,106,0.3);color:#1B3A1B;}
        .sidebar-btn.active{background:rgba(102,187,106,0.1);border-color:#66BB6A;color:#43A047;font-weight:600;}
        .sidebar-btn .icon{font-size:20px;width:28px;text-align:center;}
        .sidebar-btn .badge{margin-left:auto;background:#E53935;color:#fff;font-size:10px;padding:0 8px;border-radius:30px;font-weight:700;}
        .panel{display:none;animation:fadeSlide 0.3s ease;}
        .panel.active{display:block;}
        @keyframes fadeSlide{0%{opacity:0;transform:translateY(10px);}100%{opacity:1;transform:translateY(0);}}
        .chat-terminal{height:200px;background:#f9fbf9;border:1px solid rgba(102,187,106,0.3);border-radius:14px;padding:12px 16px;overflow-y:auto;font-size:14px;}
        .chat-msg{margin-bottom:8px;padding:6px 14px;border-radius:12px;max-width:90%;}
        .chat-msg.ai{background:rgba(102,187,106,0.08);border-left:3px solid #66BB6A;}
        .chat-msg.user{background:rgba(255,179,0,0.08);border-right:3px solid #FFB300;text-align:right;margin-left:auto;}
        .chat-msg.warning{background:rgba(229,57,53,0.08);border-left:3px solid #E53935;color:#B71C1C;}
        .feed-item{background:rgba(255,255,255,0.6);border:1px solid rgba(102,187,106,0.3);padding:12px 16px;border-radius:14px;margin-bottom:10px;border-left:4px solid #66BB6A;}
        .feed-item .user{color:#43A047;font-weight:700;}
        .feed-item .time{color:#4A6A4A;font-size:11px;float:right;}
        .feed-item .actions{margin-top:8px;display:flex;gap:16px;font-size:13px;color:#4A6A4A;cursor:pointer;}
        .feed-item .actions span:hover{color:#43A047;}
        .package-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px;margin-top:14px;}
        .package-card{background:#fff;border:1px solid rgba(255,179,0,0.15);border-radius:14px;padding:14px 8px;text-align:center;cursor:pointer;transition:0.25s;}
        .package-card:hover{border-color:#FFB300;transform:translateY(-4px);box-shadow:0 8px 24px rgba(255,179,0,0.08);}
        .package-card .pkg-name{font-size:12px;font-weight:700;color:#1B3A1B;}
        .package-card .pkg-price{color:#FFB300;font-size:15px;font-weight:800;}
        .ranking-item{display:flex;align-items:center;gap:12px;padding:6px 12px;border-bottom:1px solid rgba(0,0,0,0.05);font-size:14px;}
        .ranking-item .pos{color:#FFB300;font-weight:700;width:30px;}
        .ranking-item .name{flex:1;}
        .ranking-item .score{color:#43A047;font-weight:700;}
        .notif-bell{position:relative;cursor:pointer;font-size:22px;}
        .notif-badge{position:absolute;top:-6px;right:-8px;background:#E53935;color:#fff;border-radius:50%;padding:0 6px;font-size:10px;font-weight:800;min-width:18px;text-align:center;animation:pulse-badge 1.8s infinite;}
        @keyframes pulse-badge{0%,100%{transform:scale(1);}50%{transform:scale(1.15);}}
        .notif-dropdown{position:absolute;right:0;top:34px;width:300px;max-height:320px;overflow-y:auto;background:#fff;border:1px solid rgba(102,187,106,0.3);border-radius:16px;padding:14px;display:none;z-index:200;box-shadow:0 20px 60px rgba(0,0,0,0.06);}
        .notif-dropdown.show{display:block;}
        .notif-item{padding:8px 10px;border-bottom:1px solid rgba(0,0,0,0.05);font-size:13px;}
        .notif-item .time{color:#4A6A4A;font-size:11px;float:right;}
        .notif-item.unread{border-left:3px solid #66BB6A;}
        .status-badge{display:inline-block;padding:2px 12px;border-radius:20px;font-size:11px;font-weight:700;}
        .status-warning{background:#FFB300;color:#1B3A1B;}
        .status-red{background:#E53935;color:#fff;}
        .status-optimized{background:#66BB6A;color:#fff;}
        .status-immortal{background:#FFB300;color:#1B3A1B;}
        .avatar-lg{width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,#C8E6C9,#66BB6A);display:flex;align-items:center;justify-content:center;font-size:28px;border:2px solid #FFB300;flex-shrink:0;}
        .lock-overlay{position:absolute;inset:0;background:rgba(255,255,255,0.6);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;border-radius:20px;z-index:10;flex-direction:column;gap:12px;min-height:200px;}
        .lock-overlay .lock-icon{font-size:48px;}
        .lock-overlay p{color:#4A6A4A;font-weight:600;}
        .panel-wrapper{position:relative;min-height:200px;}
        #camera-preview{width:100%;max-height:240px;border-radius:16px;background:#000;object-fit:cover;border:2px solid rgba(102,187,106,0.3);}
        .voice-indicator{display:inline-block;width:12px;height:12px;border-radius:50%;background:#66BB6A;margin-right:6px;animation:pulse-dot 1s infinite;}
        @keyframes pulse-dot{0%,100%{opacity:0.4;transform:scale(0.9);}50%{opacity:1;transform:scale(1.2);}}
        .admin-stat{background:#fff;border:1px solid rgba(102,187,106,0.3);border-radius:16px;padding:16px;text-align:center;}
        .admin-stat .value{font-size:28px;font-weight:900;color:#43A047;}
        .admin-stat .label{font-size:12px;color:#4A6A4A;font-weight:600;}
        ::-webkit-scrollbar{width:5px;}
        ::-webkit-scrollbar-track{background:#E8F5E9;}
        ::-webkit-scrollbar-thumb{background:#66BB6A;border-radius:20px;}
        @media(max-width:1024px){.sidebar{width:70px !important;padding:10px 6px;}.sidebar .btn-text{display:none;}.sidebar .icon{font-size:24px;width:100%;text-align:center;}.sidebar .badge{display:none;}}
        @media(max-width:768px){.sidebar{display:none;}header{padding:8px 16px;flex-direction:column;align-items:stretch;gap:6px;}.logo{font-size:20px;justify-content:center;}.auth-section{justify-content:center;flex-wrap:wrap;}.auth-card{margin:16px;padding:24px 20px;}}
    </style>
</head>
<body>
    <div id="auth-modal">
        <div class="auth-card">
            <button class="close-modal" onclick="closeAuthModal()">✕</button>
            <div class="text-center mb-2"><span class="text-4xl">🧬</span></div>
            <h2 id="auth-modal-title">🔐 TIZIMGA ULANISH</h2>
            <div class="auth-tabs">
                <button id="tab-signup" class="auth-tab active" onclick="switchAuth('signup')">Ro'yxatdan o'tish</button>
                <button id="tab-signin" class="auth-tab" onclick="switchAuth('signin')">Kirish</button>
            </div>
            <div id="email-group" class="input-group"><label>📧 E-mail</label><input type="email" id="auth-email" placeholder="your@email.com" /></div>
            <div class="input-group"><label>👤 Username</label><input type="text" id="auth-user" placeholder="Bio_User" /></div>
            <div class="input-group"><label>🔑 Parol</label><input type="password" id="auth-pass" placeholder="••••••••" /></div>
            <div id="currency-group" class="input-group"><label>💱 Valyuta</label><select id="auth-curr"><option value="USD">USD</option><option value="EUR">EUR</option><option value="BTC">BTC</option><option value="SOL">SOL</option></select></div>
            <button class="btn btn-primary" style="width:100%;" onclick="executeAuth()">🚀 TIZIMNI FAOLASHTIRISH</button>
            <p id="auth-error" class="auth-error"></p>
            <div class="text-center mt-3 text-xs text-gray-500">Admin: CEO / parol: 12345678</div>
        </div>
    </div>
    <div id="main-app" style="display:none;">
        <header>
            <div class="logo" onclick="location.reload()"><span>🧬</span> BioEmpire ∞</div>
            <div class="auth-section" id="header-auth-section">
                <div id="auth-buttons" class="auth-buttons">
                    <button class="btn btn-primary btn-sm" onclick="openAuthModal('signin')">🔑 Kirish</button>
                    <button class="btn btn-gold btn-sm" onclick="openAuthModal('signup')">📝 Ro'yxatdan o'tish</button>
                </div>
                <div id="user-info" class="user-info" style="display:none;">
                    <div class="notif-bell" onclick="toggleNotifications()">
                        🔔<span class="notif-badge" id="notif-count">0</span>
                        <div class="notif-dropdown" id="notif-dropdown"><div class="font-bold text-[#43A047] text-xs mb-2">📬 Bildirishnomalar</div><div id="notif-list"></div></div>
                    </div>
                    <div class="user-avatar" id="header-avatar">🧬</div>
                    <span class="user-name" id="header-username">-</span>
                    <span class="user-balance" id="header-balance">$0</span>
                    <button class="btn btn-red btn-xs" onclick="logout()">Chiqish</button>
                </div>
            </div>
        </header>
        <div class="flex">
            <aside class="sidebar" id="main-sidebar">
                <div class="flex items-center gap-3 p-3 rounded-xl bg-[#F1F8E9] border border-[#66BB6A33] mb-4">
                    <div class="avatar-lg" id="sidebar-avatar">🧬</div>
                    <div class="flex-1 min-w-0"><div class="font-bold text-sm text-[#1B3A1B] truncate" id="sidebar-username">-</div><div class="text-xs text-gray-500" id="sidebar-status">WARNING</div></div>
                    <div class="text-right"><div class="text-[10px] text-gray-400">Balans</div><div class="text-sm font-bold text-[#43A047]" id="sidebar-balance">0.00</div></div>
                </div>
                <button class="sidebar-btn active" data-panel="panel-consult" onclick="switchPanel('panel-consult', this)"><span class="icon">🩺</span><span class="btn-text">Konsultatsiya</span></button>
                <button class="sidebar-btn" data-panel="panel-social" onclick="switchPanel('panel-social', this)"><span class="icon">📡</span><span class="btn-text">Ijtimoiy</span><span class="badge" id="feed-badge">0</span></button>
                <button class="sidebar-btn" data-panel="panel-profile" onclick="switchPanel('panel-profile', this)"><span class="icon">👤</span><span class="btn-text">Profil</span></button>
                <button class="sidebar-btn" data-panel="panel-packages" onclick="switchPanel('panel-packages', this)"><span class="icon">📦</span><span class="btn-text">Paketlar</span></button>
                <button class="sidebar-btn" data-panel="panel-stats" onclick="switchPanel('panel-stats', this)"><span class="icon">📊</span><span class="btn-text">Statistika</span></button>
                <button class="sidebar-btn" data-panel="panel-ads" onclick="switchPanel('panel-ads', this)"><span class="icon">📈</span><span class="btn-text">AI ADS</span></button>
                <button class="sidebar-btn" data-panel="panel-admin" onclick="switchPanel('panel-admin', this)"><span class="icon">⚙️</span><span class="btn-text">Admin</span></button>
            </aside>
            <main class="flex-1 min-w-0 p-4 max-w-full">
                <div id="panel-consult" class="panel active">
                    <div class="glass panel-wrapper">
                        <div id="consult-lock" class="lock-overlay" style="display:none;"><div class="lock-icon">🔒</div><p>Iltimos, avval tizimga kiring</p><button class="btn btn-primary btn-sm" onclick="openAuthModal('signin')">Kirish</button></div>
                        <div id="consult-content">
                            <h2 class="text-xl font-bold text-[#43A047] mb-3">🩺 AI KONSULTATSIYA</h2>
                            <div class="mb-4"><div class="flex gap-2 flex-wrap"><button class="btn btn-primary btn-sm" onclick="startCamera()">📷 Kamerani yoqish</button><button class="btn btn-gold btn-sm" onclick="captureAndAnalyze()">🔬 Suratga olib tahlil</button><button class="btn btn-red btn-sm" onclick="stopCamera()">⏹ To'xtatish</button></div><video id="camera-preview" autoplay playsinline style="display:none;"></video><div id="camera-placeholder" class="bg-gray-100 rounded-xl p-4 text-center text-gray-400 text-sm border border-dashed border-[#66BB6A33]">Kamera o'chirilgan</div><div id="camera-result" class="mt-2 text-sm text-[#43A047]"></div></div>
                            <div class="mb-4"><button class="btn btn-primary btn-sm" onclick="startVoice()">🎤 Ovoz bilan gapirish</button><button class="btn btn-red btn-sm" onclick="stopVoice()">⏹ To'xtatish</button><span id="voice-status" class="text-sm text-gray-500"></span><div id="voice-transcript" class="mt-2 p-3 bg-gray-50 rounded-xl text-sm text-gray-700 min-h-[48px] border border-[#66BB6A33]">Ovoz matni...</div></div>
                            <div><div class="chat-terminal" id="consult-chat"><div class="chat-msg ai">Salom! Men AI shifokorman. Simptomlaringizni yozing yoki gapiring.</div></div><div class="flex gap-2 mt-3"><input id="consult-input" type="text" placeholder="Xabar yozing..." class="flex-1 bg-white border border-[#66BB6A33] rounded-xl px-4 py-2 text-sm text-[#1B3A1B] outline-none" /><button class="btn btn-primary btn-sm" onclick="sendConsult()">Yuborish</button></div></div>
                        </div>
                    </div>
                </div>
                <div id="panel-social" class="panel">
                    <div class="glass panel-wrapper">
                        <div id="social-lock" class="lock-overlay" style="display:none;"><div class="lock-icon">🔒</div><p>Ijtimoiy tarmoqdan foydalanish uchun tizimga kiring</p><button class="btn btn-primary btn-sm" onclick="openAuthModal('signin')">Kirish</button></div>
                        <div id="social-content"><h2 class="text-xl font-bold text-[#43A047] mb-3">📡 Ijtimoiy tarmoq</h2><div class="flex gap-2 mb-4"><input id="social-input" type="text" placeholder="Holatingiz haqida yozing..." class="flex-1 bg-white border border-[#66BB6A33] rounded-xl px-4 py-2 text-sm text-[#1B3A1B] outline-none" /><button class="btn btn-primary btn-sm" onclick="createSocialPost()">Yozish</button></div><div id="social-feed" class="max-h-[520px] overflow-y-auto"></div></div>
                    </div>
                </div>
                <div id="panel-profile" class="panel">
                    <div class="glass panel-wrapper"><div id="profile-lock" class="lock-overlay" style="display:none;"><div class="lock-icon">🔒</div><p>Profilni ko'rish uchun tizimga kiring</p><button class="btn btn-primary btn-sm" onclick="openAuthModal('signin')">Kirish</button></div><div id="profile-content"><h2 class="text-xl font-bold text-[#43A047] mb-3">👤 Profil</h2><div id="profile-data"></div></div></div>
                </div>
                <div id="panel-packages" class="panel">
                    <div class="glass panel-wrapper"><div id="packages-lock" class="lock-overlay" style="display:none;"><div class="lock-icon">🔒</div><p>Paketlarni ko'rish uchun tizimga kiring</p><button class="btn btn-primary btn-sm" onclick="openAuthModal('signin')">Kirish</button></div><div id="packages-content"><h2 class="text-xl font-bold text-[#FFB300] mb-3">📦 Paketlar</h2><div class="package-grid" id="package-grid"></div></div></div>
                </div>
                <div id="panel-stats" class="panel">
                    <div class="glass panel-wrapper"><div id="stats-lock" class="lock-overlay" style="display:none;"><div class="lock-icon">🔒</div><p>Statistikani ko'rish uchun tizimga kiring</p><button class="btn btn-primary btn-sm" onclick="openAuthModal('signin')">Kirish</button></div><div id="stats-content-full"><h2 class="text-xl font-bold text-[#43A047] mb-3">📊 Statistika</h2><div id="stats-content" class="grid grid-cols-2 md:grid-cols-4 gap-4"></div><div class="mt-4"><h3 class="text-sm font-bold text-[#43A047]">🏅 Salomatlik reytingi</h3><div id="health-ranking" class="max-h-[200px] overflow-y-auto"></div></div></div></div>
                </div>
                <div id="panel-ads" class="panel">
                    <div class="glass panel-wrapper"><div id="ads-lock" class="lock-overlay" style="display:none;"><div class="lock-icon">🔒</div><p>AI ADS ni ko'rish uchun tizimga kiring</p><button class="btn btn-primary btn-sm" onclick="openAuthModal('signin')">Kirish</button></div><div id="ads-content"><h2 class="text-xl font-bold text-[#43A047] mb-3">📈 AI ADS</h2><div id="ads-performance" class="space-y-2 max-h-[500px] overflow-y-auto"></div><button class="btn btn-primary btn-sm mt-3" onclick="loadAdsPerformance()">🔄 Yangilash</button></div></div>
                </div>
                <div id="panel-admin" class="panel">
                    <div class="glass panel-wrapper"><div id="admin-lock" class="lock-overlay" style="display:none;"><div class="lock-icon">🔒</div><p>Admin paneliga kirish uchun tizimga kiring</p><button class="btn btn-primary btn-sm" onclick="openAuthModal('signin')">Kirish</button></div><div id="admin-content-full"><h2 class="text-xl font-bold text-[#FFB300] mb-3">⚙️ Admin</h2><div class="flex gap-2 mb-4"><input id="admin-user" type="text" placeholder="Admin" value="CEO" class="bg-white border border-[#66BB6A33] rounded-xl px-3 py-1 text-sm outline-none" /><input id="admin-pass" type="password" placeholder="Parol" value="12345678" class="bg-white border border-[#66BB6A33] rounded-xl px-3 py-1 text-sm outline-none" /><button class="btn btn-primary btn-sm" onclick="adminLogin()">🔐 Kirish</button></div><div id="admin-content" class="hidden"><div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4" id="admin-stats-grid"></div><div id="admin-data" class="mt-3 max-h-[300px] overflow-y-auto text-sm"></div></div></div></div>
                </div>
            </main>
        </div>
    </div>
    <script>
        let currentUser=null, authMode='signup', tokenBalance=100, notifCount=0, cameraStream=null, cameraActive=false, recognition=null, voiceActive=false, isAuthenticated=false, authToken=null;
        function openAuthModal(m){if(m)switchAuth(m);document.getElementById('auth-modal').classList.add('show');document.body.style.overflow='hidden';}
        function closeAuthModal(){document.getElementById('auth-modal').classList.remove('show');document.body.style.overflow='';}
        function switchAuth(m){authMode=m;document.getElementById('auth-modal-title').innerText=m==='signup'?'🔐 RO\'YXATDAN O\'TISH':'🔐 KIRISH';document.querySelectorAll('.auth-tab').forEach(el=>el.classList.remove('active'));document.getElementById('tab-'+m).classList.add('active');document.getElementById('email-group').style.display=m==='signup'?'block':'none';document.getElementById('currency-group').style.display=m==='signup'?'block':'none';document.getElementById('auth-error').innerText='';}
        async function executeAuth(){const user=document.getElementById('auth-user').value.trim(), pass=document.getElementById('auth-pass').value, email=document.getElementById('auth-email').value.trim(), curr=document.getElementById('auth-curr').value, errEl=document.getElementById('auth-error');errEl.innerText='';if(!user){errEl.innerText="Username kiritilmagan!";return;}if(!pass||pass.length<6){errEl.innerText="Parol kamida 6 belgi!";return;}if(authMode==='signup'&&!email){errEl.innerText="Email kiritilmagan!";return;}const url=authMode==='signup'?'/api/v2/auth/signup':'/api/v2/auth/signin', body=authMode==='signup'?{username:user,password:pass,email:email,currency:curr}:{username:user,password:pass};try{const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await res.json();if(!res.ok){errEl.innerText=data.detail||"Server xatosi.";return;}authToken=data.access_token;isAuthenticated=true;currentUser=user;closeAuthModal();document.getElementById('main-app').style.display='block';document.getElementById('auth-buttons').style.display='none';document.getElementById('user-info').style.display='flex';document.getElementById('header-username').innerText=currentUser;await loadProfile();loadSocialFeed();loadHealthRanking();loadStats();loadAdsPerformance();renderPackages();loadNotifications();setInterval(loadSocialFeed,8000);setInterval(loadHealthRanking,15000);setInterval(loadNotifications,10000);setInterval(loadAdsPerformance,30000);}catch(e){errEl.innerText="Tarmoq xatosi: "+e.message;console.error(e);}}
        function logout(){isAuthenticated=false;currentUser=null;authToken=null;localStorage.removeItem('token');document.getElementById('auth-buttons').style.display='flex';document.getElementById('user-info').style.display='none';document.getElementById('main-app').style.display='none';document.querySelectorAll('.lock-overlay').forEach(el=>el.style.display='flex');if(cameraStream){cameraStream.getTracks().forEach(t=>t.stop());cameraStream=null;}if(recognition){recognition.stop();recognition=null;}cameraActive=false;voiceActive=false;document.getElementById('consult-chat').innerHTML='<div class="chat-msg ai">Salom! Men AI shifokorman. Simptomlaringizni yozing yoki gapiring.</div>';openAuthModal('signin');}
        function switchPanel(pid,btn){document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));document.getElementById(pid).classList.add('active');document.querySelectorAll('.sidebar-btn[data-panel]').forEach(b=>b.classList.remove('active'));if(btn)btn.classList.add('active');if(!isAuthenticated){const panel=document.getElementById(pid);const lock=panel.querySelector('.lock-overlay');if(lock)lock.style.display='flex';}else{const panel=document.getElementById(pid);const lock=panel.querySelector('.lock-overlay');if(lock)lock.style.display='none';}if(isAuthenticated){if(pid==='panel-profile')loadProfile();if(pid==='panel-social')loadSocialFeed();if(pid==='panel-stats'){loadStats();loadHealthRanking();}if(pid==='panel-ads')loadAdsPerformance();if(pid==='panel-packages')renderPackages();}}
        async function loadProfile(){if(!currentUser)return;try{const res=await fetch('/api/v2/profile/'+currentUser,{headers:{'Authorization':'Bearer '+authToken}});const data=await res.json();document.getElementById('sidebar-username').innerText=currentUser;document.getElementById('sidebar-balance').innerText=data.balance.toFixed(2);document.getElementById('sidebar-status').innerText=data.status;document.getElementById('sidebar-avatar').innerText=data.avatar||'🧬';document.getElementById('header-balance').innerText='$'+data.balance.toFixed(2);document.getElementById('header-avatar').innerText=data.avatar||'🧬';const container=document.getElementById('profile-data');const sc=data.status==='WARNING'?'status-warning':data.status==='RED_ZONE'?'status-red':data.status==='OPTIMIZED'?'status-optimized':'status-immortal';container.innerHTML='<div class="grid grid-cols-1 md:grid-cols-2 gap-4"><div class="bg-white/70 p-5 rounded-xl border border-[#66BB6A33]"><div class="flex items-center gap-4"><div class="avatar-lg text-4xl">'+(data.avatar||'🧬')+'</div><div><div class="text-xl font-bold">'+currentUser+'</div><div class="text-sm text-gray-500">'+data.email+'</div></div></div><div class="mt-4 space-y-1 text-sm"><p><span class="text-gray-500">Holat:</span> <span class="status-badge '+sc+'">'+data.status+'</span></p><p><span class="text-gray-500">Balans:</span> <strong class="text-[#43A047]">'+data.balance.toFixed(2)+' '+data.currency+'</strong></p><p><span class="text-gray-500">Salomatlik:</span> <strong class="text-[#43A047]">'+data.health_score.toFixed(1)+'%</strong></p><p><span class="text-gray-500">Bio:</span> '+(data.bio||'Yo\'q')+'</p></div></div><div class="bg-white/70 p-5 rounded-xl border border-[#66BB6A33]"><h3 class="text-sm font-bold text-[#43A047]">📊 Statistika</h3><div class="mt-3 space-y-1 text-sm"><p><span class="text-gray-500">Tokenlar:</span> <strong>'+tokenBalance+'</strong></p></div></div></div>';}catch(e){console.error(e);}}
        async function loadSocialFeed(){if(!currentUser)return;try{const res=await fetch('/api/v2/social/posts');const posts=await res.json();const container=document.getElementById('social-feed');container.innerHTML='';document.getElementById('feed-badge').innerText=posts.length;posts.forEach(p=>{const div=document.createElement('div');div.className='feed-item';div.innerHTML='<div><span class="user">@'+p.username+'</span> <span class="time">'+p.timestamp+'</span></div><div>'+p.content+'</div><div class="actions"><span onclick="likePost(\''+p.id+'\')">❤️ '+(p.likes||0)+'</span><span onclick="commentPost(\''+p.id+'\')">💬 '+(p.comments?p.comments.length:0)+'</span></div>';container.appendChild(div);});}catch(e){}}
        async function createSocialPost(){if(!currentUser)return;const input=document.getElementById('social-input');if(!input.value.trim())return;try{const res=await fetch('/api/v2/social/post',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:currentUser,content:input.value})});if(res.ok){input.value='';loadSocialFeed();}}catch(e){alert('Xatolik: '+e.message);}}
        async function likePost(pid){if(!currentUser)return;try{await fetch('/api/v2/social/like',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:currentUser,post_id:pid})});loadSocialFeed();}catch(e){}}
        async function commentPost(pid){if(!currentUser)return;const comment=prompt('Komment:');if(!comment)return;try{await fetch('/api/v2/social/comment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:currentUser,post_id:pid,comment:comment})});loadSocialFeed();}catch(e){alert(e.message);}}
        async function sendConsult(){if(!currentUser){openAuthModal('signin');return;}const input=document.getElementById('consult-input');const msg=input.value.trim();if(!msg)return;if(tokenBalance<3){alert('Token yetarli emas!');return;}tokenBalance-=3;const box=document.getElementById('consult-chat');box.innerHTML+='<div class="chat-msg user">'+msg+'</div>';input.value='';box.scrollTop=box.scrollHeight;try{const res=await fetch('/api/v2/ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:currentUser,message:msg})});const data=await res.json();if(data.success){box.innerHTML+='<div class="chat-msg ai">'+data.response+'</div>';loadProfile();}else{box.innerHTML+='<div class="chat-msg warning">'+data.message+'</div>';}}catch(e){box.innerHTML+='<div class="chat-msg warning">'+e.message+'</div>';}box.scrollTop=box.scrollHeight;}
        document.addEventListener('keydown',(e)=>{if(e.key==='Enter'){if(document.activeElement?.id==='consult-input')sendConsult();if(document.activeElement?.id==='social-input')createSocialPost();}});
        async function startCamera(){if(!currentUser){openAuthModal('signin');return;}try{const video=document.getElementById('camera-preview');const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}});cameraStream=stream;video.srcObject=stream;video.style.display='block';document.getElementById('camera-placeholder').style.display='none';cameraActive=true;}catch(err){alert('Kamera yoqish xatosi: '+err.message);}}
        function stopCamera(){if(cameraStream){cameraStream.getTracks().forEach(t=>t.stop());cameraStream=null;}document.getElementById('camera-preview').style.display='none';document.getElementById('camera-placeholder').style.display='block';cameraActive=false;}
        async function captureAndAnalyze(){if(!currentUser){openAuthModal('signin');return;}const video=document.getElementById('camera-preview');if(!cameraActive||video.style.display==='none'){alert('Kamerani yoqing!');return;}if(tokenBalance<10){alert('Token yetarli emas! (10 token)');return;}tokenBalance-=10;const canvas=document.createElement('canvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;canvas.getContext('2d').drawImage(video,0,0);const base64=canvas.toDataURL('image/jpeg');const result=document.getElementById('camera-result');result.innerText='⏳ Tahlil...';try{const res=await fetch('/api/v2/camera/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:currentUser,department_id:1,image_data:base64})});const data=await res.json();if(data.success){result.innerText='🔬 '+data.analysis;loadProfile();}else{result.innerText='❌ '+data.message;}}catch(e){result.innerText='❌ '+e.message;}}
        function startVoice(){if(!currentUser){openAuthModal('signin');return;}if(!('webkitSpeechRecognition' in window)){alert('Brauzer ovozni qo‘llab-quvvatlamaydi');return;}if(voiceActive){stopVoice();return;}const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;recognition=new SpeechRecognition();recognition.lang='uz-UZ';recognition.continuous=true;recognition.interimResults=true;recognition.onstart=()=>{voiceActive=true;document.getElementById('voice-status').innerHTML='<span class="voice-indicator"></span> Aytishni boshlang...';};recognition.onresult=(event)=>{let final='';for(let i=event.resultIndex;i<event.results.length;i++){if(event.results[i].isFinal)final+=event.results[i][0].transcript;}if(final){document.getElementById('voice-transcript').innerText=final;document.getElementById('consult-input').value=final;sendConsult();}};recognition.onerror=(e)=>{console.error(e);stopVoice();};recognition.start();}
        function stopVoice(){if(recognition){recognition.stop();recognition=null;}voiceActive=false;document.getElementById('voice-status').innerHTML='';}
        async function loadHealthRanking(){try{const res=await fetch('/api/v2/health/ranking');const data=await res.json();const container=document.getElementById('health-ranking');container.innerHTML='';data.slice(0,10).forEach((item,idx)=>{const div=document.createElement('div');div.className='ranking-item';div.innerHTML='<span class="pos">'+(idx+1)+'</span><span>'+(item.avatar||'🧬')+'</span><span class="name">'+item.username+'</span><span class="score">'+item.health_score+'%</span>';container.appendChild(div);});}catch(e){}}
        async function loadStats(){try{const res=await fetch('/api/v2/system/stats');const data=await res.json();const container=document.getElementById('stats-content');container.innerHTML='<div class="admin-stat"><div class="value">$'+(data.total_revenue||0)+'</div><div class="label">Daromad</div></div><div class="admin-stat"><div class="value" style="color:#43A047;">'+(data.active_users||0)+'</div><div class="label">Aktiv</div></div><div class="admin-stat"><div class="value" style="color:#FFB300;">'+(data.total_sales||0)+'</div><div class="label">Sotuv</div></div><div class="admin-stat"><div class="value" style="color:#43A047;">'+(data.total_social_posts||0)+'</div><div class="label">Post</div></div>';}catch(e){}}
        async function loadAdsPerformance(){try{const res=await fetch('/api/v2/ai/ads-performance');const data=await res.json();const container=document.getElementById('ads-performance');container.innerHTML='<div class="text-gray-400 text-sm">Hozircha kampaniya yo\'q</div>';}catch(e){}}
        function renderPackages(){const container=document.getElementById('package-grid');container.innerHTML='<div class="package-card"><div class="pkg-name">1 Haftalik</div><div class="pkg-price">$999</div></div><div class="package-card"><div class="pkg-name">1 Oylik</div><div class="pkg-price">$9,999</div></div><div class="package-card"><div class="pkg-name">3 Oylik</div><div class="pkg-price">$299,999</div></div><div class="package-card"><div class="pkg-name">1 Yillik</div><div class="pkg-price">$1,199,999</div></div>';}
        async function loadNotifications(){if(!currentUser)return;try{const res=await fetch('/api/v2/notifications/'+currentUser);const data=await res.json();notifCount=data.filter(n=>!n.read).length;document.getElementById('notif-count').innerText=notifCount;const list=document.getElementById('notif-list');list.innerHTML='';data.slice(0,10).forEach(n=>{const div=document.createElement('div');div.className='notif-item'+(n.read?'':' unread');div.innerHTML='<span class="time">'+new Date(n.timestamp).toLocaleTimeString()+'</span><div>'+n.message+'</div>';list.appendChild(div);});}catch(e){}}
        function toggleNotifications(){const dropdown=document.getElementById('notif-dropdown');dropdown.classList.toggle('show');if(dropdown.classList.contains('show')&&notifCount>0){fetch('/api/v2/notifications/read/'+currentUser,{method:'POST'});document.getElementById('notif-count').innerText='0';}}
        async function adminLogin(){const user=document.getElementById('admin-user').value.trim();const pass=document.getElementById('admin-pass').value.trim();if(!user||!pass){alert('Admin ma\'lumotlarini kiriting!');return;}try{const res=await fetch('/api/v2/admin/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,password:pass})});const data=await res.json();if(data.success){document.getElementById('admin-content').classList.remove('hidden');adminLoadDashboard();}else{alert('Noto\'g\'ri admin ma\'lumotlari');}}catch(e){alert(e.message);}}
        async function adminLoadDashboard(){try{const res=await fetch('/api/v2/admin/dashboard?username=CEO&password=12345678');const data=await res.json();const grid=document.getElementById('admin-stats-grid');grid.innerHTML='<div class="admin-stat"><div class="value">'+(data.total_users||0)+'</div><div class="label">Foydalanuvchilar</div></div><div class="admin-stat"><div class="value" style="color:#FFB300;">$'+(data.total_revenue||0)+'</div><div class="label">Daromad</div></div>';document.getElementById('admin-data').innerHTML='<pre class="text-xs">'+JSON.stringify(data,null,2)+'</pre>';}catch(e){}}
        window.onload=function(){document.getElementById('main-app').style.display='none';document.querySelectorAll('.lock-overlay').forEach(el=>el.style.display='flex');openAuthModal('signin');};
        document.getElementById('auth-modal').addEventListener('click',function(e){if(e.target===this)closeAuthModal();});
        document.querySelectorAll('#auth-user, #auth-pass, #auth-email, #auth-curr').forEach(el=>{el.addEventListener('keydown',function(e){if(e.key==='Enter')executeAuth();});});
    </script>
</body>
</html>""")

# ---------- JINJA2 TEMPLATES ----------
templates = Jinja2Templates(directory="templates")

# ---------- DATABASE ----------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
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

# ---------- OLD JSON DB ----------
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

# ---------- AI FUNCTIONS ----------
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

@app.post("/api/v2/camera/analyze")
async def camera_analyze(req: dict):
    username = req.get("username")
    department_id = req.get("department_id")
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
    track_user_activity(username, "camera_analysis", {"department_id": department_id})
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

@app.get("/api/v2/health/ranking")
async def health_ranking(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.health_score.desc()).all()
    ranking = [{"username": u.username, "health_score": u.health_score, "status": u.status, "avatar": u.avatar} for u in users]
    return ranking

@app.get("/api/v2/system/stats")
async def system_stats():
    return {
        "total_revenue": db_json["system_vault"]["total_revenue"],
        "active_users": db_json["system_vault"]["active_users"],
        "total_sales": len(db_json.get("product_sales", [])),
        "total_social_posts": len(db_json.get("social_posts", []))
    }

@app.get("/api/v2/ai/ads-performance")
async def ads_performance():
    return db_json.get("ads_performance", {})

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
