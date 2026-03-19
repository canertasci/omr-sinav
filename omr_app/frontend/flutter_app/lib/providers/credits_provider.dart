// lib/providers/credits_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/api_service.dart';

class CreditsState {
  final int kredi;
  final int toplamKullanilan;
  final bool isLoading;
  final String? error;

  const CreditsState({
    this.kredi = 0,
    this.toplamKullanilan = 0,
    this.isLoading = false,
    this.error,
  });

  CreditsState copyWith({
    int? kredi,
    int? toplamKullanilan,
    bool? isLoading,
    String? error,
  }) {
    return CreditsState(
      kredi: kredi ?? this.kredi,
      toplamKullanilan: toplamKullanilan ?? this.toplamKullanilan,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

class CreditsNotifier extends StateNotifier<CreditsState> {
  final ApiService _api;

  CreditsNotifier(this._api) : super(const CreditsState());

  Future<void> refresh() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final balance = await _api.getCreditsBalance();
      state = state.copyWith(
        isLoading: false,
        kredi: balance['kredi'] as int,
        toplamKullanilan: balance['toplam_kullanilan'] as int,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<bool> claimRewardAd() async {
    try {
      final result = await _api.claimRewardAd();
      if (result['success'] == true) {
        state = state.copyWith(kredi: result['yeni_kredi'] as int);
        return true;
      }
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
    return false;
  }
}

final creditsProvider = StateNotifierProvider<CreditsNotifier, CreditsState>((ref) {
  final api = ref.watch(apiServiceProvider);
  return CreditsNotifier(api);
});
