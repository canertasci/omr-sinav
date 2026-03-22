"""
Unit testler — gemini_service.py
JSON parse, hata durumları, retry logic
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from services.gemini_service import gemini_cagir, _kucult_ve_base64


def _dummy_img(h=100, w=100):
    return np.zeros((h, w, 3), dtype=np.uint8)


def _mock_response(text: str, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": text}]}}]
    }
    resp.raise_for_status = MagicMock()
    return resp


class TestGeminiCagir:
    def test_basarili_json(self):
        """Geçerli JSON yanıtı dict olarak dönmeli."""
        payload = {"1": "A", "2": "B"}
        with patch("requests.post", return_value=_mock_response(json.dumps(payload))):
            sonuc = gemini_cagir(_dummy_img(), "test prompt", "fake_key")
        assert sonuc == payload

    def test_markdown_json_blogu_parse(self):
        """```json ... ``` içindeki JSON parse edilmeli."""
        payload = {"no": "123456789"}
        md_text = f"```json\n{json.dumps(payload)}\n```"
        with patch("requests.post", return_value=_mock_response(md_text)):
            sonuc = gemini_cagir(_dummy_img(), "test", "fake_key")
        assert sonuc == payload

    def test_on_metin_atlanir(self):
        """JSON'dan önce gelen metin atlanmalı."""
        payload = {"key": "value"}
        text = f"İşte sonuç: {json.dumps(payload)} Başka şey."
        with patch("requests.post", return_value=_mock_response(text)):
            sonuc = gemini_cagir(_dummy_img(), "test", "fake_key")
        assert sonuc == payload

    def test_api_key_yok(self):
        """API key olmadan hata dönmeli."""
        with patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
            sonuc = gemini_cagir(_dummy_img(), "test", "")
        assert "hata" in sonuc

    def test_rate_limit_retry(self):
        """429 alınca yeniden denenmeli."""
        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429

        payload = {"ok": True}
        success_resp = _mock_response(json.dumps(payload))

        call_count = [0]

        def mock_post(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return rate_limit_resp
            return success_resp

        with patch("requests.post", side_effect=mock_post), \
             patch("time.sleep"):  # sleep'i skip et
            sonuc = gemini_cagir(_dummy_img(), "test", "fake_key", deneme=3)
        assert sonuc == payload
        assert call_count[0] == 2

    def test_network_error_retry(self):
        """Network hatası olunca 3 kez denenmeli, sonunda hata dönmeli."""
        with patch("requests.post", side_effect=ConnectionError("network error")), \
             patch("time.sleep"):
            sonuc = gemini_cagir(_dummy_img(), "test", "fake_key", deneme=3)
        assert "hata" in sonuc

    def test_gecersiz_json_hata(self):
        """Parse edilemeyen yanıt hata dönmeli."""
        with patch("requests.post", return_value=_mock_response("Bu JSON değil!")), \
             patch("time.sleep"):
            sonuc = gemini_cagir(_dummy_img(), "test", "fake_key", deneme=1)
        assert "hata" in sonuc

    def test_tum_denemeler_baskisiz(self):
        """Tüm denemeler başarısız olunca 'Tüm denemeler başarısız' mesajı."""
        with patch("requests.post", side_effect=Exception("hata")), \
             patch("time.sleep"):
            sonuc = gemini_cagir(_dummy_img(), "test", "fake_key", deneme=2)
        assert "hata" in sonuc


class TestKucultVeBase64:
    def test_kucuk_goruntu(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = _kucult_ve_base64(img, maks=1200)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_buyuk_goruntu_kucultulur(self):
        import base64, cv2
        img = np.zeros((2000, 3000, 3), dtype=np.uint8)
        result = _kucult_ve_base64(img, maks=1200)
        decoded = base64.b64decode(result)
        arr = np.frombuffer(decoded, dtype=np.uint8)
        out_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        h, w = out_img.shape[:2]
        assert max(h, w) <= 1200
