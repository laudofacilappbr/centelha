import 'package:centelha/api/catalogo_api.dart';
import 'package:centelha/app.dart';
import 'package:centelha/idioma/preferencia_idioma.dart';
import 'package:centelha/tela/trocar_edicao.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_falsa.dart';
import 'reprodutor_falso.dart';

EdicaoResumo _ed(int id, String idioma, String publico) => EdicaoResumo(
  id: id,
  idioma: idioma,
  publico: publico,
  titulo: 'Edição $id',
  tradutor: null,
);

final _capituloI = CapituloResumo(
  id: 10,
  ordem: 1,
  titulo: 'Capítulo I — De Deus',
  referencia: 'LE-C001',
);

void main() {
  test('outras edições: só as do mesmo público, sem a atual', () {
    final obra = Obra(
      slug: 'o-livro-dos-espiritos',
      sigla: 'LE',
      autor: 'Allan Kardec',
      tituloOriginal: 'Le Livre des Esprits',
      ano: 1857,
      edicoes: [
        _ed(1, 'pt-BR', 'adulto'),
        _ed(2, 'fr-FR', 'adulto'),
        _ed(3, 'pt-BR', 'infantil'),
      ],
    );
    final adulta = OrigemCapitulo(obra: obra, edicao: obra.edicoes[0]);
    expect(adulta.outras.map((e) => e.id), [2]);
    // A edição infantil não troca para a adulta (nem o contrário).
    final infantil = OrigemCapitulo(obra: obra, edicao: obra.edicoes[2]);
    expect(infantil.outras, isEmpty);
  });

  test('questão que existe na outra edição vai para o capítulo dela', () async {
    final pedidos = <String>[];
    final destino = await mesmaPosicao(
      apiFalsa(pedidos: pedidos),
      _ed(2, 'fr-FR', 'adulto'),
      capitulo: _capituloI,
      questao: 88,
      subquestao: 'a',
    );
    expect(destino!.capitulo.id, 20);
    expect((destino.questao, destino.subquestao), (88, 'a'));
    expect(pedidos, ['/v1/edicoes/2/questoes/88']);
  });

  test('sem a questão lá, vale o capítulo de mesma referência', () async {
    final destino = await mesmaPosicao(
      apiFalsa(),
      _ed(2, 'fr-FR', 'adulto'),
      capitulo: _capituloI,
      questao: 1,
    );
    expect(destino!.capitulo.titulo, 'Chapitre premier — Dieu');
    expect(destino.questao, isNull);
  });

  test('sem capítulo correspondente: null', () async {
    final capituloII = CapituloResumo(
      id: 11,
      ordem: 2,
      titulo: 'Capítulo II',
      referencia: 'LE-C002',
    );
    final destino = await mesmaPosicao(
      apiFalsa(),
      _ed(2, 'fr-FR', 'adulto'),
      capitulo: capituloII,
    );
    expect(destino, isNull);
  });

  group('no app', () {
    Future<List<String>> abrirNaQuestao88(WidgetTester tester) async {
      tester.platformDispatcher.localesTestValue = const [Locale('pt', 'BR')];
      addTearDown(tester.platformDispatcher.clearLocalesTestValue);
      SharedPreferences.setMockInitialValues({});
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
      await tester.tap(find.text('O Livro dos Espíritos'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), '88');
      await tester.testTextInput.receiveAction(TextInputAction.search);
      await tester.pumpAndSettle();
      return pedidos;
    }

    testWidgets('trocar o idioma abre a questão à vista na outra edição', (
      tester,
    ) async {
      final pedidos = await abrirNaQuestao88(tester);
      expect(
        find.text('Pergunta de exemplo 88?').hitTestable(),
        findsOneWidget,
      );

      await tester.tap(find.byTooltip('Ler em outro idioma'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Français'));
      await tester.pumpAndSettle();

      // A questão à vista era a 88, não a primeira do capítulo.
      expect(pedidos, contains('/v1/edicoes/2/questoes/88'));
      expect(pedidos.last, '/v1/capitulos/20');
      expect(find.text('Chapitre premier — Dieu'), findsOneWidget);
      // A tela trocou no lugar: voltar leva à obra, não ao capítulo em português.
      tester.state<NavigatorState>(find.byType(Navigator).last).pop();
      await tester.pumpAndSettle();
      expect(find.text('Capítulos'), findsOneWidget);
    });

    testWidgets('com outra edição do mesmo público, o botão aparece', (
      tester,
    ) async {
      await abrirNaQuestao88(tester);
      expect(find.byTooltip('Ler em outro idioma'), findsOneWidget);
    });
  });
}
