"""
Merkezi konfigürasyon — pydantic-settings ile Settings sınıfı.
Tüm magic number'lar ve ortam değişkenleri burada tanımlıdır.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Ortam ─────────────────────────────────────────────────────────────────
    environment: str = "development"
    log_level: str = "INFO"

    # ── API Anahtarları ────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    firebase_service_account_json: str = ""
    firebase_service_account_json_b64: str = ""
    firebase_service_account_path: str = "firebase_service_account.json"

    # ── Auth ───────────────────────────────────────────────────────────────────
    skip_auth: bool = False

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: str = ""

    # ── Görüntü İşleme ────────────────────────────────────────────────────────
    tarama_dpi: int = 150
    max_goruntu_px: int = 1200
    max_upload_size_mb: int = 10    # Görüntü yükleme limiti (MB)
    max_excel_size_mb: int = 5      # Excel upload limiti (MB)

    # ── OMR Eşikleri ──────────────────────────────────────────────────────────
    guven_esigi: float = 0.70       # Bu altındaki güven skoru uyarı tetikler
    benzerlik_esigi: float = 0.85   # İsim eşleştirme benzerlik eşiği

    # ── Batch İşleme ──────────────────────────────────────────────────────────
    max_batch_size: int = 30
    thread_workers: int = 5

    # ── Kredi ─────────────────────────────────────────────────────────────────
    initial_free_credits: int = 500
    ad_reward_credits: int = 10

    # ── Admin (Streamlit) ──────────────────────────────────────────────────────
    admin_initial_password: str = ""

    # ── Sentry ────────────────────────────────────────────────────────────────
    sentry_dsn: str = ""

    # ── Hesaplanan özellikler ─────────────────────────────────────────────────
    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def max_excel_size_bytes(self) -> int:
        return self.max_excel_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.cors_origins:
            return ["*"] if not self.is_production else []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Singleton Settings instance — uygulama boyunca aynı nesne kullanılır."""
    return Settings()


# Pratik import alias
settings = get_settings()
