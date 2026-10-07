import 'package:centelha/api/catalogo_api.dart';
import 'package:centelha/app.dart';
import 'package:centelha/idioma/preferencia_idioma.dart';
import 'package:centelha/l10n/app_localizations.dart';
import 'package:centelha/tela/capitulo.dart';
import 'package:centelha/tela/compartilhar.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_falsa.dart';
import 'reprodutor_falso.dart';

Segmento _s(
  int id,
  TipoSegmento tipo,
  String texto, [
  int? questao,
  String? sub,
]) => Segmento(
  id: id,
  ordem: id,
  tipo: tipo,
  texto: texto,
  numeroQuestao: questao,
  subquestao: sub,
);

final _le = [
  _s(1, TipoSegmento.titulo, 'Dos Espíritos'),
  _s(2, TipoSegmento.pergunta, 'Os Espíritos têm forma?', 88),
  _s(3, TipoSegmento.resposta, '“Para vós, não; para nós, sim.”', 88),
  _s(4, TipoSegmento.pergunta, 'Essa chama tem cor?', 88, 'a'),
  _s(5, TipoSegmento.resposta, '“Tem uma coloração.”', 88, 'a'),
  _s(
    6,
    TipoSegmento.comentario,
    'Representam-se os gênios com uma chama.',
    88,
    'a',
  ),
];

final _capitulo = CapituloResumo(
  id: 20,
  ordem: 3,
  titulo: 'Capítulo I — Dos Espíritos',
  referencia: 'LE-C003',
);

const _citacaoLe = Citacao(
  autor: 'Allan Kardec',
  obra: 'O Livro dos Espíritos',
  slugObra: 'o-livro-dos-espiritos',
  tradutor: 'Guillon Ribeiro',
);

Obra _obra(String publico, {String idioma = 'pt-BR'}) => Obra(
  slug: 'o-evangelho-segundo-o-espiritismo',
  sigla: 'ESE',
  autor: 'Allan Kardec',
  tituloOriginal: 'L’Évangile selon le spiritisme',
  ano: 1864,
  edicoes: [
    EdicaoResumo(
      id: 7,
      idioma: idioma,
      publico: publico,
      titulo: 'O Evangelho segundo o Espiritismo',
      tradutor: 'Guillon Ribeiro',
    ),
  ],
);

