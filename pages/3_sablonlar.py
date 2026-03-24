"""
Şablon & Cevap Anahtarı & Öğrenci Listesi Sayfası.
"""
from __future__ import annotations

import json
import os
import sys
from io import BytesIO

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils_st.auth import giris_gerekli, mevcut_kullanici
from utils_st.db import cache_temizle, get_db
from utils_st.ui import css_uygula, sidebar_goster, sil_butonu, sil_onay_goster

giris_gerekli()

st.set_page_config(page_title="Şablon & Anahtar — OMR", layout="wide")
css_uygula()
sidebar_goster()

kullanici = mevcut_kullanici()
uid: int = kullanici["id"]

tab_sablon, tab_anahtar, tab_liste = st.tabs(
    ["📐 Şablonlar", "🔑 Cevap Anahtarları", "👥 Öğrenci Listeleri"]
)

# ─────────────────────────── ŞABLONLAR ────────────────────────────────────────
with tab_sablon:
    st.header("Şablon Yönetimi")
    try:
        with st.container(border=True):
            st.subheader("Yeni Şablon Ekle")
            adi = st.text_input("Şablon Adı", key="sablon_adi_input")
            ss  = st.selectbox("Soru Sayısı", [10, 20, 30, 40, 50], index=1)
            if st.button("Kaydet", type="primary", key="sablon_kaydet"):
                if adi:
                    with get_db() as con:
                        con.execute(
                            "INSERT INTO sablonlar (kullanici_id,ad,soru_sayisi) VALUES (?,?,?)",
                            (uid, adi, ss),
                        )
                    cache_temizle()
                    st.success(f"'{adi}' kaydedildi!")
                    st.rerun()
                else:
                    st.warning("Şablon adı girin!")

        st.subheader("Kayıtlı Şablonlar")
        with get_db() as con:
            rows = con.execute(
                "SELECT id,ad,soru_sayisi,tarih FROM sablonlar WHERE kullanici_id=? ORDER BY id DESC",
                (uid,),
            ).fetchall()

        if rows:
            for r in rows:
                c1, c2, c3, c4 = st.columns([3, 2, 3, 1])
                c1.markdown(f"**{r[1]}**")
                c2.write(f"{r[2]} soru")
                c3.write(r[3][:16])
                with c4:
                    sil_butonu(f"sablon_{r[0]}")
                if sil_onay_goster(f"sablon_{r[0]}", f"'{r[1]}'"):
                    with get_db() as con:
                        con.execute("DELETE FROM sablonlar WHERE id=?", (r[0],))
                    cache_temizle()
                    st.rerun()
        else:
            st.info("Henüz şablon yok.")
    except Exception as e:
        st.error(f"Hata: {e}")

