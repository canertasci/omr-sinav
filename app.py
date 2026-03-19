import streamlit as st
import sqlite3, bcrypt, json, os, base64, time, tempfile
import cv2, numpy as np, requests
import pandas as pd
from pdf2image import convert_from_path
from PIL import Image
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from io import BytesIO

# ─── AYARLAR ────────────────────────────────────────────────
TARAMA_DPI     = 300
MAX_GORUNTU_PX = 1200
DB_YOLU        = os.path.join(os.getcwd(), "omr.db")
POPPLER_PATH   = r"C:\PYTHON GENEL\OMR\poppler\poppler-24.08.0\Library\bin"

ARUCO_DICT   = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ARUCO_PARAMS = cv2.aruco.DetectorParameters()
ARUCO_DETEK  = cv2.aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMS)

# ─── VERİTABANI ─────────────────────────────────────────────
def db_bag():
    return sqlite3.connect(DB_YOLU)

def db_olustur():
    con = db_bag()
    con.executescript(
        "CREATE TABLE IF NOT EXISTS kullanicilar ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "kullanici_adi TEXT UNIQUE NOT NULL,"
        "sifre_hash TEXT NOT NULL,"
        "tam_ad TEXT);"
        "CREATE TABLE IF NOT EXISTS sablonlar ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "kullanici_id INTEGER,"
        "ad TEXT NOT NULL,"
        "soru_sayisi INTEGER DEFAULT 20,"
        "tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
        "CREATE TABLE IF NOT EXISTS cevap_anahtarlari ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "kullanici_id INTEGER,"
        "sablon_id INTEGER,"
        "ad TEXT NOT NULL,"
        "cevaplar TEXT NOT NULL,"
        "tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
        "CREATE TABLE IF NOT EXISTS ogrenci_listeleri ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "kullanici_id INTEGER,"
        "ad TEXT NOT NULL,"
        "ogrenciler TEXT NOT NULL,"
        "tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
        "CREATE TABLE IF NOT EXISTS taramalar ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "kullanici_id INTEGER,"
        "anahtar_id INTEGER,"
        "anahtar_adi TEXT,"
        "sablon_adi TEXT,"
        "soru_sayisi INTEGER,"
        "cevap_anahtari TEXT,"
        "toplam_kagit INTEGER,"
        "basarili INTEGER,"
        "tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
        "CREATE TABLE IF NOT EXISTS tarama_sonuclari ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "tarama_id INTEGER,"
        "sayfa INTEGER,"
        "ad_soyad TEXT,"
        "ogrenci_no TEXT,"
        "cevaplar TEXT,"
        "dogru INTEGER,"
        "yanlis INTEGER,"
        "bos INTEGER,"
        "puan REAL,"
        "durum TEXT,"
        "hata TEXT);"
    )
    sifre = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
    con.execute("INSERT OR IGNORE INTO kullanicilar (kullanici_adi,sifre_hash,tam_ad) VALUES (?,?,?)",
                ("admin", sifre, "Yonetici"))
    con.commit()
    con.close()

# ─── GİRİŞ ──────────────────────────────────────────────────
def giris_kontrol(adi, sifre):
    con = db_bag()
    satir = con.execute("SELECT id,sifre_hash,tam_ad FROM kullanicilar WHERE kullanici_adi=?", (adi,)).fetchone()
    con.close()
    if satir and bcrypt.checkpw(sifre.encode(), satir[1].encode()):
        return {"id": satir[0], "kullanici_adi": adi, "tam_ad": satir[2]}
    return None

def giris_sayfasi():
    st.markdown("""
    <style>
    .ana{text-align:center;color:#1a56db;font-size:2.5rem;font-weight:800;margin-top:3rem;}
    .alt{text-align:center;color:#6b7280;margin-bottom:2rem;}
    </style>
    <div class="ana">📋 OMR Sinav Sistemi</div>
    <div class="alt">Optik Isaretleme Okuyucu</div>
    """, unsafe_allow_html=True)
    _, orta, _ = st.columns([1,2,1])
    with orta:
        with st.container(border=True):
            st.subheader("Giris Yap")
            adi   = st.text_input("Kullanici Adi")
            sifre = st.text_input("Sifre", type="password")
            if st.button("Giris Yap", use_container_width=True, type="primary"):
                k = giris_kontrol(adi, sifre)
                if k:
                    st.session_state.kullanici = k
                    st.rerun()
                else:
                    st.error("Kullanici adi veya sifre hatali!")
            st.caption("Varsayilan: admin / admin123")

