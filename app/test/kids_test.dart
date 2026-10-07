import 'dart:io';

import 'package:centelha/api/catalogo_api.dart';
import 'package:centelha/idioma/preferencia_idioma.dart';
import 'package:centelha/kids/app_kids.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'catalogo_api_test.dart' show respostaJson;
import 'reprodutor_falso.dart';

Map<String, dynamic> _edicaoResumo(int id, String publico, String titulo) => {
  'id': id,
  'idioma': 'pt-BR',
  'publico': publico,
  'titulo': titulo,
  'tradutor': null,
  'publicada_em': '2026-10-01T12:00:00Z',
};

final _obras = [
  {
    'slug': 'o-livro-dos-espiritos',
    'sigla': 'LE',
    'autor': 'Allan Kardec',
    'titulo_original': 'Le Livre des Esprits',
    'ano': 1857,
    'edicoes': [
      _edicaoResumo(1, 'adulto', 'O Livro dos Espíritos'),
      _edicaoResumo(2, 'juvenil', 'O Livro dos Espíritos para jovens'),
      _edicaoResumo(3, 'infantil', 'A Clara e o Livro dos Espíritos'),
    ],
  },
];

final _rotas = <String, Object>{
  '/v1/edicoes/3': {
    ..._edicaoResumo(3, 'infantil', 'A Clara e o Livro dos Espíritos'),
    'obra_slug': 'o-livro-dos-espiritos',
    'fonte': 'adaptação',
    'capitulos': [
      {
        'id': 30,
        'ordem': 1,
        'titulo': 'Quem fez tudo?',
        'referencia_canonica': 'LEI-C001',
      },
    ],
  },
  '/v1/capitulos/30': {
    'id': 30,
    'ordem': 1,
    'titulo': 'Quem fez tudo?',
    'referencia_canonica': 'LEI-C001',
    'edicao_id': 3,
    'segmentos': [
      {
        'id': 1,
        'ordem': 1,
        'tipo': 'pergunta',
        'texto': 'Clara, quem fez o mundo?',
        'numero_questao': 1,
        'subquestao': null,
      },
    ],
    'faixa': null,
  },
};

CatalogoApi _api(List<Object> obras) => CatalogoApi(
  cliente: MockClient((r) async {
    if (r.url.path == '/v1/obras') return respostaJson(obras);
    final corpo = _rotas[r.url.path];
    return corpo == null ? respostaJson({}, 404) : respostaJson(corpo);
  }),
);

Future<void> _abrir(WidgetTester tester, List<Object> obras) async {
  tester.platformDispatcher.localesTestValue = const [Locale('pt', 'BR')];
  addTearDown(tester.platformDispatcher.clearLocalesTestValue);
  SharedPreferences.setMockInitialValues({});
  final idioma = await PreferenciaIdioma.carregar();
  final (player, _) = await playerFalso();
  await tester.pumpWidget(
    CentelhaKidsApp(api: _api(obras), idioma: idioma, player: player),
  );
  await tester.pumpAndSettle();
}

void main() {
  test('só as edições infantis entram no Kids', () {
    final obras = [for (final o in _obras) Obra.deJson(o)];
    expect(edicoesInfantis(obras).map((x) => x.$2.titulo), [
      'A Clara e o Livro dos Espíritos',
    ]);
  });

  testWidgets('lista só o infantil e abre o capítulo sem saída do app', (
    tester,
  ) async {
    await _abrir(tester, _obras);
    expect(find.text('Centelhar Kids'), findsOneWidget);
    expect(find.text('A Clara e o Livro dos Espíritos'), findsOneWidget);
    expect(find.text('O Livro dos Espíritos'), findsNothing);
    expect(find.text('O Livro dos Espíritos para jovens'), findsNothing);
    // Nada de configurações (de onde se chega ao apoio) na tela inicial.
    expect(find.byIcon(Icons.settings_outlined), findsNothing);

    await tester.tap(find.text('A Clara e o Livro dos Espíritos'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Quem fez tudo?'));
    await tester.pumpAndSettle();
    expect(find.text('Clara, quem fez o mundo?'), findsOneWidget);
    // Sem troca de idioma e sem compartilhar: segurar o trecho não abre nada.
    expect(find.byIcon(Icons.translate), findsNothing);
    await tester.longPress(find.text('Clara, quem fez o mundo?'));
    await tester.pumpAndSettle();
    expect(find.byType(BottomSheet), findsNothing);
  });

  testWidgets('sem edição infantil publicada, avisa que está chegando', (
    tester,
  ) async {
    await _abrir(tester, [
      {
        ...(_obras.first),
        'edicoes': [_edicaoResumo(1, 'adulto', 'O Livro dos Espíritos')],
      },
    ]);
    expect(find.textContaining('histórias da Clara'), findsOneWidget);
    expect(find.text('O Livro dos Espíritos'), findsNothing);
  });

  test('o Kids não importa apoio, campanhas, links, chaves nem downloads', () {
    // Regra do projeto: perfil infantil sem analítica, anúncio, apoio ou link
    // externo. Barrado no import, não num `if` que alguém pode esquecer.
    const proibidos = [
      'apoio.dart',
      'campanha.dart',
      'configuracoes.dart',
      'inicio.dart',
      'obra.dart',
      'compartilhar.dart',
      'baixados.dart',
      'planos.dart',
      'chaves.dart',
      'downloads.dart',
      'url_launcher',
      'share_plus',
    ];
    final arquivos = [
      File('lib/main_kids.dart'),
      ...Directory('lib/kids').listSync(recursive: true).whereType<File>(),
    ];
    for (final f in arquivos) {
      final imports = f
          .readAsLinesSync()
          .where((l) => l.startsWith('import '))
          .join('\n');
      for (final p in proibidos) {
        expect(imports, isNot(contains(p)), reason: '${f.path} importa $p');
      }
    }
  });

  test('o app principal não vê as edições infantis', () {
    final obra = Obra.deJson(_obras.first).semInfantil()!;
    expect(obra.edicoes.map((e) => e.publico), ['adulto', 'juvenil']);
    final soInfantil = Obra.deJson({
      ...(_obras.first),
      'edicoes': [_edicaoResumo(3, 'infantil', 'A Clara')],
    });
    expect(soInfantil.semInfantil(), isNull);
  });
}
