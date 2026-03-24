"""
OMR Ana Uygulama — giriş sayfası + ana sayfa (dashboard).
Sınav, şablon ve geçmiş işlemleri pages/ dizinindeki sayfalarda.
"""
import json
import os
import sqlite3

import bcrypt
import pandas as pd
import streamlit as st
from datetime import datetime

DB_YOLU = os.path.join(os.getcwd(), "omr.db")
TARAMA_DPI = 150
POPPLER_PATH = (
    r"C:\PYTHON_GENEL\OMR\poppler\poppler-24.08.0\Library\bin"
    if os.name == "nt"
    else None
)


# ─── VERİTABANI ─────────────────────────────────────────────

def db_bag() -> sqlite3.Connection:
    """Geriye dönük uyumluluk. Yeni kod utils_st.db.get_db() kullanmalı."""
    return sqlite3.connect(DB_YOLU)


def db_olustur() -> None:
    """İlk çalıştırmada DB şeması ve admin kullanıcısını oluşturur."""
    con = db_bag()
    con.executescript(
        "CREATE TABLE IF NOT EXISTS kullanicilar ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "kullanici_adi TEXT UNIQUE NOT NULL,"
        "sifre_hash TEXT NOT NULL,"
        "tam_ad TEXT);"
        "CREATE TABLE IF NOT EXISTS sablonlar ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "kullanici_id INTEGER, ad TEXT NOT NULL,"
        "soru_sayisi INTEGER DEFAULT 20,"
        "tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
        "CREATE TABLE IF NOT EXISTS cevap_anahtarlari ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "kullanici_id INTEGER, sablon_id INTEGER,"
        "ad TEXT NOT NULL, grup TEXT DEFAULT NULL,"
        "cevaplar TEXT NOT NULL,"
        "tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
        "CREATE TABLE IF NOT EXISTS ogrenci_listeleri ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "kullanici_id INTEGER, ad TEXT NOT NULL,"
        "ogrenciler TEXT NOT NULL,"
        "tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
        "CREATE TABLE IF NOT EXISTS taramalar ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "kullanici_id INTEGER, anahtar_id INTEGER,"
        "anahtar_adi TEXT, sablon_adi TEXT, soru_sayisi INTEGER,"
        "cevap_anahtari TEXT, toplam_kagit INTEGER, basarili INTEGER,"
        "tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
        "CREATE TABLE IF NOT EXISTS tarama_sonuclari ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "tarama_id INTEGER, sayfa INTEGER, ad_soyad TEXT,"
        "ogrenci_no TEXT, cevaplar TEXT, dogru INTEGER, yanlis INTEGER,"
        "bos INTEGER, puan REAL, durum TEXT, hata TEXT,"
        "sinav_grubu TEXT DEFAULT NULL);"
    )
    # Migration: mevcut DB'lere yeni sütunları ekle
    for _mig in [
        "ALTER TABLE cevap_anahtarlari ADD COLUMN grup TEXT DEFAULT NULL",
        "ALTER TABLE tarama_sonuclari ADD COLUMN sinav_grubu TEXT DEFAULT NULL",
    ]:
        try:
            con.execute(_mig)
        except sqlite3.OperationalError:
            pass  # sütun zaten var

    _admin_sifre = os.getenv("ADMIN_INITIAL_PASSWORD", "")
    if _admin_sifre:
        _hash = bcrypt.hashpw(_admin_sifre.encode(), bcrypt.gensalt()).decode()
        con.execute(
            "INSERT OR IGNORE INTO kullanicilar (kullanici_adi,sifre_hash,tam_ad) VALUES (?,?,?)",
            ("admin", _hash, "Yönetici"),
        )
    con.commit()
    con.close()


# ─── GİRİŞ ──────────────────────────────────────────────────

def giris_kontrol(adi: str, sifre: str) -> dict | None:
    con = db_bag()
    satir = con.execute(
        "SELECT id,sifre_hash,tam_ad FROM kullanicilar WHERE kullanici_adi=?", (adi,)
    ).fetchone()
    con.close()
    if satir and bcrypt.checkpw(sifre.encode(), satir[1].encode()):
        return {"id": satir[0], "kullanici_adi": adi, "tam_ad": satir[2]}
    return None


