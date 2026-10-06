import 'package:flutter/material.dart';

import '../l10n/app_localizations.dart';

/// Carrega um Future e mostra carregando, erro com "tentar de novo" ou o conteúdo.
class Carregavel<T> extends StatefulWidget {
  const Carregavel({
    super.key,
    required this.carregar,
    required this.construir,
    this.mensagemErro,
  });

  final Future<T> Function() carregar;
  final Widget Function(BuildContext context, T dados) construir;
  final String? mensagemErro;

  @override
  State<Carregavel<T>> createState() => _CarregavelState<T>();
}

class _CarregavelState<T> extends State<Carregavel<T>> {
  late Future<T> _futuro = widget.carregar();

  void _recarregar() {
    setState(() {
      _futuro = widget.carregar();
    });
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return FutureBuilder<T>(
      future: _futuro,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return Center(
            child: Semantics(
              label: t.carregando,
              child: const CircularProgressIndicator(),
            ),
          );
        }
        if (snap.hasError) {
          return Aviso(
            texto: widget.mensagemErro ?? t.erroCarregar,
            acao: FilledButton(
              onPressed: _recarregar,
              child: Text(t.tentarNovamente),
            ),
          );
        }
        return widget.construir(context, snap.data as T);
      },
    );
  }
}

class Aviso extends StatelessWidget {
  const Aviso({super.key, required this.texto, this.acao});

  final String texto;
  final Widget? acao;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(texto, textAlign: TextAlign.center),
            if (acao != null) ...[const SizedBox(height: 16), acao!],
          ],
        ),
      ),
    );
  }
}
