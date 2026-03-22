"""
Streamlit kimlik doğrulama yardımcıları.
"""
from __future__ import annotations

import bcrypt
import streamlit as st

from utils_st.db import get_db


def giris_kontrol(kullanici_adi: str, sifre: str) -> dict | None:
    """
    Kullanıcı adı ve şifreyi kontrol eder.
    Başarılıysa kullanıcı dict'ini döner, değilse None.
    """
    with get_db() as con:
        satir = con.execute(
            "SELECT id, sifre_hash, tam_ad FROM kullanicilar WHERE kullanici_adi=?",
            (kullanici_adi,),
        ).fetchone()

    if satir and bcrypt.checkpw(sifre.encode(), satir["sifre_hash"].encode()):
        return {
            "id": satir["id"],
            "kullanici_adi": kullanici_adi,
            "tam_ad": satir["tam_ad"],
        }
    return None


def giris_gerekli() -> bool:
    """
    Giriş yapılmış mı kontrol eder.
    Yapılmamışsa uyarı gösterir ve True döner (sayfayı durdur).
    """
    if "kullanici" not in st.session_state or not st.session_state.kullanici:
        st.warning("Bu sayfayı görmek için giriş yapmanız gerekiyor.")
        st.stop()
        return True
    return False


def mevcut_kullanici() -> dict | None:
    """Oturumda bulunan kullanıcıyı döner."""
    return st.session_state.get("kullanici")


def cikis_yap() -> None:
    """Oturumu temizler."""
    st.session_state.pop("kullanici", None)
    st.session_state.pop("giris_saati", None)
    st.rerun()
