import 'package:centelha/api/catalogo_api.dart';
import 'package:centelha/idioma/preferencia_idioma.dart';
import 'package:centelha/l10n/app_localizations.dart';
import 'package:centelha/player/controle_player.dart';
import 'package:centelha/tela/inicio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'catalogo_api_test.dart' show obrasJson, respostaJson;
import 'reprodutor_falso.dart';

/// Formato de GET /v1/campanhas (routers/campanhas.py).
Map<String, Object?> _campanha({
  String slug = 'natal-2026',
  String situacao = 'ativa',
}) => {
  'slug': slug,
  'titulo': 'Natal solidário',
  'texto': 'Cestas básicas para 200 famílias.',
  'instituicao': {
    'nome': 'Lar Espírita Exemplo',
    'cnpj': '11222333000181',
    'descricao': 'Atende famílias do bairro desde 1950.',
    'chave_pix': '11222333000181',
    'pagina_doacao': 'https://lar.exemplo.org/doe',
    'site': 'javascript:alert(1)',
  },
  'inicio': '2026-12-01',
  'fim': '2026-12-24',
  'situacao': situacao,
  'meta_centavos': 1000000,
  'imagem_url': null,
  'arrecadado_centavos': null,
  'resultado': null,
  'publicado_em': '2026-11-20T12:00:00Z',
  'atualizado_em': '2026-11-20T12:00:00Z',
};

CatalogoApi _api({
  bool caridade = true,
  List<Object> campanhas = const [],
  List<String>? pedidos,
  bool falha = false,
}) => CatalogoApi(
  cliente: MockClient((r) async {
    pedidos?.add(r.url.path);
    switch (r.url.path) {
      case '/v1/obras':
        return respostaJson(obrasJson);
      case '/v1/config':
        return respostaJson({
          'apoio': false,
          'caridade': caridade,
          'anuncios': false,
        });
      case '/v1/campanhas':
        return falha ? respostaJson({}, 500) : respostaJson(campanhas);
    }
    return respostaJson({}, 404);
  }),
);

Future<void> _abrirInicio(
  WidgetTester tester,
  CatalogoApi api, {
  List<Uri>? abertos,
  Map<String, Object> salvo = const {},
}) async {
  SharedPreferences.setMockInitialValues(salvo);
  final idioma = await PreferenciaIdioma.carregar();
  final (player, _) = await playerFalso();
  await tester.pumpWidget(
    MaterialApp(
      locale: const Locale('pt'),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      builder: (context, filho) => EscopoPlayer(player: player, child: filho!),
      // Chave nova a cada montagem: o teste reabre o app no mesmo lugar da árvore.
      home: TelaInicio(
        key: UniqueKey(),
        api: api,
        idioma: idioma,
        abrirLink: (uri) async {
          abertos?.add(uri);
          return true;
        },
      ),
    ),
  );
  await tester.pumpAndSettle();
}

final _cartao = find.text('Natal solidário');

void main() {
  testWidgets('sem caridade ligada, nem busca campanhas', (tester) async {
    final pedidos = <String>[];
    await _abrirInicio(
      tester,
      _api(caridade: false, campanhas: [_campanha()], pedidos: pedidos),
    );
    expect(_cartao, findsNothing);
    expect(pedidos, isNot(contains('/v1/campanhas')));
    expect(find.text('O Livro dos Espíritos'), findsOneWidget);
  });

  testWidgets('mostra só a campanha ativa', (tester) async {
    await _abrirInicio(
      tester,
      _api(
        campanhas: [
          _campanha(slug: 'pascoa', situacao: 'futura'),
          _campanha(),
        ],
      ),
    );
    expect(_cartao, findsOneWidget);
    expect(find.text('Campanha de caridade'), findsOneWidget);
    expect(
      find.text('Para Lar Espírita Exemplo · até 24 de dezembro de 2026'),
      findsOneWidget,
    );
  });

  testWidgets('só campanhas encerradas ou futuras: sem cartão', (tester) async {
    await _abrirInicio(
      tester,
      _api(
        campanhas: [
          _campanha(situacao: 'encerrada'),
          _campanha(slug: 'pascoa', situacao: 'futura'),
        ],
      ),
    );
    expect(_cartao, findsNothing);
  });

  testWidgets('erro ao buscar campanhas não atrapalha o catálogo', (
    tester,
  ) async {
    await _abrirInicio(tester, _api(falha: true));
    expect(_cartao, findsNothing);
    expect(find.text('O Livro dos Espíritos'), findsOneWidget);
  });

  testWidgets('fechada, a mesma campanha não volta; outra aparece', (
    tester,
  ) async {
    await _abrirInicio(tester, _api(campanhas: [_campanha()]));
    await tester.tap(find.byTooltip('Fechar campanha'));
    await tester.pumpAndSettle();
    expect(_cartao, findsNothing);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('campanha_fechada'), 'natal-2026');

    await _abrirInicio(
      tester,
      _api(campanhas: [_campanha()]),
      salvo: {'campanha_fechada': 'natal-2026'},
    );
    expect(_cartao, findsNothing);

    await _abrirInicio(
      tester,
      _api(campanhas: [_campanha(slug: 'inverno-2027')]),
      salvo: {'campanha_fechada': 'natal-2026'},
    );
    expect(_cartao, findsOneWidget);
  });

  testWidgets('no Android, a tela da campanha tem Pix e a página de doação', (
    tester,
  ) async {
    final copiado = <String>[];
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (chamada) async {
        if (chamada.method == 'Clipboard.setData') {
          copiado.add((chamada.arguments as Map)['text'] as String);
        }
        return null;
      },
    );
    final abertos = <Uri>[];
    await _abrirInicio(
      tester,
      _api(campanhas: [_campanha()]),
      abertos: abertos,
    );
    await tester.tap(_cartao);
    await tester.pumpAndSettle();

    expect(find.text('Cestas básicas para 200 famílias.'), findsOneWidget);
    expect(find.text('Meta: R\$ 10.000,00'), findsOneWidget);
    expect(find.text('CNPJ 11.222.333/0001-81'), findsOneWidget);
    // O site da instituição não é https: não vira botão.
    expect(find.text('Conhecer a instituição'), findsNothing);

    await tester.tap(find.text('Copiar chave Pix'));
    await tester.pumpAndSettle();
    expect(copiado, ['11222333000181']);

    await tester.tap(find.text('Doar pelo site da instituição'));
    await tester.pumpAndSettle();
    expect(abertos, [Uri.parse('https://lar.exemplo.org/doe')]);
  });

  testWidgets('no iOS, o cartão abre a página da campanha no navegador', (
    tester,
  ) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    final abertos = <Uri>[];
    await _abrirInicio(
      tester,
      _api(campanhas: [_campanha()]),
      abertos: abertos,
    );
    await tester.tap(_cartao);
    await tester.pumpAndSettle();
    expect(abertos, [
      Uri.parse('https://centelhar.com.br/campanhas/natal-2026'),
    ]);
    expect(find.text('Copiar chave Pix'), findsNothing);
    debugDefaultTargetPlatformOverride = null;
  });
}
