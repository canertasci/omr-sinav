"""
SQLite veritabanı context manager ve yardımcı fonksiyonlar.
Tüm sayfalarda `with get_db() as con:` şeklinde kullanılır.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

import streamlit as st

DB_YOLU = os.path.join(os.getcwd(), "omr.db")

# ─── Context Manager ──────────────────────────────────────────────────────────

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    SQLite bağlantısını context manager ile yönetir.
    Hata olursa rollback, başarılıysa commit yapar ve her durumda kapatır.

    Kullanım:
        with get_db() as con:
            con.execute(...)
    """
    con = sqlite3.connect(DB_YOLU)
    con.row_factory = sqlite3.Row  # Sözlük benzeri erişim
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ─── Pahalı Sorgular (cache'li) ───────────────────────────────────────────────

@st.cache_data(ttl=300)  # 5 dakika cache
def sablonlari_getir(kullanici_id: int) -> list[dict]:
    """Kullanıcının şablonlarını getirir (5 dk cache)."""
    with get_db() as con:
        rows = con.execute(
            "SELECT id, ad, soru_sayisi, tarih FROM sablonlar WHERE kullanici_id=? ORDER BY tarih DESC",
            (kullanici_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@st.cache_data(ttl=300)
def cevap_anahtarlarini_getir(kullanici_id: int) -> list[dict]:
    """Kullanıcının cevap anahtarlarını getirir (5 dk cache)."""
    with get_db() as con:
        rows = con.execute(
            "SELECT id, ad, soru_sayisi, tarih FROM cevap_anahtarlari WHERE kullanici_id=? ORDER BY tarih DESC",
            (kullanici_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@st.cache_data(ttl=60)
def son_taramalari_getir(kullanici_id: int, limit: int = 20) -> list[dict]:
    """Son tarama kayıtlarını getirir (1 dk cache)."""
    with get_db() as con:
        rows = con.execute(
            """SELECT t.id, t.anahtar_adi, t.toplam_kagit, t.basarili, t.tarih
               FROM taramalar t
               WHERE t.kullanici_id=?
               ORDER BY t.tarih DESC
               LIMIT ?""",
            (kullanici_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def cache_temizle() -> None:
    """Tüm cache'leri temizler (veri değişikliği sonrası çağır)."""
    sablonlari_getir.clear()
    cevap_anahtarlarini_getir.clear()
    son_taramalari_getir.clear()
