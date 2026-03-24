"""
OMR Engine — Optik İşaret Tanıma Motoru
Mevcut çalışan kodu aynen taşır, sadece modüler yapıya uyarlanmıştır.
"""
from __future__ import annotations

import io
import base64

import cv2
import numpy as np
from PIL import Image, ImageOps

from services.gemini_service import gemini_cagir
from utils.image_utils import kucult_ve_base64 as _kucult_b64, on_isleme
from utils.logger import get_logger
from utils import prompts
from config import settings
from exceptions import OMRDetectionError

log = get_logger("omr.engine")

# ─────────────────────────── Sabitler ────────────────────────────────

TARAMA_DPI = settings.tarama_dpi
MAX_GORUNTU_PX = settings.max_goruntu_px
GUVEN_ESIGI = settings.guven_esigi

ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ARUCO_PARAMS = cv2.aruco.DetectorParameters()
ARUCO_DETEK = cv2.aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMS)

# ─────────────────────────── Görüntü Yardımcıları ────────────────────

def pil_to_cv(pil_img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def kucult_ve_base64(cv_img: np.ndarray, maks: int = MAX_GORUNTU_PX) -> str:
    """image_utils canonical versiyonuna yönlendirir."""
    return _kucult_b64(cv_img, maks=maks)


# ─────────────────────────── ArUco Tespiti ───────────────────────────

MIN_GORUNTU_PX = 500  # Minimum görüntü boyutu


# 3-of-4 partial detection: eksik köşe tahmini formülleri
# Layout: 0=TL, 1=TR, 2=BL, 3=BR
# tahmin = a + b - c  (dikdörtgen kenar vektörü)
_TAHMIN_FORMULLER: dict[int, tuple[int, int, int]] = {
    0: (1, 2, 3),  # TL = TR + BL - BR
    1: (0, 3, 2),  # TR = TL + BR - BL
    2: (0, 3, 1),  # BL = TL + BR - TR
    3: (1, 2, 0),  # BR = TR + BL - TL
}


def aruco_tespit(cv_img: np.ndarray) -> dict | None:
    """
    4 ArUco marker'ı (ID 0-3) tespit eder.
    - Minimum 500×500 px görüntü kontrolü
    - Marker pozisyon doğrulaması (x_sol < x_sag, y_ust < y_alt)
    - 4 marker bulunamazsa None döner
    - 3 marker bulunursa geometrik tahmin ile 4.'yü hesaplar (kismi_algilama=True)
    """
    h, w = cv_img.shape[:2]
    if h < MIN_GORUNTU_PX or w < MIN_GORUNTU_PX:
        log.warning("Görüntü çok küçük", extra={"boyut": f"{w}x{h}", "min": MIN_GORUNTU_PX})
        return None

    gri = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = ARUCO_DETEK.detectMarkers(gri)
    bulunan = ids.flatten().tolist() if ids is not None else []
    log.info("ArUco algılama", extra={"bulunan_ids": bulunan, "toplam": len(bulunan), "boyut": f"{w}x{h}"})
    if ids is None or len(ids) < 3:
        log.warning("Yetersiz ArUco marker", extra={"bulunan": len(bulunan), "gerekli": 3})
        return None

    markerlar: dict[int, np.ndarray] = {}
    for i, mid in enumerate(ids.flatten()):
        if mid in [0, 1, 2, 3]:
            markerlar[int(mid)] = corners[i][0]

    kismi_algilama = False

    if len(markerlar) == 4:
        pass  # Normal yol
    elif len(markerlar) == 3:
        bulunan_idler = set(markerlar.keys())
        eksik_id = ({0, 1, 2, 3} - bulunan_idler).pop()
        a_id, b_id, c_id = _TAHMIN_FORMULLER[eksik_id]
        tahmin: np.ndarray = markerlar[a_id] + markerlar[b_id] - markerlar[c_id]

        # Geometrik geçerlilik: tüm 4 merkez yeterli alan kapsıyor mu?
        test_markerlar = dict(markerlar)
        test_markerlar[eksik_id] = tahmin
        merkezler_x = [test_markerlar[i].mean(axis=0)[0] for i in range(4)]
        merkezler_y = [test_markerlar[i].mean(axis=0)[1] for i in range(4)]
        span_x = max(merkezler_x) - min(merkezler_x)
        span_y = max(merkezler_y) - min(merkezler_y)
        if span_x < w * 0.25 or span_y < h * 0.25:
            log.warning(
                "3-marker kısmi algılama: yetersiz kapsam → None",
                extra={"span_x_pct": round(span_x / w * 100, 1),
                       "span_y_pct": round(span_y / h * 100, 1)},
            )
            return None

        markerlar[eksik_id] = tahmin
        kismi_algilama = True
        log.warning(
            "3/4 marker bulundu, 4. köşe tahmin edildi",
            extra={"eksik_id": eksik_id, "tahmin_merkez": tahmin.mean(axis=0).tolist()},
        )
    else:
        return None

    # Pozisyon doğrulama: x_sol < x_sag, y_ust < y_alt
    try:
        x_sol = markerlar[0][0][0]
        x_sag = markerlar[1][1][0]
        y_ust = markerlar[0][0][1]
        y_alt = markerlar[2][3][1]

        if x_sol >= x_sag:
            log.warning("ArUco pozisyon hatası: sol marker sağ markerin sağında")
            return None
        if y_ust >= y_alt:
            log.warning("ArUco pozisyon hatası: üst marker alt markerin altında")
            return None
    except (KeyError, IndexError) as exc:
        log.error("ArUco pozisyon doğrulama hatası", extra={"hata": str(exc)})
        return None

    if kismi_algilama:
        markerlar["kismi_algilama"] = True  # type: ignore[assignment]
    return markerlar


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

PROMPT_NO = prompts.OGRENCI_NO


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
    return prompts.cevap_balonlari(soru_bas, soru_bit)


def cevap_oku(bolge_img: np.ndarray, soru_bas: int, soru_bit: int, api_key: str) -> dict[int, str]:
    sonuc = gemini_cagir(bolge_img, cevap_prompt(soru_bas, soru_bit), api_key)
    if not isinstance(sonuc, dict) or "hata" in sonuc:
        return {i: "HATA" for i in range(soru_bas, soru_bit + 1)}
    return {int(k): str(v).upper() for k, v in sonuc.items() if str(k).isdigit()}


# ─────────────────────────── Bilgi Okuma ─────────────────────────────

PROMPT_BILGI = prompts.OGRENCI_BILGI
PROMPT_GRUP = prompts.SINAV_GRUBU


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

def sinav_grubu_oku(bolge_img: np.ndarray, api_key: str) -> str | None:
    """Sol üst bölgeden sınav grubunu (A/B/C/D) tespit eder."""
    sonuc = gemini_cagir(bolge_img, PROMPT_GRUP, api_key)
    if isinstance(sonuc, dict) and "hata" not in sonuc:
        tespit = str(sonuc.get("sinav_grubu", "YOK")).strip().upper()
        if tespit in ("A", "B", "C", "D"):
            return tespit
    return None


def kagit_oku(
    goruntu_bytes: bytes,
    cevap_anahtari: dict,
    api_key: str,
    soru_sayisi: int = 20,
    grup_anahtarlari: dict[str, dict] | None = None,
) -> dict:
    """
    goruntu_bytes : bytes (JPEG / PNG / HEIC-converted)
    cevap_anahtari: {1: "A", 2: "C", ...}  ya da {"1": "A", ...}  — varsayılan anahtar
    grup_anahtarlari: {"A": {1: "A", ...}, "B": {...}} — grup bazlı anahtarlar (opsiyonel)
    Döner         : dict (ogrenci_no, ad_soyad, sinav_grubu, cevaplar, dogru, yanlis, bos, puan, guvenskor, hata)
    """
    # Anahtarların int olduğundan emin ol
    anahtar_int: dict[int, str] = {int(k): str(v).upper() for k, v in cevap_anahtari.items()}

    try:
        pil_img = Image.open(io.BytesIO(goruntu_bytes))
        # Telefon kamerası EXIF rotasyon bilgisi ekler — PIL bunu otomatik uygulamaz.
        # exif_transpose görüntüyü doğru yönde döndürür, marker algılama için kritik.
        pil_img = ImageOps.exif_transpose(pil_img)
    except Exception as exc:
        log.warning("Görüntü açılamadı", extra={"hata": str(exc)})
        return {
            "ogrenci_no": "?????????",
            "ad_soyad": "?", "bolum": "?", "ders": "?",
            "cevaplar": {str(i): "HATA" for i in range(1, soru_sayisi + 1)},
            "dogru": 0, "yanlis": 0, "bos": soru_sayisi,
            "puan": 0.0, "guvenskor": 0.0,
            "hata": f"Görüntü açılamadı: {exc}",
        }

    cv_img = pil_to_cv(pil_img)
    h, w = cv_img.shape[:2]
    log.info("Görüntü boyutu", extra={"genislik": w, "yukseklik": h, "format": pil_img.format})
    markerlar = aruco_tespit(cv_img)
    kismi_algilama: bool = isinstance(markerlar, dict) and bool(markerlar.pop("kismi_algilama", False))

    if markerlar is None:
        log.warning("ArUco marker bulunamadı")
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
            "hata": (
                "ArUco marker bulunamadı. Lütfen şunları kontrol edin:\n"
                "• Kağıt 4 köşesindeki kare marker'lar görünür olmalı\n"
                "• Görüntü net ve iyi aydınlatılmış olmalı\n"
                "• Kağıt eğimli veya kırışık olmamalı\n"
                "• En az 500×500 piksel çözünürlük gereklidir"
            ),
        }

    bolgeler = bolgeleri_ayir(cv_img, markerlar)

    # Kısmi hata kurtarma: her bölge bağımsız işlenir
    bilgi = bilgi_oku(bolgeler[0], api_key)
    ogrenci_no = ogrenci_no_oku(bolgeler[1], api_key)

    # Sınav grubu tespiti (sadece grup anahtarları varsa)
    sinav_grubu: str | None = None
    if grup_anahtarlari:
        sinav_grubu = sinav_grubu_oku(bolgeler[0], api_key)
        log.info("Sınav grubu tespiti", extra={"sinav_grubu": sinav_grubu})

    # Doğru cevap anahtarını seç
    kullanilan_anahtar = anahtar_int
    if sinav_grubu and grup_anahtarlari and sinav_grubu in grup_anahtarlari:
        kullanilan_anahtar = {int(k): str(v).upper() for k, v in grup_anahtarlari[sinav_grubu].items()}

    orta = soru_sayisi // 2
    cevaplar: dict[int, str] = {}

    # Sol cevap bölgesi
    try:
        cevaplar.update(cevap_oku(bolgeler[2], 1, orta, api_key))
    except Exception as exc:
        log.error("Sol cevap bölgesi okunamadı", extra={"hata": str(exc)})
        cevaplar.update({i: "HATA" for i in range(1, orta + 1)})

    # Sağ cevap bölgesi
    try:
        cevaplar.update(cevap_oku(bolgeler[3], orta + 1, soru_sayisi, api_key))
    except Exception as exc:
        log.error("Sağ cevap bölgesi okunamadı", extra={"hata": str(exc)})
        cevaplar.update({i: "HATA" for i in range(orta + 1, soru_sayisi + 1)})

    dogru, yanlis, bos, puan = puanla(cevaplar, kullanilan_anahtar, soru_sayisi)

    hata_sayisi = sum(1 for v in cevaplar.values() if v in ("HATA", "?"))
    guvenskor = round(1.0 - (hata_sayisi / soru_sayisi), 2)

    return {
        "ogrenci_no": ogrenci_no,
        "ad_soyad": bilgi.get("ad_soyad", "?"),
        "bolum": bilgi.get("bolum", "?"),
        "ders": bilgi.get("ders", "?"),
        "sinav_grubu": sinav_grubu,
        "cevaplar": {str(k): v for k, v in cevaplar.items()},
        "dogru": dogru,
        "yanlis": yanlis,
        "bos": bos,
        "puan": puan,
        "guvenskor": guvenskor,
        "kismi_algilama": kismi_algilama,
        "hata": None,
    }
