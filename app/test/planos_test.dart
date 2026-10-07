import 'package:centelha/app.dart';
import 'package:centelha/idioma/preferencia_idioma.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_falsa.dart';
import 'reprodutor_falso.dart';

Future<List<String>> _abrirPlano(
  WidgetTester tester, [
  Map<String, Object> salvo = const {},
]) async {
  tester.platformDispatcher.localesTestValue = const [Locale('pt', 'BR')];
  addTearDown(tester.platformDispatcher.clearLocalesTestValue);
  SharedPreferences.setMockInitialValues(salvo);
  final idioma = await PreferenciaIdioma.carregar();
  final (player, _) = await playerFalso();
  final pedidos = <String>[];
  await tester.pumpWidget(
    CentelhaApp(
      api: apiFalsa(pedidos: pedidos),
      idioma: idioma,
      player: player,
    ),
  );
  await tester.pumpAndSettle();
  await tester.tap(find.text('Planos de estudo'));
  await tester.pumpAndSettle();
  expect(find.text('Plano de teste'), findsOneWidget);
  await tester.tap(find.text('Plano de teste'));
  await tester.pumpAndSettle();
  return pedidos;
}

void main() {
  testWidgets('marcar o dia como lido fica salvo no aparelho', (tester) async {
    await _abrirPlano(tester);
    expect(find.text('0 de 3 dias lidos'), findsOneWidget);
    await tester.tap(find.text('Dia 1'));
    await tester.pumpAndSettle();
    expect(find.text('1 de 3 dias lidos'), findsOneWidget);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getStringList('plano.teste.lidos'), ['1']);
  });

  testWidgets('o progresso salvo volta ao abrir o plano', (tester) async {
    await _abrirPlano(tester, {
      'plano.teste.lidos': ['1', '3'],
    });
    expect(find.text('2 de 3 dias lidos'), findsOneWidget);
  });

  testWidgets('ler a questão do dia abre o capítulo nela', (tester) async {
    final pedidos = await _abrirPlano(tester);
    await tester.tap(find.byTooltip('Ler').first);
    await tester.pumpAndSettle();
    // A questão é resolvida na edição do idioma de quem lê (pt-BR, edição 1).
    expect(pedidos, contains('/v1/edicoes/1/questoes/88'));
    expect(find.text('Pergunta de exemplo 88?').hitTestable(), findsOneWidget);
  });

  testWidgets('capítulo canônico é achado pela referência', (tester) async {
    final pedidos = await _abrirPlano(tester);
    await tester.tap(find.byTooltip('Ler').at(1));
    await tester.pumpAndSettle();
    expect(pedidos, contains('/v1/edicoes/1'));
    expect(pedidos.last, '/v1/capitulos/11');
  });

  testWidgets('obra que o catálogo não tem avisa', (tester) async {
    await _abrirPlano(tester);
    await tester.tap(find.byTooltip('Ler').at(2));
    await tester.pumpAndSettle();
    expect(
      find.text('Esta leitura ainda não está publicada neste idioma.'),
      findsOneWidget,
    );
  });
}