def giris_sayfasi() -> None:
    st.markdown("""
    <style>
    .ana{text-align:center;color:#1a237e;font-size:2.8rem;font-weight:900;margin-top:3rem;}
    .alt{text-align:center;color:#5c6bc0;font-size:1rem;margin-top:4px;}
    .uni{text-align:center;color:#9e9e9e;font-size:0.85rem;margin-bottom:2rem;}
    </style>
    <div class="ana">🎓 ÖğretmenAI</div>
    <div class="alt">Sınav Değerlendirme Sistemi</div>
    <div class="uni">Yalova Üniversitesi</div>
    """, unsafe_allow_html=True)
    _, orta, _ = st.columns([1, 2, 1])
    with orta:
        with st.container(border=True):
            st.subheader("Giriş Yap")
            adi   = st.text_input("Kullanıcı Adı")
            sifre = st.text_input("Şifre", type="password")
            if st.button("Giriş Yap", use_container_width=True, type="primary"):
                k = giris_kontrol(adi, sifre)
                if k:
                    st.session_state.kullanici = k
                    st.session_state.giris_saati = datetime.now().strftime("%H:%M")
                    st.rerun()
                else:
                    st.error("Kullanıcı adı veya şifre hatalı!")
            st.caption("İlk çalıştırmada ADMIN_INITIAL_PASSWORD env değişkeni ile şifre belirleyin.")


# ─── ANA SAYFA (Dashboard) ───────────────────────────────────

@st.cache_data(ttl=60)
def _dashboard_verileri(uid: int) -> tuple:
    con = db_bag()
    sablon_sayisi  = con.execute("SELECT COUNT(*) FROM sablonlar WHERE kullanici_id=?", (uid,)).fetchone()[0]
    tarama_sayisi  = con.execute("SELECT COUNT(*) FROM taramalar WHERE kullanici_id=?", (uid,)).fetchone()[0]
    listeler       = con.execute("SELECT ogrenciler FROM ogrenci_listeleri WHERE kullanici_id=?", (uid,)).fetchall()
    son_taramalar  = con.execute(
        "SELECT t.anahtar_adi, t.sablon_adi, t.toplam_kagit, t.basarili, t.tarih, "
        "ROUND(COALESCE(AVG(s.puan),0),1) "
        "FROM taramalar t LEFT JOIN tarama_sonuclari s ON t.id=s.tarama_id "
        "WHERE t.kullanici_id=? GROUP BY t.id ORDER BY t.id DESC LIMIT 5", (uid,)
    ).fetchall()
    con.close()
    ogrenci_sayisi = sum(len(json.loads(r[0])) for r in listeler)
    return sablon_sayisi, tarama_sayisi, ogrenci_sayisi, son_taramalar


# ─── UYGULAMA GİRİŞ NOKTASI ─────────────────────────────────

st.set_page_config(
    page_title="ÖğretmenAI | OMR Sistemi",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)
try:
    from utils_st.ui import css_uygula, sidebar_goster
except Exception as _imp_err:
    import traceback as _tb
    st.error(f"Import hatası: {_imp_err}")
    st.code(_tb.format_exc())
    st.stop()

db_olustur()
css_uygula()  # her zaman uygula — login sayfasında da nav'ı gizlemek için

if "kullanici" not in st.session_state:
    # Giriş yapılmamışken sidebar navigasyonu tamamen gizle
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stSidebarNavItems"] { display: none !important; }
    header [data-testid="stSidebarCollapsedControl"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)
    giris_sayfasi()
else:
    sidebar_goster()
    k = st.session_state.kullanici

    # ─── Dashboard İçeriği ───────────────────────────────────
    st.header("Ana Sayfa")
    st.divider()
    uid = k["id"]
    try:
        sablon_sayisi, tarama_sayisi, ogrenci_sayisi, son_taramalar = _dashboard_verileri(uid)
        c1, c2, c3 = st.columns(3)
        c1.metric("📐 Şablon Sayısı", sablon_sayisi)
        c2.metric("👥 Toplam Öğrenci", ogrenci_sayisi)
        c3.metric("📊 Toplam Tarama", tarama_sayisi)
        st.divider()
        st.subheader("Son 5 Tarama")
        if son_taramalar:
            df = pd.DataFrame(
                son_taramalar,
                columns=["Cevap Anahtarı", "Şablon", "Toplam Kağıt", "Başarılı", "Tarih", "Ort. Puan"],
            )
            df["Tarih"] = df["Tarih"].str[:16]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Henüz tarama yapılmamış.")
    except Exception as e:
        st.error(f"Hata: {e}")
