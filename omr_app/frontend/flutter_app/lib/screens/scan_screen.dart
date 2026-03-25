// lib/screens/scan_screen.dart
import 'dart:convert';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_hooks/flutter_hooks.dart';
import 'package:go_router/go_router.dart';
import 'package:hooks_riverpod/hooks_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:pdfx/pdfx.dart';
import 'package:share_plus/share_plus.dart';

import '../providers/settings_provider.dart';
import '../services/api_service.dart';

// ─── Scan Screen ─────────────────────────────────────────────────────

class ScanScreen extends HookConsumerWidget {
  const ScanScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tabController = useTabController(initialLength: 2);
    final geminiKey = ref.watch(geminiKeyProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Sınav Tara'),
        bottom: TabBar(
          controller: tabController,
          tabs: const [
            Tab(icon: Icon(Icons.picture_as_pdf), text: 'PDF ile Toplu'),
            Tab(icon: Icon(Icons.camera_alt), text: 'Kamera ile Tek'),
          ],
        ),
      ),
      body: Column(
        children: [
          if (geminiKey.isEmpty)
            MaterialBanner(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              content: const Text(
                'Tarama yapmak için Gemini API key gerekli.',
                style: TextStyle(fontSize: 13),
              ),
              leading: const Icon(Icons.warning_amber_rounded, color: Colors.orange),
              backgroundColor: Colors.orange.shade50,
              actions: [
                TextButton(
                  onPressed: () => context.push('/profile'),
                  child: const Text('Ayarlara Git'),
                ),
              ],
            ),
          Expanded(
            child: TabBarView(
              controller: tabController,
              children: const [
                _PdfScanTab(),
                _SingleScanTab(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ─── PDF ile Toplu Tarama ────────────────────────────────────────────

class _PdfScanTab extends HookConsumerWidget {
  const _PdfScanTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pdfFile = useState<File?>(null);
    final pdfAd = useState('');
    final pdfPageCount = useState(0);
    final excelFile = useState<File?>(null);
    final excelAd = useState('');
    final sinavAdi = useTextEditingController(text: 'Sinav_1');
    final soruSayisi = useState(20);
    final cevaplar = useState<Map<int, String>>({});
    final isConverting = useState(false);
    final isLoading = useState(false);
    final error = useState<String?>(null);
    final result = useState<Map<String, dynamic>?>(null);
    final geminiKey = ref.watch(geminiKeyProvider);

    Future<void> pickPdf() async {
      final res = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf'],
      );
      if (res != null && res.files.single.path != null) {
        pdfFile.value = File(res.files.single.path!);
        pdfAd.value = res.files.single.name;
        isConverting.value = true;
        try {
          final doc = await PdfDocument.openFile(res.files.single.path!);
          pdfPageCount.value = doc.pagesCount;
          await doc.close();
        } catch (_) {
          pdfPageCount.value = 0;
        } finally {
          isConverting.value = false;
        }
      }
    }

    Future<void> pickExcel() async {
      final res = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['xlsx', 'xls'],
      );
      if (res != null && res.files.single.path != null) {
        excelFile.value = File(res.files.single.path!);
        excelAd.value = res.files.single.name;
      }
    }

    Future<List<File>> pdfToImages(String pdfPath) async {
      final doc = await PdfDocument.openFile(pdfPath);
      final dir = await getTemporaryDirectory();
      final images = <File>[];
      for (int i = 1; i <= doc.pagesCount; i++) {
        final page = await doc.getPage(i);
        final img = await page.render(
          width: page.width * 2,
          height: page.height * 2,
          format: PdfPageImageFormat.jpeg,
          quality: 90,
        );
        await page.close();
        if (img != null) {
          final f = File('${dir.path}/pdf_page_$i.jpg');
          await f.writeAsBytes(img.bytes);
          images.add(f);
        }
      }
      await doc.close();
      return images;
    }

    Future<void> shareExcel(String b64, String ad) async {
      final bytes = base64Decode(b64);
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/$ad');
      await file.writeAsBytes(bytes);
      await Share.shareXFiles([XFile(file.path)], text: ad);
    }

    Future<void> process() async {
      if (pdfFile.value == null) {
        error.value = 'PDF dosyası seçin';
        return;
      }
      if (cevaplar.value.length < soruSayisi.value) {
        error.value =
            'Tüm soruların cevabını girin (${cevaplar.value.length}/${soruSayisi.value})';
        return;
      }
      if (geminiKey.isEmpty) {
        error.value = 'Gemini API key girilmemiş. Ayarlar ekranından ekleyin.';
        return;
      }

      isLoading.value = true;
      error.value = null;
      result.value = null;

      try {
        final images = await pdfToImages(pdfFile.value!.path);
        final api = ref.read(apiServiceProvider);
        final cevapAnahtari = {
          for (final e in cevaplar.value.entries) '${e.key}': e.value,
        };
        final res = await api.scanExcelSinav(
          imageFiles: images,
          cevapAnahtari: cevapAnahtari,
          soruSayisi: soruSayisi.value,
          sinavAdi: sinavAdi.text.isNotEmpty ? sinavAdi.text : 'Sinav',
          ogrenciListesiExcel: excelFile.value,
          geminiApiKey: geminiKey,
        );
        result.value = res;
      } catch (e) {
        if (e is DioException && e.response != null) {
          error.value = 'HTTP ${e.response!.statusCode}: ${e.response!.data}';
        } else {
          error.value = e.toString();
        }
      } finally {
        isLoading.value = false;
      }
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // PDF Seç
        _SectionCard(
          icon: Icons.picture_as_pdf,
          title: 'Cevap Kağıtları (PDF)',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Her sayfa = bir öğrencinin cevap kağıdı',
                style: TextStyle(fontSize: 12, color: Colors.grey),
              ),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: pickPdf,
                icon: const Icon(Icons.upload_file),
                label: Text(pdfAd.value.isEmpty ? 'PDF Seç' : pdfAd.value),
              ),
              if (isConverting.value)
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: Row(children: [
                    SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2)),
                    SizedBox(width: 8),
                    Text('PDF okunuyor...'),
                  ]),
                ),
              if (pdfPageCount.value > 0)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Row(children: [
                    const Icon(Icons.check_circle,
                        color: Colors.green, size: 18),
                    const SizedBox(width: 6),
                    Text('${pdfPageCount.value} sayfa (öğrenci)'),
                  ]),
                ),
            ],
          ),
        ),
        const SizedBox(height: 12),

        // Öğrenci Listesi
        _SectionCard(
          icon: Icons.group,
          title: 'Öğrenci Listesi (isteğe bağlı)',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'A = Öğrenci No | B = Ad Soyad (başlık satırı olmadan)',
                style: TextStyle(fontSize: 12, color: Colors.grey),
              ),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: pickExcel,
                icon: const Icon(Icons.table_chart),
                label: Text(
                    excelAd.value.isEmpty ? 'Excel Yükle' : excelAd.value),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),

        // Sınav Bilgileri
        _SectionCard(
          icon: Icons.info_outline,
          title: 'Sınav Bilgileri',
          child: Column(children: [
            TextField(
              controller: sinavAdi,
              decoration: const InputDecoration(
                  labelText: 'Sınav Adı',
                  prefixIcon: Icon(Icons.label)),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<int>(
              value: soruSayisi.value,
              decoration: const InputDecoration(
                  labelText: 'Soru Sayısı',
                  prefixIcon: Icon(Icons.format_list_numbered)),
              items: [10, 20, 25, 40, 50, 100]
                  .map((n) => DropdownMenuItem(
                      value: n, child: Text('$n soru')))
                  .toList(),
              onChanged: (v) {
                if (v != null) {
                  soruSayisi.value = v;
                  cevaplar.value = {};
                }
              },
            ),
          ]),
        ),
        const SizedBox(height: 12),

        // Cevap Anahtarı
        _SectionCard(
          icon: Icons.key,
          title: 'Cevap Anahtarı',
          trailing: Text(
            '${cevaplar.value.length}/${soruSayisi.value}',
            style: TextStyle(
              color: cevaplar.value.length == soruSayisi.value
                  ? Colors.green
                  : Colors.orange,
              fontWeight: FontWeight.bold,
            ),
          ),
          child: _CevapGrid(
            soruSayisi: soruSayisi.value,
            cevaplar: cevaplar.value,
            onChanged: (q, c) =>
                cevaplar.value = {...cevaplar.value, q: c},
          ),
        ),
        const SizedBox(height: 16),

        if (error.value != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(error.value!,
                style: const TextStyle(color: Colors.red)),
          ),

        FilledButton.icon(
          onPressed: isLoading.value ? null : process,
          icon: isLoading.value
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: Colors.white))
              : const Icon(Icons.play_arrow),
          label: Text(isLoading.value
              ? 'İşleniyor... (${pdfPageCount.value} kağıt)'
              : 'Sınavı İşle'),
        ),

        if (result.value != null) ...[
          const SizedBox(height: 20),
          _ResultPanel(
            result: result.value!,
            sinavAdi: sinavAdi.text,
            onShareOzet: () => shareExcel(
              result.value!['ozet_excel_b64'] as String,
              '${sinavAdi.text}_ozet.xlsx',
            ),
            onShareDetay: () => shareExcel(
              result.value!['detay_excel_b64'] as String,
              '${sinavAdi.text}_detay.xlsx',
            ),
          ),
        ],
        const SizedBox(height: 32),
      ],
    );
  }
}

