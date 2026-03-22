"""
FastAPI TestClient testleri — /api/v1/results/*
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


SINAV_ID = "sinav_test_001"
SINAV_MOCK = {
    "id": SINAV_ID,
    "ogretmen_id": "dev_user_001",
    "ad": "TestSinavi",
    "soru_sayisi": 5,
    "cevap_anahtari": {"1": "A", "2": "B", "3": "C", "4": "D", "5": "E"},
}
SONUCLAR_MOCK = [
    {
        "id": "s1",
        "ogrenci_no": "123456789",
        "ad_soyad": "Ali Veli",
        "puan": 80.0,
        "guvenskor": 0.9,
        "dogru": 4, "yanlis": 1, "bos": 0,
        "cevaplar": {"1": "A", "2": "B", "3": "C", "4": "D", "5": "A"},
    },
    {
        "id": "s2",
        "ogrenci_no": "987654321",
        "ad_soyad": "Ayşe Fatma",
        "puan": 60.0,
        "guvenskor": 0.8,
        "dogru": 3, "yanlis": 2, "bos": 0,
        "cevaplar": {"1": "A", "2": "X", "3": "C", "4": "X", "5": "E"},
    },
]


class TestGetResults:
    def test_sonuc_listesi(self, client, auth_headers):
        with patch("services.firebase_service.sinav_getir", return_value=SINAV_MOCK), \
             patch("services.firebase_service.sinav_sonuclari", return_value=SONUCLAR_MOCK):
            resp = client.get(f"/api/v1/results/{SINAV_ID}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["toplam"] == 2
        assert len(data["sonuclar"]) == 2

    def test_sinav_bulunamadi(self, client, auth_headers):
        with patch("services.firebase_service.sinav_getir", return_value=None):
            resp = client.get(f"/api/v1/results/{SINAV_ID}", headers=auth_headers)
        assert resp.status_code == 404

    def test_yetki_hatasi(self, client, auth_headers):
        """Başka öğretmenin sınavına erişim 403 döndürmeli."""
        baska_sinav = {**SINAV_MOCK, "ogretmen_id": "baska_ogretmen"}
        with patch("services.firebase_service.sinav_getir", return_value=baska_sinav):
            resp = client.get(f"/api/v1/results/{SINAV_ID}", headers=auth_headers)
        assert resp.status_code == 403


class TestGetStatistics:
    def test_istatistik_hesaplama(self, client, auth_headers):
        with patch("services.firebase_service.sinav_getir", return_value=SINAV_MOCK), \
             patch("services.firebase_service.sinav_sonuclari", return_value=SONUCLAR_MOCK):
            resp = client.get(f"/api/v1/results/{SINAV_ID}/statistics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ogrenci_sayisi"] == 2
        assert data["ortalama"] == 70.0
        assert data["min_puan"] == 60.0
        assert data["max_puan"] == 80.0

    def test_sonuc_yok_404(self, client, auth_headers):
        with patch("services.firebase_service.sinav_getir", return_value=SINAV_MOCK), \
             patch("services.firebase_service.sinav_sonuclari", return_value=[]):
            resp = client.get(f"/api/v1/results/{SINAV_ID}/statistics", headers=auth_headers)
        assert resp.status_code == 404

    def test_standart_sapma_tek_ogrenci(self, client, auth_headers):
        """Tek öğrenci varsa standart sapma 0.0 olmalı."""
        tek = [SONUCLAR_MOCK[0]]
        with patch("services.firebase_service.sinav_getir", return_value=SINAV_MOCK), \
             patch("services.firebase_service.sinav_sonuclari", return_value=tek):
            resp = client.get(f"/api/v1/results/{SINAV_ID}/statistics", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["standart_sapma"] == 0.0


class TestExcelExport:
    def test_excel_export(self, client, auth_headers):
        with patch("services.firebase_service.sinav_getir", return_value=SINAV_MOCK), \
             patch("services.firebase_service.sinav_sonuclari", return_value=SONUCLAR_MOCK):
            resp = client.get(f"/api/v1/results/{SINAV_ID}/export", headers=auth_headers)
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]
        assert len(resp.content) > 0
