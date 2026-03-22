"""
FastAPI ana uygulama — OMR Backend
"""
from __future__ import annotations

import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from exceptions import (
    GeminiAPIError,
    ImageValidationError,
    InsufficientCreditsError,
    OMRBaseError,
    OMRDetectionError,
)

# .env dosyasını backend dizininde kesin bul (çalışma dizini farklı olsa bile)
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from utils.logger import get_logger, setup_root_logger, RequestLoggingMiddleware
from routers import auth, credits, results, scan, template
from models.schemas import HealthResponse
from config import settings

# Rate limiter (global, router'lar import eder)
limiter = Limiter(key_func=get_remote_address)

setup_root_logger(settings.log_level)
log = get_logger("omr.main")

# ─────────────────────────── Metrics Store ───────────────────────────────────

class MetricsStore:
    """Thread-safe basit metrics depolaması."""
    def __init__(self):
        self._lock = Lock()
        self.total_requests = 0
        self.error_counts: dict[int, int] = defaultdict(int)
        self.total_response_time_ms = 0.0
        self.gemini_success = 0
        self.gemini_error = 0

    def record_request(self, status_code: int, elapsed_ms: float):
        with self._lock:
            self.total_requests += 1
            self.total_response_time_ms += elapsed_ms
            if status_code >= 400:
                self.error_counts[status_code] += 1

    def to_dict(self) -> dict:
        with self._lock:
            avg_ms = (
                round(self.total_response_time_ms / self.total_requests, 1)
                if self.total_requests > 0 else 0.0
            )
            total_errors = sum(self.error_counts.values())
            error_rate = round(total_errors / self.total_requests, 4) if self.total_requests > 0 else 0.0
            return {
                "total_requests": self.total_requests,
                "error_rate": error_rate,
                "error_counts": dict(self.error_counts),
                "avg_response_ms": avg_ms,
                "gemini_success": self.gemini_success,
                "gemini_error": self.gemini_error,
            }


metrics = MetricsStore()

# ─────────────────────────── Sentry ──────────────────────────────────────────

def _setup_sentry():
    dsn = settings.sentry_dsn
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        sentry_sdk.init(
            dsn=dsn,
            environment=settings.environment,
            traces_sample_rate=0.2,
            integrations=[FastApiIntegration(), StarletteIntegration()],
        )
        log.info("Sentry başlatıldı", extra={"environment": settings.environment})
    except ImportError:
        log.warning("sentry-sdk kurulu değil, Sentry devre dışı")


# ─────────────────────────── Lifespan ────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlarken ve kapanırken çalışır."""
    _setup_sentry()
    log.info("OMR Backend başlatıldı", extra={
        "gemini_key": "var" if settings.gemini_api_key else "EKSİK",
        "skip_auth": str(settings.skip_auth),
        "environment": settings.environment,
    })
    yield
    log.info("OMR Backend kapandı")


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

if settings.is_production and not settings.cors_origins:
    log.warning(
        "PRODUCTION ortamında CORS_ORIGINS ayarlanmamış! "
        "Güvenlik için .env dosyasına explicit origin listesi ekleyin."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ─────────────────────────── Metrics Middleware ───────────────────────────────

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    metrics.record_request(response.status_code, elapsed_ms)
    return response


# ─────────────────────────── Exception Handler'lar ───────────────────

_STATUS_MAP: dict[type, int] = {
    OMRDetectionError: 422,
    InsufficientCreditsError: 402,
    GeminiAPIError: 502,
    ImageValidationError: 400,
}


@app.exception_handler(OMRBaseError)
async def omr_error_handler(request: Request, exc: OMRBaseError) -> JSONResponse:
    status = _STATUS_MAP.get(type(exc), 500)
    log.error(
        "OMR hatası",
        extra={
            "type": type(exc).__name__,
            "detail": exc.detail,
            "path": request.url.path,
        },
        exc_info=True,
    )
    return JSONResponse(status_code=status, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error(
        "Beklenmeyen hata",
        extra={"path": request.url.path, "method": request.method},
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Sunucuda beklenmeyen bir hata oluştu. Lütfen tekrar deneyin."},
    )


# ─────────────────────────── Router'lar ──────────────────────────────

app.include_router(auth.router)
app.include_router(scan.router)
app.include_router(template.router)
app.include_router(results.router)
app.include_router(credits.router)


# ─────────────────────────── Sistem Endpoint'leri ────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Sistem"])
async def health():
    """Railway/Render health check endpoint."""
    return HealthResponse()


@app.get("/metrics", tags=["Sistem"], summary="Uygulama metrikleri")
async def get_metrics():
    """
    Basit JSON metrikler: toplam istek, hata oranı, ortalama süre,
    Gemini API başarı/hata sayısı.
    """
    return JSONResponse(content=metrics.to_dict())


@app.get("/debug/env-check", tags=["Sistem"], summary="Env var teşhis")
async def debug_env_check():
    """Railway'de kritik env var'ların durumunu gösterir (değerleri GÖSTERMEz)."""
    b64_raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_B64", "")
    json_raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    path_raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "")
    gemini_raw = os.getenv("GEMINI_API_KEY", "")
    firebase_keys = [k for k in os.environ if "FIREBASE" in k.upper() or "FIRE" in k.upper()]
    return {
        "GEMINI_API_KEY": f"SET (len={len(gemini_raw)}, starts={gemini_raw[:8]}...)" if gemini_raw else "NOT SET ⚠️",
        "settings.gemini_api_key": f"SET (len={len(settings.gemini_api_key)})" if settings.gemini_api_key else "EMPTY ⚠️",
        "FIREBASE_SERVICE_ACCOUNT_JSON_B64": f"SET (len={len(b64_raw)})" if b64_raw else "NOT SET",
        "FIREBASE_SERVICE_ACCOUNT_JSON": f"SET (len={len(json_raw)})" if json_raw else "NOT SET",
        "FIREBASE_SERVICE_ACCOUNT_PATH": path_raw or "NOT SET",
        "settings.firebase_service_account_json_b64": f"SET (len={len(settings.firebase_service_account_json_b64)})" if settings.firebase_service_account_json_b64 else "EMPTY",
        "settings.firebase_service_account_path": settings.firebase_service_account_path,
        "all_firebase_env_keys": firebase_keys,
        "total_env_vars": len(os.environ),
    }


@app.get("/debug/test-gemini", tags=["Sistem"], summary="Gemini API bağlantı testi")
async def debug_test_gemini(api_key: str = ""):
    """Gemini API'nin çalışıp çalışmadığını test eder (basit metin isteği)."""
    import requests as _req
    key = api_key or os.getenv("GEMINI_API_KEY", "") or settings.gemini_api_key
    if not key:
        return {"durum": "HATA", "mesaj": "API key yok. ?api_key=YOUR_KEY ile deneyin."}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
    body = {
        "contents": [{"parts": [{"text": "Sadece 'merhaba' yaz, başka bir şey yazma."}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 10},
    }
    try:
        resp = _req.post(url, json=body, timeout=15)
        if resp.status_code == 200:
            text = resp.json()["candidates"][0]["content"]["parts"][-1].get("text", "")
            return {"durum": "OK", "gemini_yanit": text.strip(), "model": "gemini-2.5-flash"}
        else:
            return {"durum": "HATA", "status_code": resp.status_code, "detay": resp.text[:500]}
    except Exception as exc:
        return {"durum": "HATA", "mesaj": str(exc)}


@app.get("/", tags=["Sistem"])
async def root():
    return {
        "mesaj": "OMR Öğretmen API çalışıyor",
        "docs": "/docs",
        "versiyon": "1.0.0",
    }