# ─── OMR YARDIMCI FONKSİYONLAR ──────────────────────────────
def pil_to_cv(img):
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def b64_yap(cv_img):
    h, w = cv_img.shape[:2]
    if max(h,w) > MAX_GORUNTU_PX:
        oran = MAX_GORUNTU_PX / max(h,w)
        cv_img = cv2.resize(cv_img, (int(w*oran), int(h*oran)))
    _, buf = cv2.imencode(".jpg", cv_img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return base64.b64encode(buf).decode()

def aruco_tespit(cv_img):
    gri = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = ARUCO_DETEK.detectMarkers(gri)
    if ids is None or len(ids) < 4:
        return None
    m = {}
    for i, mid in enumerate(ids.flatten()):
        if mid in [0,1,2,3]:
            m[int(mid)] = corners[i][0]
    return m if len(m) == 4 else None

def bolgeleri_ayir(cv_img, m):
    dk = {0:m[0][0], 1:m[1][1], 2:m[2][3], 3:m[3][2]}
    xl = int(dk[0][0]); xr = int(dk[1][0])
    yt = int(dk[0][1]); yb = int(dk[2][1])
    xm = int((xl+xr)/2); ym = int((yt+yb)/2)
    return {
        0: cv_img[yt:ym, xl:xm],
        1: cv_img[yt:ym, xm:xr],
        2: cv_img[ym:yb, xl:xm],
        3: cv_img[ym:yb, xm:xr],
    }

def gemini_cagir_web(cv_img, prompt, api_key):
    url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/jpeg", "data": b64_yap(cv_img)}}
        ]}],
        "generationConfig": {"temperature": 0, "thinkingConfig": {"thinkingBudget": 1024}}
    }
    for d in range(3):
        try:
            r = requests.post(url, json=body, timeout=30)
            if r.status_code == 429:
                time.sleep(10); continue
            r.raise_for_status()
            metin = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if "```" in metin:
                for p in metin.split("```"):
                    p = p.strip()
                    if p.startswith("json"): p = p[4:].strip()
                    if p.startswith("{"): metin = p.strip(); break
            if "{" in metin and "}" in metin:
                metin = metin[metin.index("{"):metin.rindex("}")+1]
            return json.loads(metin)
        except Exception as e:
            if d < 2: time.sleep(2)
            else: return {"hata": str(e)}

PROMPT_NO = (
    "Bu goruntude bir ogrenci numarasi balon tablosu var.\n"
    "9 SUTUN (soldan saga 1-9. hane), 10 SATIR (0-9 rakamlari).\n"
    "Her sutunda YALNIZCA BIR balon dolu olmalidir.\n"
    "Her sutunu BAGIMSIZ degerlendirip EN KOYU balonu bul.\n"
    "Bos balon = sadece ince cember, ici beyaz.\n"
    "Yanlis okuma yapma, dikkatli incele.\n"
    'SADECE JSON don: {"no": "123456789"}'
)

def cevap_prompt(bas, bit):
    return (
        f"Bu goruntude {bas}-{bit} sorularinin cevap balonlari var.\n"
        "Her satir bir soru, satirda A B C D E siklari var.\n"
        "Her satiri BAGIMSIZ degerlendirip EN KOYU balonu bul.\n"
        "Birden fazla esit koyulukta balon varsa hepsini yaz (ornegin \"A/C\").\n"
        "Hic dolu balon yoksa \"BOS\" yaz.\n"
        f"SADECE JSON don: {{\"{bas}\": \"A\", ..., \"{bit}\": \"C\"}}"
    )

