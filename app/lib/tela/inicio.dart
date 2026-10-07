import 'package:flutter/material.dart';

import '../api/catalogo_api.dart';
import '../idioma/preferencia_idioma.dart';
import '../l10n/app_localizations.dart';
import '../offline/downloads.dart';
import '../tema/centelha_tema.dart';
import '../player/controle_player.dart';
import '../player/progresso.dart';
import 'apoio.dart';
import 'campanha.dart';
import 'baixados.dart';
import 'capitulo.dart';
import 'comum.dart';
import 'configuracoes.dart';
import 'obra.dart';
import 'planos.dart';

/// Início: as obras publicadas.
class TelaInicio extends StatefulWidget {
  const TelaInicio({
    super.key,
    required this.api,
    required this.idioma,
    this.abrirLink = abrirNoNavegador,
  });

  final CatalogoApi api;
  final PreferenciaIdioma idioma;
  final AbrirLink abrirLink;

  @override
  State<TelaInicio> createState() => _TelaInicioState();
}

class _TelaInicioState extends State<TelaInicio> {
  late Future<List<Obra>> _obras = widget.api.obras();
  late Future<Campanha?> _campanha = campanhaParaMostrar(widget.api);

  void _recarregar() {
    setState(() {
      _obras = widget.api.obras();
      _campanha = campanhaParaMostrar(widget.api);
    });
  }

  void _fecharCampanha(Campanha campanha) {
    setState(() {
      _campanha = Future.value();
    });
    fecharCampanha(campanha);
  }

  void _abrirBaixados(Downloads downloads) => Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => TelaBaixados(api: widget.api, downloads: downloads),
    ),
  );

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
                builder: (_) =>
                    TelaConfiguracoes(idioma: widget.idioma, api: widget.api),
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
            // Sem internet o catálogo não vem, mas os baixados tocam.
            final downloads = EscopoPlayer.of(context).downloads;
            return Aviso(
              texto: t.erroCatalogo,
              acao: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  FilledButton(
                    onPressed: _recarregar,
                    child: Text(t.tentarNovamente),
                  ),
                  if (downloads != null)
                    TextButton(
                      onPressed: () => _abrirBaixados(downloads),
                      child: Text(t.ouvirBaixados),
                    ),
                ],
              ),
            );
          }
          // O infantil fica só no Centelhar Kids (#50): aqui não aparece.
          final obras = [for (final o in snap.data!) ?o.semInfantil()];
          if (obras.isEmpty) return Aviso(texto: t.catalogoVazio);
          final idioma = idiomaDoConteudo(Localizations.localeOf(context));
          return RefreshIndicator(
            onRefresh: () async {
              _recarregar();
              await _obras.catchError((_) => <Obra>[]);
            },
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                FutureBuilder<Campanha?>(
                  future: _campanha,
                  builder: (context, snap) => switch (snap.data) {
                    final c? => CartaoCampanha(
                      campanha: c,
                      aoFechar: () => _fecharCampanha(c),
                      abrirLink: widget.abrirLink,
                    ),
                    null => const SizedBox.shrink(),
                  },
                ),
                if (EscopoPlayer.of(context).downloads case final d?)
                  _AvisoVencimento(
                    downloads: d,
                    abrir: () => _abrirBaixados(d),
                  ),
                if (EscopoPlayer.of(context).armazem.ultimo() case final u?)
                  _ContinuarOuvindo(api: widget.api, ultimo: u),
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Card(
                    margin: EdgeInsets.zero,
                    child: ListTile(
                      leading: const Icon(Icons.event_note_outlined),
                      title: Text(t.planosDeEstudo),
                      subtitle: Text(t.planosDeEstudoChamada),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) =>
                              TelaPlanos(api: widget.api, obras: obras),
                        ),
                      ),
                    ),
                  ),
                ),
                for (final obra in obras)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: _CartaoObra(
                      api: widget.api,
                      obra: obra,
                      idioma: idioma,
                    ),
                  ),
              ],
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

class _ContinuarOuvindo extends StatelessWidget {
  const _ContinuarOuvindo({required this.api, required this.ultimo});

  final CatalogoApi api;
  final UltimoOuvido ultimo;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final tema = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Card(
        margin: EdgeInsets.zero,
        color: tema.colorScheme.surfaceContainerHighest,
        clipBehavior: Clip.antiAlias,
        child: ListTile(
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 16,
            vertical: 8,
          ),
          leading: Icon(
            Icons.play_circle,
            color: tema.colorScheme.primary,
            size: 40,
          ),
          title: Text(t.continuarOuvindo, style: tema.textTheme.labelSmall),
          subtitle: Text(
            '${ultimo.capitulo.titulo}\n${ultimo.info.edicao}',
            style: tema.textTheme.titleSmall,
          ),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => TelaCapitulo(
                api: api,
                resumo: ultimo.capitulo,
                edicao: ultimo.info.edicao,
                autor: ultimo.info.autor,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Chave de capítulo baixado perto de vencer (decisão 2B): o app renova sozinho ao
/// abrir com internet; se ainda está aqui, é porque não conseguiu.
class _AvisoVencimento extends StatelessWidget {
  const _AvisoVencimento({required this.downloads, required this.abrir});

  final Downloads downloads;
  final VoidCallback abrir;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final tema = Theme.of(context);
    return ListenableBuilder(
      listenable: downloads,
      builder: (context, _) => FutureBuilder<List<Baixado>>(
        future: downloads.vencendo(DateTime.now()),
        builder: (context, snap) {
          final n = snap.data?.length ?? 0;
          if (n == 0) return const SizedBox.shrink();
          return Padding(
            padding: const EdgeInsets.only(bottom: 20),
            child: Card(
              margin: EdgeInsets.zero,
              color: tema.colorScheme.surfaceContainerHighest,
              child: ListTile(
                leading: const Icon(Icons.wifi_off),
                title: Text(t.avisoBaixadosVencendo(n)),
                trailing: const Icon(Icons.chevron_right),
                onTap: abrir,
              ),
            ),
          );
        },
      ),
    );
  }
}
