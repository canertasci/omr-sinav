"""
Firebase / Firestore servis katmanı.
Kullanıcı CRUD, kredi işlemleri, sınav/sonuç kayıtları.
"""
from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from typing import Any

import firebase_admin
from firebase_admin import firestore, auth, credentials

_firebase_initialized = False
_db = None


def _get_db():
    global _firebase_initialized, _db
    if not _firebase_initialized:
        sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        if sa_json:
            sa_dict = json.loads(sa_json)
            cred = credentials.Certificate(sa_dict)
        else:
            sa_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase_service_account.json")
            cred = credentials.Certificate(sa_path)

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        _firebase_initialized = True

    if _db is None:
        _db = firestore.client()
    return _db


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────── Kullanıcı ───────────────────────────────

def kullanici_olustur(uid: str, email: str, tam_ad: str, kullanici_tipi: str = "bireysel") -> dict:
    """Yeni kullanıcı oluşturur, 500 ücretsiz kredi verir."""
    db = _get_db()
    ilk_kredi = int(os.getenv("INITIAL_FREE_CREDITS", "500"))
    simdi = _now()

    kullanici = {
        "uid": uid,
        "email": email,
        "tam_ad": tam_ad,
        "kullanici_tipi": kullanici_tipi,
        "kurum_id": None,
        "kredi": ilk_kredi,
        "toplam_kullanilan": 0,
        "kayit_tarihi": simdi,
        "son_giris": simdi,
    }
    db.collection("users").document(uid).set(kullanici)

    # Kredi işlemi kaydı
    db.collection("kredi_islemleri").add({
        "uid": uid,
        "tur": "hediye",
        "miktar": ilk_kredi,
        "aciklama": "İlk kayıt hediyesi",
        "tarih": simdi,
        "play_purchase_token": None,
    })

    return kullanici


def kullanici_getir(uid: str) -> dict | None:
    db = _get_db()
    doc = db.collection("users").document(uid).get()
    return doc.to_dict() if doc.exists else None


def son_giris_guncelle(uid: str) -> None:
    db = _get_db()
    db.collection("users").document(uid).update({"son_giris": _now()})


# ─────────────────────────── Kredi ───────────────────────────────────

def kredi_oku(uid: str) -> int:
    kullanici = kullanici_getir(uid)
    return kullanici.get("kredi", 0) if kullanici else 0


def kredi_dус(uid: str, miktar: int = 1, aciklama: str = "Başarılı okuma") -> bool:
    """
    Atomik Firestore transaction ile kredi düşer.
    Yeterli kredi yoksa False döner ve kredi düşmez.
    """
    db = _get_db()
    ref = db.collection("users").document(uid)

    @firestore.transactional
    def _transaction(transaction, ref):
        snapshot = ref.get(transaction=transaction)
        mevcut_kredi = snapshot.get("kredi")
        if mevcut_kredi < miktar:
            return False
        yeni_kredi = mevcut_kredi - miktar
        transaction.update(ref, {
            "kredi": yeni_kredi,
            "toplam_kullanilan": snapshot.get("toplam_kullanilan", 0) + miktar,
        })
        return True

    trans = db.transaction()
    basarili = _transaction(trans, ref)

    if basarili:
        db.collection("kredi_islemleri").add({
            "uid": uid,
            "tur": "kullanim",
            "miktar": -miktar,
            "aciklama": aciklama,
            "tarih": _now(),
            "play_purchase_token": None,
        })

    return basarili


def kredi_ekle(uid: str, miktar: int, aciklama: str, play_token: str | None = None) -> int:
    """Kredi ekler ve yeni bakiyeyi döndürür."""
    db = _get_db()
    ref = db.collection("users").document(uid)

    @firestore.transactional
    def _transaction(transaction, ref):
        snapshot = ref.get(transaction=transaction)
        yeni_kredi = snapshot.get("kredi", 0) + miktar
        transaction.update(ref, {"kredi": yeni_kredi})
        return yeni_kredi

    trans = db.transaction()
    yeni_kredi = _transaction(trans, ref)

    db.collection("kredi_islemleri").add({
        "uid": uid,
        "tur": "satin_alma" if play_token else "reklam",
        "miktar": miktar,
        "aciklama": aciklama,
        "tarih": _now(),
        "play_purchase_token": play_token,
    })

    return yeni_kredi


def satin_alma_Token_kullanildi_mi(token: str) -> bool:
    """Purchase token daha önce kullanılmış mı? (double-spend önleme)"""
    db = _get_db()
    docs = (
        db.collection("kredi_islemleri")
        .where("play_purchase_token", "==", token)
        .limit(1)
        .get()
    )
    return len(docs) > 0


# ─────────────────────────── Sınav ───────────────────────────────────

def sinav_olustur(sinav_data: dict) -> str:
    db = _get_db()
    simdi = _now()
    sinav_data["olusturulma"] = simdi
    sinav_data["guncelleme"] = simdi
    _, ref = db.collection("sinavlar").add(sinav_data)
    return ref.id


def sinav_getir(sinav_id: str) -> dict | None:
    db = _get_db()
    doc = db.collection("sinavlar").document(sinav_id).get()
    return doc.to_dict() if doc.exists else None


def ogretmen_sinavlari(ogretmen_id: str) -> list[dict]:
    db = _get_db()
    docs = (
        db.collection("sinavlar")
        .where("ogretmen_id", "==", ogretmen_id)
        .order_by("olusturulma", direction=firestore.Query.DESCENDING)
        .get()
    )
    return [{"id": d.id, **d.to_dict()} for d in docs]


# ─────────────────────────── Sonuç ───────────────────────────────────

def sonuc_kaydet(sonuc_data: dict) -> str:
    db = _get_db()
    sonuc_data["tarama_tarihi"] = _now()
    sonuc_data["kontrol_edildi"] = False
    _, ref = db.collection("sonuclar").add(sonuc_data)
    return ref.id


def sinav_sonuclari(sinav_id: str) -> list[dict]:
    db = _get_db()
    docs = (
        db.collection("sonuclar")
        .where("sinav_id", "==", sinav_id)
        .order_by("tarama_tarihi", direction=firestore.Query.DESCENDING)
        .get()
    )
    return [{"id": d.id, **d.to_dict()} for d in docs]


def sonuc_guncelle(sonuc_id: str, guncelleme: dict) -> None:
    db = _get_db()
    db.collection("sonuclar").document(sonuc_id).update(guncelleme)
