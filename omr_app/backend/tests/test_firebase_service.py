"""
Unit testler — firebase_service.py (Firestore CRUD mock)
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest


@pytest.fixture
def mock_db():
    """Firestore client mock'u."""
    db = MagicMock()
    return db


@pytest.fixture
def patched_fb(mock_db):
    """firebase_service._get_db'yi mock_db ile patch'le."""
    with patch("services.firebase_service._get_db", return_value=mock_db):
        import services.firebase_service as fb
        yield fb, mock_db


class TestKullanici:
    def test_kullanici_olustur(self, patched_fb):
        fb, db = patched_fb
        with patch.dict("os.environ", {"INITIAL_FREE_CREDITS": "500"}):
            kullanici = fb.kullanici_olustur("uid1", "test@x.com", "Ad Soyad")
        assert kullanici["kredi"] == 500
        assert kullanici["uid"] == "uid1"
        # Firestore set çağrılmalı
        db.collection.assert_any_call("users")

    def test_kullanici_getir_var(self, patched_fb):
        fb, db = patched_fb
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"uid": "uid1", "kredi": 200}
        db.collection.return_value.document.return_value.get.return_value = doc

        sonuc = fb.kullanici_getir("uid1")
        assert sonuc["kredi"] == 200

    def test_kullanici_getir_yok(self, patched_fb):
        fb, db = patched_fb
        doc = MagicMock()
        doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = doc

        sonuc = fb.kullanici_getir("yok")
        assert sonuc is None


class TestKredi:
    def test_kredi_oku(self, patched_fb):
        fb, db = patched_fb
        with patch.object(fb, "kullanici_getir", return_value={"kredi": 150}):
            kredi = fb.kredi_oku("uid1")
        assert kredi == 150

    def test_kredi_oku_kullanici_yok(self, patched_fb):
        fb, db = patched_fb
        with patch.object(fb, "kullanici_getir", return_value=None):
            kredi = fb.kredi_oku("yok")
        assert kredi == 0

    def test_cift_harcama_token_kontrol(self, patched_fb):
        fb, db = patched_fb
        # Token bulunuyor
        db.collection.return_value.where.return_value.limit.return_value.get.return_value = [MagicMock()]
        assert fb.satin_alma_Token_kullanildi_mi("token") is True

    def test_cift_harcama_token_yok(self, patched_fb):
        fb, db = patched_fb
        db.collection.return_value.where.return_value.limit.return_value.get.return_value = []
        assert fb.satin_alma_Token_kullanildi_mi("yeni_token") is False


class TestSinavSonuc:
    def test_sonuc_kaydet(self, patched_fb):
        fb, db = patched_fb
        mock_ref = MagicMock()
        mock_ref.id = "sonuc_123"
        db.collection.return_value.add.return_value = (None, mock_ref)

        sonuc_id = fb.sonuc_kaydet({
            "sinav_id": "s1",
            "ogrenci_no": "12345",
            "puan": 85.0,
        })
        assert sonuc_id == "sonuc_123"

    def test_sinav_getir_yok(self, patched_fb):
        fb, db = patched_fb
        doc = MagicMock()
        doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = doc

        assert fb.sinav_getir("yok") is None
