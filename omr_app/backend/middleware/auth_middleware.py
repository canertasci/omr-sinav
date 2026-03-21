"""
Firebase token doğrulama middleware.

SKIP_AUTH=true olduğunda (geliştirme modu) token doğrulanmaz,
test için sabit bir uid döndürülür.
"""
from __future__ import annotations

import base64
import os
import json

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Header, HTTPException

_firebase_initialized = False

# Modül yüklenirken bir kez hesapla + logla
_SKIP = os.getenv("SKIP_AUTH", "false").strip().lower() in ("true", "1", "yes")
print(f"[AUTH] SKIP_AUTH env='{os.getenv('SKIP_AUTH', 'NOT_SET')}' → bypass={_SKIP}")


def _init_firebase() -> None:
    global _firebase_initialized
    if _firebase_initialized:
        return

    # 1) Base64 encoded JSON (Railway için önerilen yöntem)
    sa_b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_B64")
    if sa_b64:
        sa_dict = json.loads(base64.b64decode(sa_b64).decode())
        cred = credentials.Certificate(sa_dict)
    # 2) Düz JSON string
    elif os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON"):
        sa_dict = json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON"))
        cred = credentials.Certificate(sa_dict)
    else:
        # Dosya yolundan yükle (lokal geliştirme)
        sa_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase_service_account.json")
        if not os.path.exists(sa_path):
            raise RuntimeError(
                f"Firebase service account bulunamadı: {sa_path}\n"
                "FIREBASE_SERVICE_ACCOUNT_JSON veya FIREBASE_SERVICE_ACCOUNT_PATH "
                ".env dosyasında tanımlı olmalı."
            )
        cred = credentials.Certificate(sa_path)

    firebase_admin.initialize_app(cred)
    _firebase_initialized = True


async def verify_firebase_token(
    authorization: str = Header(None, description="Bearer <firebase_id_token>"),
) -> dict:
    """
    FastAPI Dependency — korumalı route'larda kullanılır.

    Döner: {"uid": "...", "email": "...", ...}
    """
    # Hem modül-level hem runtime kontrol (Railway geç inject edebilir)
    skip = _SKIP or os.getenv("SKIP_AUTH", "false").strip().lower() in ("true", "1", "yes")
    if skip:
        return {"uid": "dev_user_001", "email": "dev@example.com"}

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Geçersiz token formatı. 'Bearer <token>' formatında olmalı.",
        )

    token = authorization.split("Bearer ", 1)[1].strip()

    try:
        _init_firebase()
        decoded = auth.verify_id_token(token)
        return decoded  # {"uid": "...", "email": "...", ...}
    except firebase_admin.exceptions.FirebaseError as exc:
        raise HTTPException(status_code=401, detail=f"Token doğrulanamadı: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