def bilgi_prompt():
    return (
        "Bu goruntude ogrenci bilgi formu var.\n"
        "Ad Soyad, Bolum/Program ve Ders Adi alanlarini oku. El yazisi olabilir.\n"
        "SADECE JSON don: {\"ad_soyad\": \"Ad Soyad\", \"bolum\": \"Bolum\", \"ders\": \"Ders\"}"
    )

def kagit_oku_web(pil_img, cevap_anahtari, api_key, soru_sayisi=20):
    cv_img    = pil_to_cv(pil_img)
    markerlar = aruco_tespit(cv_img)
    if markerlar is None:
        return None, "ArUco marker bulunamadi"
    bolgeler = bolgeleri_ayir(cv_img, markerlar)
    bilgi    = gemini_cagir_web(bolgeler[0], bilgi_prompt(), api_key)
    ad_soyad = bilgi.get("ad_soyad","?") if isinstance(bilgi,dict) and "hata" not in bilgi else "?"
    h, w  = bolgeler[1].shape[:2]
    buyuk = cv2.resize(bolgeler[1], (int(w*1.5), int(h*1.5)), interpolation=cv2.INTER_CUBIC)
    no_s  = gemini_cagir_web(buyuk, PROMPT_NO, api_key)
    no    = str(no_s.get("no","?????????")) if isinstance(no_s,dict) and "hata" not in no_s else "?????????"
    no    = no[:9].ljust(9,"?")
    cevaplar = {}
    orta = soru_sayisi // 2
    c1   = gemini_cagir_web(bolgeler[2], cevap_prompt(1, orta), api_key)
    c2   = gemini_cagir_web(bolgeler[3], cevap_prompt(orta+1, soru_sayisi), api_key)
    if isinstance(c1,dict) and "hata" not in c1:
        cevaplar.update({int(k):str(v).upper() for k,v in c1.items() if str(k).isdigit()})
    if isinstance(c2,dict) and "hata" not in c2:
        cevaplar.update({int(k):str(v).upper() for k,v in c2.items() if str(k).isdigit()})
    dogru  = sum(1 for s in range(1,soru_sayisi+1) if cevaplar.get(s)==cevap_anahtari.get(s))
    yanlis = sum(1 for s in range(1,soru_sayisi+1)
                 if cevaplar.get(s) not in (cevap_anahtari.get(s),"BOS","HATA")
                 and "/" not in str(cevaplar.get(s,"")))
    bos  = sum(1 for s in range(1,soru_sayisi+1) if cevaplar.get(s)=="BOS")
    puan = round(dogru * (100/soru_sayisi), 2)
    return {"ad_soyad":ad_soyad,"ogrenci_no":no,"cevaplar":cevaplar,
            "dogru":dogru,"yanlis":yanlis,"bos":bos,"puan":puan}, None

# ─── EXCEL ──────────────────────────────────────────────────
def excel_ozet(sonuclar):
    wb = Workbook(); ws = wb.active; ws.title = "Ozet"
    mavi  = PatternFill("solid", fgColor="1a56db")
    beyaz = Font(color="FFFFFF", bold=True)
    kenar = Border(left=Side(style="thin"),right=Side(style="thin"),
                   top=Side(style="thin"),bottom=Side(style="thin"))
    for j,b in enumerate(["Sayfa","Ad Soyad","Ogrenci No","Durum","Dogru","Yanlis","Bos","Puan"],1):
        h = ws.cell(row=1,column=j,value=b)
        h.fill=mavi; h.font=beyaz; h.alignment=Alignment(horizontal="center"); h.border=kenar
    for i,s in enumerate(sonuclar,2):
        for j,d in enumerate([s.get("sayfa"),s.get("ad_soyad"),s.get("ogrenci_no"),
                               s.get("durum"),s.get("dogru"),s.get("yanlis"),
                               s.get("bos"),s.get("puan")],1):
            hc = ws.cell(row=i,column=j,value=d)
            hc.border=kenar; hc.alignment=Alignment(horizontal="center")
            durum = s.get("durum","")
            if "Eslesme var" in durum: hc.fill=PatternFill("solid",fgColor="d1fae5")
            elif "farkli" in durum:    hc.fill=PatternFill("solid",fgColor="fef3c7")
            elif "yok" in durum:       hc.fill=PatternFill("solid",fgColor="fee2e2")
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width=18
    buf = BytesIO(); wb.save(buf); return buf.getvalue()

