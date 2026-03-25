// lib/screens/login_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/auth_provider.dart';
import '../services/api_service.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  final _adCtrl = TextEditingController();
  bool _isRegister = false;
  bool _obscure = true;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passCtrl.dispose();
    _adCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final notifier = ref.read(authNotifierProvider.notifier);

    if (_isRegister) {
      await notifier.registerWithEmail(_emailCtrl.text.trim(), _passCtrl.text);
      // Firestore'a kayıt
      if (ref.read(authNotifierProvider).valueOrNull != null) {
        await ref.read(apiServiceProvider).register(tamAd: _adCtrl.text.trim());
      }
    } else {
      await notifier.signInWithEmail(_emailCtrl.text.trim(), _passCtrl.text);
    }

    final err = ref.read(authNotifierProvider).error;
    if (err != null && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(err.toString()), backgroundColor: Colors.red),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final authState = ref.watch(authNotifierProvider);

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Form(
              key: _formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Logo / başlık
                  Icon(Icons.document_scanner, size: 72, color: theme.colorScheme.primary),
                  const SizedBox(height: 16),
                  Text(
                    'ÖğretmenAI',
                    style: theme.textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: theme.colorScheme.primary,
                    ),
                  ),
                  Text(
                    'Sınav Değerlendirme Modülü',
                    style: theme.textTheme.bodyMedium?.copyWith(color: Colors.grey),
                  ),
                  const SizedBox(height: 36),

                  // Kayıt modunda ad soyad
                  if (_isRegister) ...[
                    TextFormField(
                      controller: _adCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Ad Soyad',
                        prefixIcon: Icon(Icons.person),
                      ),
                      validator: (v) => v == null || v.isEmpty ? 'Ad Soyad gerekli' : null,
                    ),
                    const SizedBox(height: 16),
                  ],

                  TextFormField(
                    controller: _emailCtrl,
                    keyboardType: TextInputType.emailAddress,
                    decoration: const InputDecoration(
                      labelText: 'E-posta',
                      prefixIcon: Icon(Icons.email),
                    ),
                    validator: (v) => v == null || !v.contains('@') ? 'Geçerli e-posta girin' : null,
                  ),
                  const SizedBox(height: 16),

                  TextFormField(
                    controller: _passCtrl,
                    obscureText: _obscure,
                    decoration: InputDecoration(
                      labelText: 'Şifre',
                      prefixIcon: const Icon(Icons.lock),
                      suffixIcon: IconButton(
                        icon: Icon(_obscure ? Icons.visibility : Icons.visibility_off),
                        onPressed: () => setState(() => _obscure = !_obscure),
                      ),
                    ),
                    validator: (v) => v == null || v.length < 6 ? 'En az 6 karakter' : null,
                  ),
                  const SizedBox(height: 24),

                  authState.isLoading
                      ? const CircularProgressIndicator()
                      : FilledButton(
                          onPressed: _submit,
                          child: Text(_isRegister ? 'Kayıt Ol' : 'Giriş Yap'),
                        ),
                  const SizedBox(height: 12),

                  TextButton(
                    onPressed: () => setState(() => _isRegister = !_isRegister),
                    child: Text(
                      _isRegister
                          ? 'Zaten hesabım var — Giriş Yap'
                          : 'Hesabım yok — Kayıt Ol',
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
