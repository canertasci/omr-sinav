"""
POST /api/v1/scan/single  — tek kağıt okuma
POST /api/v1/scan/batch   — toplu kağıt okuma (max 30)
"""
from __future__ import annotations

import base64
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, HTTPException

from middleware.auth_middleware import verify_firebase_token
from models.schemas import (
    BatchSonuc,
    KontrolGerekli,
    ScanBatchRequest,
    ScanBatchResponse,
    ScanResponse,
    ScanSingleRequest,
)
from services import firebase_service as fb
from services.omr_engine import kagit_oku

router = APIRouter(prefix="/api/v1/scan", tags=["Tarama"])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


def _decode_image(b64: str) -> bytes:
    """Base64 → bytes. data:image/... prefix'i varsa soyar."""
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    return base64.b64decode(b64)


@router.post("/single", response_model=ScanResponse, summary="Tek kağıt oku")
async def scan_single(
    req: ScanSingleRequest,
    token_data: dict = Depends(verify_firebase_token),
):
    """
    Tek OMR kağıdını okur. Başarılı okumada 1 kredi düşer.
    ArUco tespit başarısız → kredi düşmez, hata döner.
    """
    uid = token_data["uid"]
    goruntu_bytes = _decode_image(req.goruntu_base64)

    # OMR pipeline
    sonuc = kagit_oku(
        goruntu_bytes=goruntu_bytes,
        cevap_anahtari=req.cevap_anahtari,
        api_key=GEMINI_API_KEY,
        soru_sayisi=req.soru_sayisi,
    )

    # ArUco tespit başarısızdı → kredi düşme
    if sonuc.get("hata") and "ArUco" in str(sonuc.get("hata", "")):
        return ScanResponse(**sonuc)

    # Gemini/başka hata → yine kredi düşme, sonucu döndür
    if sonuc.get("hata"):
        return ScanResponse(**sonuc)

    # Başarılı → 1 kredi düş
    kredi_yeterli = fb.kredi_dус(uid, miktar=1, aciklama=f"Sınav {req.sinav_id} tarama")
    if not kredi_yeterli:
        raise HTTPException(status_code=402, detail="Yetersiz kredi. Lütfen kredi satın alın.")

    # Firestore'a kaydet
    fb.sonuc_kaydet({
        "sinav_id": req.sinav_id,
        "sablon_id": req.sablon_id,
        "ogretmen_id": uid,
        "ogrenci_no": sonuc["ogrenci_no"],
        "ad_soyad": sonuc["ad_soyad"],
        "bolum": sonuc.get("bolum", "?"),
        "ders": sonuc.get("ders", "?"),
        "cevaplar": sonuc["cevaplar"],
        "dogru": sonuc["dogru"],
        "yanlis": sonuc["yanlis"],
        "bos": sonuc["bos"],
        "puan": sonuc["puan"],
        "guvenskor": sonuc["guvenskor"],
    })

    return ScanResponse(**sonuc)


@router.post("/batch", response_model=ScanBatchResponse, summary="Toplu kağıt oku (max 30)")
async def scan_batch(
    req: ScanBatchRequest,
    token_data: dict = Depends(verify_firebase_token),
):
    """
    Birden fazla kağıdı toplu okur.
    Önce kaç kredi gerektiğini hesaplar, yeterliyse devam eder.
    Her başarılı okuma için 1 kredi düşer (bireysel transaction).
    """
    uid = token_data["uid"]

    if len(req.goruntuler) > 30:
        raise HTTPException(status_code=400, detail="Tek istekte maksimum 30 görüntü")

    # Kredi kontrolü
    mevcut_kredi = fb.kredi_oku(uid)
    if mevcut_kredi < 1:
        raise HTTPException(status_code=402, detail="Yetersiz kredi")

    sonuclar: list[BatchSonuc] = []
    kontrol_listesi: list[KontrolGerekli] = []
    basarili = 0
    hatali = 0

    # Paralel işleme
    def _isle(indeks: int, b64: str) -> BatchSonuc:
        try:
            goruntu_bytes = _decode_image(b64)
            sonuc = kagit_oku(
                goruntu_bytes=goruntu_bytes,
                cevap_anahtari=req.cevap_anahtari,
                api_key=GEMINI_API_KEY,
                soru_sayisi=req.soru_sayisi,
            )
            aruco_hatasi = sonuc.get("hata") and "ArUco" in str(sonuc.get("hata", ""))

            if not aruco_hatasi and not sonuc.get("hata"):
                # Kredi düş (bireysel, başarısız olursa okuma yine döner ama kayıt yapılmaz)
                kredi_duste = fb.kredi_dус(uid, miktar=1, aciklama=f"Batch {req.sinav_id}")
                if kredi_duste:
                    fb.sonuc_kaydet({
                        "sinav_id": req.sinav_id,
                        "sablon_id": req.sablon_id,
                        "ogretmen_id": uid,
                        "ogrenci_no": sonuc["ogrenci_no"],
                        "ad_soyad": sonuc["ad_soyad"],
                        "bolum": sonuc.get("bolum", "?"),
                        "ders": sonuc.get("ders", "?"),
                        "cevaplar": sonuc["cevaplar"],
                        "dogru": sonuc["dogru"],
                        "yanlis": sonuc["yanlis"],
                        "bos": sonuc["bos"],
                        "puan": sonuc["puan"],
                        "guvenskor": sonuc["guvenskor"],
                    })

            return BatchSonuc(indeks=indeks, sonuc=ScanResponse(**sonuc))
        except Exception as exc:
            return BatchSonuc(indeks=indeks, hata_mesaji=str(exc))

    GUVEN_ESIGI = 0.70

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_isle, i, b64): i for i, b64 in enumerate(req.goruntuler)}
        for future in as_completed(futures):
            bs = future.result()
            sonuclar.append(bs)
            if bs.hata_mesaji:
                hatali += 1
                kontrol_listesi.append(KontrolGerekli(
                    indeks=bs.indeks,
                    sebep=bs.hata_mesaji,
                    guvenskor=0.0,
                ))
            else:
                basarili += 1
                sonuc = bs.sonuc
                if sonuc and (sonuc.hata or sonuc.guvenskor < GUVEN_ESIGI):
                    sebep = sonuc.hata or f"Düşük güven skoru ({sonuc.guvenskor:.2f})"
                    kontrol_listesi.append(KontrolGerekli(
                        indeks=bs.indeks,
                        sebep=sebep,
                        guvenskor=sonuc.guvenskor,
                    ))

    sonuclar.sort(key=lambda x: x.indeks)
    kontrol_listesi.sort(key=lambda x: x.indeks)

    return ScanBatchResponse(
        sonuclar=sonuclar,
        toplam=len(req.goruntuler),
        basarili=basarili,
        hatali=hatali,
        kontrol_gerekli=kontrol_listesi,
    )