void main() {
  final t = lookupAppLocalizations(const Locale('pt'));

  test('pergunta e resposta vão juntas; comentário vai sozinho', () {
    expect(trechoDe(_le[1], _le).map((s) => s.id), [2, 3]);
    expect(trechoDe(_le[2], _le).map((s) => s.id), [2, 3]);
    // A subquestão é outra pergunta: não arrasta a 88 nem é arrastada por ela.
    expect(trechoDe(_le[3], _le).map((s) => s.id), [4, 5]);
    expect(trechoDe(_le[5], _le).map((s) => s.id), [6]);
  });

  test('questão do LE sai com citação e link permanente da questão', () {
    final texto = textoParaCompartilhar(
      t,
      _citacaoLe,
      _capitulo,
      trechoDe(_le[1], _le),
      site: 'https://centelha.com.br',
    );
    expect(
      texto,
      '88. Os Espíritos têm forma?\n'
      '\n'
      '“Para vós, não; para nós, sim.”\n'
      '\n'
      '— Allan Kardec, O Livro dos Espíritos, questão 88. '
      'Tradução de Guillon Ribeiro.\n'
      'https://centelha.com.br/livro-dos-espiritos/questao/88',
    );
    expect(
      textoParaCompartilhar(t, _citacaoLe, _capitulo, [_le[3], _le[4]]),
      startsWith('88a. Essa chama tem cor?'),
    );
  });

  test('trecho sem questão leva à página do capítulo no site', () {
    final citacao = Citacao.daEdicao(
      _obra('adulto'),
      _obra('adulto').edicoes.single,
    )!;
    final paragrafo = _s(9, TipoSegmento.paragrafo, 'Fora da caridade.');
    expect(
      linkNoSite(citacao, _capitulo, [
        paragrafo,
      ], site: 'https://centelha.com.br').toString(),
      'https://centelha.com.br/obras/o-evangelho-segundo-o-espiritismo/capitulo-3',
    );
  });

  test('edição que não está no site vai sem link', () {
    final frances = _obra('adulto', idioma: 'fr-FR');
    final citacao = Citacao.daEdicao(frances, frances.edicoes.single)!;
    final paragrafo = _s(9, TipoSegmento.paragrafo, 'Hors la charité.');
    expect(linkNoSite(citacao, _capitulo, [paragrafo]), isNull);
    expect(
      textoParaCompartilhar(t, citacao, _capitulo, [paragrafo]),
      isNot(contains('http')),
    );
  });

  test('edição juvenil ou infantil não tem citação: não compartilha', () {
    // Perfil infantil: nenhum link externo (CLAUDE.md).
    for (final publico in ['infantil', 'juvenil']) {
      final obra = _obra(publico);
      expect(Citacao.daEdicao(obra, obra.edicoes.single), isNull);
    }
  });

  testWidgets('sem compartilhar, segurar o trecho não abre nada', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: const Locale('pt'),
        home: Scaffold(body: TextoCapitulo(segmentos: _le)),
      ),
    );
    await tester.longPress(find.text('Os Espíritos têm forma?'));
    await tester.pumpAndSettle();
    expect(find.text('Compartilhar trecho'), findsNothing);
  });

  group('no app', () {
    late List<String> compartilhados;
    String? copiado;

    setUp(() {
      compartilhados = [];
      copiado = null;
      compartilhador = (texto, origem) async => compartilhados.add(texto);
    });

    Future<void> abrirCapitulo(WidgetTester tester) async {
      tester.platformDispatcher.localesTestValue = const [Locale('pt', 'BR')];
      addTearDown(tester.platformDispatcher.clearLocalesTestValue);
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        (chamada) async {
          if (chamada.method == 'Clipboard.setData') {
            copiado = (chamada.arguments as Map)['text'] as String;
          }
          return null;
        },
      );
      SharedPreferences.setMockInitialValues({});
      final idioma = await PreferenciaIdioma.carregar();
      final (player, _) = await playerFalso();
      await tester.pumpWidget(
        CentelhaApp(api: apiFalsa(), idioma: idioma, player: player),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('O Livro dos Espíritos'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Capítulo I — De Deus'));
      await tester.pumpAndSettle();
    }

    testWidgets('segurar a pergunta compartilha a questão com o link', (
      tester,
    ) async {
      await abrirCapitulo(tester);
      await tester.longPress(find.text('Pergunta de exemplo 1?'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Compartilhar trecho'));
      await tester.pumpAndSettle();

      expect(compartilhados, hasLength(1));
      expect(
        compartilhados.single,
        startsWith(
          '1. Pergunta de exemplo 1?\n\n“Resposta de exemplo 1.”\n\n'
          '— Allan Kardec, O Livro dos Espíritos, questão 1. '
          'Tradução de Guillon Ribeiro.\n',
        ),
      );
      expect(compartilhados.single, endsWith('/livro-dos-espiritos/questao/1'));
    });

    testWidgets('copiar põe o mesmo texto na área de transferência', (
      tester,
    ) async {
      await abrirCapitulo(tester);
      await tester.longPress(find.text('“Resposta de exemplo 2.”'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Copiar trecho'));
      await tester.pumpAndSettle();

      expect(copiado, startsWith('2. Pergunta de exemplo 2?'));
      expect(find.text('Trecho copiado.'), findsOneWidget);
      expect(compartilhados, isEmpty);
    });

    testWidgets('título do capítulo não oferece compartilhar', (tester) async {
      await abrirCapitulo(tester);
      await tester.longPress(find.text('De Deus'));
      await tester.pumpAndSettle();
      expect(find.text('Compartilhar trecho'), findsNothing);
    });
  });
}
