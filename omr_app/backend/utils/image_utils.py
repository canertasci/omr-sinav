"""
Görüntü yardımcı fonksiyonları — tek canonical versiyon.
omr_engine.py ve gemini_service.py tarafından kullanılır.
"""
from __future__ import annotations

import base64

import cv2
import numpy as np
from fastapi import HTTPException

# ─────────────────────────── Ön İşleme ───────────────────────────────────────


def on_isleme(cv_img: np.ndarray) -> np.ndarray:
    """
    Tarama öncesi görüntü iyileştirme: adaptif kontrast + eğiklik düzeltme.

    1. CLAHE ile yerel kontrast güçlendirir
    2. minAreaRect ile eğim açısını tespit edip 0.5° üzerindeki eğimi düzeltir
    3. BGR görüntü döner (ArUco algılama için)

    Args:
        cv_img: BGR veya gri tonlama OpenCV görüntüsü

    Returns:
        İyileştirilmiş BGR görüntü, orijinal boyut korunur
    """
    if len(cv_img.shape) == 3:
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = cv_img.copy()

    # 1. Adaptif kontrast iyileştirme (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 2. Eğiklik tespiti ve düzeltme (deskew)
    _, binary = cv2.threshold(
        enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    coords = np.column_stack(np.where(binary > 0))

    if len(coords) > 500:
        angle = cv2.minAreaRect(coords)[-1]
        # minAreaRect açıyı −90..0 arasında verir; 0 ya da −90 yakınındakileri düzelt
        if angle < -45:
            angle = 90 + angle
        if abs(angle) > 0.5:  # 0.5° altındaki eğimi görmezden gel
            h, w = enhanced.shape[:2]
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            enhanced = cv2.warpAffine(
                enhanced, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

# Varsayılan sabitler (config.py kullanılmaya başlandığında oradan gelecek)
_DEFAULT_MAX_PX = 1200
_DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def kucult_ve_base64(
    cv_img: np.ndarray,
    maks: int = _DEFAULT_MAX_PX,
    jpeg_kalite: int = 90,
) -> str:
    """
    OpenCV görüntüsünü isteğe bağlı olarak küçültür,
    JPEG'e encode edip base64 string döner.

    Args:
        cv_img: BGR formatında OpenCV görüntüsü
        maks: Uzun kenar için maksimum piksel sayısı
        jpeg_kalite: JPEG kalitesi (1-100)
    """
    h, w = cv_img.shape[:2]
    if max(h, w) > maks:
        oran = maks / max(h, w)
        cv_img = cv2.resize(cv_img, (int(w * oran), int(h * oran)))
    _, buf = cv2.imencode(".jpg", cv_img, [cv2.IMWRITE_JPEG_QUALITY, jpeg_kalite])
    return base64.b64encode(buf).decode("utf-8")


def decode_base64_image(b64: str, max_bytes: int = _DEFAULT_MAX_BYTES) -> bytes:
    """
    Base64 string'i bytes'a çevirir.
    data:image/... prefix varsa temizler.
    Boyut kontrolü uygular: aşarsa HTTPException(413) fırlatır.

    Args:
        b64: Base64 kodlu görüntü string'i
        max_bytes: Maksimum izin verilen byte sayısı
    """
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    raw = base64.b64decode(b64)
    if len(raw) > max_bytes:
        mb = len(raw) / (1024 * 1024)
        max_mb = max_bytes / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Görüntü boyutu {mb:.1f}MB — maksimum {max_mb:.0f}MB izin verilir.",
        )
    return raw
