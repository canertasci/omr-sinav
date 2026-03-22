"""
Test fixtures — mock Firebase, mock Gemini, FastAPI TestClient
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import base64
import io

import pytest
import numpy as np
import cv2

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

# ─── Env defaults (before any imports that read env) ─────────────────────────
os.environ.setdefault("SKIP_AUTH", "true")
os.environ.setdefault("GEMINI_API_KEY", "test_key_123")
os.environ.setdefault("ENVIRONMENT", "test")

# ─── Mock firebase_admin before any module imports it ────────────────────────
firebase_mock = MagicMock()
sys.modules.setdefault("firebase_admin", firebase_mock)
sys.modules.setdefault("firebase_admin.credentials", MagicMock())
sys.modules.setdefault("firebase_admin.auth", MagicMock())
sys.modules.setdefault("firebase_admin.firestore", MagicMock())
sys.modules.setdefault("firebase_admin.exceptions", MagicMock())


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_aruco_image() -> bytes:
    """4 ArUco marker içeren sahte bir test görüntüsü oluştur."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    img = np.ones((800, 600, 3), dtype=np.uint8) * 200  # gri arka plan

    marker_size = 60
    positions = [
        (10, 10),    # id=0 sol üst
        (530, 10),   # id=1 sağ üst
        (10, 730),   # id=2 sol alt
        (530, 730),  # id=3 sağ alt
    ]

    for marker_id, (x, y) in enumerate(positions):
        marker = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size)
        marker_bgr = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
        img[y:y + marker_size, x:x + marker_size] = marker_bgr

    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def _make_plain_image() -> bytes:
    """ArUco marker içermeyen düz görüntü."""
    img = np.ones((400, 400, 3), dtype=np.uint8) * 180
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def _to_b64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode()


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def aruco_image_bytes() -> bytes:
    return _make_aruco_image()


@pytest.fixture
def plain_image_bytes() -> bytes:
    return _make_plain_image()


@pytest.fixture
def aruco_image_b64(aruco_image_bytes) -> str:
    return _to_b64(aruco_image_bytes)


@pytest.fixture
def plain_image_b64(plain_image_bytes) -> str:
    return _to_b64(plain_image_bytes)


@pytest.fixture
def sample_cevap_anahtari() -> dict[str, str]:
    return {str(i): ch for i, ch in enumerate(
        ["A", "B", "C", "D", "E", "A", "B", "C", "D", "E",
         "A", "B", "C", "D", "E", "A", "B", "C", "D", "E"], 1
    )}


@pytest.fixture
def mock_firebase_db():
    """Firestore mock döner."""
    db = MagicMock()
    # Kullanıcı belgesi
    user_doc = MagicMock()
    user_doc.exists = True
    user_doc.to_dict.return_value = {
        "uid": "dev_user_001",
        "email": "dev@example.com",
        "tam_ad": "Test Kullanıcı",
        "kredi": 500,
        "toplam_kullanilan": 0,
    }
    db.collection.return_value.document.return_value.get.return_value = user_doc

    # Kredi işlemi transaction
    trans = MagicMock()
    db.transaction.return_value = trans

    return db


@pytest.fixture
def mock_gemini_response():
    """Başarılı Gemini yanıtını mock'la."""
    return {"1": "A", "2": "B", "3": "C", "4": "D", "5": "E",
            "6": "A", "7": "B", "8": "C", "9": "D", "10": "E",
            "11": "A", "12": "B", "13": "C", "14": "D", "15": "E",
            "16": "A", "17": "B", "18": "C", "19": "D", "20": "E"}


@pytest.fixture
def client(mock_firebase_db):
    """FastAPI TestClient — Firebase mock'lanmış."""
    from unittest.mock import patch as _patch
    import services.firebase_service as fb

    with _patch.object(fb, "_get_db", return_value=mock_firebase_db):
        from fastapi.testclient import TestClient
        from main import app
        with TestClient(app) as c:
            yield c


@pytest.fixture
def client_no_raise(mock_firebase_db):
    """FastAPI TestClient — raise_server_exceptions=False (exception handler testleri için)."""
    from unittest.mock import patch as _patch
    import services.firebase_service as fb

    with _patch.object(fb, "_get_db", return_value=mock_firebase_db):
        from fastapi.testclient import TestClient
        from main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """SKIP_AUTH=true olduğunda geçerli header'lar."""
    return {"Authorization": "Bearer test_token"}
