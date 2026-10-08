import 'package:centelha/api/catalogo_api.dart';
import 'package:centelha/app.dart';
import 'package:centelha/idioma/preferencia_idioma.dart';
import 'package:centelha/player/barra_player.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_falsa.dart';
import 'reprodutor_falso.dart';

Future<ReprodutorFalso> _abrirApp(
  WidgetTester tester,
  CatalogoApi api, [
  Map<String, Object> salvo = const {},
]) async {
  tester.platformDispatcher.localesTestValue = const [Locale('pt', 'BR')];
  addTearDown(tester.platformDispatcher.clearLocalesTestValue);
  SharedPreferences.setMockInitialValues(salvo);
  final idioma = await PreferenciaIdioma.carregar();
  final (player, motor) = await playerFalso();
  await tester.pumpWidget(
    CentelhaApp(api: api, idioma: idioma, player: player),
  );
  await tester.pumpAndSettle();
  return motor;
}

Future<void> _abrirObra(WidgetTester tester) async {
  await tester.tap(find.text('O Livro dos Espíritos'));
  await tester.pumpAndSettle();
}

Future<void> _buscar(WidgetTester tester, String texto) async {
  await tester.enterText(find.byType(TextField), texto);
  await tester.testTextInput.receiveAction(TextInputAction.search);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('obra mostra créditos e capítulos; capítulo mostra o texto', (
    tester,
  ) async {
    await _abrirApp(tester, apiFalsa());
    await _abrirObra(tester);
    expect(find.text('Tradução: Guillon Ribeiro'), findsOneWidget);
    expect(find.text('Fonte: FEB, 1944'), findsOneWidget);
    expect(find.text('Capítulo II — Dos elementos gerais'), findsOneWidget);

    await tester.tap(find.text('Capítulo I — De Deus'));
    await tester.pumpAndSettle();
    expect(find.text('De Deus'), findsOneWidget);
    expect(find.text('1.'), findsOneWidget);
    expect(find.text('Pergunta de exemplo 1?'), findsOneWidget);
    expect(find.text('“Resposta de exemplo 1.”'), findsOneWidget);
  });

  testWidgets('"questão 88" abre o capítulo já rolado até a questão', (
    tester,
  ) async {
    final pedidos = <String>[];
    await _abrirApp(tester, apiFalsa(pedidos: pedidos));
    await _abrirObra(tester);
    await _buscar(tester, 'questão 88');

    expect(pedidos, contains('/v1/edicoes/1/questoes/88'));
    expect(pedidos.last, '/v1/capitulos/10');
    final alvo = find.text('Pergunta de exemplo 88?');
    expect(alvo, findsOneWidget);
    final y = tester.getTopLeft(alvo).dy;
    final altura =
        tester.view.physicalSize.height / tester.view.devicePixelRatio;
    expect(y, inInclusiveRange(0, altura), reason: 'a questão 88 está na tela');
    // A primeira questão ficou para trás, fora da tela.
    expect(find.text('Pergunta de exemplo 1?').hitTestable(), findsNothing);
  });

  testWidgets('"88a" vai até a subquestão', (tester) async {
    await _abrirApp(tester, apiFalsa());
    await _abrirObra(tester);
    await _buscar(tester, '88a');
    expect(find.text('Subquestão de exemplo?').hitTestable(), findsOneWidget);
    expect(find.text('88a.'), findsOneWidget);
  });

  testWidgets(
    'questão inexistente e texto sem número avisam sem sair da obra',
    (tester) async {
      await _abrirApp(tester, apiFalsa());
      await _abrirObra(tester);
      await _buscar(tester, '999');
      expect(find.text('A questão 999 não está nesta edição.'), findsOneWidget);
      expect(find.text('Capítulos'), findsOneWidget);

      await _buscar(tester, 'deus');
      expect(find.text('Digite o número da questão.'), findsOneWidget);
    },
  );

  testWidgets('falha de rede na busca avisa', (tester) async {
    await _abrirApp(tester, apiFalsa(falham: {'/v1/edicoes/1/questoes/88'}));
    await _abrirObra(tester);
    await _buscar(tester, '88');
    expect(
      find.text('Não foi possível carregar. Confira a conexão.'),
      findsOneWidget,
    );
  });

  testWidgets('trocar a edição recarrega título e capítulos', (tester) async {
    await _abrirApp(tester, apiFalsa());
    await _abrirObra(tester);
    await tester.tap(find.text('Français'));
    await tester.pumpAndSettle();
    expect(find.text('Le Livre des Esprits'), findsOneWidget);
    expect(find.text('Chapitre premier — Dieu'), findsOneWidget);
    expect(find.text('Capítulo I — De Deus'), findsNothing);
  });

  testWidgets('capítulo só com texto avisa na lista e no lugar do player', (
    tester,
  ) async {
    await _abrirApp(tester, apiFalsa());
    await _abrirObra(tester);
    expect(find.text('Só texto, sem narração'), findsNothing);

    await tester.tap(find.text('Français'));
    await tester.pumpAndSettle();
    expect(find.text('Só texto, sem narração'), findsOneWidget);

    await tester.tap(find.text('Chapitre premier — Dieu'));
    await tester.pumpAndSettle();
    expect(find.text('Paragraphe d’exemple sur Dieu.'), findsOneWidget);
    expect(
      find.text('Este capítulo ainda não tem narração. Você pode ler o texto.'),
      findsOneWidget,
    );
    expect(find.byType(BarraPlayer), findsNothing);
  });

  testWidgets('capítulo que falha ao carregar oferece tentar de novo', (
    tester,
  ) async {
    await _abrirApp(tester, apiFalsa());
    await _abrirObra(tester);
    await tester.tap(find.text('Capítulo II — Dos elementos gerais'));
    await tester.pumpAndSettle();
    expect(find.text('Tentar de novo'), findsOneWidget);
  });

  test('lê a busca por questão', () {
    expect(lerBuscaQuestao('88'), (numero: 88, sub: null));
    expect(lerBuscaQuestao('Questão 88'), (numero: 88, sub: null));
    expect(lerBuscaQuestao('q. 150'), (numero: 150, sub: null));
    expect(lerBuscaQuestao(' 88a '), (numero: 88, sub: 'a'));
    expect(lerBuscaQuestao('88 a'), (numero: 88, sub: 'a'));
    expect(lerBuscaQuestao('deus'), isNull);
    expect(lerBuscaQuestao('0'), isNull);
  });

  test('tipo de segmento desconhecido vira parágrafo', () {
    final cap = Capitulo.deJson(capituloLongo);
    expect(cap.segmentos.last.tipo, TipoSegmento.paragrafo);
    expect(cap.segmentos.first.tipo, TipoSegmento.titulo);
  });
}
