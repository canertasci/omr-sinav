"""
Global exception handler testleri.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ─────────────────────────── OMRBaseError Alt Tipleri ────────────────────────

class TestOMRExceptionHandlers:
    def test_omr_detection_error_returns_422(self, client: TestClient, auth_headers: dict):
        """OMRDetectionError → 422 Unprocessable Entity."""
        from exceptions import OMRDetectionError
        import services.firebase_service as fb

        with patch.object(fb, "sinav_getir", side_effect=OMRDetectionError("Test tespit hatası")):
            resp = client.get("/api/v1/results/sinav123", headers=auth_headers)
        assert resp.status_code == 422
        assert "detail" in resp.json()

    def test_insufficient_credits_returns_402(self, client: TestClient, auth_headers: dict):
        """InsufficientCreditsError → 402 Payment Required."""
        from exceptions import InsufficientCreditsError
        import services.firebase_service as fb

        with patch.object(
            fb, "kullanici_getir", side_effect=InsufficientCreditsError("Kredi yetersiz")
        ):
            resp = client.get("/api/v1/credits/balance", headers=auth_headers)
        assert resp.status_code == 402

    def test_image_validation_error_returns_400(self, client: TestClient, auth_headers: dict):
        """ImageValidationError → 400 Bad Request."""
        from exceptions import ImageValidationError
        import services.firebase_service as fb

        with patch.object(
            fb, "sinav_getir", side_effect=ImageValidationError("Görüntü geçersiz")
        ):
            resp = client.get("/api/v1/results/sinav123", headers=auth_headers)
        assert resp.status_code == 400

    def test_gemini_api_error_returns_502(self, client: TestClient, auth_headers: dict):
        """GeminiAPIError → 502 Bad Gateway."""
        from exceptions import GeminiAPIError
        import services.firebase_service as fb

        with patch.object(
            fb, "sinav_getir", side_effect=GeminiAPIError("Gemini API hatası")
        ):
            resp = client.get("/api/v1/results/sinav123", headers=auth_headers)
        assert resp.status_code == 502

    def test_omr_base_error_without_subtype_returns_500(self, client: TestClient, auth_headers: dict):
        """OMRBaseError direkt kullanımı → 500."""
        from exceptions import OMRBaseError
        import services.firebase_service as fb

        with patch.object(fb, "sinav_getir", side_effect=OMRBaseError("Bilinmeyen OMR hatası")):
            resp = client.get("/api/v1/results/sinav123", headers=auth_headers)
        assert resp.status_code == 500

    def test_error_response_has_detail_field(self, client: TestClient, auth_headers: dict):
        """Hata yanıtı 'detail' alanı içermeli."""
        from exceptions import OMRDetectionError
        import services.firebase_service as fb

        with patch.object(fb, "sinav_getir", side_effect=OMRDetectionError("marker yok")):
            resp = client.get("/api/v1/results/sinav123", headers=auth_headers)
        body = resp.json()
        assert "detail" in body
        assert isinstance(body["detail"], str)


class TestGeneralExceptionHandler:
    def test_unhandled_exception_returns_500(self, client_no_raise: TestClient, auth_headers: dict):
        """İşlenmemiş exception → 500 Internal Server Error."""
        import services.firebase_service as fb

        with patch.object(fb, "sinav_getir", side_effect=RuntimeError("Beklenmedik hata")):
            resp = client_no_raise.get("/api/v1/results/sinav123", headers=auth_headers)
        assert resp.status_code == 500

    def test_unhandled_exception_detail_is_generic(self, client_no_raise: TestClient, auth_headers: dict):
        """500 yanıtı iç hata detayını sızdırmamalı."""
        import services.firebase_service as fb

        with patch.object(
            fb, "sinav_getir", side_effect=ValueError("gizli iç hata bilgisi")
        ):
            resp = client_no_raise.get("/api/v1/results/sinav123", headers=auth_headers)
        body = resp.json()
        assert "detail" in body
        # İç hata mesajı sızdırılmamalı
        assert "gizli iç hata bilgisi" not in body["detail"]