def excel_detay(sonuclar, cevap_anahtari, soru_sayisi=20):
    wb = Workbook(); ws = wb.active; ws.title = "Detay"
    mavi  = PatternFill("solid",fgColor="1a56db")
    beyaz = Font(color="FFFFFF",bold=True)
    kenar = Border(left=Side(style="thin"),right=Side(style="thin"),
                   top=Side(style="thin"),bottom=Side(style="thin"))
    basliklar = ["Ad Soyad","Ogrenci No"] + [f"S{i}" for i in range(1,soru_sayisi+1)]
    for j,b in enumerate(basliklar,1):
        h = ws.cell(row=1,column=j,value=b)
        h.fill=mavi; h.font=beyaz; h.alignment=Alignment(horizontal="center"); h.border=kenar
    ws.cell(row=2,column=1,value="CEVAP ANAHTARI").font=Font(bold=True)
    ws.cell(row=2,column=2,value="-")
    for s in range(1,soru_sayisi+1):
        hc = ws.cell(row=2,column=s+2,value=cevap_anahtari.get(s,"?"))
        hc.fill=PatternFill("solid",fgColor="dbeafe")
        hc.font=Font(bold=True); hc.alignment=Alignment(horizontal="center"); hc.border=kenar
    for i,s in enumerate(sonuclar,3):
        ws.cell(row=i,column=1,value=s.get("ad_soyad","")).border=kenar
        ws.cell(row=i,column=2,value=s.get("ogrenci_no","")).border=kenar
        for soru in range(1,soru_sayisi+1):
            c  = s.get("cevaplar",{}).get(soru,"?")
            a  = cevap_anahtari.get(soru,"?")
            hc = ws.cell(row=i,column=soru+2,value=c)
            hc.alignment=Alignment(horizontal="center"); hc.border=kenar
            if c==a:       hc.fill=PatternFill("solid",fgColor="d1fae5")
            elif c=="BOS": hc.fill=PatternFill("solid",fgColor="f3f4f6")
            else:          hc.fill=PatternFill("solid",fgColor="fee2e2")
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width=12
    buf = BytesIO(); wb.save(buf); return buf.getvalue()

# ─── SAYFALAR ───────────────────────────────────────────────
def sayfa_sablon():
    st.header("Sablon Yonetimi")
    uid = st.session_state.kullanici["id"]
    with st.container(border=True):
        st.subheader("Yeni Sablon Ekle")
        adi = st.text_input("Sablon Adi")
        ss  = st.selectbox("Soru Sayisi", [10,20,30,40,50], index=1)
        if st.button("Kaydet", type="primary"):
            if adi:
                con = db_bag()
                con.execute("INSERT INTO sablonlar (kullanici_id,ad,soru_sayisi) VALUES (?,?,?)",(uid,adi,ss))
                con.commit(); con.close()
                st.success(f"'{adi}' kaydedildi!"); st.rerun()
            else: st.warning("Sablon adi girin!")
    st.subheader("Kayitli Sablonlar")
    con = db_bag()
    rows = con.execute("SELECT id,ad,soru_sayisi,tarih FROM sablonlar WHERE kullanici_id=? ORDER BY id DESC",(uid,)).fetchall()
    con.close()
    if rows:
        for r in rows:
            c1,c2,c3,c4 = st.columns([3,2,3,1])
            c1.write(f"**{r[1]}**"); c2.write(f"{r[2]} soru"); c3.write(r[3][:16])
            if c4.button("Sil",key=f"ds{r[0]}"):
                con2=db_bag(); con2.execute("DELETE FROM sablonlar WHERE id=?",(r[0],)); con2.commit(); con2.close(); st.rerun()
    else: st.info("Henuz sablon yok.")

