"""
POST /api/v1/template/generate — OMR şablonu PDF + koordinat JSON üret
"""
from __future__ import annotations

import base64
import io
import json
import uuid

from fastapi import APIRouter, Depends
from fpdf import FPDF

from middleware.auth_middleware import verify_firebase_token
from models.schemas import (
    ArucoMarker,
    BolgeInfo,
    KoordinatJSON,
    TemplateGenerateRequest,
    TemplateGenerateResponse,
)

router = APIRouter(prefix="/api/v1/template", tags=["Şablon"])

# Sayfa boyutu: A4
SAYFA_W = 210.0
SAYFA_H = 297.0

# ArUco marker boyutu (mm)
MARKER_MM = 15.0
MARGIN = 5.0  # kenara uzaklık

# Soru seçenekleri
SECENEKLER = ["A", "B", "C", "D", "E"]


class OMRTemplate(FPDF):
    """FPDF tabanlı OMR şablon oluşturucu."""

    def __init__(self, soru_sayisi: int, ders_adi: str, **kwargs):
        super().__init__(**kwargs)
        self.soru_sayisi = soru_sayisi
        self.ders_adi = ders_adi
        self.set_margins(0, 0, 0)
        self.set_auto_page_break(auto=False)
        self.add_page()

    # ── ArUco Placeholder (gerçek ArUco PNG gerektirir) ──────────────
    def _draw_aruco_box(self, x: float, y: float, marker_id: int):
        """Gerçek ArUco yerine dolgulu kare + ID metni (PDF'de)."""
        self.set_fill_color(0, 0, 0)
        self.rect(x, y, MARKER_MM, MARKER_MM, style="F")
        # Köşe deseni: sağ alt 1/3'ü beyaz bırak (basit temsil)
        inner = MARKER_MM / 3
        self.set_fill_color(255, 255, 255)
        self.rect(x + inner, y + inner, inner, inner, style="F")
        self.set_font("Helvetica", size=5)
        self.set_text_color(255, 255, 255)
        self.set_xy(x, y + MARKER_MM - 4)
        self.cell(MARKER_MM, 4, f"ID:{marker_id}", align="C")
        self.set_text_color(0, 0, 0)

    # ── Öğrenci Bilgi Alanı (sol üst) ────────────────────────────────
    def _draw_bilgi_alani(self, x: float, y: float, w: float, h: float):
        self.set_draw_color(0, 0, 0)
        self.rect(x, y, w, h)
        self.set_font("Helvetica", style="B", size=9)
        self.set_xy(x + 2, y + 3)
        self.cell(w - 4, 5, "OMR SINAV KAĞIDI", align="C")

        self.set_font("Helvetica", size=8)
        satir_h = 8.0
        alanlar = ["Ad Soyad:", "Bölüm / Program:", "Ders Adı:", "İmza:"]
        if self.ders_adi:
            alanlar[2] = f"Ders: {self.ders_adi}"

        for i, alan in enumerate(alanlar):
            yy = y + 12 + i * satir_h
            self.set_xy(x + 2, yy)
            self.cell(30, 5, alan)
            self.line(x + 32, yy + 5, x + w - 2, yy + 5)

    # ── Öğrenci No Grid (sağ üst): 9 sütun × 10 satır ───────────────
    def _draw_no_grid(self, x: float, y: float, w: float, h: float):
        self.set_font("Helvetica", style="B", size=7)
        self.set_xy(x + 2, y + 1)
        self.cell(w - 4, 4, "ÖĞRENCİ NUMARASI", align="C")

        haneler = 9
        rakamlar = 10
        hucre_w = (w - 4) / haneler
        hucre_h = (h - 10) / (rakamlar + 1)

        # Sütun başlıkları (H1, H2, ...)
        self.set_font("Helvetica", size=5)
        for s in range(haneler):
            self.set_xy(x + 2 + s * hucre_w, y + 6)
            self.cell(hucre_w, hucre_h, str(s + 1), align="C")

        # Balonlar
        r = hucre_w * 0.38
        for s in range(haneler):
            for rakam in range(rakamlar):
                cx = x + 2 + s * hucre_w + hucre_w / 2
                cy = y + 10 + (rakam + 0.5) * hucre_h

                # Rakam etiketi (sadece ilk sütun için)
                if s == 0:
                    self.set_font("Helvetica", size=4)
                    self.set_xy(cx - hucre_w - 1, cy - hucre_h / 2)
                    self.cell(hucre_w, hucre_h, str(rakam), align="R")

                self.set_draw_color(0, 0, 0)
                self.ellipse(cx - r, cy - r, r * 2, r * 2)

    # ── Cevap Balonları ───────────────────────────────────────────────
    def _draw_cevaplar(self, x: float, y: float, w: float, h: float, bas: int, bit: int):
        soru_sayisi = bit - bas + 1
        self.set_font("Helvetica", style="B", size=7)
        self.set_xy(x + 2, y + 1)
        self.cell(w - 4, 4, f"SORULAR {bas}–{bit}", align="C")

        hucre_h = (h - 8) / soru_sayisi
        hucre_w = (w - 4) / (len(SECENEKLER) + 1)  # +1 soru numarası için
        r = min(hucre_w, hucre_h) * 0.38

        for i, soru_no in enumerate(range(bas, bit + 1)):
            yy = y + 8 + i * hucre_h

            # Soru numarası
            self.set_font("Helvetica", size=5)
            self.set_xy(x + 2, yy)
            self.cell(hucre_w, hucre_h, str(soru_no), align="R")

            # Şık balonları
            for j, secim in enumerate(SECENEKLER):
                cx = x + 2 + (j + 1.5) * hucre_w
                cy = yy + hucre_h / 2
                self.set_draw_color(0, 0, 0)
                self.ellipse(cx - r, cy - r, r * 2, r * 2)
                self.set_font("Helvetica", size=4)
                self.set_xy(cx - hucre_w / 2, yy)
                self.cell(hucre_w, hucre_h, secim, align="C")

    def olustur(self) -> None:
        """Şablonu çizer."""
        # Koordinat hesaplama
        x_sol = MARGIN
        x_sag = SAYFA_W - MARGIN - MARKER_MM
        y_ust = MARGIN
        y_alt = SAYFA_H - MARGIN - MARKER_MM

        x_orta = SAYFA_W / 2
        y_orta = SAYFA_H / 2

        # ArUco markers
        self._draw_aruco_box(x_sol, y_ust, 0)   # ID 0 sol üst
        self._draw_aruco_box(x_sag, y_ust, 1)   # ID 1 sağ üst
        self._draw_aruco_box(x_sol, y_alt, 2)   # ID 2 sol alt
        self._draw_aruco_box(x_sag, y_alt, 3)   # ID 3 sağ alt

        # Bölge koordinatları (marker kenarından başla)
        bolge_x_sol = x_sol + MARKER_MM + 2
        bolge_x_orta = x_orta + 1
        bolge_y_ust = y_ust + MARKER_MM + 2
        bolge_y_orta = y_orta + 1

        bolge_w_sol = x_orta - bolge_x_sol - 1
        bolge_w_sag = (x_sag - 2) - bolge_x_orta
        bolge_h_ust = y_orta - bolge_y_ust - 1
        bolge_h_alt = (y_alt - 2) - bolge_y_orta

        orta = self.soru_sayisi // 2

        # 4 bölge
        self._draw_bilgi_alani(bolge_x_sol, bolge_y_ust, bolge_w_sol, bolge_h_ust)
        self._draw_no_grid(bolge_x_orta, bolge_y_ust, bolge_w_sag, bolge_h_ust)
        self._draw_cevaplar(bolge_x_sol, bolge_y_orta, bolge_w_sol, bolge_h_alt, 1, orta)
        self._draw_cevaplar(bolge_x_orta, bolge_y_orta, bolge_w_sag, bolge_h_alt, orta + 1, self.soru_sayisi)


