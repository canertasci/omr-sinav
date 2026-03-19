"""
GET  /api/v1/credits/balance        — kredi bakiyesi
POST /api/v1/credits/verify-purchase — Google Play token doğrulama ve kredi ekleme
POST /api/v1/credits/reward-ad      — Rewarded reklam → +10 kredi
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException

from middleware.auth_middleware import verify_firebase_token
from models.schemas import (
    KrediBalanceResponse,
    VerifyPurchaseRequest,
    VerifyPurchaseResponse,
)
from services import firebase_service as fb

router = APIRouter(prefix="/api/v1/credits", tags=["Kredi"])

# Google Play ürün ID → kredi miktarı
URUN_KREDI_MAPI = {
    "credits_1500": 1500,
    "credits_3000": 3000,
    "credits_10000": 10000,
}

REKLAM_KREDI = 10  # Rewarded reklam başına kazanılan kredi


@router.get("/balance", response_model=KrediBalanceResponse, summary="Kredi bakiyesi")
async def get_balance(token_data: dict = Depends(verify_firebase_token)):
    uid = token_data["uid"]
    kullanici = fb.kullanici_getir(uid)
    if not kullanici:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    return KrediBalanceResponse(
        uid=uid,
        kredi=kullanici.get("kredi", 0),
        toplam_kullanilan=kullanici.get("toplam_kullanilan", 0),
    )


@router.post("/verify-purchase", response_model=VerifyPurchaseResponse, summary="Google Play satın alma doğrula")
async def verify_purchase(
    req: VerifyPurchaseRequest,
    token_data: dict = Depends(verify_firebase_token),
):
    """
    Flutter → FastAPI → Google Play Developer API doğrulama akışı.
    
    Faz 3'te tam Google Play Developer API entegrasyonu yapılacak.
    Şu an: token daha önce kullanılmış mı kontrolü + kredi ekleme.
    """
    uid = token_data["uid"]

    if req.product_id not in URUN_KREDI_MAPI:
        raise HTTPException(status_code=400, detail=f"Geçersiz ürün ID: {req.product_id}")

    # Double-spend önleme
    if fb.satin_alma_Token_kullanildi_mi(req.purchase_token):
        raise HTTPException(
            status_code=409,
            detail="Bu satın alma daha önce kullanılmış",
        )

    # TODO Faz 3: Google Play Developer API ile token doğrulama
    # from services.play_billing_service import verify_play_token
    # if not verify_play_token(req.product_id, req.purchase_token):
    #     raise HTTPException(status_code=402, detail="Geçersiz satın alma tokeni")

    miktar = URUN_KREDI_MAPI[req.product_id]
    yeni_kredi = fb.kredi_ekle(
        uid=uid,
        miktar=miktar,
        aciklama=f"Google Play: {req.product_id}",
        play_token=req.purchase_token,
    )

    return VerifyPurchaseResponse(
        success=True,
        yeni_kredi=yeni_kredi,
        mesaj=f"{miktar} kredi başarıyla eklendi",
    )


@router.post("/reward-ad", response_model=VerifyPurchaseResponse, summary="Rewarded reklam kredisi")
async def reward_ad(token_data: dict = Depends(verify_firebase_token)):
    """
    AdMob rewarded reklam izleme tamamlandığında Flutter bu endpoint'i çağırır.
    +10 kredi ekler.
    
    Not: Gerçek ortamda AdMob server-side callback zaten doğrulama sağlar.
    Bu endpoint basit implementasyondur.
    """
    uid = token_data["uid"]
    yeni_kredi = fb.kredi_ekle(
        uid=uid,
        miktar=REKLAM_KREDI,
        aciklama="Rewarded reklam izlendi",
    )
    return VerifyPurchaseResponse(
        success=True,
        yeni_kredi=yeni_kredi,
        mesaj=f"+{REKLAM_KREDI} kredi kazanıldı",
    )
