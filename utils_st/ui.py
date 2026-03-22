"""
Streamlit UI yardımcıları: CSS, silme onay butonları.
"""
from __future__ import annotations

import streamlit as st


def css_uygula() -> None:
    """Uygulama genelinde özel CSS stillerini ekler."""
    st.markdown("""
    <style>
    /* ─── Streamlit otomatik sayfa nav'ını gizle (bizim custom nav kullanıyoruz) ─── */
    [data-testid="stSidebarNav"] { display: none !important; }
    /* ─── Sidebar: koyu mavi ─── */
    section[data-testid="stSidebar"] > div:first-child {
        background: linear-gradient(180deg, #1a237e 0%, #283593 100%);
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stCaption p,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] small,
    section[data-testid="stSidebar"] label { color: white !important; }
    section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.25) !important; }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
        color: white !important; padding: 4px 8px; border-radius: 6px; transition: background 0.15s;
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover {
        background: rgba(255,255,255,0.15) !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.15) !important;
        border: 1px solid rgba(255,255,255,0.35) !important;
        color: white !important; border-radius: 8px !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.28) !important;
    }
    /* ─── Sidebar nav links (Streamlit 1.36+) ─── */
    section[data-testid="stSidebar"] a,
    section[data-testid="stSidebar"] a * {
        color: white !important;
        text-decoration: none !important;
    }
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a span,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a p,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a div {
        color: white !important;
        background: transparent !important;
    }
    section[data-testid="stSidebar"] [data-testid="stPageLink"] {
        border-radius: 8px !important;
        background: rgba(255,255,255,0.08) !important;
        margin-bottom: 2px !important;
    }
    section[data-testid="stSidebar"] [data-testid="stPageLink"]:hover,
    section[data-testid="stSidebar"] [data-testid="stPageLink"]:hover a {
        background: rgba(255,255,255,0.18) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"],
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] * {
        color: white !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {
        background: rgba(255,255,255,0.15) !important;
        border-radius: 6px !important;
    }
    /* ─── Primary buttons: yeşil ─── */
    .stButton > button[kind="primary"],
    .stButton > button[kind="primaryFormSubmit"] {
        background: #2E7D32 !important;
        border-color: #2E7D32 !important;
        color: white !important; border-radius: 8px !important;
    }
    .stButton > button[kind="primary"]:hover { background: #1B5E20 !important; }
    /* ─── Secondary/sil buttons: kırmızı ─── */
    div[data-testid="stButton"] button[kind="secondary"] {
        border-color: #C62828 !important; color: #C62828 !important; border-radius: 8px !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        background: #FFEBEE !important; color: #B71C1C !important;
    }
    /* ─── Metric kartları ─── */
    [data-testid="metric-container"] {
        background: white; border: 1px solid #e8eaf6; border-radius: 12px;
        padding: 16px 20px; box-shadow: 0 2px 8px rgba(26,35,126,0.09);
    }
    [data-testid="metric-container"] [data-testid="stMetricLabel"] { color: #5c6bc0 !important; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #1a237e !important; font-weight: 700 !important;
    }
    /* ─── Genel ─── */
    .stApp { background: #f5f6fa; }
    h1, h2, h3 { color: #1a237e !important; }
    </style>
    """, unsafe_allow_html=True)


LOGO_HTML = """
<div style="
    background: linear-gradient(135deg, #185FA5, #378ADD);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 16px;
">
    <div style="display:flex; align-items:center; justify-content:space-between;">
        <div>
            <div style="color:white; font-size:16px; font-weight:700; line-height:1.2;">Akademisyen</div>
            <div style="color:#FCDE5A; font-size:24px; font-weight:700; line-height:1.2;">AI</div>
        </div>
        <div style="display:grid; grid-template-columns:repeat(3,14px); gap:5px;">
            <div style="width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,0.25)"></div>
            <div style="width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,0.25)"></div>
            <div style="width:14px;height:14px;border-radius:50%;background:#FCDE5A"></div>
            <div style="width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,0.9)"></div>
            <div style="width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,0.25)"></div>
            <div style="width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,0.25)"></div>
            <div style="width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,0.25)"></div>
            <div style="width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,0.25)"></div>
            <div style="width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,0.9)"></div>
        </div>
    </div>
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.2);margin:10px 0 6px;">
    <div style="color:rgba(255,255,255,0.7);font-size:9px;letter-spacing:1px;">
        YALOVA ÜNİVERSİTESİ · OMR SİSTEMİ
    </div>
</div>
"""


def sidebar_goster() -> None:
    """Oturum açıkken tüm sayfalarda ortak sidebar'ı gösterir."""
    k = st.session_state.get("kullanici")
    if not k:
        return
    with st.sidebar:
        st.markdown(LOGO_HTML, unsafe_allow_html=True)
        tam_ad = k.get("tam_ad") or k.get("kullanici_adi", "")
        giris_saati = st.session_state.get("giris_saati", "")
        st.markdown(f"**👤 {tam_ad}**")
        if giris_saati:
            st.caption(f"🕐 Giriş: {giris_saati}")
        st.divider()
        st.page_link("app.py",             label="🏠 Ana Sayfa",        use_container_width=True)
        st.page_link("pages/1_tarama.py",  label="📋 Sınav Oku",        use_container_width=True)
        st.page_link("pages/2_sonuclar.py",label="📊 Geçmiş Taramalar", use_container_width=True)
        st.page_link("pages/3_sablonlar.py",label="📐 Şablonlar",       use_container_width=True)
        st.page_link("pages/4_ayarlar.py", label="⚙️ Ayarlar",          use_container_width=True)
        st.divider()
        if st.button("🚪 Çıkış Yap", use_container_width=True):
            st.session_state.pop("kullanici", None)
            st.session_state.pop("giris_saati", None)
            st.rerun()


def sil_butonu(btn_key: str, label: str = "Sil") -> None:
    """Silme butonunu göster, tıklanınca session_state'e işaretle."""
    if st.button(label, key=f"sil_btn_{btn_key}"):
        st.session_state[f"sil_bekle_{btn_key}"] = True
        st.rerun()


def sil_onay_goster(btn_key: str, isim: str = "bu kayıt") -> bool:
    """
    Onay dialogunu göster.
    Kullanıcı 'Evet, Sil' tıklarsa True döner.
    İptal veya henüz onay gösterilmiyorsa False döner.
    """
    if not st.session_state.get(f"sil_bekle_{btn_key}", False):
        return False
    st.warning(f"⚠️ **{isim}** silinecek. Bu işlem geri alınamaz!")
    c1, c2 = st.columns(2)
    if c1.button("İptal", key=f"iptal_{btn_key}"):
        st.session_state[f"sil_bekle_{btn_key}"] = False
        st.rerun()
    if c2.button("✓ Evet, Sil", key=f"onayla_{btn_key}"):
        st.session_state[f"sil_bekle_{btn_key}"] = False
        return True
    return False
