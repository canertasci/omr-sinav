// lib/providers/settings_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kGeminiKey = 'gemini_api_key';

class SettingsNotifier extends AsyncNotifier<String> {
  @override
  Future<String> build() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_kGeminiKey) ?? '';
  }

  Future<void> save(String key) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kGeminiKey, key.trim());
    state = AsyncData(key.trim());
  }
}

final settingsProvider =
    AsyncNotifierProvider<SettingsNotifier, String>(SettingsNotifier.new);

/// Gemini API key'i doğrudan String olarak sunar (boş ise '').
final geminiKeyProvider = Provider<String>(
  (ref) => ref.watch(settingsProvider).valueOrNull ?? '',
);
