"""
Tüm Gemini prompt şablonları merkezi dosyada.
omr_engine.py ve diğer modüller buradan import eder.
"""
from __future__ import annotations


OGRENCI_NO = """
Bu görüntüde bir öğrenci numarası balon tablosu var.
- 9 SÜTUN (soldan sağa = 1. hane, 2. hane, ..., 9. hane)
- 10 SATIR (yukarıdan aşağı = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 rakamları)
- Her sütunda KESINLIKLE YALNIZCA BİR balon dolu olmalıdır.
- Dolu balon = tamamen siyah veya koyu dolgulu daire.
- Her sütunu BAĞIMSIZ olarak değerlendirip en koyu balonu bul.
SADECE JSON dön, başka hiçbir şey yazma:
{"no": "123456789"}
"""

OGRENCI_BILGI = """
Bu görüntüde öğrenci bilgi formu var.
Ad Soyad, Bölüm/Program ve Ders Adı alanlarını oku. El yazısı olabilir.
SADECE JSON dön:
{"ad_soyad": "Ad Soyad", "bolum": "Bölüm", "ders": "Ders"}
"""

SINAV_GRUBU = """
Bu görüntüde öğrenci bilgi formu ve altında "Sınav Grubu" bölümü var.
Sınav Grubu kısmında A, B, C, D seçenekleri var (checkbox/balon).
Öğrenci bu balonlardan BİRİNİ doldurmuş olmalı.
- Dolu balon = tamamen siyah veya koyu dolgulu daire.
- Hangi balon doluysa o grubu döndür.
- Hiçbiri dolu değilse veya bölüm yoksa "YOK" döndür.
SADECE JSON dön:
{"sinav_grubu": "A"}
"""


def cevap_balonlari(soru_bas: int, soru_bit: int) -> str:
    """Belirtilen soru aralığı için cevap okuma prompt'u."""
    return f"""
Bu görüntüde {soru_bas} ile {soru_bit} arasındaki soruların cevap balonları var.
- Her satır bir soru, her satırda A B C D E şıkları var.
- Her satırda YALNIZCA BİR balon dolu olmalıdır (en koyu olan).
- Birden fazla eşit koyulukta balon varsa hepsini yaz (örneğin "A/C").
- Hiç dolu balon yoksa "BOS" yaz.
SADECE JSON dön:
{{"{soru_bas}": "A", "{soru_bas + 1}": "BOS", ..., "{soru_bit}": "C"}}
"""
