"""
Firebase token doğrulama middleware.

SKIP_AUTH=true olduğunda (geliştirme modu) token doğrulanmaz,
test için sabit bir uid döndürülür.
"""
from __future__ import annotations

import os

import firebase_admin
from firebase_admin import auth
from fastapi import Header, HTTPException

from utils.logger import get_logger

log = get_logger("omr.auth")

# Modül yüklenirken bir kez hesapla + logla
_SKIP = os.getenv("SKIP_AUTH", "false").strip().lower() in ("true", "1", "yes")
log.info("Auth middleware yüklendi", extra={
    "skip_auth_env": os.getenv("SKIP_AUTH", "NOT_SET"),
    "bypass": _SKIP,
})


async def verify_firebase_token(
    authorization: str = Header(None, description="Bearer <firebase_id_token>"),
) -> dict:
    """
    FastAPI Dependency — korumalı route'larda kullanılır.

    Döner: {"uid": "...", "email": "...", ...}
    """
    # ENVIRONMENT=production iken SKIP_AUTH=true çalışmasın
    env = os.getenv("ENVIRONMENT", "development").lower()
    skip_requested = _SKIP or os.getenv("SKIP_AUTH", "false").strip().lower() in ("true", "1", "yes")

    if skip_requested and env == "production":
        log.error(
            "SKIP_AUTH=true production ortamında engellendi! "
            "Güvenlik açığı önlendi. ENVIRONMENT değişkenini kontrol edin.",
        )
        skip_requested = False

    if skip_requested:
        return {"uid": "dev_user_001", "email": "dev@example.com"}

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Geçersiz token formatı. 'Bearer <token>' formatında olmalı.",
        )

    token = authorization.split("Bearer ", 1)[1].strip()

    try:
        # Firebase init'i merkezi firebase_service'den al (idempotent)
        from services.firebase_service import init_firebase
        init_firebase()
        decoded = auth.verify_id_token(token)
        log.info("Token doğrulandı", extra={"uid": decoded.get("uid")})
        return decoded  # {"uid": "...", "email": "...", ...}
    except firebase_admin.exceptions.FirebaseError as exc:
        log.warning("Token doğrulama başarısız", extra={"error": str(exc)})
        raise HTTPException(status_code=401, detail=f"Token doğrulanamadı: {exc}") from exc
    except RuntimeError as exc:
        # Firebase init hatası (service account bulunamadı)
        log.error("Firebase başlatılamadı", extra={"error": str(exc)})
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        log.warning("Token doğrulama hatası", extra={"error": str(exc)})
        raise HTTPException(status_code=401, detail=str(exc)) from exc
