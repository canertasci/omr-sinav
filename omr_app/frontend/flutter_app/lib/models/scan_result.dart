// lib/models/scan_result.dart

class ScanResult {
  final String ogrenciNo;
  final String adSoyad;
  final String bolum;
  final String ders;
  final Map<String, String> cevaplar;
  final int dogru;
  final int yanlis;
  final int bos;
  final double puan;
  final double guvenskor;
  final String? hata;

  const ScanResult({
    required this.ogrenciNo,
    required this.adSoyad,
    required this.bolum,
    required this.ders,
    required this.cevaplar,
    required this.dogru,
    required this.yanlis,
    required this.bos,
    required this.puan,
    required this.guvenskor,
    this.hata,
  });

  factory ScanResult.fromJson(Map<String, dynamic> json) {
    return ScanResult(
      ogrenciNo: json['ogrenci_no'] as String? ?? '?????????',
      adSoyad: json['ad_soyad'] as String? ?? '?',
      bolum: json['bolum'] as String? ?? '?',
      ders: json['ders'] as String? ?? '?',
      cevaplar: (json['cevaplar'] as Map<String, dynamic>? ?? {})
          .map((k, v) => MapEntry(k, v.toString())),
      dogru: json['dogru'] as int? ?? 0,
      yanlis: json['yanlis'] as int? ?? 0,
      bos: json['bos'] as int? ?? 0,
      puan: (json['puan'] as num?)?.toDouble() ?? 0.0,
      guvenskor: (json['guvenskor'] as num?)?.toDouble() ?? 0.0,
      hata: json['hata'] as String?,
    );
  }

  bool get manuelKontrolGerekli => guvenskor < 0.85;
  bool get basarili => hata == null;
}
