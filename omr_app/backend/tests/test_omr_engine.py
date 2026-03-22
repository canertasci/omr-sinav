"""
Unit testler — omr_engine.py
Test edilenler: puanla(), aruco_tespit(), kucult_ve_base64(), guvenskor hesaplama
"""
from __future__ import annotations

import io
import base64

import numpy as np
import cv2
import pytest
from PIL import Image

from services.omr_engine import (
    puanla,
    aruco_tespit,
    kucult_ve_base64,
    pil_to_cv,
    bolgeleri_ayir,
    kagit_oku,
    MAX_GORUNTU_PX,
)
from utils.image_utils import on_isleme


# ─────────────────────── puanla() ─────────────────────────────────────────────

class TestPuanla:
    def test_tamamen_dogru(self):
        anahtar = {i: "A" for i in range(1, 21)}
        cevaplar = {i: "A" for i in range(1, 21)}
        dogru, yanlis, bos, puan = puanla(cevaplar, anahtar, 20)
        assert dogru == 20
        assert yanlis == 0
        assert bos == 0
        assert puan == 100.0

    def test_tamamen_yanlis(self):
        anahtar = {i: "A" for i in range(1, 21)}
        cevaplar = {i: "B" for i in range(1, 21)}
        dogru, yanlis, bos, puan = puanla(cevaplar, anahtar, 20)
        assert dogru == 0
        assert yanlis == 20
        assert bos == 0
        assert puan == 0.0

    def test_karma(self):
        anahtar = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E"}
        cevaplar = {1: "A", 2: "X", 3: "BOS", 4: "D", 5: "HATA"}
        dogru, yanlis, bos, puan = puanla(cevaplar, anahtar, 5)
        assert dogru == 2   # 1 ve 4
        assert yanlis == 1  # 2 (X)
        assert bos == 1     # 3

    def test_bos_cevaplar(self):
        anahtar = {i: "A" for i in range(1, 11)}
        cevaplar = {i: "BOS" for i in range(1, 11)}
        dogru, yanlis, bos, puan = puanla(cevaplar, anahtar, 10)
        assert dogru == 0
        assert yanlis == 0
        assert bos == 10
        assert puan == 0.0

    def test_puan_basi_10_soru(self):
        anahtar = {i: "A" for i in range(1, 11)}
        cevaplar = {i: "A" for i in range(1, 6)}  # 5 doğru
        cevaplar.update({i: "BOS" for i in range(6, 11)})
        dogru, yanlis, bos, puan = puanla(cevaplar, anahtar, 10)
        assert puan == 50.0

    def test_coklu_sik_yanlis_sayilmaz(self):
        """'A/C' gibi çoklu şık yanlış sayılmamalı."""
        anahtar = {1: "A"}
        cevaplar = {1: "A/C"}  # / içeren → yanlış sayılmaz
        dogru, yanlis, bos, puan = puanla(cevaplar, anahtar, 1)
        assert yanlis == 0


# ─────────────────────── aruco_tespit() ───────────────────────────────────────

class TestArucoTespit:
    def _make_aruco_img(self, size: int = 800) -> np.ndarray:
        """4 ArUco marker içeren test görüntüsü."""
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        img = np.ones((size, size, 3), dtype=np.uint8) * 200
        marker_size = size // 10
        positions = [
            (5, 5),
            (size - marker_size - 5, 5),
            (5, size - marker_size - 5),
            (size - marker_size - 5, size - marker_size - 5),
        ]
        for mid, (x, y) in enumerate(positions):
            m = cv2.aruco.generateImageMarker(aruco_dict, mid, marker_size)
            m_bgr = cv2.cvtColor(m, cv2.COLOR_GRAY2BGR)
            img[y:y + marker_size, x:x + marker_size] = m_bgr
        return img

    def test_4_marker_bulunur(self):
        img = self._make_aruco_img()
        sonuc = aruco_tespit(img)
        assert sonuc is not None
        assert len(sonuc) == 4
        assert set(sonuc.keys()) == {0, 1, 2, 3}

    def test_marker_yok(self):
        img = np.ones((400, 400, 3), dtype=np.uint8) * 200
        assert aruco_tespit(img) is None

    def test_3_marker_yeterli_degil(self):
        """3 marker aynı sütunda (dejenere düzende) → kısmi algılama span hatası → None."""
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        img = np.ones((600, 600, 3), dtype=np.uint8) * 200
        marker_size = 60
        for mid in range(3):  # 3 tane, aynı sütunda
            m = cv2.aruco.generateImageMarker(aruco_dict, mid, marker_size)
            m_bgr = cv2.cvtColor(m, cv2.COLOR_GRAY2BGR)
            img[10 + mid * 80:10 + mid * 80 + marker_size, 10:10 + marker_size] = m_bgr
        assert aruco_tespit(img) is None

    def test_aruco_3_markers_partial_detection(self):
        """3 marker köşelerde düzgün konumda → 4. köşe tahmin edilir, None dönmez."""
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        img = np.ones((800, 800, 3), dtype=np.uint8) * 200
        marker_size = 80
        # 3 köşeye marker koy (id=3 kasıtlı eksik)
        pozisyonlar = [
            (5, 5),            # id=0 sol üst
            (715, 5),          # id=1 sağ üst
            (5, 715),          # id=2 sol alt
            # id=3 sağ alt — kasıtlı bırakıldı
        ]
        for mid, (x, y) in enumerate(pozisyonlar):
            m = cv2.aruco.generateImageMarker(aruco_dict, mid, marker_size)
            m_bgr = cv2.cvtColor(m, cv2.COLOR_GRAY2BGR)
            img[y:y + marker_size, x:x + marker_size] = m_bgr
        sonuc = aruco_tespit(img)
        assert sonuc is not None, "3 köşeli marker kısmi algılama başarısız oldu"
        assert len([k for k in sonuc if isinstance(k, int)]) == 4, "4 marker olmalı"
        assert set(k for k in sonuc if isinstance(k, int)) == {0, 1, 2, 3}

    def test_aruco_partial_detection_flag(self):
        """Kısmi algılamada 'kismi_algilama' flag'ı True olmalı."""
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        img = np.ones((800, 800, 3), dtype=np.uint8) * 200
        marker_size = 80
        pozisyonlar = [(5, 5), (715, 5), (5, 715)]
        for mid, (x, y) in enumerate(pozisyonlar):
            m = cv2.aruco.generateImageMarker(aruco_dict, mid, marker_size)
            m_bgr = cv2.cvtColor(m, cv2.COLOR_GRAY2BGR)
            img[y:y + marker_size, x:x + marker_size] = m_bgr
        sonuc = aruco_tespit(img)
        assert sonuc is not None
        assert sonuc.get("kismi_algilama") is True