# ─────────────────────────── CEVAP ANAHTARLARI ───────────────────────────────
with tab_anahtar:
    st.header("Cevap Anahtarı")
    try:
        with get_db() as con:
            sablonlar = [
                tuple(r) for r in con.execute(
                    "SELECT id,ad,soru_sayisi FROM sablonlar WHERE kullanici_id=?", (uid,)
                ).fetchall()
            ]

        if not sablonlar:
            st.warning("Önce şablon ekleyin!")
            st.stop()

        sablon  = st.selectbox("Şablon Seç", sablonlar, format_func=lambda x: f"{x[1]} ({x[2]} soru)")
        ss_a    = sablon[2]

        col_adi, col_grup = st.columns([3, 1])
        with col_adi:
            adi_a = st.text_input("Cevap Anahtarı Adı (örn: Vize 2025)", key="anahtar_adi_input")
        with col_grup:
            grup_sec = st.selectbox(
                "Sınav Grubu",
                ["Tek Grup (Grupsuz)", "A", "B", "C", "D"],
                key="grup_sec",
                help="Birden fazla sınav grubu varsa her grup için ayrı anahtar girin.",
            )
        grup_val = None if grup_sec.startswith("Tek") else grup_sec

        tab1, tab2 = st.tabs(["✏️ Manuel Giriş", "📂 Dosyadan Yükle"])
        cevaplar: dict[int, str] = {}

        with tab1:
            st.caption("Her soru için doğru şıkkı seçin.")
            for i in range(0, ss_a, 5):
                cols = st.columns(5)
                for j, col in enumerate(cols):
                    sno = i + j + 1
                    if sno <= ss_a:
                        with col:
                            cevaplar[sno] = st.selectbox(
                                f"Soru {sno}", ["A", "B", "C", "D", "E"], key=f"ca{sno}"
                            )

        with tab2:
            ornek_df = pd.DataFrame({"Soru No": range(1, ss_a + 1), "Cevap": ["A"] * ss_a})
            ornek_buf = BytesIO()
            ornek_df.to_excel(ornek_buf, index=False, engine="openpyxl")
            st.download_button(
                "⬇️ Örnek Şablon İndir", ornek_buf.getvalue(),
                "ornek_cevap_anahtari.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            yuklenen = st.file_uploader("CSV veya Excel Yükle", type=["csv", "xlsx", "xls"],
                                        key="anahtar_yukle")
            if yuklenen:
                try:
                    if yuklenen.name.endswith(".csv"):
                        df_yukle = pd.read_csv(yuklenen, header=0)
                    else:
                        df_yukle = pd.read_excel(yuklenen, header=0, engine="openpyxl")
                    for _, row in df_yukle.iterrows():
                        try:
                            sno = int(row.iloc[0])
                            cvp = str(row.iloc[1]).strip().upper()
                            if 1 <= sno <= ss_a and cvp in ["A", "B", "C", "D", "E"]:
                                cevaplar[sno] = cvp
                        except Exception:
                            pass
                    st.success(f"{len(cevaplar)} soru yüklendi.")
                except Exception as exc:
                    st.error(f"Dosya okunamadı: {exc}")

        if st.button("Anahtarı Kaydet", type="primary", key="anahtar_kaydet"):
            if adi_a:
                # Aynı şablon + grup kombinasyonu varsa uyar
                with get_db() as con:
                    if grup_val:
                        var_mi = con.execute(
                            "SELECT id FROM cevap_anahtarlari WHERE sablon_id=? AND grup=? AND kullanici_id=?",
                            (sablon[0], grup_val, uid),
                        ).fetchone()
                        if var_mi:
                            st.warning(f"Bu şablon için Grup {grup_val} anahtarı zaten var! Önce eskisini silin.")
                            st.stop()
                    con.execute(
                        "INSERT INTO cevap_anahtarlari (kullanici_id,sablon_id,ad,grup,cevaplar) VALUES (?,?,?,?,?)",
                        (uid, sablon[0], adi_a, grup_val, json.dumps(cevaplar)),
                    )
                st.success(f"'{adi_a}'{' (Grup ' + grup_val + ')' if grup_val else ''} kaydedildi!")
                st.rerun()
            else:
                st.warning("Cevap anahtarı adı girin!")

        st.subheader("Kayıtlı Anahtarlar")
        with get_db() as con:
            rows_a = con.execute(
                "SELECT id,ad,sablon_id,cevaplar,tarih,grup FROM cevap_anahtarlari "
                "WHERE kullanici_id=? ORDER BY id DESC", (uid,)
            ).fetchall()

        for r in rows_a:
            grup_goster = f" **[Grup {r[5]}]**" if r[5] else ""
            c1, c2, c3, c4 = st.columns([4, 2, 1, 1])
            c1.write(f"**{r[1]}**{grup_goster}")
            c2.write(r[4][:16])
            duzenle_key = f"duzenle_{r[0]}"
            if c3.button("✏️", key=f"btn_{duzenle_key}", help="Düzenle"):
                st.session_state[duzenle_key] = not st.session_state.get(duzenle_key, False)
                st.rerun()
            with c4:
                sil_butonu(f"anahtar_{r[0]}")
            if sil_onay_goster(f"anahtar_{r[0]}", f"'{r[1]}'"):
                with get_db() as con:
                    con.execute("DELETE FROM cevap_anahtarlari WHERE id=?", (r[0],))
                st.rerun()

            if st.session_state.get(duzenle_key, False):
                mevcut = {int(k): v for k, v in json.loads(r[3]).items()}
                with get_db() as con:
                    sablon_row = con.execute(
                        "SELECT soru_sayisi FROM sablonlar WHERE id=?", (r[2],)
                    ).fetchone()
                edit_ss = sablon_row[0] if sablon_row else len(mevcut)
                with st.container(border=True):
                    st.markdown(f"**✏️ Düzenleniyor: {r[1]}**")
                    yeni_cevaplar: dict[int, str] = {}
                    for i in range(0, edit_ss, 5):
                        cols = st.columns(5)
                        for j, col in enumerate(cols):
                            sno = i + j + 1
                            if sno <= edit_ss:
                                with col:
                                    varsayilan = ["A", "B", "C", "D", "E"].index(
                                        mevcut.get(sno, "A")
                                    )
                                    yeni_cevaplar[sno] = st.selectbox(
                                        f"Soru {sno}", ["A", "B", "C", "D", "E"],
                                        index=varsayilan, key=f"edit_{r[0]}_{sno}",
                                    )
                    col_kaydet, col_iptal = st.columns(2)
                    if col_kaydet.button("💾 Kaydet", key=f"kaydet_{r[0]}", type="primary"):
                        with get_db() as con:
                            con.execute(
                                "UPDATE cevap_anahtarlari SET cevaplar=? WHERE id=?",
                                (json.dumps(yeni_cevaplar), r[0]),
                            )
                        st.session_state[duzenle_key] = False
                        st.success("Güncellendi!")
                        st.rerun()
                    if col_iptal.button("İptal", key=f"iptal_edit_{r[0]}"):
                        st.session_state[duzenle_key] = False
                        st.rerun()

    except Exception as e:
        st.error(f"Hata: {e}")

