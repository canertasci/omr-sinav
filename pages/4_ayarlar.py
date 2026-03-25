"""
Ayarlar & Kullanıcı Yönetimi Sayfası.
"""
from __future__ import annotations

import os
import sys

import bcrypt
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils_st.auth import giris_gerekli, mevcut_kullanici, cikis_yap
from utils_st.db import get_db
from utils_st.ui import css_uygula, sidebar_goster

giris_gerekli()

st.set_page_config(page_title="Ayarlar — OMR", layout="centered")
css_uygula()
sidebar_goster()

kullanici = mevcut_kullanici()
uid: int = kullanici["id"]
kadi: str = kullanici["kullanici_adi"]

st.header("⚙️ Ayarlar & Kullanıcı Yönetimi")
st.write(f"Giriş yapan: **{kullanici['tam_ad']}** (`{kadi}`)")
st.divider()

tab_sifre, tab_kullanici = st.tabs(["🔐 Şifre Değiştir", "👤 Kullanıcı Yönetimi"])

# ─────────────────────────── ŞİFRE ────────────────────────────────────────────
with tab_sifre:
    with st.form("sifre_form"):
        mevcut_sifre = st.text_input("Mevcut Şifre", type="password")
        yeni_sifre   = st.text_input("Yeni Şifre", type="password")
        yeni_sifre2  = st.text_input("Yeni Şifre (Tekrar)", type="password")
        gonder = st.form_submit_button("Değiştir", type="primary")

    if gonder:
        if yeni_sifre != yeni_sifre2:
            st.error("Yeni şifreler eşleşmiyor!")
        elif len(yeni_sifre) < 6:
            st.error("Şifre en az 6 karakter olmalı.")
        else:
            with get_db() as con:
                satir = con.execute(
                    "SELECT sifre_hash FROM kullanicilar WHERE id=?", (uid,)
                ).fetchone()
            if satir and bcrypt.checkpw(mevcut_sifre.encode(), satir["sifre_hash"].encode()):
                yeni_hash = bcrypt.hashpw(yeni_sifre.encode(), bcrypt.gensalt()).decode()
                with get_db() as con:
                    con.execute(
                        "UPDATE kullanicilar SET sifre_hash=? WHERE id=?", (yeni_hash, uid)
                    )
                st.success("Şifre güncellendi!")
            else:
                st.error("Mevcut şifre hatalı!")

# ─────────────────────────── KULLANICI YÖNETİMİ ──────────────────────────────
with tab_kullanici:
    with st.container(border=True):
        st.subheader("Yeni Kullanıcı Ekle")
        yadi = st.text_input("Kullanıcı Adı", key="yeni_kadi")
        ytam = st.text_input("Ad Soyad", key="yeni_tam")
        ysif = st.text_input("Şifre", type="password", key="yeni_sif")
        if st.button("Kullanıcı Ekle", type="primary"):
            if yadi and ysif:
                try:
                    sh = bcrypt.hashpw(ysif.encode(), bcrypt.gensalt()).decode()
                    with get_db() as con:
                        con.execute(
                            "INSERT INTO kullanicilar (kullanici_adi,sifre_hash,tam_ad) VALUES (?,?,?)",
                            (yadi, sh, ytam),
                        )
                    st.success(f"'{yadi}' eklendi!")
                except Exception:
                    st.error("Bu kullanıcı adı zaten var!")
            else:
                st.warning("Kullanıcı adı ve şifre gerekli!")

    st.divider()
    with get_db() as con:
        kullanicilar = con.execute(
            "SELECT id, kullanici_adi, tam_ad FROM kullanicilar ORDER BY id"
        ).fetchall()
    st.subheader(f"Kayıtlı Kullanıcılar ({len(kullanicilar)})")
    for k in kullanicilar:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{k[2] or k[1]}** (`{k[1]}`)")
        if k[0] != uid and c2.button("Sil", key=f"usr_sil_{k[0]}"):
            with get_db() as con:
                con.execute("DELETE FROM kullanicilar WHERE id=?", (k[0],))
            st.rerun()

st.divider()
if st.button("🚪 Çıkış Yap", type="secondary"):
    cikis_yap()