// ─── Kamera ile Tek Tarama ───────────────────────────────────────────

class _SingleScanTab extends HookConsumerWidget {
  const _SingleScanTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final imageFile = useState<File?>(null);
    final sinavAdi = useTextEditingController(text: 'Sinav_1');
    final soruSayisi = useState(20);
    final cevaplar = useState<Map<int, String>>({});
    final isLoading = useState(false);
    final error = useState<String?>(null);
    final result = useState<Map<String, dynamic>?>(null);
    final geminiKey = ref.watch(geminiKeyProvider);

    Future<void> takePhoto() async {
      final picker = ImagePicker();
      final picked = await picker.pickImage(
          source: ImageSource.camera, imageQuality: 85);
      if (picked != null) {
        imageFile.value = File(picked.path);
        result.value = null;
        error.value = null;
      }
    }

    Future<void> pickGallery() async {
      final picker = ImagePicker();
      final picked = await picker.pickImage(
          source: ImageSource.gallery, imageQuality: 85);
      if (picked != null) {
        imageFile.value = File(picked.path);
        result.value = null;
        error.value = null;
      }
    }

    Future<void> scan() async {
      if (imageFile.value == null) {
        error.value = 'Fotoğraf çekin veya seçin';
        return;
      }
      if (cevaplar.value.length < soruSayisi.value) {
        error.value =
            'Tüm soruların cevabını girin (${cevaplar.value.length}/${soruSayisi.value})';
        return;
      }
      if (geminiKey.isEmpty) {
        error.value = 'Gemini API key girilmemiş. Ayarlar ekranından ekleyin.';
        return;
      }

      isLoading.value = true;
      error.value = null;
      result.value = null;

      try {
        final api = ref.read(apiServiceProvider);
        final cevapAnahtari = {
          for (final e in cevaplar.value.entries) '${e.key}': e.value,
        };
        final res = await api.scanExcelSinav(
          imageFiles: [imageFile.value!],
          cevapAnahtari: cevapAnahtari,
          soruSayisi: soruSayisi.value,
          sinavAdi: sinavAdi.text.isNotEmpty ? sinavAdi.text : 'Sinav',
          geminiApiKey: geminiKey,
        );
        result.value = res;
      } catch (e) {
        error.value = e.toString();
      } finally {
        isLoading.value = false;
      }
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Fotoğraf
        _SectionCard(
          icon: Icons.image,
          title: 'Cevap Kağıdı',
          child: Column(children: [
            if (imageFile.value != null)
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.file(imageFile.value!,
                    height: 200,
                    width: double.infinity,
                    fit: BoxFit.cover),
              )
            else
              Container(
                height: 140,
                width: double.infinity,
                decoration: BoxDecoration(
                  color: Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.grey.shade300),
                ),
                child: const Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.camera_alt, size: 40, color: Colors.grey),
                    SizedBox(height: 8),
                    Text('Fotoğraf çekin veya seçin',
                        style: TextStyle(color: Colors.grey)),
                  ],
                ),
              ),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: takePhoto,
                  icon: const Icon(Icons.camera_alt),
                  label: const Text('Kamera'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: pickGallery,
                  icon: const Icon(Icons.photo_library),
                  label: const Text('Galeri'),
                ),
              ),
            ]),
          ]),
        ),
        const SizedBox(height: 12),

        // Sınav Bilgileri
        _SectionCard(
          icon: Icons.info_outline,
          title: 'Sınav Bilgileri',
          child: Column(children: [
            TextField(
              controller: sinavAdi,
              decoration: const InputDecoration(
                  labelText: 'Sınav Adı',
                  prefixIcon: Icon(Icons.label)),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<int>(
              value: soruSayisi.value,
              decoration: const InputDecoration(
                  labelText: 'Soru Sayısı',
                  prefixIcon: Icon(Icons.format_list_numbered)),
              items: [10, 20, 25, 40, 50, 100]
                  .map((n) => DropdownMenuItem(
                      value: n, child: Text('$n soru')))
                  .toList(),
              onChanged: (v) {
                if (v != null) {
                  soruSayisi.value = v;
                  cevaplar.value = {};
                }
              },
            ),
          ]),
        ),
        const SizedBox(height: 12),

        // Cevap Anahtarı
        _SectionCard(
          icon: Icons.key,
          title: 'Cevap Anahtarı',
          trailing: Text(
            '${cevaplar.value.length}/${soruSayisi.value}',
            style: TextStyle(
              color: cevaplar.value.length == soruSayisi.value
                  ? Colors.green
                  : Colors.orange,
              fontWeight: FontWeight.bold,
            ),
          ),
          child: _CevapGrid(
            soruSayisi: soruSayisi.value,
            cevaplar: cevaplar.value,
            onChanged: (q, c) =>
                cevaplar.value = {...cevaplar.value, q: c},
          ),
        ),
        const SizedBox(height: 16),

        if (error.value != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(error.value!,
                style: const TextStyle(color: Colors.red)),
          ),

        FilledButton.icon(
          onPressed: isLoading.value ? null : scan,
          icon: isLoading.value
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: Colors.white))
              : const Icon(Icons.document_scanner),
          label:
              Text(isLoading.value ? 'Taranıyor...' : 'Tara'),
        ),

        if (result.value != null) ...[
          const SizedBox(height: 20),
          _SingleResultCard(result: result.value!),
        ],
        const SizedBox(height: 32),
      ],
    );
  }
}

