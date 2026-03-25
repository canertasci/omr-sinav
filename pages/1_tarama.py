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
from utils_st.excel import excel_detay, excel_ozet, excel_not_girisi
from utils_st.omr import get_gemini_key, kagit_oku_web
from utils_st.ui import css_uygula, sidebar_goster
from utils_st.camera import kamera_tarama_component, csv_ogrenci_listesi_yukle

st.set_page_config(page_title="Sınav Oku — OMR", layout="wide")
giris_gerekli()
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
            "SELECT id,ad,sablon_id,cevaplar,grup FROM cevap_anahtarlari WHERE kullanici_id=?", (uid,)
        ).fetchall()]
        listeler   = [tuple(r) for r in con.execute(
            "SELECT id,ad,ogrenciler FROM ogrenci_listeleri WHERE kullanici_id=?", (uid,)
        ).fetchall()]

    if not sablonlar or not anahtarlar:
        st.warning("Önce **Şablon ve Cevap Anahtarı** sayfasından şablon ve cevap anahtarı ekleyin!")
        st.stop()

    c1, c2 = st.columns(2)
    with c1:
        sablon = st.selectbox("Şablon", sablonlar, format_func=lambda x: f"{x[1]} ({x[2]} soru)")
        # Seçili şablona ait anahtarları filtrele
        sablon_anahtarlari = [a for a in anahtarlar if a[2] == sablon[0]]
        if not sablon_anahtarlari:
            st.warning("Bu şablon için cevap anahtarı bulunamadı!")
            st.stop()

        # Gruplu anahtarlar var mı kontrol et
        gruplu_anahtarlar = [a for a in sablon_anahtarlari if a[4] is not None]
        grupsuz_anahtarlar = [a for a in sablon_anahtarlari if a[4] is None]

        if gruplu_anahtarlar:
            # Gruplu mod: kullanıcıya bilgi ver
            mevcut_gruplar = sorted(set(a[4] for a in gruplu_anahtarlar))
            st.info(f"Gruplu cevap anahtarları mevcut: **{', '.join(mevcut_gruplar)}**. "
                    f"Sınav grubu kağıttan otomatik tespit edilecek.")
            # İlk grupsuz veya ilk gruplu anahtarı varsayılan olarak seç
            anahtar = grupsuz_anahtarlar[0] if grupsuz_anahtarlar else gruplu_anahtarlar[0]
        else:
            anahtar = st.selectbox(
                "Cevap Anahtarı", sablon_anahtarlari,
                format_func=lambda x: x[1],
            )
    with c2:
        # Öğrenci listesi: mevcut DB veya CSV yükle
        liste_tab1, liste_tab2 = st.tabs(["Mevcut Listeler", "CSV Yükle"])

        liste = None  # Varsayılan
        with liste_tab1:
            liste = st.selectbox(
                "Öğrenci Listesi (opsiyonel)", [None] + list(listeler),
                format_func=lambda x: "Seçme" if x is None else x[1],
            )

        with liste_tab2:
            st.caption("Yalova UBS format: Sütun A = No, Sütun B = Ad")
            csv_temp = csv_ogrenci_listesi_yukle()
            if csv_temp:
                # CSV'den gelen listeyi kullan
                og_dict = {o["no"]: o["ad"] for o in csv_temp}
                st.session_state["csv_liste"] = csv_temp

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

    # ─── Tarama Seçeneği: PDF vs Kamera ────────────────────────────────
    st.divider()
    tarama_tipi = st.radio(
        "Tarama Yöntemi",
        ["PDF Yükle", "📱 Kameradan Çek"],
        horizontal=True,
        help="PDF: Tüm kağıtları birden | Kamera: Teker teker tarama"
    )

    pdf = None
    kamera_goruntusu = None

    if tarama_tipi == "PDF Yükle":
        pdf = st.file_uploader("Sınav PDF", type=["pdf"])
    else:
        st.info("💡 **Kamera Taraması:** Sınav kağıdını kameraya doğru tutarak fotoğraf çek.")
        kamera_goruntusu = kamera_tarama_component()

    if (pdf or (tarama_tipi == "📱 Kameradan Çek" and kamera_goruntusu and kamera_goruntusu.get("status") == "captured")) and api_key and st.button("Sınavı Oku", type="primary", use_container_width=True):
        anahtardict: dict[int, str] = {int(k): v for k, v in json.loads(anahtar[3]).items()}
        ss: int = sablon[2]

        # Grup anahtarlarını hazırla
        grup_anahtarlari: dict[str, dict[int, str]] | None = None
        if gruplu_anahtarlar:
            grup_anahtarlari = {}
            for ga in gruplu_anahtarlar:
                grup_harf = ga[4]  # "A", "B", "C", "D"
                grup_anahtarlari[grup_harf] = {int(k): v for k, v in json.loads(ga[3]).items()}

        og_dict: dict[str, str] = {}
        if liste:
            og_dict = {o["no"]: o["ad"] for o in json.loads(liste[2])}

        # ─── PDF vs Kamera İşleme ────────────────────────────────
        sayfalar = []

        if tarama_tipi == "PDF Yükle":
            # PDF modunda: tüm sayfaları birden işle
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
        else:
            # Kamera modunda: tek görüntüyü PIL Image'a çevir
            from PIL import Image
            import io
            import base64

            img_b64 = kamera_goruntusu.get("image_base64", "")
            if img_b64.startswith("data:image"):
                # Data URI format: "data:image/jpeg;base64,..."
                img_b64 = img_b64.split(",")[1]

            img_bytes = base64.b64decode(img_b64)
            img = Image.open(io.BytesIO(img_bytes))
            sayfalar = [img]

        toplam = len(sayfalar)
        st.write(f"**{toplam} sayfa bulundu**")
        prog    = st.progress(0)
        durum   = st.empty()
        sonuclar: list[dict[str, Any]] = []

        with st.spinner("Sayfalar Gemini ile okunuyor..."):
            for i, sayfa in enumerate(sayfalar, 1):
                durum.write(f"Sayfa {i}/{toplam} okunuyor...")
                s, hata = kagit_oku_web(sayfa, anahtardict, api_key, ss, grup_anahtarlari)
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
                    "cevaplar,dogru,yanlis,bos,puan,durum,hata,sinav_grubu) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (tarama_id, s.get("sayfa"), s.get("ad_soyad", "?"),
                     s.get("ogrenci_no", "?"), json.dumps(s.get("cevaplar", {})),
                     s.get("dogru", 0), s.get("yanlis", 0), s.get("bos", 0),
                     s.get("puan", 0), s.get("durum", ""), s.get("hata"),
                     s.get("sinav_grubu")),
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
        # Grup bilgisi varsa tabloya ekle
        herhangi_grup = any(s.get("sinav_grubu") for s in sonuclar)
        df_data = []
        for s in sonuclar:
            satir: dict[str, Any] = {
                "Sayfa": s.get("sayfa"),
                "Ad Soyad": s.get("ad_soyad"),
                "No": s.get("ogrenci_no"),
            }
            if herhangi_grup:
                satir["Grup"] = s.get("sinav_grubu", "-")
            satir.update({
                "Durum": s.get("durum"),
                "Doğru": s.get("dogru"),
                "Yanlış": s.get("yanlis"),
                "Puan": s.get("puan"),
            })
            df_data.append(satir)
        st.dataframe(pd.DataFrame(df_data), use_container_width=True)

        # Grup bazında özet (varsa)
        if herhangi_grup:
            st.subheader("Grup Bazında Özet")
            grup_sonuc: dict[str, list] = {}
            for s in sonuclar:
                g = s.get("sinav_grubu", "Bilinmiyor")
                if g not in grup_sonuc:
                    grup_sonuc[g] = []
                grup_sonuc[g].append(s.get("puan", 0))
            ozet_data = []
            for g in sorted(grup_sonuc.keys()):
                puanlar = grup_sonuc[g]
                ozet_data.append({
                    "Grup": g if g else "Bilinmiyor",
                    "Öğrenci Sayısı": len(puanlar),
                    "Ortalama Puan": round(sum(puanlar) / len(puanlar), 1) if puanlar else 0,
                    "En Yüksek": max(puanlar) if puanlar else 0,
                    "En Düşük": min(puanlar) if puanlar else 0,
                })
            st.dataframe(pd.DataFrame(ozet_data), use_container_width=True, hide_index=True)

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

        # ─── Üniversite Not Giriş Sistemi ────────────────────────────
        st.divider()
        st.subheader("🎓 Üniversite Not Giriş Dosyasına Aktar")
        st.caption(
            "Üniversitenin not giriş Excel dosyasını yükleyin. "
            "Öğrenci numaralarına göre eşleştirme yapılır ve GR yerine puanlar yazılır."
        )

        col_dosya, col_tur = st.columns([3, 1])
        with col_dosya:
            uni_excel = st.file_uploader(
                "Üniversite Not Giriş Excel Dosyası",
                type=["xlsx", "xls"],
                key="uni_excel_upload",
            )
        with col_tur:
            not_turu = st.selectbox("Not Türü", ["Vize", "Final"], key="not_turu_sec")

        if uni_excel:
            try:
                dolmus_excel, eslesen, toplam = excel_not_girisi(
                    uni_excel.read(), sonuclar, not_turu,
                    dosya_adi=uni_excel.name,
                )
                if eslesen > 0:
                    st.success(
                        f"✅ **{toplam}** öğrenciden **{eslesen}** tanesi eşleşti ve "
                        f"**{not_turu}** notu girildi."
                    )
                    if eslesen < toplam:
                        st.warning(
                            f"⚠️ {toplam - eslesen} öğrenci eşleşmedi — "
                            f"öğrenci numaraları tarama sonuçlarıyla uyuşmuyor olabilir."
                        )
                    st.download_button(
                        f"📥 {not_turu} Notları Girilmiş Excel İndir",
                        dolmus_excel,
                        f"not_girisi_{not_turu.lower()}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        type="primary",
                    )
                else:
                    st.error(
                        "❌ Hiçbir öğrenci eşleşmedi! "
                        "Öğrenci numaralarının doğru okunduğundan emin olun."
                    )
            except ValueError as ve:
                st.error(f"❌ {ve}")
            except Exception as e:
                st.error(f"Dosya işlenirken hata: {e}")

except Exception as e:
    st.error(f"Hata: {e}")
