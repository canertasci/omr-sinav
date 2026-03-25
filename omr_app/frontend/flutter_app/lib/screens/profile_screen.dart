// lib/screens/profile_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_hooks/flutter_hooks.dart';
import 'package:hooks_riverpod/hooks_riverpod.dart';

import '../providers/auth_provider.dart';
import '../providers/settings_provider.dart';

class ProfileScreen extends HookConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentKey = ref.watch(settingsProvider).valueOrNull ?? '';
    final controller = useTextEditingController(text: currentKey);
    final obscure = useState(true);
    final saved = useState(false);

    // Kaydedilen key değişince controller'ı güncelle
    useEffect(() {
      controller.text = currentKey;
      return null;
    }, [currentKey]);

    Future<void> saveKey() async {
      await ref.read(settingsProvider.notifier).save(controller.text);
      saved.value = true;
      Future.delayed(const Duration(seconds: 2), () {
        saved.value = false;
      });
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Ayarlar')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ── Gemini API Key ───────────────────────────────────────
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Text('Gemini API Key',
                          style: TextStyle(
                              fontWeight: FontWeight.bold, fontSize: 16)),
                      const Spacer(),
                      IconButton(
                        tooltip: 'Nasıl alınır?',
                        icon: const Icon(Icons.help_outline),
                        onPressed: () => _showHelpDialog(context),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'OMR tarama için Google Gemini API key gereklidir.',
                    style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: controller,
                    obscureText: obscure.value,
                    decoration: InputDecoration(
                      labelText: 'API Key',
                      hintText: 'AIza...',
                      prefixIcon: const Icon(Icons.key),
                      suffixIcon: IconButton(
                        icon: Icon(obscure.value
                            ? Icons.visibility
                            : Icons.visibility_off),
                        onPressed: () => obscure.value = !obscure.value,
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      if (saved.value) ...[
                        const Icon(Icons.check_circle,
                            color: Colors.green, size: 18),
                        const SizedBox(width: 6),
                        const Text('Kaydedildi',
                            style: TextStyle(color: Colors.green)),
                        const Spacer(),
                      ] else
                        const Spacer(),
                      FilledButton.icon(
                        onPressed: saveKey,
                        icon: const Icon(Icons.save),
                        label: const Text('Kaydet'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // ── Çıkış ────────────────────────────────────────────────
          OutlinedButton.icon(
            onPressed: () async {
              final confirm = await showDialog<bool>(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('Çıkış Yap'),
                  content: const Text('Hesabınızdan çıkmak istiyor musunuz?'),
                  actions: [
                    TextButton(
                        onPressed: () => Navigator.pop(ctx, false),
                        child: const Text('Vazgeç')),
                    FilledButton(
                        onPressed: () => Navigator.pop(ctx, true),
                        child: const Text('Çıkış Yap')),
                  ],
                ),
              );
              if (confirm == true && context.mounted) {
                await ref.read(authNotifierProvider.notifier).signOut();
              }
            },
            icon: const Icon(Icons.logout, color: Colors.red),
            label: const Text('Çıkış Yap',
                style: TextStyle(color: Colors.red)),
            style: OutlinedButton.styleFrom(
                side: const BorderSide(color: Colors.red)),
          ),
        ],
      ),
    );
  }

  void _showHelpDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.help_outline, color: Colors.blue),
            SizedBox(width: 8),
            Text('API Key Nasıl Alınır?'),
          ],
        ),
        content: const SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              _Step(
                  n: '1',
                  text: 'Google hesabınızla '
                      'aistudio.google.com adresine gidin.'),
              _Step(n: '2', text: '"Get API key" butonuna tıklayın.'),
              _Step(
                  n: '3',
                  text: '"Create API key" ile yeni bir key oluşturun.'),
              _Step(n: '4', text: 'Oluşturulan key\'i kopyalayın.'),
              _Step(
                  n: '5',
                  text:
                      'Bu ekrandaki alana yapıştırıp "Kaydet" e basın.'),
              SizedBox(height: 12),
              Text(
                'Not: Gemini 2.5 Flash modeli ücretsiz kotasıyla '
                'günlük yüzlerce tarama yapabilirsiniz.',
                style: TextStyle(
                    fontSize: 12, color: Colors.grey),
              ),
            ],
          ),
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Anladım'),
          ),
        ],
      ),
    );
  }
}

class _Step extends StatelessWidget {
  final String n;
  final String text;
  const _Step({required this.n, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 12,
            backgroundColor: Theme.of(context).colorScheme.primary,
            child: Text(n,
                style:
                    const TextStyle(color: Colors.white, fontSize: 12)),
          ),
          const SizedBox(width: 10),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}
