import 'package:centelha/api/catalogo_api.dart';
import 'package:centelha/app.dart';
import 'package:centelha/idioma/preferencia_idioma.dart';
import 'package:centelha/l10n/app_localizations.dart';
import 'package:centelha/tema/centelha_tema.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'catalogo_api_test.dart' show obrasJson, respostaJson;

Future<PreferenciaIdioma> _idioma([
  Map<String, Object> salvo = const {},
]) async {
  SharedPreferences.setMockInitialValues(salvo);
  return PreferenciaIdioma.carregar();
}

CatalogoApi _api({int falhasAntes = 0}) {
  var chamadas = 0;
  return CatalogoApi(
    cliente: MockClient(
      (_) async => chamadas++ < falhasAntes
          ? respostaJson({}, 503)
          : respostaJson(obrasJson),
    ),
  );
}

void main() {
  testWidgets('mostra as obras no idioma do aparelho', (tester) async {
    tester.platformDispatcher.localesTestValue = const [Locale('pt', 'BR')];
    addTearDown(tester.platformDispatcher.clearLocalesTestValue);
    await tester.pumpWidget(CentelhaApp(api: _api(), idioma: await _idioma()));
    await tester.pumpAndSettle();
    expect(find.text('Obras'), findsOneWidget);
    expect(find.text('O Livro dos Espíritos'), findsOneWidget);
    expect(find.text('Allan Kardec · 1857'), findsOneWidget);
    expect(find.text('2 edições'), findsOneWidget);
  });

  testWidgets('aparelho em francês: interface e edição em francês', (
    tester,
  ) async {
    tester.platformDispatcher.localesTestValue = const [Locale('fr', 'CA')];
    addTearDown(tester.platformDispatcher.clearLocalesTestValue);
    await tester.pumpWidget(CentelhaApp(api: _api(), idioma: await _idioma()));
    await tester.pumpAndSettle();
    expect(find.text('Œuvres'), findsOneWidget);
    expect(find.text('Le Livre des Esprits'), findsOneWidget);
  });

  testWidgets('trocar o idioma nas configurações vale na hora e fica salvo', (
    tester,
  ) async {
    tester.platformDispatcher.localesTestValue = const [Locale('pt', 'BR')];
    addTearDown(tester.platformDispatcher.clearLocalesTestValue);
    final idioma = await _idioma();
    await tester.pumpWidget(CentelhaApp(api: _api(), idioma: idioma));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Configurações'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('English'));
    await tester.pumpAndSettle();
    expect(find.text('Settings'), findsOneWidget);
    expect((await SharedPreferences.getInstance()).getString('idioma'), 'en');

    await tester.tap(find.text('Device language'));
    await tester.pumpAndSettle();
    expect(find.text('Configurações'), findsOneWidget);
    expect((await SharedPreferences.getInstance()).getString('idioma'), isNull);
  });

  testWidgets('erro no catálogo oferece tentar de novo', (tester) async {
    tester.platformDispatcher.localesTestValue = const [Locale('pt', 'BR')];
    addTearDown(tester.platformDispatcher.clearLocalesTestValue);
    await tester.pumpWidget(
      CentelhaApp(api: _api(falhasAntes: 1), idioma: await _idioma()),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Não foi possível carregar'), findsOneWidget);
    await tester.tap(find.text('Tentar de novo'));
    await tester.pumpAndSettle();
    expect(find.text('O Livro dos Espíritos'), findsOneWidget);
  });

  testWidgets('cabe em celular estreito com texto grande', (tester) async {
    // 320 px e fonte em 130%: overflow vira erro e derruba o teste.
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 1.3;
    addTearDown(tester.view.reset);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpWidget(CentelhaApp(api: _api(), idioma: await _idioma()));
    await tester.pumpAndSettle();
    expect(find.text('Allan Kardec · 1857'), findsOneWidget);
    await tester.tap(find.byIcon(Icons.settings_outlined));
    await tester.pumpAndSettle();
    expect(find.text('Español'), findsOneWidget);
  });

  test(
    'idioma salvo vence o do aparelho; idioma desconhecido é ignorado',
    () async {
      expect((await _idioma({'idioma': 'es'})).locale, const Locale('es'));
      expect((await _idioma({'idioma': 'de'})).locale, isNull);
    },
  );

  test(
    'resolve o idioma do aparelho pelos suportados, com português por padrão',
    () {
      const suportados = AppLocalizations.supportedLocales;
      expect(
        resolverLocale(const [Locale('es', 'MX')], suportados),
        const Locale('es'),
      );
      expect(
        resolverLocale(const [Locale('de'), Locale('fr', 'BE')], suportados),
        const Locale('fr'),
      );
      expect(
        resolverLocale(const [Locale('ja')], suportados),
        const Locale('pt'),
      );
      expect(idiomaDoConteudo(const Locale('pt')), 'pt-BR');
      expect(idiomaDoConteudo(const Locale('fr')), 'fr');
    },
  );

  test('tema usa as cores da marca', () {
    expect(TemaCentelha.escuro.scaffoldBackgroundColor, CoresCentelha.noite950);
    expect(TemaCentelha.escuro.colorScheme.primary, CoresCentelha.ouro);
    expect(TemaCentelha.claro.colorScheme.primary, CoresCentelha.ouroForte);
    expect(TemaCentelha.claro.textTheme.headlineSmall!.fontFamily, 'Comfortaa');
  });
}