# ─────────────────────────── ÖĞRENCİ LİSTELERİ ──────────────────────────────
with tab_liste:
    st.header("Öğrenci Listesi")
    try:
        with st.container(border=True):
            st.subheader("Excel Yükle")
            st.info("📋 **Excel formatı:** Başlık satırı olmadan, **A sütunu** = Öğrenci No, **B sütunu** = Ad Soyad")
            ornek_og = pd.DataFrame([
                {"Öğrenci No": "22010001", "Ad Soyad": "Ali Yılmaz"},
                {"Öğrenci No": "22010002", "Ad Soyad": "Ayşe Kaya"},
            ])
            ornek_buf_og = BytesIO()
            ornek_og.to_excel(ornek_buf_og, index=False, header=False, engine="openpyxl")
            st.download_button(
                "⬇️ Örnek Excel Şablonu İndir", ornek_buf_og.getvalue(),
                "ornek_ogrenci_listesi.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="ornek_og_indir",
            )
            adi_l    = st.text_input("Liste Adı", key="liste_adi")
            yuklenen_l = st.file_uploader("Excel Dosyası", type=["xlsx", "xls"], key="liste_yukle")
            if yuklenen_l and adi_l and st.button("Listeyi Kaydet", type="primary", key="liste_kaydet"):
                raw = yuklenen_l.read()
                header_check = raw[:50].lower()
                if b"<html" in header_check or b"<?xml" in header_check or b"<table" in header_check:
                    # HTML olarak kaydedilmiş .xls dosyası
                    html_str = raw.decode("utf-8", errors="ignore")
                    tables = pd.read_html(html_str)
                    df = max(tables, key=len)
                else:
                    engine = "openpyxl" if yuklenen_l.name.endswith(".xlsx") else "xlrd"
                    df = pd.read_excel(BytesIO(raw), header=None, engine=engine)
                ogrenciler = [
                    {"no": str(r[0]).strip(), "ad": str(r[1]).strip()}
                    for _, r in df.iterrows()
                ]
                with get_db() as con:
                    con.execute(
                        "INSERT INTO ogrenci_listeleri (kullanici_id,ad,ogrenciler) VALUES (?,?,?)",
                        (uid, adi_l, json.dumps(ogrenciler, ensure_ascii=False)),
                    )
                st.success(f"{len(ogrenciler)} öğrenci kaydedildi!")
                st.rerun()

        st.subheader("Kayıtlı Listeler")
        with get_db() as con:
            rows_l = con.execute(
                "SELECT id,ad,ogrenciler,tarih FROM ogrenci_listeleri "
                "WHERE kullanici_id=? ORDER BY id DESC", (uid,)
            ).fetchall()

        for r in rows_l:
            og = json.loads(r[2])
            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
            c1.markdown(f"**{r[1]}**")
            c2.write(f"{len(og)} öğrenci")
            c3.write(r[3][:16])
            goruntu_key = f"goruntu_{r[0]}"
            if c4.button("👁️", key=f"btn_{goruntu_key}", help="Görüntüle"):
                st.session_state[goruntu_key] = not st.session_state.get(goruntu_key, False)
                st.rerun()
            with c5:
                sil_butonu(f"liste_{r[0]}")
            if sil_onay_goster(f"liste_{r[0]}", f"'{r[1]}'"):
                with get_db() as con:
                    con.execute("DELETE FROM ogrenci_listeleri WHERE id=?", (r[0],))
                st.rerun()

            if st.session_state.get(goruntu_key, False):
                with st.container(border=True):
                    st.markdown(f"**👥 {r[1]}** — {len(og)} öğrenci")
                    df_og = pd.DataFrame(og).rename(
                        columns={"no": "Öğrenci No", "ad": "Ad Soyad"}
                    )
                    st.dataframe(df_og, use_container_width=True, hide_index=True)
                    buf_og = BytesIO()
                    df_og.to_excel(buf_og, index=False, engine="openpyxl")
                    st.download_button(
                        "⬇️ Excel İndir", buf_og.getvalue(), f"{r[1]}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"indir_{r[0]}",
                    )
    except Exception as e:
        st.error(f"Hata: {e}")