// ─── Section Card ─────────────────────────────────────────────────────

class _SectionCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final Widget child;
  final Widget? trailing;

  const _SectionCard({
    required this.icon,
    required this.title,
    required this.child,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(icon,
                  size: 20,
                  color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 8),
              Text(title,
                  style: const TextStyle(
                      fontWeight: FontWeight.bold, fontSize: 15)),
              const Spacer(),
              if (trailing != null) trailing!,
            ]),
            const SizedBox(height: 12),
            child,
          ],
        ),
      ),
    );
  }
}

// ─── Cevap Grid ───────────────────────────────────────────────────────

class _CevapGrid extends StatelessWidget {
  final int soruSayisi;
  final Map<int, String> cevaplar;
  final void Function(int, String) onChanged;

  const _CevapGrid({
    required this.soruSayisi,
    required this.cevaplar,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: List.generate(soruSayisi, (i) {
        final q = i + 1;
        final selected = cevaplar[q];
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 2),
          child: Row(children: [
            SizedBox(
              width: 30,
              child: Text('$q.',
                  style:
                      const TextStyle(fontWeight: FontWeight.bold)),
            ),
            ...['A', 'B', 'C', 'D', 'E'].map((opt) {
              final isSelected = selected == opt;
              return Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 2),
                  child: GestureDetector(
                    onTap: () => onChanged(q, opt),
                    child: Container(
                      height: 30,
                      decoration: BoxDecoration(
                        color: isSelected
                            ? Theme.of(context).colorScheme.primary
                            : Colors.grey.shade100,
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(
                          color: isSelected
                              ? Theme.of(context).colorScheme.primary
                              : Colors.grey.shade300,
                        ),
                      ),
                      alignment: Alignment.center,
                      child: Text(opt,
                          style: TextStyle(
                            color: isSelected
                                ? Colors.white
                                : Colors.black87,
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                          )),
                    ),
                  ),
                ),
              );
            }),
          ]),
        );
      }),
    );
  }
}

