"""
FastAPI TestClient testleri — /api/v1/credits/*
Kredi bakiyesi, kredi kesimi, çift harcama önleme
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


class TestBalance:
    def test_bakiye_doner(self, client, auth_headers):
        with patch("services.firebase_service.kullanici_getir", return_value={
            "uid": "dev_user_001",
            "kredi": 250,
            "toplam_kullanilan": 50,
        }):
            resp = client.get("/api/v1/credits/balance", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["kredi"] == 250
        assert data["toplam_kullanilan"] == 50

    def test_kullanici_yok_404(self, client, auth_headers):
        with patch("services.firebase_service.kullanici_getir", return_value=None):
            resp = client.get("/api/v1/credits/balance", headers=auth_headers)
        assert resp.status_code == 404


class TestVerifyPurchase:
    def test_gecerli_satin_alma(self, client, auth_headers):
        with patch("services.firebase_service.satin_alma_Token_kullanildi_mi", return_value=False), \
             patch("services.firebase_service.kredi_ekle", return_value=2000):
            resp = client.post(
                "/api/v1/credits/verify-purchase",
                json={"product_id": "credits_1500", "purchase_token": "token_abc123"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["yeni_kredi"] == 2000

    def test_cift_harcama_onleme(self, client, auth_headers):
        """Aynı token iki kez kullanılırsa 409 döner."""
        with patch("services.firebase_service.satin_alma_Token_kullanildi_mi", return_value=True):
            resp = client.post(
                "/api/v1/credits/verify-purchase",
                json={"product_id": "credits_1500", "purchase_token": "kullanilmis_token"},
                headers=auth_headers,
            )
        assert resp.status_code == 409

    def test_gecersiz_urun_id(self, client, auth_headers):
        resp = client.post(
            "/api/v1/credits/verify-purchase",
            json={"product_id": "gecersiz_urun", "purchase_token": "token123"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_gecerli_urun_idler(self, client, auth_headers):
        """Tüm geçerli ürün ID'leri kabul edilmeli."""
        gecerli = ["credits_1500", "credits_3000", "credits_10000"]
        for pid in gecerli:
            with patch("services.firebase_service.satin_alma_Token_kullanildi_mi", return_value=False), \
                 patch("services.firebase_service.kredi_ekle", return_value=1000):
                resp = client.post(
                    "/api/v1/credits/verify-purchase",
                    json={"product_id": pid, "purchase_token": f"tok_{pid}"},
                    headers=auth_headers,
                )
            assert resp.status_code == 200, f"{pid} için başarısız"


class TestRewardAd:
    def test_reklam_kredisi(self, client, auth_headers):
        with patch("services.firebase_service.kredi_ekle", return_value=510):
            resp = client.post("/api/v1/credits/reward-ad", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "+10" in data["mesaj"]
