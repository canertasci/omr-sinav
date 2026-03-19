"""
FastAPI ana uygulama — OMR Backend
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# .env yükle (Railway/Render'da environment variables zaten set edilmiş olur)
load_dotenv()

from routers import auth, credits, results, scan, template
from models.schemas import HealthResponse

# ─────────────────────────── Lifespan ────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlarken ve kapanırken çalışır."""
    print("🚀 OMR Backend başlatıldı")
    print(f"   GEMINI_API_KEY: {'✓ var' if os.getenv('GEMINI_API_KEY') else '✗ eksik!'}")
    print(f"   SKIP_AUTH: {os.getenv('SKIP_AUTH', 'false')}")
    yield
    print("👋 OMR Backend kapandı")


# ─────────────────────────── FastAPI App ─────────────────────────────

app = FastAPI(
    title="OMR Öğretmen API",
    description=(
        "Optik İşaret Tanıma (OMR) tabanlı sınav değerlendirme sistemi.\n\n"
        "**Faz 1** — Tek ve toplu kağıt okuma, şablon üretimi, sonuç yönetimi."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─────────────────────────── CORS ────────────────────────────────────

# Production'da Flutter app domain'ini buraya ekle
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────── Router'lar ──────────────────────────────

app.include_router(auth.router)
app.include_router(scan.router)
app.include_router(template.router)
app.include_router(results.router)
app.include_router(credits.router)


# ─────────────────────────── Sağlık Kontrolü ─────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Sistem"])
async def health():
    """Railway/Render health check endpoint."""
    return HealthResponse()


@app.get("/", tags=["Sistem"])
async def root():
    return {
        "mesaj": "OMR Öğretmen API çalışıyor",
        "docs": "/docs",
        "versiyon": "1.0.0",
    }
