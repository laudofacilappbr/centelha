import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api/catalogo_api.dart';
import '../chave/chaves.dart';
import '../l10n/app_localizations.dart';
import '../offline/downloads.dart';
import 'capitulo.dart';
import 'comum.dart';

/// Capítulos baixados, que abrem sem internet: o capítulo vem da ficha guardada com
/// o download, não da API.
class TelaBaixados extends StatefulWidget {
  const TelaBaixados({
    super.key,
    required this.api,
    required this.downloads,
    this.agora = DateTime.now,
  });

  final CatalogoApi api;
  final Downloads downloads;
  final DateTime Function() agora;

  @override
  State<TelaBaixados> createState() => _TelaBaixadosState();
}

class _TelaBaixadosState extends State<TelaBaixados> {
  late Future<List<Baixado>> _lista = widget.downloads.lista();

  @override
  void initState() {
    super.initState();
    widget.downloads.addListener(_recarregar);
  }

  @override
  void dispose() {
    widget.downloads.removeListener(_recarregar);
    super.dispose();
  }

  void _recarregar() => setState(() => _lista = widget.downloads.lista());

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(t.baixados)),
      body: FutureBuilder<List<Baixado>>(
        future: _lista,
        builder: (context, snap) {
          final lista = snap.data;
          if (lista == null) {
            return const Center(child: CircularProgressIndicator());
          }
          if (lista.isEmpty) return Aviso(texto: t.baixadosVazio);
          return ListView(
            children: [
              for (final b in lista)
                ListTile(
                  title: Text(b.capitulo.resumo.titulo),
                  subtitle: Text(_situacao(context, b)),
                  leading: Icon(
                    _vencendo(b) ? Icons.wifi_off : Icons.download_done,
                  ),
                  trailing: IconButton(
                    tooltip: t.apagar,
                    icon: const Icon(Icons.delete_outline),
                    onPressed: () => widget.downloads.apagar(b.faixa),
                  ),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => TelaCapitulo(
                        api: widget.api,
                        resumo: b.capitulo.resumo,
                        edicao: b.info.edicao,
                        autor: b.info.autor,
                        pronto: b.capitulo,
                      ),
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  bool _vencendo(Baixado b) =>
      b.validaAte == null ||
      b.validaAte!.isBefore(widget.agora().add(ClienteChaves.folgaRenovacao));

  String _situacao(BuildContext context, Baixado b) {
    final t = AppLocalizations.of(context);
    final validade = b.validaAte;
    if (validade == null || !validade.isAfter(widget.agora())) {
      return t.baixadoVencido(b.info.edicao);
    }
    final data = DateFormat.yMd(Localizations.localeOf(context).toLanguageTag())
        .format(validade.toLocal());
    return _vencendo(b)
        ? t.baixadoRenovar(b.info.edicao, data)
        : t.baixadoValeAte(b.info.edicao, data);
  }
}
