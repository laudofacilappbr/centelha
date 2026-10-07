// Centelha Kids (#50, ADR 0006): app separado, só com as edições infantis, na
// categoria Kids das lojas. Mesmo código do app principal, outra entrada
// (lib/main_kids.dart).
//
// Regra do projeto para o público infantil: nenhuma analítica, anúncio, apoio, Pix ou
// link externo. Aqui isso não é um `if`: as telas com apoio, campanha, configurações,
// compartilhar e troca de idioma não são importadas por este arquivo
// (test/kids_test.dart confere), o player não tem chaves nem downloads, e o capítulo
// abre sem citação nem origem, o que desliga compartilhar e trocar de edição.
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import '../api/catalogo_api.dart';
import '../idioma/preferencia_idioma.dart';
import '../l10n/app_localizations.dart';
import '../player/controle_player.dart';
import '../tela/capitulo.dart';
import '../tela/comum.dart';
import '../tema/centelha_tema.dart';

const publicoInfantil = 'infantil';

class CentelhaKidsApp extends StatelessWidget {
  const CentelhaKidsApp({
    super.key,
    required this.api,
    required this.idioma,
    required this.player,
  });

  final CatalogoApi api;
  final PreferenciaIdioma idioma;
  final ControlePlayer player;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: idioma,
      builder: (context, _) => MaterialApp(
        onGenerateTitle: (context) => AppLocalizations.of(context).kidsTitulo,
        debugShowCheckedModeBanner: false,
        theme: TemaCentelha.claro,
        darkTheme: TemaCentelha.escuro,
        locale: idioma.locale,
        supportedLocales: AppLocalizations.supportedLocales,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        localeListResolutionCallback: resolverLocale,
        builder: (context, filho) =>
            EscopoPlayer(player: player, child: filho!),
        home: TelaInicioKids(api: api),
      ),
    );
  }
}

/// Só as edições infantis, de todas as obras; o resto do catálogo não aparece.
List<(Obra, EdicaoResumo)> edicoesInfantis(List<Obra> obras) => [
  for (final o in obras)
    for (final e in o.edicoes)
      if (e.publico == publicoInfantil) (o, e),
];

class TelaInicioKids extends StatelessWidget {
  const TelaInicioKids({super.key, required this.api});

  final CatalogoApi api;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(t.kidsTitulo)),
      body: Carregavel<List<Obra>>(
        carregar: api.obras,
        construir: (context, obras) {
          final edicoes = edicoesInfantis(obras);
          if (edicoes.isEmpty) return Aviso(texto: t.kidsVazio);
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              for (final (obra, edicao) in edicoes)
                Card(
                  child: ListTile(
                    title: Text(edicao.titulo),
                    subtitle: Text(obra.autor),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => _TelaEdicaoKids(
                          api: api,
                          obra: obra,
                          edicao: edicao,
                        ),
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
}

class _TelaEdicaoKids extends StatelessWidget {
  const _TelaEdicaoKids({
    required this.api,
    required this.obra,
    required this.edicao,
  });

  final CatalogoApi api;
  final Obra obra;
  final EdicaoResumo edicao;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(edicao.titulo)),
      body: Carregavel<Edicao>(
        carregar: () => api.edicao(edicao.id),
        construir: (context, e) => ListView(
          padding: const EdgeInsets.symmetric(vertical: 8),
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
              child: Text(
                t.capitulos,
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            for (final c in e.capitulos)
              ListTile(
                title: Text(c.titulo),
                trailing: const Icon(Icons.chevron_right),
                // Sem citação e sem origem: nada de compartilhar nem de trocar de
                // edição, que levariam para fora do público infantil.
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => TelaCapitulo(
                      api: api,
                      resumo: c,
                      edicao: edicao.titulo,
                      autor: obra.autor,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