// ─── Result Panel (Batch) ─────────────────────────────────────────────

class _ResultPanel extends StatelessWidget {
  final Map<String, dynamic> result;
  final String sinavAdi;
  final VoidCallback onShareOzet;
  final VoidCallback onShareDetay;

  const _ResultPanel({
    required this.result,
    required this.sinavAdi,
    required this.onShareOzet,
    required this.onShareDetay,
  });

  @override
  Widget build(BuildContext context) {
    final toplam = result['toplam'] ?? 0;
    final basarili = result['basarili'] ?? 0;
    final hatali = result['hatali'] ?? 0;

    return Card(
      color: Theme.of(context).colorScheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('İşlem Tamamlandı',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _Stat('Toplam', '$toplam', Colors.blue),
                _Stat('Başarılı', '$basarili', Colors.green),
                _Stat('Hatalı', '$hatali', Colors.red),
              ],
            ),
            const SizedBox(height: 16),
            Row(children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: onShareOzet,
                  icon: const Icon(Icons.table_chart),
                  label: const Text('Özet Excel'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton.icon(
                  onPressed: onShareDetay,
                  icon: const Icon(Icons.grid_on),
                  label: const Text('Detay Excel'),
                ),
              ),
            ]),
          ],
        ),
      ),
    );
  }
}

