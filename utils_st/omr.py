"""
Streamlit OMR yardımcısı — PIL görüntüden kağıt okur.
Backend servislerini kullanır; her iki sayfa da buradan import eder.
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import cv2
import streamlit as st

# Backend path setup
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "omr_app", "backend"))

from PIL import Image  # noqa: E402 (after sys.path manipulation)
from services.omr_engine import aruco_tespit, bolgeleri_ayir, pil_to_cv
from services.gemini_service import gemini_cagir
from utils.prompts import OGRENCI_NO, cevap_balonlari, OGRENCI_BILGI


def get_gemini_key() -> str:
    """Gemini API key'i st.secrets veya env'den oku."""
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY", "")


def kagit_oku_web(
    pil_img: Image.Image,
    cevap_anahtari: dict[int, str],
    api_key: str,
    soru_sayisi: int = 20,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    PIL görüntüsünden sınav kağıdını okur.

    Returns:
        (sonuc_dict, None)  — başarılı
        (None, hata_mesaji) — başarısız
    """
    cv_img    = pil_to_cv(pil_img)
    markerlar = aruco_tespit(cv_img)
    if markerlar is None:
        return None, "ArUco marker bulunamadı"

    bolgeler = bolgeleri_ayir(cv_img, markerlar)
    orta = soru_sayisi // 2
    h, w  = bolgeler[1].shape[:2]
    buyuk = cv2.resize(bolgeler[1], (int(w * 1.5), int(h * 1.5)),
                       interpolation=cv2.INTER_CUBIC)

    with ThreadPoolExecutor(max_workers=4) as ex:
        f_bilgi = ex.submit(gemini_cagir, bolgeler[0], OGRENCI_BILGI, api_key)
        f_no    = ex.submit(gemini_cagir, buyuk, OGRENCI_NO, api_key)
        f_c1    = ex.submit(gemini_cagir, bolgeler[2], cevap_balonlari(1, orta), api_key)
        f_c2    = ex.submit(gemini_cagir, bolgeler[3], cevap_balonlari(orta + 1, soru_sayisi), api_key)
        bilgi, no_s, c1, c2 = (
            f_bilgi.result(), f_no.result(), f_c1.result(), f_c2.result()
        )

    ad_soyad = (
        bilgi.get("ad_soyad", "?")
        if isinstance(bilgi, dict) and "hata" not in bilgi
        else "?"
    )
    no = (
        str(no_s.get("no", "?????????"))
        if isinstance(no_s, dict) and "hata" not in no_s
        else "?????????"
    )
    no = no[:9].ljust(9, "?")

    cevaplar: dict[int, str] = {}
    if isinstance(c1, dict) and "hata" not in c1:
        cevaplar.update({int(k): str(v).upper() for k, v in c1.items() if str(k).isdigit()})
    if isinstance(c2, dict) and "hata" not in c2:
        cevaplar.update({int(k): str(v).upper() for k, v in c2.items() if str(k).isdigit()})

    dogru  = sum(1 for s in range(1, soru_sayisi + 1) if cevaplar.get(s) == cevap_anahtari.get(s))
    yanlis = sum(
        1 for s in range(1, soru_sayisi + 1)
        if cevaplar.get(s) not in (cevap_anahtari.get(s), "BOS", "HATA")
        and "/" not in str(cevaplar.get(s, ""))
    )
    bos  = sum(1 for s in range(1, soru_sayisi + 1) if cevaplar.get(s) == "BOS")
    puan = round(dogru * (100 / soru_sayisi), 2)

    return {
        "ad_soyad": ad_soyad,
        "ogrenci_no": no,
        "cevaplar": cevaplar,
        "dogru": dogru,
        "yanlis": yanlis,
        "bos": bos,
        "puan": puan,
    }, None
