"""
POST /api/v1/auth/register — Yeni kullanıcı kaydı (Firebase Auth'tan sonra çağrılır)
GET  /api/v1/auth/me       — Giriş yapmış kullanıcı bilgileri
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from middleware.auth_middleware import verify_firebase_token
from models.schemas import RegisterRequest, RegisterResponse
from services import firebase_service as fb

router = APIRouter(prefix="/api/v1/auth", tags=["Kimlik Doğrulama"])


@router.post("/register", response_model=RegisterResponse, summary="Yeni kullanıcı kaydı")
async def register(
    req: RegisterRequest,
    token_data: dict = Depends(verify_firebase_token),
):
    """
    Flutter, Firebase Auth ile kayıt/giriş yaptıktan sonra bu endpoint'i çağırır.
    Firestore'da kullanıcı belgesi oluşturur ve 500 ücretsiz kredi verir.
    Kullanıcı zaten varsa bilgilerini döndürür (idempotent).
    """
    uid = token_data["uid"]
    email = token_data.get("email", "")

    # Zaten kayıtlıysa güncelleme yapma, sadece döndür
    mevcut = fb.kullanici_getir(uid)
    if mevcut:
        fb.son_giris_guncelle(uid)
        return RegisterResponse(
            uid=uid,
            email=email,
            tam_ad=mevcut.get("tam_ad", req.tam_ad),
            kredi=mevcut.get("kredi", 0),
            mesaj="Mevcut kullanıcı",
        )

    kullanici = fb.kullanici_olustur(
        uid=uid,
        email=email,
        tam_ad=req.tam_ad,
        kullanici_tipi=req.kullanici_tipi,
    )

    return RegisterResponse(
        uid=uid,
        email=email,
        tam_ad=req.tam_ad,
        kredi=kullanici["kredi"],
        mesaj="Hoş geldiniz! 500 ücretsiz kredi hesabınıza eklendi.",
    )


@router.get("/me", summary="Kullanıcı bilgileri")
async def me(token_data: dict = Depends(verify_firebase_token)):
    uid = token_data["uid"]
    kullanici = fb.kullanici_getir(uid)
    if not kullanici:
        raise HTTPException(
            status_code=404,
            detail="Kullanıcı bulunamadı. Önce /auth/register endpoint'ini çağırın.",
        )
    return kullanici