// ─── Result Card (Single) ─────────────────────────────────────────────

class _SingleResultCard extends StatelessWidget {
  final Map<String, dynamic> result;
  const _SingleResultCard({required this.result});

  @override
  Widget build(BuildContext context) {
    final sonuclar = result['sonuclar'] as List<dynamic>? ?? [];
    if (sonuclar.isEmpty) {
      return const Card(child: Padding(
        padding: EdgeInsets.all(16),
        child: Text('Sonuç alınamadı'),
      ));
    }
    // Tek kağıt: ilk (ve tek) sonucu göster
    final s = (sonuclar.first as Map<String, dynamic>?)?['sonuc']
        as Map<String, dynamic>?;
    // excel-sinav endpoint her zaman ozet/detay döndürür ama
    // tek kağıt için özet tablosunu parse edelim
    final theme = Theme.of(context);
    return Card(
      color: theme.colorScheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Sonuç',
                style: theme.textTheme.titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text('Toplam: ${result['toplam']}  '
                'Başarılı: ${result['basarili']}  '
                'Hatalı: ${result['hatali']}'),
          ],
        ),
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _Stat(this.label, this.value, this.color);

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Text(value,
          style: TextStyle(
              fontSize: 28, fontWeight: FontWeight.bold, color: color)),
      Text(label,
          style: TextStyle(color: Colors.grey.shade700)),
    ]);
  }
}
