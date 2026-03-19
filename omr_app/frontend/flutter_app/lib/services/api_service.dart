// lib/services/api_service.dart
import 'dart:convert';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/scan_result.dart';

// Backend URL — production'da Railway/Render URL'si
const String _kBaseUrl = 'http://10.0.2.2:8000'; // Android emülatörde localhost

class ApiService {
  late final Dio _dio;

  ApiService() {
    _dio = Dio(BaseOptions(
      baseUrl: _kBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 60),
    ));

    // Firebase ID Token interceptor
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final user = FirebaseAuth.instance.currentUser;
        if (user != null) {
          final token = await user.getIdToken();
          options.headers['Authorization'] = 'Bearer $token';
        }
        return handler.next(options);
      },
      onError: (error, handler) {
        return handler.next(error);
      },
    ));
  }

  // ── Tarama ────────────────────────────────────────────────────────

  Future<ScanResult> scanSingle({
    required File imageFile,
    required String sinavId,
    required String sablonId,
    required Map<String, String> cevapAnahtari,
    required int soruSayisi,
  }) async {
    final bytes = await imageFile.readAsBytes();
    final b64 = base64Encode(bytes);

    final resp = await _dio.post('/api/v1/scan/single', data: {
      'goruntu_base64': b64,
      'sablon_id': sablonId,
      'sinav_id': sinavId,
      'cevap_anahtari': cevapAnahtari,
      'soru_sayisi': soruSayisi,
    });

    return ScanResult.fromJson(resp.data as Map<String, dynamic>);
  }

  Future<List<ScanResult>> scanBatch({
    required List<File> imageFiles,
    required String sinavId,
    required String sablonId,
    required Map<String, String> cevapAnahtari,
    required int soruSayisi,
  }) async {
    final goruntuler = <String>[];
    for (final f in imageFiles) {
      final bytes = await f.readAsBytes();
      goruntuler.add(base64Encode(bytes));
    }

    final resp = await _dio.post('/api/v1/scan/batch', data: {
      'goruntuler': goruntuler,
      'sablon_id': sablonId,
      'sinav_id': sinavId,
      'cevap_anahtari': cevapAnahtari,
      'soru_sayisi': soruSayisi,
    });

    final data = resp.data as Map<String, dynamic>;
    final sonuclar = data['sonuclar'] as List;
    return sonuclar
        .where((s) => s['sonuc'] != null)
        .map((s) => ScanResult.fromJson(s['sonuc'] as Map<String, dynamic>))
        .toList();
  }

  // ── Şablon ────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> generateTemplate({
    required int soruSayisi,
    required String dersAdi,
    String layoutTipi = 'standart',
  }) async {
    final resp = await _dio.post('/api/v1/template/generate', data: {
      'soru_sayisi': soruSayisi,
      'ders_adi': dersAdi,
      'layout_tipi': layoutTipi,
    });
    return resp.data as Map<String, dynamic>;
  }

  // ── Auth ──────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> register({
    required String tamAd,
    String kullaniciTipi = 'bireysel',
  }) async {
    final resp = await _dio.post('/api/v1/auth/register', data: {
      'tam_ad': tamAd,
      'kullanici_tipi': kullaniciTipi,
    });
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getMe() async {
    final resp = await _dio.get('/api/v1/auth/me');
    return resp.data as Map<String, dynamic>;
  }

  // ── Kredi ─────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getCreditsBalance() async {
    final resp = await _dio.get('/api/v1/credits/balance');
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> claimRewardAd() async {
    final resp = await _dio.post('/api/v1/credits/reward-ad');
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> verifyPurchase({
    required String productId,
    required String purchaseToken,
  }) async {
    final resp = await _dio.post('/api/v1/credits/verify-purchase', data: {
      'product_id': productId,
      'purchase_token': purchaseToken,
    });
    return resp.data as Map<String, dynamic>;
  }

  // ── Sonuçlar ──────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getResults(String sinavId) async {
    final resp = await _dio.get('/api/v1/results/$sinavId');
    return resp.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getStatistics(String sinavId) async {
    final resp = await _dio.get('/api/v1/results/$sinavId/statistics');
    return resp.data as Map<String, dynamic>;
  }
}

final apiServiceProvider = Provider<ApiService>((ref) => ApiService());
