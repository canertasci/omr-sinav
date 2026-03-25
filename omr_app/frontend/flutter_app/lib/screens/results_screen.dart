import 'package:flutter/material.dart';

class ResultsScreen extends StatelessWidget {
  final String sinavId;
  const ResultsScreen({super.key, required this.sinavId});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Sonuçlar')),
      body: Center(child: Text('Sınav ID: $sinavId')),
    );
  }
}
