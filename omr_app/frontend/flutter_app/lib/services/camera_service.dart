// lib/services/camera_service.dart
import 'dart:io';
import 'package:google_mlkit_document_scanner/google_mlkit_document_scanner.dart';
import 'package:image_picker/image_picker.dart';

/// Kamera ve galeri erişim servisi.
/// Google ML Kit Document Scanner (offline, ücretsiz) önceliklidir.
/// Kullanılamıyorsa image_picker fallback'e düşer.
class CameraService {
  final ImagePicker _picker = ImagePicker();

  /// ML Kit Document Scanner ile belge tarama (yüksek kalite, perspektif düzeltme)
  Future<List<File>> scanWithMLKit({int maxPages = 30}) async {
    final options = DocumentScannerOptions(
      documentFormat: DocumentFormat.jpeg,
      mode: ScannerMode.full,
      isGalleryImport: false,
      pageLimit: maxPages,
    );

    final scanner = DocumentScanner(options: options);

    try {
      final result = await scanner.scanDocument();
      return result.images.map((path) => File(path)).toList();
    } catch (e) {
      // ML Kit yoksa boş liste döner, çağıran fallback uygular
      return [];
    } finally {
      scanner.close();
    }
  }

  /// Galeriden çoklu görüntü seçimi
  Future<List<File>> pickFromGallery({int maxImages = 30}) async {
    final images = await _picker.pickMultiImage(imageQuality: 95);
    return images.map((x) => File(x.path)).toList();
  }

  /// Tek fotoğraf çekimi (kamera)
  Future<File?> takePhoto() async {
    final image = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 95,
      preferredCameraDevice: CameraDevice.rear,
    );
    return image != null ? File(image.path) : null;
  }

  /// HEIC → JPEG dönüşümü (iOS)
  /// Not: image_picker iOS'ta zaten JPEG döndürebilir.
  /// Gerekli olursa flutter_image_compress paketi eklenir.
  Future<File> ensureJpeg(File file) async {
    final ext = file.path.toLowerCase();
    if (ext.endsWith('.heic') || ext.endsWith('.heif')) {
      // TODO: flutter_image_compress ile dönüştür
      // Şimdilik dosyayı olduğu gibi döndür
      return file;
    }
    return file;
  }
}

// Global singleton
final cameraService = CameraService();
