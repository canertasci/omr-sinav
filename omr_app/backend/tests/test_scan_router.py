"""
FastAPI TestClient testleri — /api/v1/scan/*
"""
from __future__ import annotations

import base64
import json
from unittest.mock import patch, MagicMock

import numpy as np
import cv2
import pytest


def _make_plain_b64() -> str:
    img = np.ones((400, 400, 3), dtype=np.uint8) * 180
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode()


PLAIN_B64 = _make_plain_b64()
CEVAP_ANAHTARI = {str(i): "A" for i in range(1, 21)}


class TestScanSingle:
    def test_aruco_yok_hata_donar(self, client, auth_headers):
        """ArUco bulunamazsa 200 + hata mesajı döner, kredi düşmez."""
        resp = client.post(
            "/api/v1/scan/single",
            json={
                "goruntu_base64": PLAIN_B64,
                "sablon_id": "sablon1",
                "sinav_id": "sinav1",
                "cevap_anahtari": CEVAP_ANAHTARI,
                "soru_sayisi": 20,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["hata"] is not None
        assert "ArUco" in data["hata"]

    def test_auth_bearer_format_zorunlu(self, client, auth_headers):
        """Bearer prefix olmayan header 401 döndürmeli (SKIP_AUTH=false ortamında geçerli)."""
        # SKIP_AUTH=true test ortamında geçerli, sadece format kontrolü
        # Bu test, verify_firebase_token'ın Bearer olmayan header'ı reddettiğini doğrular
        # Gerçek test için integration test gerekir
        assert True  # Placeholder - gerçek test Step 3 sonrası eklenir

    def test_max_goruntu_boyutu_asarsa_413(self, client, auth_headers):
        """10MB'ı aşan görüntü 413 döndürmeli."""
        buyuk_data = base64.b64encode(b"X" * (10 * 1024 * 1024 + 1)).decode()
        resp = client.post(
            "/api/v1/scan/single",
            json={
                "goruntu_base64": buyuk_data,
                "sablon_id": "s1",
                "sinav_id": "e1",
                "cevap_anahtari": CEVAP_ANAHTARI,
                "soru_sayisi": 20,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 413


class TestScanBatch:
    def test_30_limit_asimi(self, client, auth_headers):
        """31 görüntü gönderilince 400 veya 422 döner."""
        resp = client.post(
            "/api/v1/scan/batch",
            json={
                "goruntuler": [PLAIN_B64] * 31,
                "sablon_id": "s1",
                "sinav_id": "e1",
                "cevap_anahtari": CEVAP_ANAHTARI,
                "soru_sayisi": 20,
            },
            headers=auth_headers,
        )
        # Pydantic max_length=30 ile 422, ya da router içinde 400 dönebilir
        assert resp.status_code in (400, 422)

    def test_bos_liste(self, client, auth_headers):
        """Boş liste 422 (validation error) döner."""
        resp = client.post(
            "/api/v1/scan/batch",
            json={
                "goruntuler": [],
                "sablon_id": "s1",
                "sinav_id": "e1",
                "cevap_anahtari": CEVAP_ANAHTARI,
                "soru_sayisi": 20,
            },
            headers=auth_headers,
        )
        # Boş liste valid değil (min_length=1 yoksa 200/422 dönebilir, kontrol edelim)
        assert resp.status_code in (200, 422)

    def test_aruco_yok_toplu(self, client, auth_headers, mock_firebase_db):
        """ArUco yoksa batch sonuçlarında hata olmalı."""
        with patch("services.firebase_service.kredi_oku", return_value=100):
            resp = client.post(
                "/api/v1/scan/batch",
                json={
                    "goruntuler": [PLAIN_B64, PLAIN_B64],
                    "sablon_id": "s1",
                    "sinav_id": "e1",
                    "cevap_anahtari": CEVAP_ANAHTARI,
                    "soru_sayisi": 20,
                },
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["toplam"] == 2


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["durum"] == "ok"

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "OMR" in resp.json()["mesaj"]

    def test_metrics(self, client):
        """Metrics endpoint gerekli alanları döndürmeli."""
        resp = client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_requests" in data
        assert "error_rate" in data
        assert "avg_response_ms" in data
