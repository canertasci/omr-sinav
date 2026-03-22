"""
Excel export yardımcı fonksiyonları — tüm sayfalar buradan import eder.
"""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side


def excel_ozet(sonuclar: list[dict]) -> bytes:
    """Özet (Özet) sayfası: her öğrenci için tek satır."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Ozet"
    mavi  = PatternFill("solid", fgColor="1a56db")
    beyaz = Font(color="FFFFFF", bold=True)
    kenar = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    for j, b in enumerate(
        ["Sayfa", "Ad Soyad", "Öğrenci No", "Durum", "Doğru", "Yanlış", "Boş", "Puan"], 1
    ):
        h = ws.cell(row=1, column=j, value=b)
        h.fill = mavi
        h.font = beyaz
        h.alignment = Alignment(horizontal="center")
        h.border = kenar
    for i, s in enumerate(sonuclar, 2):
        for j, d in enumerate(
            [s.get("sayfa"), s.get("ad_soyad"), s.get("ogrenci_no"),
             s.get("durum"), s.get("dogru"), s.get("yanlis"),
             s.get("bos"), s.get("puan")], 1,
        ):
            hc = ws.cell(row=i, column=j, value=d)
            hc.border = kenar
            hc.alignment = Alignment(horizontal="center")
            durum = s.get("durum", "")
            if "Eşleşme var" in durum:
                hc.fill = PatternFill("solid", fgColor="d1fae5")
            elif "farklı" in durum:
                hc.fill = PatternFill("solid", fgColor="fef3c7")
            elif "yok" in durum:
                hc.fill = PatternFill("solid", fgColor="fee2e2")
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 18
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def excel_detay(sonuclar: list[dict], cevap_anahtari: dict, soru_sayisi: int = 20) -> bytes:
    """Detay sayfası: her öğrenci × soru matrisi."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Detay"
    mavi  = PatternFill("solid", fgColor="1a56db")
    beyaz = Font(color="FFFFFF", bold=True)
    kenar = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    basliklar = ["Ad Soyad", "Öğrenci No"] + [f"S{i}" for i in range(1, soru_sayisi + 1)]
    for j, b in enumerate(basliklar, 1):
        h = ws.cell(row=1, column=j, value=b)
        h.fill = mavi
        h.font = beyaz
        h.alignment = Alignment(horizontal="center")
        h.border = kenar
    ws.cell(row=2, column=1, value="CEVAP ANAHTARI").font = Font(bold=True)
    ws.cell(row=2, column=2, value="-")
    for s in range(1, soru_sayisi + 1):
        hc = ws.cell(row=2, column=s + 2, value=cevap_anahtari.get(s, "?"))
        hc.fill = PatternFill("solid", fgColor="dbeafe")
        hc.font = Font(bold=True)
        hc.alignment = Alignment(horizontal="center")
        hc.border = kenar
    for i, s in enumerate(sonuclar, 3):
        ws.cell(row=i, column=1, value=s.get("ad_soyad", "")).border = kenar
        ws.cell(row=i, column=2, value=s.get("ogrenci_no", "")).border = kenar
        for soru in range(1, soru_sayisi + 1):
            c  = s.get("cevaplar", {}).get(soru, "?")
            a  = cevap_anahtari.get(soru, "?")
            hc = ws.cell(row=i, column=soru + 2, value=c)
            hc.alignment = Alignment(horizontal="center")
            hc.border = kenar
            if c == a:
                hc.fill = PatternFill("solid", fgColor="d1fae5")
            elif c == "BOS":
                hc.fill = PatternFill("solid", fgColor="f3f4f6")
            else:
                hc.fill = PatternFill("solid", fgColor="fee2e2")
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 12
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
