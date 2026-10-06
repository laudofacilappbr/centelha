import 'package:flutter/material.dart';

import '../api/catalogo_api.dart';
import '../idioma/preferencia_idioma.dart';
import '../l10n/app_localizations.dart';
import '../tema/centelha_tema.dart';
import 'comum.dart';
import 'configuracoes.dart';
import 'obra.dart';

/// Início: as obras publicadas.
class TelaInicio extends StatefulWidget {
  const TelaInicio({super.key, required this.api, required this.idioma});

  final CatalogoApi api;
  final PreferenciaIdioma idioma;

  @override
  State<TelaInicio> createState() => _TelaInicioState();
}

class _TelaInicioState extends State<TelaInicio> {
  late Future<List<Obra>> _obras = widget.api.obras();

  void _recarregar() {
    setState(() {
      _obras = widget.api.obras();
    });
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(t.obras),
        actions: [
          IconButton(
            tooltip: t.configuracoes,
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => TelaConfiguracoes(idioma: widget.idioma),
              ),
            ),
          ),
        ],
      ),
      body: FutureBuilder<List<Obra>>(
        future: _obras,
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
              texto: t.erroCatalogo,
              acao: FilledButton(
                onPressed: _recarregar,
                child: Text(t.tentarNovamente),
              ),
            );
          }
          final obras = snap.data!;
          if (obras.isEmpty) return Aviso(texto: t.catalogoVazio);
          final idioma = idiomaDoConteudo(Localizations.localeOf(context));
          return RefreshIndicator(
            onRefresh: () async {
              _recarregar();
              await _obras.catchError((_) => <Obra>[]);
            },
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: obras.length,
              separatorBuilder: (_, _) => const SizedBox(height: 12),
              itemBuilder: (context, i) =>
                  _CartaoObra(api: widget.api, obra: obras[i], idioma: idioma),
            ),
          );
        },
      ),
    );
  }
}

class _CartaoObra extends StatelessWidget {
  const _CartaoObra({
    required this.api,
    required this.obra,
    required this.idioma,
  });

  final CatalogoApi api;
  final Obra obra;
  final String idioma;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final tema = Theme.of(context);
    final edicao = obra.edicaoPara(idioma);
    final linhaAutor = [
      obra.autor,
      if (obra.ano != null) '${obra.ano}',
    ].join(' · ');
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) =>
                TelaObra(api: api, obra: obra, edicaoInicial: edicao),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: tema.colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(Raios.sm),
                ),
                child: Text(obra.sigla, style: tema.textTheme.titleSmall),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(edicao.titulo, style: tema.textTheme.titleMedium),
                    Text(linhaAutor, style: tema.textTheme.bodySmall),
                    Text(
                      t.edicoes(obra.edicoes.length),
                      style: tema.textTheme.labelSmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