def sayfa_anahtar():
    st.header("Cevap Anahtari")
    uid = st.session_state.kullanici["id"]
    con = db_bag()
    sablonlar = con.execute("SELECT id,ad,soru_sayisi FROM sablonlar WHERE kullanici_id=?",(uid,)).fetchall()
    con.close()
    if not sablonlar: st.warning("Once sablon ekleyin!"); return
    sablon = st.selectbox("Sablon Sec", sablonlar, format_func=lambda x: f"{x[1]} ({x[2]} soru)")
    ss     = sablon[2]
    adi    = st.text_input("Cevap Anahtari Adi (orn: Vize 2025)")
    st.subheader("Cevaplari Sec")
    cevaplar = {}
    for i in range(0, ss, 5):
        cols = st.columns(5)
        for j,col in enumerate(cols):
            sno = i+j+1
            if sno <= ss:
                with col:
                    cevaplar[sno] = st.selectbox(f"Soru {sno}",["A","B","C","D","E"],key=f"ca{sno}")
    if st.button("Anahtari Kaydet", type="primary"):
        if adi:
            con = db_bag()
            con.execute("INSERT INTO cevap_anahtarlari (kullanici_id,sablon_id,ad,cevaplar) VALUES (?,?,?,?)",
                        (uid,sablon[0],adi,json.dumps(cevaplar)))
            con.commit(); con.close()
            st.success(f"'{adi}' kaydedildi!")
        else: st.warning("Cevap anahtari adi girin!")
    st.subheader("Kayitli Anahtarlar")
    con = db_bag()
    rows = con.execute("SELECT id,ad,tarih FROM cevap_anahtarlari WHERE kullanici_id=? ORDER BY id DESC",(uid,)).fetchall()
    con.close()
    for r in rows:
        c1,c2,c3 = st.columns([4,3,1])
        c1.write(f"**{r[1]}**"); c2.write(r[2][:16])
        if c3.button("Sil",key=f"da{r[0]}"):
            con2=db_bag(); con2.execute("DELETE FROM cevap_anahtarlari WHERE id=?",(r[0],)); con2.commit(); con2.close(); st.rerun()

def sayfa_liste():
    st.header("Ogrenci Listesi")
    uid = st.session_state.kullanici["id"]
    with st.container(border=True):
        st.subheader("Excel Yukle")
        st.caption("A sutunu = Ogrenci No | B sutunu = Ad Soyad")
        adi      = st.text_input("Liste Adi")
        yuklenen = st.file_uploader("Excel Dosyasi", type=["xlsx","xls"])
        if yuklenen and adi and st.button("Listeyi Kaydet", type="primary"):
            engine = "openpyxl" if yuklenen.name.endswith(".xlsx") else "xlrd"
            df = pd.read_excel(yuklenen, header=None, engine=engine)
            ogrenciler = [{"no":str(r[0]).strip(),"ad":str(r[1]).strip()} for _,r in df.iterrows()]
            con = db_bag()
            con.execute("INSERT INTO ogrenci_listeleri (kullanici_id,ad,ogrenciler) VALUES (?,?,?)",
                        (uid,adi,json.dumps(ogrenciler,ensure_ascii=False)))
            con.commit(); con.close()
            st.success(f"{len(ogrenciler)} ogrenci kaydedildi!"); st.rerun()
    st.subheader("Kayitli Listeler")
    con = db_bag()
    rows = con.execute("SELECT id,ad,ogrenciler,tarih FROM ogrenci_listeleri WHERE kullanici_id=? ORDER BY id DESC",(uid,)).fetchall()
    con.close()
    for r in rows:
        og = json.loads(r[2])
        c1,c2,c3,c4 = st.columns([3,2,3,1])
        c1.write(f"**{r[1]}**"); c2.write(f"{len(og)} ogrenci"); c3.write(r[3][:16])
        if c4.button("Sil",key=f"dl{r[0]}"):
            con2=db_bag(); con2.execute("DELETE FROM ogrenci_listeleri WHERE id=?",(r[0],)); con2.commit(); con2.close(); st.rerun()

