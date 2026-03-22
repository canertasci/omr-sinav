"""
Domain-specific exception sınıfları.
"""
from __future__ import annotations


class OMRBaseError(Exception):
    """Tüm OMR hatalarının base class'ı."""
    def __init__(self, message: str, detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or message


class OMRDetectionError(OMRBaseError):
    """Görüntü işleme veya ArUco marker tespiti başarısız."""
    pass


class InsufficientCreditsError(OMRBaseError):
    """Kullanıcının yeterli kredisi yok."""
    pass


class GeminiAPIError(OMRBaseError):
    """Gemini API iletişim veya parse hatası."""
    def __init__(self, message: str, raw_response: str | None = None):
        super().__init__(message)
        self.raw_response = raw_response


class ImageValidationError(OMRBaseError):
    """Görüntü validasyon hatası (boyut, format)."""
    pass


class FirestoreError(OMRBaseError):
    """Firestore işlem hatası."""
    pass
