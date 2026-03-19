"""
Gemini 2.5 Flash API wrapper.
GEMINI_API_KEY .env'den okunur.
"""
from __future__ import annotations

import base64
import json
import os
import time

import cv2
import numpy as np
import requests

MAX_GORUNTU_PX = 1200


def _kucult_ve_base64(cv_img: np.ndarray, maks: int = MAX_GORUNTU_PX) -> str:
    h, w = cv_img.shape[:2]
    if max(h, w) > maks:
        oran = maks / max(h, w)
        cv_img = cv2.resize(cv_img, (int(w * oran), int(h * oran)))
    _, buf = cv2.imencode(".jpg", cv_img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return base64.b64encode(buf).decode("utf-8")


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
            "thinkingConfig": {"thinkingBudget": 1024},
        },
    }

    for d in range(deneme):
        try:
            resp = requests.post(url, json=body, timeout=30)
            if resp.status_code == 429:
                time.sleep(10)
                continue
            resp.raise_for_status()

            metin: str = (
                resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            )

            # Markdown kod bloğundan JSON çıkar
            if "```" in metin:
                for parca in metin.split("```"):
                    parca = parca.strip()
                    if parca.startswith("json"):
                        parca = parca[4:].strip()
                    if parca.startswith("{"):
                        metin = parca.strip()
                        break

            # Eğer JSON başlamadan önce metin varsa kırp
            if "{" in metin and "}" in metin:
                metin = metin[metin.index("{") : metin.rindex("}") + 1]

            return json.loads(metin)

        except Exception as exc:
            if d < deneme - 1:
                time.sleep(2)
            else:
                return {"hata": str(exc)}

    return {"hata": "Tüm denemeler başarısız"}