def sayfa_sinav():
    st.header("Sinav Oku")
    uid = st.session_state.kullanici["id"]
    con = db_bag()
    sablonlar  = con.execute("SELECT id,ad,soru_sayisi FROM sablonlar WHERE kullanici_id=?",(uid,)).fetchall()
    anahtarlar = con.execute("SELECT id,ad,sablon_id,cevaplar FROM cevap_anahtarlari WHERE kullanici_id=?",(uid,)).fetchall()
    listeler   = con.execute("SELECT id,ad,ogrenciler FROM ogrenci_listeleri WHERE kullanici_id=?",(uid,)).fetchall()
    con.close()
    if not sablonlar or not anahtarlar:
        st.warning("Once sablon ve cevap anahtari ekleyin!"); return
    c1,c2 = st.columns(2)
    with c1:
        sablon  = st.selectbox("Sablon", sablonlar, format_func=lambda x: f"{x[1]} ({x[2]} soru)")
        anahtar = st.selectbox("Cevap Anahtari", anahtarlar, format_func=lambda x: x[1])
    with c2:
        liste   = st.selectbox("Ogrenci Listesi (opsiyonel)", [None]+list(listeler),
                               format_func=lambda x: "Secme" if x is None else x[1])
        api_key = st.text_input("Gemini API Key", type="password")
    pdf = st.file_uploader("Sinav PDF", type=["pdf"])
    if pdf and api_key and st.button("Sinavi Oku", type="primary", use_container_width=True):
        anahtardict = {int(k):v for k,v in json.loads(anahtar[3]).items()}
        ss          = sablon[2]
        og_dict     = {}
        if liste:
            og_dict = {o["no"]:o["ad"] for o in json.loads(liste[2])}
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf.read()); tmp = f.name
        sayfalar = convert_from_path(tmp, dpi=TARAMA_DPI, poppler_path=POPPLER_PATH)
        toplam   = len(sayfalar)
        st.write(f"**{toplam} sayfa bulundu**")
        prog     = st.progress(0)
        durum    = st.empty()
        sonuclar = []
        for i,sayfa in enumerate(sayfalar,1):
            if i > 1: time.sleep(1)
            durum.write(f"Sayfa {i}/{toplam} okunuyor...")
            s, hata = kagit_oku_web(sayfa, anahtardict, api_key, ss)
            if hata:
                sonuclar.append({"sayfa":i,"hata":hata,"durum":"Hata",
                                  "ad_soyad":"?","ogrenci_no":"?","dogru":0,
                                  "yanlis":0,"bos":ss,"puan":0,"cevaplar":{}})
            else:
                d = "Liste secilmedi"
                if og_dict:
                    no_e     = s["ogrenci_no"] in og_dict
                    liste_ad = og_dict.get(s["ogrenci_no"],"").lower()
                    ad_e     = any(p in liste_ad for p in s["ad_soyad"].lower().split() if len(p)>2)
                    if no_e and ad_e:  d = "Eslesme var"
                    elif no_e:         d = "No eslesti, ad farkli"
                    elif ad_e:         d = "Ad eslesti, no farkli"
                    else:              d = "Eslesme yok"
                s["sayfa"] = i; s["durum"] = d
                sonuclar.append(s)
            prog.progress(i/toplam)
        durum.empty()
        # ── DB'ye kaydet ─────────────────────────────────────
        basarili = sum(1 for s in sonuclar if not s.get("hata"))
        con = db_bag()
        cur = con.execute(
            "INSERT INTO taramalar (kullanici_id,anahtar_id,anahtar_adi,sablon_adi,"
            "soru_sayisi,cevap_anahtari,toplam_kagit,basarili) VALUES (?,?,?,?,?,?,?,?)",
            (uid, anahtar[0], anahtar[1], sablon[1], ss,
             json.dumps(anahtardict), toplam, basarili)
        )
        tarama_id = cur.lastrowid
        for s in sonuclar:
            con.execute(
                "INSERT INTO tarama_sonuclari (tarama_id,sayfa,ad_soyad,ogrenci_no,"
                "cevaplar,dogru,yanlis,bos,puan,durum,hata) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (tarama_id, s.get("sayfa"), s.get("ad_soyad","?"),
                 s.get("ogrenci_no","?"), json.dumps(s.get("cevaplar",{})),
                 s.get("dogru",0), s.get("yanlis",0), s.get("bos",0),
                 s.get("puan",0), s.get("durum",""), s.get("hata"))
            )
        con.commit(); con.close()
        st.session_state.sonuclar    = sonuclar
        st.session_state.anahtardict = anahtardict
        st.session_state.ss          = ss
        st.success(f"{toplam} kagit okundu ve kaydedildi!"); st.rerun()
    if "sonuclar" in st.session_state:
        sonuclar    = st.session_state.sonuclar
        anahtardict = st.session_state.anahtardict
        ss          = st.session_state.ss
        st.subheader("Sonuclar")
        df_data = [{"Sayfa":s.get("sayfa"),"Ad Soyad":s.get("ad_soyad"),
                    "No":s.get("ogrenci_no"),"Durum":s.get("durum"),
                    "Dogru":s.get("dogru"),"Yanlis":s.get("yanlis"),
                    "Puan":s.get("puan")} for s in sonuclar]
        st.dataframe(pd.DataFrame(df_data), use_container_width=True)
        c1,c2 = st.columns(2)
        with c1:
            st.download_button("Ozet Excel Indir", excel_ozet(sonuclar),
                               "ozet.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
        with c2:
            st.download_button("Detay Excel Indir", excel_detay(sonuclar,anahtardict,ss),
                               "detay.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)

def sayfa_gecmis():
    st.header("Gecmis Taramalar")
    uid = st.session_state.kullanici["id"]

    con = db_bag()
    taramalar = con.execute(
        "SELECT id,anahtar_adi,sablon_adi,soru_sayisi,toplam_kagit,basarili,tarih "
        "FROM taramalar WHERE kullanici_id=? ORDER BY id DESC", (uid,)
    ).fetchall()
    con.close()

    if not taramalar:
        st.info("Henuz kayitli tarama yok. 'Sinav Oku' sayfasindan tarama yapabilirsiniz.")
        return

    # Secili tarama session'da sakla
    if "gecmis_secili" not in st.session_state:
        st.session_state.gecmis_secili = None

    # ── Tarama listesi ──────────────────────────────────────
    st.subheader(f"Toplam {len(taramalar)} tarama")
    for t in taramalar:
        tid, anahtar_adi, sablon_adi, ss, toplam, basarili, tarih = t
        hata_sayisi = toplam - basarili
        secili = st.session_state.gecmis_secili == tid

        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
            c1.markdown(f"**{anahtar_adi}**  \n{sablon_adi} · {ss} soru")
            c2.markdown(f"**{toplam}** kagit  \n{basarili} basarili" +
                        (f", {hata_sayisi} hata" if hata_sayisi else ""))
            c3.markdown(f"{tarih[:16]}")
            if c4.button("Goster" if not secili else "Gizle", key=f"gos{tid}"):
                st.session_state.gecmis_secili = None if secili else tid
                st.rerun()
            if c5.button("Sil", key=f"sil{tid}"):
                con2 = db_bag()
                con2.execute("DELETE FROM tarama_sonuclari WHERE tarama_id=?", (tid,))
                con2.execute("DELETE FROM taramalar WHERE id=?", (tid,))
                con2.commit(); con2.close()
                if st.session_state.gecmis_secili == tid:
                    st.session_state.gecmis_secili = None
                st.rerun()

        # ── Secili taramanin detayi ─────────────────────────
        if secili:
            con = db_bag()
            row_t = con.execute(
                "SELECT cevap_anahtari FROM taramalar WHERE id=?", (tid,)
            ).fetchone()
            sonuclar_db = con.execute(
                "SELECT sayfa,ad_soyad,ogrenci_no,cevaplar,dogru,yanlis,bos,puan,durum,hata "
                "FROM tarama_sonuclari WHERE tarama_id=? ORDER BY sayfa", (tid,)
            ).fetchall()
            con.close()

            anahtardict = {int(k): v for k, v in json.loads(row_t[0]).items()}
            sonuclar = []
            for r in sonuclar_db:
                sonuclar.append({
                    "sayfa": r[0], "ad_soyad": r[1], "ogrenci_no": r[2],
                    "cevaplar": {int(k): v for k, v in json.loads(r[3]).items()},
                    "dogru": r[4], "yanlis": r[5], "bos": r[6],
                    "puan": r[7], "durum": r[8], "hata": r[9],
                })

            df_data = [{"Sayfa": s["sayfa"], "Ad Soyad": s["ad_soyad"],
                        "No": s["ogrenci_no"], "Durum": s["durum"],
                        "Dogru": s["dogru"], "Yanlis": s["yanlis"], "Puan": s["puan"]}
                       for s in sonuclar]
            st.dataframe(pd.DataFrame(df_data), use_container_width=True)

            ec1, ec2 = st.columns(2)
            with ec1:
                st.download_button(
                    "Ozet Excel", excel_ozet(sonuclar), f"ozet_{tid}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key=f"exc_ozet_{tid}"
                )
            with ec2:
                st.download_button(
                    "Detay Excel", excel_detay(sonuclar, anahtardict, ss), f"detay_{tid}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key=f"exc_detay_{tid}"
                )

def sayfa_kullanici():
    st.header("Kullanici Yonetimi")
    uid  = st.session_state.kullanici["id"]
    kadi = st.session_state.kullanici["kullanici_adi"]
    with st.container(border=True):
        st.subheader("Yeni Kullanici Ekle")
        yadi = st.text_input("Kullanici Adi")
        ytam = st.text_input("Ad Soyad")
        ysif = st.text_input("Sifre", type="password")
        if st.button("Kullanici Ekle", type="primary"):
            if yadi and ysif:
                try:
                    sh = bcrypt.hashpw(ysif.encode(),bcrypt.gensalt()).decode()
                    con = db_bag()
                    con.execute("INSERT INTO kullanicilar (kullanici_adi,sifre_hash,tam_ad) VALUES (?,?,?)",(yadi,sh,ytam))
                    con.commit(); con.close()
                    st.success(f"'{yadi}' eklendi!")
                except: st.error("Bu kullanici adi zaten var!")
            else: st.warning("Kullanici adi ve sifre gerekli!")
    with st.container(border=True):
        st.subheader("Sifre Degistir")
        eski = st.text_input("Mevcut Sifre", type="password")
        yeni = st.text_input("Yeni Sifre", type="password")
        if st.button("Sifreyi Degistir"):
            if giris_kontrol(kadi, eski):
                sh = bcrypt.hashpw(yeni.encode(),bcrypt.gensalt()).decode()
                con = db_bag()
                con.execute("UPDATE kullanicilar SET sifre_hash=? WHERE id=?",(sh,uid))
                con.commit(); con.close()
                st.success("Sifre degistirildi!")
            else: st.error("Mevcut sifre hatali!")

# ─── ANA UYGULAMA ────────────────────────────────────────────
st.set_page_config(page_title="OMR Sinav Sistemi", page_icon="📋",
                   layout="wide", initial_sidebar_state="expanded")
db_olustur()

if "kullanici" not in st.session_state:
    giris_sayfasi()
else:
    k = st.session_state.kullanici
    with st.sidebar:
        st.markdown(f"### {k['tam_ad'] or k['kullanici_adi']}")
        st.divider()
        sayfa = st.radio("Menu",[
            "Sablon Yonetimi",
            "Cevap Anahtari",
            "Ogrenci Listesi",
            "Sinav Oku",
            "Gecmis Taramalar",
            "Kullanici Yonetimi",
        ])
        st.divider()
        if st.button("Cikis Yap"):
            del st.session_state.kullanici
            st.rerun()

    if   sayfa == "Sablon Yonetimi":    sayfa_sablon()
    elif sayfa == "Cevap Anahtari":     sayfa_anahtar()
    elif sayfa == "Ogrenci Listesi":    sayfa_liste()
    elif sayfa == "Sinav Oku":          sayfa_sinav()
    elif sayfa == "Gecmis Taramalar":   sayfa_gecmis()
    elif sayfa == "Kullanici Yonetimi": sayfa_kullanici()
