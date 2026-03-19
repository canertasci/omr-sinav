// lib/providers/scan_provider.dart
import 'dart:io';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/scan_result.dart';
import '../services/api_service.dart';

// ─── Tarama State ────────────────────────────────────────────────────

class ScanState {
  final bool isLoading;
  final ScanResult? result;
  final List<ScanResult> batchResults;
  final String? error;
  final String? sinavId;
  final Map<String, String> cevapAnahtari;
  final int soruSayisi;

  const ScanState({
    this.isLoading = false,
    this.result,
    this.batchResults = const [],
    this.error,
    this.sinavId,
    this.cevapAnahtari = const {},
    this.soruSayisi = 20,
  });

  ScanState copyWith({
    bool? isLoading,
    ScanResult? result,
    List<ScanResult>? batchResults,
    String? error,
    String? sinavId,
    Map<String, String>? cevapAnahtari,
    int? soruSayisi,
  }) {
    return ScanState(
      isLoading: isLoading ?? this.isLoading,
      result: result ?? this.result,
      batchResults: batchResults ?? this.batchResults,
      error: error,
      sinavId: sinavId ?? this.sinavId,
      cevapAnahtari: cevapAnahtari ?? this.cevapAnahtari,
      soruSayisi: soruSayisi ?? this.soruSayisi,
    );
  }
}

// ─── Scan Notifier ───────────────────────────────────────────────────

class ScanNotifier extends StateNotifier<ScanState> {
  final ApiService _api;

  ScanNotifier(this._api) : super(const ScanState());

  void setSinavConfig({
    required String sinavId,
    required Map<String, String> cevapAnahtari,
    required int soruSayisi,
  }) {
    state = state.copyWith(
      sinavId: sinavId,
      cevapAnahtari: cevapAnahtari,
      soruSayisi: soruSayisi,
    );
  }

  Future<void> scanSingle(File imageFile) async {
    if (state.sinavId == null || state.cevapAnahtari.isEmpty) {
      state = state.copyWith(error: 'Önce sınav bilgilerini ayarlayın');
      return;
    }

    state = state.copyWith(isLoading: true, error: null);

    try {
      final sonuc = await _api.scanSingle(
        imageFile: imageFile,
        sinavId: state.sinavId!,
        sablonId: 'default',
        cevapAnahtari: state.cevapAnahtari,
        soruSayisi: state.soruSayisi,
      );
      state = state.copyWith(isLoading: false, result: sonuc);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<void> scanBatch(List<File> imageFiles) async {
    if (state.sinavId == null || state.cevapAnahtari.isEmpty) {
      state = state.copyWith(error: 'Önce sınav bilgilerini ayarlayın');
      return;
    }

    state = state.copyWith(isLoading: true, error: null, batchResults: []);

    try {
      final sonuclar = await _api.scanBatch(
        imageFiles: imageFiles,
        sinavId: state.sinavId!,
        sablonId: 'default',
        cevapAnahtari: state.cevapAnahtari,
        soruSayisi: state.soruSayisi,
      );
      state = state.copyWith(isLoading: false, batchResults: sonuclar);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  void reset() {
    state = ScanState(
      sinavId: state.sinavId,
      cevapAnahtari: state.cevapAnahtari,
      soruSayisi: state.soruSayisi,
    );
  }
}

final scanProvider = StateNotifierProvider<ScanNotifier, ScanState>((ref) {
  final api = ref.watch(apiServiceProvider);
  return ScanNotifier(api);
});
