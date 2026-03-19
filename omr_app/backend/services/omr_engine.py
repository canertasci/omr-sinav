"""
OMR Engine — Optik İşaret Tanıma Motoru
Mevcut çalışan kodu aynen taşır, sadece modüler yapıya uyarlanmıştır.
"""
from __future__ import annotations

import io
import base64

import cv2
import numpy as np
from PIL import Image

from services.gemini_service import gemini_cagir

# ─────────────────────────── Sabitler ────────────────────────────────

TARAMA_DPI = 300
MAX_GORUNTU_PX = 1200

ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ARUCO_PARAMS = cv2.aruco.DetectorParameters()
ARUCO_DETEK = cv2.aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMS)

# ─────────────────────────── Görüntü Yardımcıları ────────────────────

def pil_to_cv(pil_img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def kucult_ve_base64(cv_img: np.ndarray, maks: int = MAX_GORUNTU_PX) -> str:
    h, w = cv_img.shape[:2]
    if max(h, w) > maks:
        oran = maks / max(h, w)
        cv_img = cv2.resize(cv_img, (int(w * oran), int(h * oran)))
    _, buf = cv2.imencode(".jpg", cv_img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return base64.b64encode(buf).decode("utf-8")


# ─────────────────────────── ArUco Tespiti ───────────────────────────

def aruco_tespit(cv_img: np.ndarray) -> dict | None:
    gri = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = ARUCO_DETEK.detectMarkers(gri)
    if ids is None or len(ids) < 4:
        return None
    markerlar: dict[int, np.ndarray] = {}
    for i, mid in enumerate(ids.flatten()):
        if mid in [0, 1, 2, 3]:
            markerlar[int(mid)] = corners[i][0]
    return markerlar if len(markerlar) == 4 else None


# ─────────────────────────── 4 Bölgeye Ayırma ────────────────────────

def bolgeleri_ayir(cv_img: np.ndarray, markerlar: dict) -> dict[int, np.ndarray]:
    """
    Her marker'ın DIŞ köşesi alınır.
    Döner:
        0 → Sol üst  — öğrenci bilgi (el yazısı)
        1 → Sağ üst  — öğrenci no grid (9×10)
        2 → Sol alt  — sorular 1–N/2
        3 → Sağ alt  — sorular N/2+1–N
    """
    dis_kose = {
        0: markerlar[0][0],  # sol üst marker'ın SOL ÜST köşesi
        1: markerlar[1][1],  # sağ üst marker'ın SAĞ ÜST köşesi
        2: markerlar[2][3],  # sol alt marker'ın SOL ALT köşesi
        3: markerlar[3][2],  # sağ alt marker'ın SAĞ ALT köşesi
    }
    x_sol = int(dis_kose[0][0])
    x_sag = int(dis_kose[1][0])
    y_ust = int(dis_kose[0][1])
    y_alt = int(dis_kose[2][1])
    x_orta = int((x_sol + x_sag) / 2)
    y_orta = int((y_ust + y_alt) / 2)

    return {
        0: cv_img[y_ust:y_orta, x_sol:x_orta],
        1: cv_img[y_ust:y_orta, x_orta:x_sag],
        2: cv_img[y_orta:y_alt, x_sol:x_orta],
        3: cv_img[y_orta:y_alt, x_orta:x_sag],
    }


# ─────────────────────────── Öğrenci No ──────────────────────────────

PROMPT_NO = """
Bu görüntüde bir öğrenci numarası balon tablosu var.
- 9 SÜTUN (soldan sağa = 1. hane, 2. hane, ..., 9. hane)
- 10 SATIR (yukarıdan aşağı = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 rakamları)
- Her sütunda KESINLIKLE YALNIZCA BİR balon dolu olmalıdır.
- Dolu balon = tamamen siyah veya koyu dolgulu daire.
- Her sütunu BAĞIMSIZ olarak değerlendirip en koyu balonu bul.
SADECE JSON dön, başka hiçbir şey yazma:
{"no": "123456789"}
"""


def ogrenci_no_oku(bolge_img: np.ndarray, api_key: str) -> str:
    h, w = bolge_img.shape[:2]
    # Bölgeyi 1.5x büyüt — Gemini daha net görür
    buyuk = cv2.resize(bolge_img, (int(w * 1.5), int(h * 1.5)),
                       interpolation=cv2.INTER_CUBIC)
    sonuc = gemini_cagir(buyuk, PROMPT_NO, api_key)
    if not isinstance(sonuc, dict) or "hata" in sonuc:
        return "?????????"
    no = str(sonuc.get("no", "?????????")).replace("null", "?")
    return no[:9].ljust(9, "?")


# ─────────────────────────── Cevap Okuma ─────────────────────────────

def cevap_prompt(soru_bas: int, soru_bit: int) -> str:
    return f"""
Bu görüntüde {soru_bas} ile {soru_bit} arasındaki soruların cevap balonları var.
- Her satır bir soru, her satırda A B C D E şıkları var.
- Her satırda YALNIZCA BİR balon dolu olmalıdır (en koyu olan).
- Birden fazla eşit koyulukta balon varsa hepsini yaz (örneğin "A/C").
- Hiç dolu balon yoksa "BOS" yaz.
SADECE JSON dön:
{{"{soru_bas}": "A", "{soru_bas + 1}": "BOS", ..., "{soru_bit}": "C"}}
"""


def cevap_oku(bolge_img: np.ndarray, soru_bas: int, soru_bit: int, api_key: str) -> dict[int, str]:
    sonuc = gemini_cagir(bolge_img, cevap_prompt(soru_bas, soru_bit), api_key)
    if not isinstance(sonuc, dict) or "hata" in sonuc:
        return {i: "HATA" for i in range(soru_bas, soru_bit + 1)}
    return {int(k): str(v).upper() for k, v in sonuc.items() if str(k).isdigit()}


# ─────────────────────────── Bilgi Okuma ─────────────────────────────

PROMPT_BILGI = """
Bu görüntüde öğrenci bilgi formu var.
Ad Soyad, Bölüm/Program ve Ders Adı alanlarını oku. El yazısı olabilir.
SADECE JSON dön:
{"ad_soyad": "Ad Soyad", "bolum": "Bölüm", "ders": "Ders"}
"""


def bilgi_oku(bolge_img: np.ndarray, api_key: str) -> dict[str, str]:
    sonuc = gemini_cagir(bolge_img, PROMPT_BILGI, api_key)
    if not isinstance(sonuc, dict) or "hata" in sonuc:
        return {"ad_soyad": "?", "bolum": "?", "ders": "?"}
    return sonuc


# ─────────────────────────── Puanlama ────────────────────────────────

def puanla(
    cevaplar: dict[int, str],
    anahtar: dict[int, str],
    soru_sayisi: int,
) -> tuple[int, int, int, float]:
    puan_basi = 100 / soru_sayisi
    dogru = sum(
        1 for s in range(1, soru_sayisi + 1)
        if cevaplar.get(s) == anahtar.get(s)
    )
    yanlis = sum(
        1 for s in range(1, soru_sayisi + 1)
        if cevaplar.get(s) not in (anahtar.get(s), "BOS", "HATA")
        and "/" not in str(cevaplar.get(s, ""))
    )
    bos = sum(
        1 for s in range(1, soru_sayisi + 1)
        if cevaplar.get(s) == "BOS"
    )
    puan = round(dogru * puan_basi, 2)
    return dogru, yanlis, bos, puan


# ─────────────────────────── Ana Pipeline ────────────────────────────

def kagit_oku(
    goruntu_bytes: bytes,
    cevap_anahtari: dict,
    api_key: str,
    soru_sayisi: int = 20,
) -> dict:
    """
    goruntu_bytes : bytes (JPEG / PNG / HEIC-converted)
    cevap_anahtari: {1: "A", 2: "C", ...}  ya da {"1": "A", ...}
    Döner         : dict (ogrenci_no, ad_soyad, cevaplar, dogru, yanlis, bos, puan, guvenskor, hata)
    """
    # Anahtarların int olduğundan emin ol
    anahtar_int: dict[int, str] = {int(k): str(v).upper() for k, v in cevap_anahtari.items()}

    pil_img = Image.open(io.BytesIO(goruntu_bytes))
    cv_img = pil_to_cv(pil_img)
    markerlar = aruco_tespit(cv_img)

    if markerlar is None:
        return {
            "ogrenci_no": "?????????",
            "ad_soyad": "?",
            "bolum": "?",
            "ders": "?",
            "cevaplar": {str(i): "HATA" for i in range(1, soru_sayisi + 1)},
            "dogru": 0,
            "yanlis": 0,
            "bos": soru_sayisi,
            "puan": 0.0,
            "guvenskor": 0.0,
            "hata": "ArUco marker bulunamadı — kağıt düzgün çekilmemiş olabilir",
        }

    bolgeler = bolgeleri_ayir(cv_img, markerlar)
    bilgi = bilgi_oku(bolgeler[0], api_key)
    ogrenci_no = ogrenci_no_oku(bolgeler[1], api_key)

    orta = soru_sayisi // 2
    cevaplar: dict[int, str] = {}
    cevaplar.update(cevap_oku(bolgeler[2], 1, orta, api_key))
    cevaplar.update(cevap_oku(bolgeler[3], orta + 1, soru_sayisi, api_key))

    dogru, yanlis, bos, puan = puanla(cevaplar, anahtar_int, soru_sayisi)

    hata_sayisi = sum(1 for v in cevaplar.values() if v in ("HATA", "?"))
    guvenskor = round(1.0 - (hata_sayisi / soru_sayisi), 2)

    return {
        "ogrenci_no": ogrenci_no,
        "ad_soyad": bilgi.get("ad_soyad", "?"),
        "bolum": bilgi.get("bolum", "?"),
        "ders": bilgi.get("ders", "?"),
        "cevaplar": {str(k): v for k, v in cevaplar.items()},
        "dogru": dogru,
        "yanlis": yanlis,
        "bos": bos,
        "puan": puan,
        "guvenskor": guvenskor,
        "hata": None,
    }
