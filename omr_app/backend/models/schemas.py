"""
Pydantic v2 şemaları — OMR API
"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


# ─────────────────────────────── SCAN ────────────────────────────────

class ScanSingleRequest(BaseModel):
    goruntu_base64: str = Field(..., description="JPEG/PNG görüntü, base64 kodlanmış")
    sablon_id: str = Field(..., description="Şablon ID (Firestore'dan)")
    sinav_id: str = Field(..., description="Sınav ID")
    cevap_anahtari: dict[str, str] = Field(
        ...,
        description='Cevap anahtarı: {"1": "A", "2": "C", ...}',
        examples=[{"1": "A", "2": "C", "3": "B"}],
    )
    soru_sayisi: int = Field(
        default=20,
        ge=10,
        le=100,
        description="Soru sayısı (10/20/25/40/50/100)",
    )
    gemini_api_key: str | None = Field(
        default=None,
        description="Kullanıcının kendi Gemini API key'i (opsiyonel)",
    )


class ScanBatchRequest(BaseModel):
    goruntuler: list[str] = Field(
        ...,
        max_length=30,
        description="Base64 görüntü listesi, maksimum 30 adet",
    )
    sablon_id: str
    sinav_id: str
    cevap_anahtari: dict[str, str]
    soru_sayisi: int = Field(default=20, ge=10, le=100)


class ScanResponse(BaseModel):
    ogrenci_no: str
    ad_soyad: str
    bolum: str = "?"
    ders: str = "?"
    cevaplar: dict[str, str]
    dogru: int
    yanlis: int
    bos: int
    puan: float
    guvenskor: float = Field(
        ...,
        description="0.0–1.0 arası güven skoru. <0.85 ise manuel kontrol önerilir.",
    )
    hata: str | None = None


class BatchSonuc(BaseModel):
    indeks: int
    sonuc: ScanResponse | None = None
    hata_mesaji: str | None = None


class KontrolGerekli(BaseModel):
    indeks: int
    sebep: str
    guvenskor: float


class ScanBatchResponse(BaseModel):
    sonuclar: list[BatchSonuc]
    toplam: int
    basarili: int
    hatali: int
    kontrol_gerekli: list[KontrolGerekli] = []


# ─────────────────────────────── TEMPLATE ────────────────────────────

class TemplateGenerateRequest(BaseModel):
    soru_sayisi: int = Field(
        default=20,
        description="Soru sayısı",
    )
    layout_tipi: str = Field(
        default="standart",
        pattern="^(standart|genis)$",
        description="standart: 4 eşit parça | genis: sağ taraf tüm sorular",
    )
    ders_adi: str = Field(default="", max_length=100)


class ArucoMarker(BaseModel):
    id: int
    konum: str
    x_mm: float
    y_mm: float


class BolgeInfo(BaseModel):
    bolge: int
    aciklama: str
    hane: int | None = None
    rakam: int | None = None
    bas: int | None = None
    bit: int | None = None


class KoordinatJSON(BaseModel):
    sablon_id: str
    soru_sayisi: int
    sayfa_genislik_mm: float = 210.0
    sayfa_yukseklik_mm: float = 297.0
    aruco_markers: list[ArucoMarker]
    bolgeler: dict[str, BolgeInfo]


class TemplateGenerateResponse(BaseModel):
    pdf_base64: str
    koordinat_json: KoordinatJSON
    sablon_id: str


# ─────────────────────────────── RESULTS ─────────────────────────────

class SonucListResponse(BaseModel):
    sonuclar: list[dict[str, Any]]
    toplam: int


class IstatistikResponse(BaseModel):
    sinav_id: str
    ogrenci_sayisi: int
    ortalama: float
    medyan: float
    min_puan: float
    max_puan: float
    standart_sapma: float
    soru_basari_oranlari: dict[str, float]  # {"1": 0.85, "2": 0.60, ...}


# ─────────────────────────────── CREDITS ─────────────────────────────

class KrediBalanceResponse(BaseModel):
    uid: str
    kredi: int
    toplam_kullanilan: int


class VerifyPurchaseRequest(BaseModel):
    product_id: str = Field(
        ...,
        description="Google Play product ID (credits_1500, credits_3000, credits_10000)",
    )
    purchase_token: str


class VerifyPurchaseResponse(BaseModel):
    success: bool
    yeni_kredi: int
    mesaj: str


# ─────────────────────────────── AUTH ────────────────────────────────

class RegisterRequest(BaseModel):
    tam_ad: str = Field(..., max_length=100)
    kullanici_tipi: str = Field(
        default="bireysel",
        pattern="^(bireysel|kurum_yonetici|kurum_uye)$",
    )


class RegisterResponse(BaseModel):
    uid: str
    email: str
    tam_ad: str
    kredi: int
    mesaj: str


# ─────────────────────────────── EXCEL SINAV ─────────────────────────

class ExcelSinavRequest(BaseModel):
    goruntuler: list[str] = Field(
        ..., max_length=100,
        description="Base64 görüntü listesi (her biri bir cevap kağıdı)",
    )
    ogrenci_listesi_b64: str | None = Field(
        default=None,
        description="Öğrenci listesi Excel base64 (A=No, B=Ad Soyad, başlık yok)",
    )
    cevap_anahtari: dict[str, str]
    soru_sayisi: int = Field(default=20, ge=10, le=100)
    sinav_adi: str = Field(default="Sinav", max_length=100)
    gemini_api_key: str | None = None


class ExcelSinavResponse(BaseModel):
    ozet_excel_b64: str
    detay_excel_b64: str
    toplam: int
    basarili: int
    hatali: int


# ─────────────────────────────── HEALTH ──────────────────────────────

class HealthResponse(BaseModel):
    durum: str = "ok"
    versiyon: str = "1.0.0"
