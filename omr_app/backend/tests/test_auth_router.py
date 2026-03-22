"""
FastAPI TestClient testleri — /api/v1/auth/*
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


class TestAuthRegister:
    def test_yeni_kullanici_kayit(self, client, auth_headers, mock_firebase_db):
        """Yeni kullanıcı kaydı 500 kredi ile oluşturulmalı."""
        kullanici_doc = MagicMock()
        kullanici_doc.exists = False

        with patch("services.firebase_service.kullanici_getir", return_value=None), \
             patch("services.firebase_service.kullanici_olustur", return_value={
                 "uid": "dev_user_001",
                 "email": "dev@example.com",
                 "tam_ad": "Test User",
                 "kredi": 500,
             }):
            resp = client.post(
                "/api/v1/auth/register",
                json={"tam_ad": "Test User", "kullanici_tipi": "bireysel"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["kredi"] == 500
        assert data["uid"] == "dev_user_001"

    def test_mevcut_kullanici_guncellenmez(self, client, auth_headers):
        """Zaten kayıtlı kullanıcı için güncelleme yapılmamalı."""
        with patch("services.firebase_service.kullanici_getir", return_value={
            "uid": "dev_user_001",
            "tam_ad": "Mevcut Kullanıcı",
            "kredi": 300,
        }), patch("services.firebase_service.son_giris_guncelle"):
            resp = client.post(
                "/api/v1/auth/register",
                json={"tam_ad": "Mevcut Kullanıcı"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mesaj"] == "Mevcut kullanıcı"

    def test_gecersiz_kullanici_tipi(self, client, auth_headers):
        """Geçersiz kullanıcı_tipi 422 döndürmeli."""
        resp = client.post(
            "/api/v1/auth/register",
            json={"tam_ad": "Test", "kullanici_tipi": "GECERSIZ"},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestAuthMe:
    def test_mevcut_kullanici(self, client, auth_headers):
        """Kayıtlı kullanıcı bilgileri dönmeli."""
        with patch("services.firebase_service.kullanici_getir", return_value={
            "uid": "dev_user_001",
            "email": "dev@example.com",
            "kredi": 100,
        }):
            resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["uid"] == "dev_user_001"

    def test_kayitsiz_kullanici_404(self, client, auth_headers):
        """Kayıtsız kullanıcı 404 almalı."""
        with patch("services.firebase_service.kullanici_getir", return_value=None):
            resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 404
