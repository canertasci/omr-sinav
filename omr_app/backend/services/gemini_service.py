"""
Gemini 2.5 Flash API wrapper.
GEMINI_API_KEY .env'den okunur.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time

import cv2
import numpy as np
import requests

from utils.logger import get_logger
from utils.image_utils import kucult_ve_base64 as _kucult_ve_base64
from config import settings

log = get_logger("omr.gemini")
MAX_GORUNTU_PX = settings.max_goruntu_px

# Regex: metin içinde ilk JSON objesini bul (birden fazla {} varsa da güvenli)
_JSON_RE = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', re.DOTALL)


def _json_cıkar(metin: str) -> str:
    """
    Ham Gemini yanıtından JSON string'i çıkarır.
    1. Markdown ```json ... ``` bloğunu dener
    2. Regex ile ilk geçerli JSON objesini bulur
    3. Fallback: { ile } arasını al
    """
    metin = metin.strip()

    # Markdown kod bloğu
    if "```" in metin:
        for parca in metin.split("```"):
            parca = parca.strip()
            if parca.startswith("json"):
                parca = parca[4:].strip()
            if parca.startswith("{"):
                # Regex ile en dıştaki JSON'u al
                m = _JSON_RE.search(parca)
                if m:
                    return m.group(0)

    # Regex extraction (birden fazla JSON bloğunu handle eder — ilkini al)
    m = _JSON_RE.search(metin)
    if m:
        return m.group(0)

    # Fallback: basit { ... } ayıklama
    if "{" in metin and "}" in metin:
        return metin[metin.index("{") : metin.rindex("}") + 1]

    return metin


def gemini_cagir(
    cv_img: np.ndarray,
    prompt: str,
    api_key: str | None = None,
    deneme: int = 3,
) -> dict:
    """
    Gemini 2.5 Flash'a görüntü + prompt gönderir.
    Yanıtı JSON parse ederek dict döndürür.
    Hata durumunda {"hata": "<mesaj>"} döndürür.
    """
    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {"hata": "GEMINI_API_KEY bulunamadı"}

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )
    b64 = _kucult_ve_base64(cv_img)
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    log.info("Gemini API çağrısı başlıyor", extra={"deneme_sayisi": deneme})

    for d in range(deneme):
        try:
            resp = requests.post(url, json=body, timeout=30)
            if resp.status_code == 429:
                log.warning("Gemini rate limit — bekleniyor", extra={"deneme": d + 1})
                time.sleep(10)
                continue
            resp.raise_for_status()

            parts = resp.json()["candidates"][0]["content"]["parts"]
            # Extended Thinking açıkken parts[0] "thought" içerir, gerçek yanıt son parttadır
            metin: str = next(
                (p["text"] for p in reversed(parts) if not p.get("thought", False)),
                parts[-1].get("text", ""),
            ).strip()

            metin = _json_cıkar(metin)
            sonuc = json.loads(metin)
            log.info("Gemini API başarılı", extra={"deneme": d + 1})
            return sonuc

        except json.JSONDecodeError as exc:
            _ham = locals().get("metin", "")
            log.error("Gemini JSON parse hatası", extra={
                "deneme": d + 1,
                "hata": str(exc),
                "ham_metin": _ham[:200] if _ham else "",
            })
            if d < deneme - 1:
                time.sleep(2)
            else:
                return {"hata": f"JSON parse hatası: {exc}"}
        except requests.exceptions.Timeout as exc:
            log.warning("Gemini API zaman aşımı", extra={"deneme": d + 1})
            if d < deneme - 1:
                time.sleep(2)
            else:
                return {"hata": f"Zaman aşımı: {exc}"}
        except requests.exceptions.ConnectionError as exc:
            log.error("Gemini API bağlantı hatası", extra={"deneme": d + 1, "hata": str(exc)})
            if d < deneme - 1:
                time.sleep(2)
            else:
                return {"hata": f"Bağlantı hatası: {exc}"}
        except requests.exceptions.HTTPError as exc:
            log.error("Gemini HTTP hatası", extra={"deneme": d + 1, "hata": str(exc), "status": exc.response.status_code if exc.response else None})
            if d < deneme - 1:
                time.sleep(2)
            else:
                return {"hata": f"HTTP hatası: {exc}"}
        except (KeyError, IndexError, TypeError) as exc:
            log.error("Gemini yanıt yapısı beklenmedik", extra={"deneme": d + 1, "hata": str(exc)})
            if d < deneme - 1:
                time.sleep(2)
            else:
                return {"hata": f"Beklenmedik yanıt yapısı: {exc}"}
        except Exception as exc:  # noqa: BLE001
            # Ağ hatası, timeout vs. dahil beklenmedik tüm hatalar
            log.error("Gemini bilinmeyen hata", extra={"deneme": d + 1, "hata": str(exc), "tip": type(exc).__name__})
            if d < deneme - 1:
                time.sleep(2)
            else:
                return {"hata": str(exc)}

    return {"hata": "Tüm denemeler başarısız"}
