"""
Geçmiş Taramalar Sayfası — geçmiş tarama kayıtları, filtre, Excel export.
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
from utils_st.db import get_db
from utils_st.excel import excel_detay, excel_ozet
from utils_st.ui import css_uygula, sidebar_goster, sil_butonu, sil_onay_goster

st.set_page_config(page_title="Geçmiş Taramalar — OMR", layout="wide")
giris_gerekli()
css_uygula()
sidebar_goster()

kullanici = mevcut_kullanici()
uid: int = kullanici["id"]

st.header("📊 Geçmiş Taramalar")
st.divider()

try:
    with get_db() as con:
        taramalar = con.execute(
            "SELECT id,anahtar_adi,sablon_adi,soru_sayisi,toplam_kagit,basarili,tarih "
            "FROM taramalar WHERE kullanici_id=? ORDER BY id DESC", (uid,)
        ).fetchall()

    if not taramalar:
        st.info("Henüz kayıtlı tarama yok. '📋 Sınav Oku' sayfasından tarama yapabilirsiniz.")
        st.stop()

    if "gecmis_secili" not in st.session_state:
        st.session_state.gecmis_secili = None

    # ── Filtreleme ────────────────────────────────────────────
    with st.expander("🔍 Filtrele", expanded=False):
        fc1, fc2 = st.columns(2)
        with fc1:
            sablon_adlari = sorted({t[2] for t in taramalar})
            secili_sablon = st.selectbox("Şablon Adı", ["Tümü"] + sablon_adlari)
        with fc2:
            tarih_sec = st.date_input("Tarih Filtresi", value=None, key="gcm_tarih")
            tarih_filtre = tarih_sec.strftime("%Y-%m") if tarih_sec else ""

    if secili_sablon != "Tümü":
        taramalar = [t for t in taramalar if t[2] == secili_sablon]
    if tarih_filtre:
        taramalar = [t for t in taramalar if tarih_filtre in t[6]]

    # ── Toplu Excel Export ────────────────────────────────────
    if taramalar:
        if st.button("📥 Tümünü Excel'e Aktar", type="primary"):
            rows = [
                {
                    "Cevap Anahtarı": t[1], "Şablon": t[2],
                    "Soru Sayısı": t[3], "Toplam Kağıt": t[4],
                    "Başarılı": t[5], "Tarih": t[6][:16],
                }
                for t in taramalar
            ]
            buf = BytesIO()
            pd.DataFrame(rows).to_excel(buf, index=False, engine="openpyxl")
            st.download_button(
                "⬇️ İndir", buf.getvalue(), "gecmis_taramalar.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    st.subheader(f"Toplam {len(taramalar)} tarama")

    for t in taramalar:
        tid, anahtar_adi, sablon_adi, ss, toplam, basarili, tarih = t
        hata_sayisi = toplam - basarili
        secili = st.session_state.gecmis_secili == tid

        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
            c1.markdown(f"**{anahtar_adi}**  \n{sablon_adi} · {ss} soru")
            c2.markdown(
                f"**{toplam}** kağıt  \n{basarili} başarılı"
                + (f", {hata_sayisi} hata" if hata_sayisi else "")
            )
            c3.markdown(f"{tarih[:16]}")
            if c4.button("Göster" if not secili else "Gizle", key=f"gos{tid}"):
                st.session_state.gecmis_secili = None if secili else tid
                st.rerun()
            with c5:
                sil_butonu(f"tarama_{tid}")
            if sil_onay_goster(f"tarama_{tid}", f"'{anahtar_adi}' taraması"):
                with get_db() as con:
                    con.execute("DELETE FROM tarama_sonuclari WHERE tarama_id=?", (tid,))
                    con.execute("DELETE FROM taramalar WHERE id=?", (tid,))
                if st.session_state.gecmis_secili == tid:
                    st.session_state.gecmis_secili = None
                st.rerun()

        if secili:
            with get_db() as con:
                row_t = con.execute(
                    "SELECT cevap_anahtari FROM taramalar WHERE id=?", (tid,)
                ).fetchone()
                sonuclar_db = con.execute(
                    "SELECT sayfa,ad_soyad,ogrenci_no,cevaplar,dogru,yanlis,bos,puan,durum,hata "
                    "FROM tarama_sonuclari WHERE tarama_id=? ORDER BY sayfa", (tid,)
                ).fetchall()

            anahtardict: dict[int, str] = {int(k): v for k, v in json.loads(row_t[0]).items()}
            sonuclar = [
                {
                    "sayfa": r[0], "ad_soyad": r[1], "ogrenci_no": r[2],
                    "cevaplar": {int(k): v for k, v in json.loads(r[3]).items()},
                    "dogru": r[4], "yanlis": r[5], "bos": r[6],
                    "puan": r[7], "durum": r[8], "hata": r[9],
                }
                for r in sonuclar_db
            ]

            df_data = [
                {
                    "Sayfa": s["sayfa"], "Ad Soyad": s["ad_soyad"],
                    "No": s["ogrenci_no"], "Durum": s["durum"],
                    "Doğru": s["dogru"], "Yanlış": s["yanlis"], "Puan": s["puan"],
                }
                for s in sonuclar
            ]
            st.dataframe(pd.DataFrame(df_data), use_container_width=True)

            ec1, ec2 = st.columns(2)
            with ec1:
                st.download_button(
                    "Özet Excel", excel_ozet(sonuclar), f"ozet_{tid}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key=f"exc_ozet_{tid}",
                )
            with ec2:
                st.download_button(
                    "Detay Excel", excel_detay(sonuclar, anahtardict, ss), f"detay_{tid}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key=f"exc_detay_{tid}",
                )

except Exception as e:
    st.error(f"Hata: {e}")