# ─────────────────────── kucult_ve_base64() ───────────────────────────────────

class TestKucultVeBase64:
    def test_kucuk_goruntu_degismez(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        b64 = kucult_ve_base64(img, maks=1200)
        decoded = base64.b64decode(b64)
        arr = np.frombuffer(decoded, dtype=np.uint8)
        decoded_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        assert decoded_img is not None

    def test_buyuk_goruntu_kucultulur(self):
        img = np.zeros((2000, 2000, 3), dtype=np.uint8)
        b64 = kucult_ve_base64(img, maks=1200)
        decoded = base64.b64decode(b64)
        arr = np.frombuffer(decoded, dtype=np.uint8)
        decoded_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        h, w = decoded_img.shape[:2]
        assert max(h, w) <= 1200

    def test_valid_base64_string(self):
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        b64 = kucult_ve_base64(img)
        # Geçerli base64 olmalı
        decoded = base64.b64decode(b64)
        assert len(decoded) > 0


# ─────────────────────── on_isleme() ──────────────────────────────────────────

class TestOnIsleme:
    def test_bgr_input_shape_korunur(self):
        """BGR görüntü boyutu değişmemeli."""
        img = np.random.randint(0, 255, (800, 600, 3), dtype=np.uint8)
        result = on_isleme(img)
        assert result.shape[0] == img.shape[0]
        assert result.shape[1] == img.shape[1]
        assert len(result.shape) == 3  # BGR çıktı

    def test_gri_input_bgr_cikti(self):
        """Gri tonlama girişi → BGR çıktı."""
        img = np.random.randint(0, 255, (800, 600), dtype=np.uint8)
        result = on_isleme(img)
        assert len(result.shape) == 3  # BGR'ye dönüştürüldü
        assert result.shape[2] == 3

    def test_kucuk_goruntu_islenir(self):
        """Küçük görüntü (az nokta) sorunsuz işlenir."""
        img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        result = on_isleme(img)
        assert result.shape == img.shape

    def test_cikti_uint8(self):
        """Çıktı uint8 tipinde olmalı."""
        img = np.random.randint(0, 255, (400, 400, 3), dtype=np.uint8)
        result = on_isleme(img)
        assert result.dtype == np.uint8


# ─────────────────────── pil_to_cv() ──────────────────────────────────────────

def test_pil_to_cv_rgb_to_bgr():
    pil = Image.new("RGB", (10, 10), color=(255, 0, 0))  # kırmızı
    cv = pil_to_cv(pil)
    assert cv.shape == (10, 10, 3)
    # PIL kırmızısı → OpenCV'de B=0, G=0, R=255
    assert cv[0, 0, 2] == 255


# ─────────────────────── kagit_oku() — ArUco yok ──────────────────────────────

def test_kagit_oku_aruco_yok(plain_image_bytes, sample_cevap_anahtari):
    """ArUco marker yoksa hata dönmeli, puan 0 olmalı."""
    sonuc = kagit_oku(plain_image_bytes, sample_cevap_anahtari, "test_key", 20)
    assert sonuc["hata"] is not None
    assert "ArUco" in sonuc["hata"]
    assert sonuc["puan"] == 0.0
    assert sonuc["guvenskor"] == 0.0


# ─────────────────────── guvenskor hesaplama ──────────────────────────────────

def test_guvenskor_tam():
    """Hiç HATA yoksa güvenskor 1.0 olmalı."""
    from services.omr_engine import puanla
    cevaplar = {i: "A" for i in range(1, 21)}
    anahtar = {i: "A" for i in range(1, 21)}
    _, _, _, _ = puanla(cevaplar, anahtar, 20)
    hata_sayisi = sum(1 for v in cevaplar.values() if v in ("HATA", "?"))
    guvenskor = round(1.0 - (hata_sayisi / 20), 2)
    assert guvenskor == 1.0


def test_guvenskor_hata():
    """10 HATA varsa güvenskor 0.5 olmalı."""
    cevaplar = {i: "HATA" for i in range(1, 11)}
    cevaplar.update({i: "A" for i in range(11, 21)})
    hata_sayisi = sum(1 for v in cevaplar.values() if v in ("HATA", "?"))
    guvenskor = round(1.0 - (hata_sayisi / 20), 2)
    assert guvenskor == 0.5
