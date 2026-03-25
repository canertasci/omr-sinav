// lib/screens/template_screen.dart
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_hooks/flutter_hooks.dart';
import 'package:hooks_riverpod/hooks_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../services/api_service.dart';

class TemplateScreen extends HookConsumerWidget {
  const TemplateScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dersAdi = useTextEditingController();
    final soruSayisi = useState(20);
    final layoutTipi = useState('standart');
    final isLoading = useState(false);
    final error = useState<String?>(null);
    final success = useState(false);

    Future<void> generate() async {
      isLoading.value = true;
      error.value = null;
      success.value = false;

      try {
        final api = ref.read(apiServiceProvider);
        final result = await api.generateTemplate(
          soruSayisi: soruSayisi.value,
          dersAdi: dersAdi.text.trim(),
          layoutTipi: layoutTipi.value,
        );

        // PDF base64 → dosya → paylaş
        final pdfB64 = result['pdf_base64'] as String;
        final pdfBytes = base64Decode(pdfB64);
        final dir = await getTemporaryDirectory();
        final file = File('${dir.path}/omr_sablon_${soruSayisi.value}s.pdf');
        await file.writeAsBytes(pdfBytes);

        await Share.shareXFiles(
          [XFile(file.path)],
          text: 'OMR Şablon — ${soruSayisi.value} soru',
        );
        success.value = true;
      } catch (e) {
        error.value = e.toString();
      } finally {
        isLoading.value = false;
      }
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Şablon Oluştur')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Açıklama
          Card(
            color: Theme.of(context).colorScheme.secondaryContainer,
            child: const Padding(
              padding: EdgeInsets.all(14),
              child: Row(
                children: [
                  Icon(Icons.info_outline),
                  SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Oluşturulan PDF\'i yazdırın. '
                      'Öğrenciler bu kağıda cevaplarını doldursun.',
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),

          // Form
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Şablon Ayarları',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 16),

                  TextField(
                    controller: dersAdi,
                    decoration: const InputDecoration(
                      labelText: 'Ders Adı (isteğe bağlı)',
                      prefixIcon: Icon(Icons.book),
                      hintText: 'örn. Matematik',
                    ),
                  ),
                  const SizedBox(height: 16),

                  DropdownButtonFormField<int>(
                    value: soruSayisi.value,
                    decoration: const InputDecoration(
                      labelText: 'Soru Sayısı',
                      prefixIcon: Icon(Icons.format_list_numbered),
                    ),
                    items: [10, 20, 25, 40, 50, 100]
                        .map((n) => DropdownMenuItem(
                            value: n, child: Text('$n soru')))
                        .toList(),
                    onChanged: (v) {
                      if (v != null) soruSayisi.value = v;
                    },
                  ),
                  const SizedBox(height: 16),

                  Text('Layout', style: Theme.of(context).textTheme.bodyMedium),
                  const SizedBox(height: 8),
                  SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(
                          value: 'standart',
                          label: Text('Standart'),
                          icon: Icon(Icons.grid_view)),
                      ButtonSegment(
                          value: 'genis',
                          label: Text('Geniş'),
                          icon: Icon(Icons.view_list)),
                    ],
                    selected: {layoutTipi.value},
                    onSelectionChanged: (s) => layoutTipi.value = s.first,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          if (error.value != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(error.value!,
                  style: const TextStyle(color: Colors.red)),
            ),

          if (success.value)
            const Padding(
              padding: EdgeInsets.only(bottom: 12),
              child: Row(
                children: [
                  Icon(Icons.check_circle, color: Colors.green),
                  SizedBox(width: 8),
                  Text('PDF oluşturuldu!',
                      style: TextStyle(color: Colors.green)),
                ],
              ),
            ),

          FilledButton.icon(
            onPressed: isLoading.value ? null : generate,
            icon: isLoading.value
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.picture_as_pdf),
            label: Text(isLoading.value ? 'Oluşturuluyor...' : 'PDF Oluştur'),
          ),
        ],
      ),
    );
  }
}
