"""
OMR Tarama Sayfası — PDF yükleme, sınav okuma, sonuç gösterimi.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from typing import Any

import pandas as pd
import streamlit as st
from pdf2image import convert_from_path

# Proje kök dizinini ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils_st.auth import giris_gerekli, mevcut_kullanici
from utils_st.db import get_db
from utils_st.excel import excel_detay, excel_ozet
from utils_st.omr import get_gemini_key, kagit_oku_web
from utils_st.ui import css_uygula, sidebar_goster

giris_gerekli()

st.set_page_config(page_title="Sınav Oku — OMR", layout="wide")
css_uygula()
sidebar_goster()

kullanici = mevcut_kullanici()
uid: int = kullanici["id"]

POPPLER_PATH = (
    r"C:\PYTHON_GENEL\OMR\poppler\poppler-24.08.0\Library\bin"
    if os.name == "nt"
    else None
)

st.header("📋 Sınav Oku")
st.divider()

try:
    with get_db() as con:
        sablonlar  = [tuple(r) for r in con.execute(
            "SELECT id,ad,soru_sayisi FROM sablonlar WHERE kullanici_id=?", (uid,)
        ).fetchall()]
        anahtarlar = [tuple(r) for r in con.execute(
            "SELECT id,ad,sablon_id,cevaplar FROM cevap_anahtarlari WHERE kullanici_id=?", (uid,)
        ).fetchall()]
        listeler   = [tuple(r) for r in con.execute(
            "SELECT id,ad,ogrenciler FROM ogrenci_listeleri WHERE kullanici_id=?", (uid,)
        ).fetchall()]

    if not sablonlar or not anahtarlar:
        st.warning("Önce **Şablon ve Cevap Anahtarı** sayfasından şablon ve cevap anahtarı ekleyin!")
        st.stop()

    c1, c2 = st.columns(2)
    with c1:
        sablon  = st.selectbox("Şablon", sablonlar, format_func=lambda x: f"{x[1]} ({x[2]} soru)")
        anahtar = st.selectbox("Cevap Anahtarı", anahtarlar, format_func=lambda x: x[1])
    with c2:
        liste = st.selectbox(
            "Öğrenci Listesi (opsiyonel)", [None] + list(listeler),
            format_func=lambda x: "Seçme" if x is None else x[1],
        )
        _api_key_sabit = get_gemini_key()
        if _api_key_sabit:
            api_key = _api_key_sabit
            st.info("✅ Gemini API Key yapılandırılmış.")
        else:
            api_key = st.text_input("Gemini API Key", type="password", placeholder="AIza...")
            with st.expander("ℹ️ Gemini API Key nasıl alınır?"):
                st.markdown(
                    "1. [aistudio.google.com](https://aistudio.google.com) adresine git\n"
                    "2. Google hesabınla giriş yap\n"
                    "3. Sol menüden **'Get API Key'** → **'Create API Key'** tıkla\n"
                    "4. Oluşturulan `AIza...` ile başlayan anahtarı kopyala\n\n"
                    "> 🔒 Key sadece bu oturumda kullanılır, sunucuda saklanmaz."
                )

    pdf = st.file_uploader("Sınav PDF", type=["pdf"])

    if pdf and api_key and st.button("Sınavı Oku", type="primary", use_container_width=True):
        anahtardict: dict[int, str] = {int(k): v for k, v in json.loads(anahtar[3]).items()}
        ss: int = sablon[2]
        og_dict: dict[str, str] = {}
        if liste:
            og_dict = {o["no"]: o["ad"] for o in json.loads(liste[2])}

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf.read())
            tmp = f.name
        try:
            with st.spinner("PDF dönüştürülüyor..."):
                sayfalar = convert_from_path(tmp, dpi=150, poppler_path=POPPLER_PATH)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

        toplam = len(sayfalar)
        st.write(f"**{toplam} sayfa bulundu**")
        prog    = st.progress(0)
        durum   = st.empty()
        sonuclar: list[dict[str, Any]] = []

        with st.spinner("Sayfalar Gemini ile okunuyor..."):
            for i, sayfa in enumerate(sayfalar, 1):
                durum.write(f"Sayfa {i}/{toplam} okunuyor...")
                s, hata = kagit_oku_web(sayfa, anahtardict, api_key, ss)
                if hata:
                    sonuclar.append({
                        "sayfa": i, "hata": hata, "durum": "Hata",
                        "ad_soyad": "?", "ogrenci_no": "?",
                        "dogru": 0, "yanlis": 0, "bos": ss, "puan": 0, "cevaplar": {},
                    })
                else:
                    d = "Liste seçilmedi"
                    if og_dict:
                        no_e     = s["ogrenci_no"] in og_dict
                        liste_ad = og_dict.get(s["ogrenci_no"], "").lower()
                        ad_e     = any(
                            p in liste_ad for p in s["ad_soyad"].lower().split() if len(p) > 2
                        )
                        if no_e and ad_e:   d = "Eşleşme var"
                        elif no_e:          d = "No eşleşti, ad farklı"
                        elif ad_e:          d = "Ad eşleşti, no farklı"
                        else:               d = "Eşleşme yok"
                    s["sayfa"] = i
                    s["durum"] = d
                    sonuclar.append(s)
                prog.progress(i / toplam)

        durum.empty()
        basarili = sum(1 for s in sonuclar if not s.get("hata"))

        with get_db() as con:
            cur = con.execute(
                "INSERT INTO taramalar (kullanici_id,anahtar_id,anahtar_adi,sablon_adi,"
                "soru_sayisi,cevap_anahtari,toplam_kagit,basarili) VALUES (?,?,?,?,?,?,?,?)",
                (uid, anahtar[0], anahtar[1], sablon[1], ss,
                 json.dumps(anahtardict), toplam, basarili),
            )
            tarama_id = cur.lastrowid
            for s in sonuclar:
                con.execute(
                    "INSERT INTO tarama_sonuclari (tarama_id,sayfa,ad_soyad,ogrenci_no,"
                    "cevaplar,dogru,yanlis,bos,puan,durum,hata) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (tarama_id, s.get("sayfa"), s.get("ad_soyad", "?"),
                     s.get("ogrenci_no", "?"), json.dumps(s.get("cevaplar", {})),
                     s.get("dogru", 0), s.get("yanlis", 0), s.get("bos", 0),
                     s.get("puan", 0), s.get("durum", ""), s.get("hata")),
                )

        st.session_state.sonuclar    = sonuclar
        st.session_state.anahtardict = anahtardict
        st.session_state.ss          = ss
        st.success(f"✅ {toplam} kağıt okundu ve kaydedildi!")
        st.rerun()

    # ─── Sonuçları Göster ────────────────────────────────────
    if "sonuclar" in st.session_state:
        sonuclar    = st.session_state.sonuclar
        anahtardict = st.session_state.anahtardict
        ss          = st.session_state.ss

        st.subheader("Sonuçlar")
        df_data = [
            {
                "Sayfa": s.get("sayfa"), "Ad Soyad": s.get("ad_soyad"),
                "No": s.get("ogrenci_no"), "Durum": s.get("durum"),
                "Doğru": s.get("dogru"), "Yanlış": s.get("yanlis"), "Puan": s.get("puan"),
            }
            for s in sonuclar
        ]
        st.dataframe(pd.DataFrame(df_data), use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "📥 Özet Excel İndir", excel_ozet(sonuclar), "ozet.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "📥 Detay Excel İndir", excel_detay(sonuclar, anahtardict, ss), "detay.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

except Exception as e:
    st.error(f"Hata: {e}")
