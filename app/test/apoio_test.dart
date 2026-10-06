import 'package:centelha/api/catalogo_api.dart';
import 'package:centelha/app.dart';
import 'package:centelha/idioma/preferencia_idioma.dart';
import 'package:centelha/l10n/app_localizations.dart';
import 'package:centelha/tela/apoio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'catalogo_api_test.dart' show obrasJson, respostaJson;
import 'reprodutor_falso.dart';

const _apoioLigado = {
  'ligado': true,
  'recebedor': 'Fulano de Tal',
  'mensagem': null,
  'valores_centavos': [500, 1000, 2500],
  'compra_no_app': false,
  'chave_pix': 'apoio@centelha.app',
  'link_externo': 'https://apoie.exemplo.org/centelha',
};

CatalogoApi _api({required bool ligado, Map<String, Object?>? apoio}) =>
    CatalogoApi(
      cliente: MockClient((r) async {
        switch (r.url.path) {
          case '/v1/obras':
            return respostaJson(obrasJson);
          case '/v1/config':
            return respostaJson({
              'apoio': ligado,
              'caridade': false,
              'anuncios': false,
            });
          case '/v1/apoio':
            return respostaJson(
              apoio ?? (ligado ? _apoioLigado : {'ligado': false}),
            );
        }
        return respostaJson({}, 404);
      }),
    );

Future<void> _abrirConfiguracoes(WidgetTester tester, CatalogoApi api) async {
  tester.platformDispatcher.localesTestValue = const [Locale('pt', 'BR')];
  addTearDown(tester.platformDispatcher.clearLocalesTestValue);
  SharedPreferences.setMockInitialValues({});
  final idioma = await PreferenciaIdioma.carregar();
  final (player, _) = await playerFalso();
  await tester.pumpWidget(
    CentelhaApp(api: api, idioma: idioma, player: player),
  );
  await tester.pumpAndSettle();
  await tester.tap(find.byTooltip('Configurações'));
  await tester.pumpAndSettle();
}

Widget _telaApoio(CatalogoApi api, AbrirLink abrirLink) => MaterialApp(
  locale: const Locale('pt'),
  supportedLocales: AppLocalizations.supportedLocales,
  localizationsDelegates: const [
    AppLocalizations.delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
  ],
  home: TelaApoio(api: api, abrirLink: abrirLink),
);

void main() {
  testWidgets('com o apoio desligado, a entrada não aparece', (tester) async {
    await _abrirConfiguracoes(tester, _api(ligado: false));
    expect(find.text('Apoie o Centelha'), findsNothing);
    expect(find.text('Licenças'), findsOneWidget);
  });

  testWidgets('com o apoio ligado, a entrada leva à tela de apoio', (
    tester,
  ) async {
    await _abrirConfiguracoes(tester, _api(ligado: true));
    await tester.tap(find.text('Apoie o Centelha'));
    await tester.pumpAndSettle();
    expect(find.text('O apoio vai para Fulano de Tal.'), findsOneWidget);
    expect(find.text('R\$ 5,00'), findsOneWidget);
    expect(find.text('R\$ 25,00'), findsOneWidget);
    expect(
      find.text(
        'Apoiar não libera nenhum conteúdo: o app é o mesmo para todos.',
      ),
      findsOneWidget,
    );
  });

  testWidgets('copia a chave Pix e abre o link fora do app', (tester) async {
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
    await tester.pumpWidget(
      _telaApoio(_api(ligado: true), (uri) async {
        abertos.add(uri);
        return true;
      }),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Copiar chave Pix'));
    await tester.pumpAndSettle();
    expect(copiado, ['apoio@centelha.app']);
    expect(find.text('Chave Pix copiada.'), findsOneWidget);

    await tester.tap(find.text('Apoiar pelo site'));
    await tester.pumpAndSettle();
    expect(abertos, [Uri.parse('https://apoie.exemplo.org/centelha')]);
  });

  testWidgets('desligado entre a configuração e a tela: avisa', (tester) async {
    await tester.pumpWidget(_telaApoio(_api(ligado: false), (_) async => true));
    await tester.pumpAndSettle();
    expect(find.text('O apoio não está disponível agora.'), findsOneWidget);
  });

  test('link que não é https não vira botão', () {
    final a = Apoio.deJson({
      ..._apoioLigado,
      'link_externo': 'javascript:alert(1)',
    });
    expect(a.linkExterno, isNull);
    expect(Apoio.deJson({'ligado': false}).valoresCentavos, isEmpty);
  });
}