def _koordinat_json_olustur(sablon_id: str, soru_sayisi: int) -> KoordinatJSON:
    orta = soru_sayisi // 2
    return KoordinatJSON(
        sablon_id=sablon_id,
        soru_sayisi=soru_sayisi,
        sayfa_genislik_mm=SAYFA_W,
        sayfa_yukseklik_mm=SAYFA_H,
        aruco_markers=[
            ArucoMarker(id=0, konum="sol_ust", x_mm=MARGIN, y_mm=MARGIN),
            ArucoMarker(id=1, konum="sag_ust", x_mm=SAYFA_W - MARGIN - MARKER_MM, y_mm=MARGIN),
            ArucoMarker(id=2, konum="sol_alt", x_mm=MARGIN, y_mm=SAYFA_H - MARGIN - MARKER_MM),
            ArucoMarker(id=3, konum="sag_alt", x_mm=SAYFA_W - MARGIN - MARKER_MM, y_mm=SAYFA_H - MARGIN - MARKER_MM),
        ],
        bolgeler={
            "ogrenci_bilgi": BolgeInfo(bolge=0, aciklama="sol_ust"),
            "ogrenci_no": BolgeInfo(bolge=1, aciklama="sag_ust", hane=9, rakam=10),
            "sorular_1": BolgeInfo(bolge=2, aciklama="sol_alt", bas=1, bit=orta),
            "sorular_2": BolgeInfo(bolge=3, aciklama="sag_alt", bas=orta + 1, bit=soru_sayisi),
        },
    )


@router.post("/generate", response_model=TemplateGenerateResponse, summary="OMR şablonu oluştur")
async def generate_template(
    req: TemplateGenerateRequest,
    _token: dict = Depends(verify_firebase_token),
):
    sablon_id = str(uuid.uuid4())[:8]

    pdf = OMRTemplate(soru_sayisi=req.soru_sayisi, ders_adi=req.ders_adi)
    pdf.olustur()

    buf = io.BytesIO()
    pdf_bytes = pdf.output()
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    koordinat = _koordinat_json_olustur(sablon_id, req.soru_sayisi)

    return TemplateGenerateResponse(
        pdf_base64=pdf_b64,
        koordinat_json=koordinat,
        sablon_id=sablon_id,
    )
