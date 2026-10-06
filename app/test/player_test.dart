import 'dart:convert';

import 'package:centelha/api/catalogo_api.dart';
import 'package:centelha/app.dart';
import 'package:centelha/idioma/preferencia_idioma.dart';
import 'package:centelha/player/controle_player.dart';
import 'package:centelha/player/reprodutor.dart';
import 'package:fake_async/fake_async.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_falsa.dart';
import 'reprodutor_falso.dart';

const _info = InfoFaixa(
  titulo: 'Capítulo I — De Deus',
  edicao: 'O Livro dos Espíritos',
  autor: 'Allan Kardec',
);

final _capitulo = Capitulo.deJson(capituloLongo);

Future<(ControlePlayer, ReprodutorFalso)> _player([
  Map<String, Object> salvo = const {},
]) async {
  SharedPreferences.setMockInitialValues(salvo);
  return playerFalso();
}

String _posicao(int versao, int ms, [int? segmento]) =>
    jsonEncode({'versao': versao, 'ms': ms, 'segmento': segmento});

Future<Map<String, dynamic>?> _salva() async {
  final texto = (await SharedPreferences.getInstance()).getString('posicao:10');
  return texto == null ? null : jsonDecode(texto) as Map<String, dynamic>;
}

void main() {
  group('controle do player', () {
    test('abre onde parou, sem começar a tocar', () async {
      final (player, motor) = await _player({
        'posicao:10': _posicao(2, 1234000, 610),
      });
      await player.abrir(_capitulo, _info);
      expect(motor.inicio, const Duration(milliseconds: 1234000));
      expect(motor.chamadas, isNot(contains('tocar')));
      expect(motor.info!.autor, 'Allan Kardec');
    });

    test('áudio regenerado: retoma no começo do mesmo segmento', () async {
      // Posição gravada na versão 1; a faixa agora é a 2, com outros tempos.
      final (player, motor) = await _player({
        'posicao:10': _posicao(1, 999999, 880),
      });
      await player.abrir(_capitulo, _info);
      expect(motor.inicio, const Duration(seconds: 88 * 20));
    });

    test('grava a posição tocando, a cada 5 s, e ao pausar', () async {
      final (player, motor) = await _player();
      await player.abrir(_capitulo, _info);
      await player.alternar();
      motor.avancarTempo(const Duration(seconds: 3));
      await pumpEventQueue();
      expect(await _salva(), anyOf(isNull, containsPair('ms', 0)));
      motor.avancarTempo(const Duration(seconds: 25));
      await pumpEventQueue();
      expect(await _salva(), {'versao': 2, 'ms': 25000, 'segmento': 10});
      motor.avancarTempo(const Duration(seconds: 27));
      await player.alternar();
      await pumpEventQueue();
      expect((await _salva())!['ms'], 27000);
      expect(player.armazem.ultimo()!.capitulo.id, 10);
    });

    test('velocidade vale na hora e na próxima faixa', () async {
      final (player, motor) = await _player();
      await player.abrir(_capitulo, _info);
      await player.definirVelocidade(1.5);
      expect(motor.vel, 1.5);
      final (outro, motor2) = await playerFalso();
      await outro.abrir(_capitulo, _info);
      expect(motor2.vel, 1.5);
    });

    test('pular para trás não passa do começo nem do fim', () async {
      final (player, motor) = await _player();
      await player.abrir(_capitulo, _info);
      await player.pular(-ControlePlayer.salto);
      expect(motor.chamadas.last, 'irPara 0s');
      await player.irPara(const Duration(milliseconds: 2495000));
      await player.pular(ControlePlayer.salto);
      expect(motor.chamadas.last, 'irPara 2500s');
    });

    test('timer de sono pausa no tempo escolhido e pode ser desligado', () {
      fakeAsync((tempo) {
        late ControlePlayer player;
        late ReprodutorFalso motor;
        _player().then((r) => (player, motor) = r);
        tempo.flushMicrotasks();
        player.abrir(_capitulo, _info);
        player.alternar();
        tempo.flushMicrotasks();

        player.timerSono(const Duration(minutes: 15));
        expect(player.fimTimerSono, isNotNull);
        tempo.elapse(const Duration(minutes: 14));
        expect(motor.estaTocando, isTrue);
        tempo.elapse(const Duration(minutes: 1));
        expect(motor.estaTocando, isFalse);
        expect(player.fimTimerSono, isNull);

        player.alternar();
        player.timerSono(const Duration(minutes: 30));
        player.timerSono(null);
        tempo.elapse(const Duration(hours: 1));
        expect(motor.estaTocando, isTrue);
      });
    });

    test('ao terminar, a próxima vez começa do início', () async {
      final (player, motor) = await _player({
        'posicao:10': _posicao(2, 2400000),
      });
      await player.abrir(_capitulo, _info);
      motor.chegarAoFim();
      await pumpEventQueue();
      expect(await _salva(), isNull);
      expect(player.posicao, Duration.zero);
    });

    test('marcadores: salva com segmento, ordena e remove', () async {
      final (player, motor) = await _player();
      await player.abrir(_capitulo, _info);
      await player.irPara(const Duration(seconds: 100));
      await player.marcar();
      await player.irPara(const Duration(seconds: 40));
      await player.marcar();
      final lista = player.marcadores;
      expect([for (final m in lista) m.posicao.ms], [40000, 100000]);
      expect(lista.last.posicao.segmentoId, 50);
      await player.removerMarcador(lista.first);
      expect(player.marcadores.single.posicao.ms, 100000);
    });

    test('faixa cifrada (#73) não é carregada por este app', () async {
      final json = {
        ...capituloLongo,
        'faixa': {
          ...(capituloLongo['faixa'] as Map<String, dynamic>),
          'formato': 'cent1',
        },
      };
      final (player, motor) = await _player();
      await player.abrir(Capitulo.deJson(json), _info);
      expect(motor.chamadas, isEmpty);
      expect(Capitulo.deJson(capituloLongo).faixa!.tocavel, isTrue);
    });
  });

  group('tela', () {
    Future<ReprodutorFalso> abrirCapitulo(
      WidgetTester tester, [
      Map<String, Object> salvo = const {},
    ]) async {
      tester.platformDispatcher.localesTestValue = const [Locale('pt', 'BR')];
      addTearDown(tester.platformDispatcher.clearLocalesTestValue);
      SharedPreferences.setMockInitialValues(salvo);
      final idioma = await PreferenciaIdioma.carregar();
      final (player, motor) = await playerFalso();
      await tester.pumpWidget(
        CentelhaApp(api: apiFalsa(), idioma: idioma, player: player),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('O Livro dos Espíritos'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Capítulo I — De Deus'));
      await tester.pumpAndSettle();
      return motor;
    }

    testWidgets('capítulo com áudio abre o player e toca e pausa', (
      tester,
    ) async {
      final motor = await abrirCapitulo(tester);
      expect(motor.chamadas.first, 'carregar');
      expect(find.text('41:40'), findsOneWidget);

      await tester.tap(find.byTooltip('Tocar'));
      await tester.pump();
      expect(motor.estaTocando, isTrue);
      expect(find.byTooltip('Pausar'), findsOneWidget);
      motor.avancarTempo(const Duration(minutes: 1, seconds: 5));
      await tester.pump();
      expect(find.text('01:05'), findsOneWidget);

      await tester.tap(find.byTooltip('Avançar 15 segundos'));
      await tester.pump();
      expect(motor.chamadas.last, 'irPara 80s');
    });

    testWidgets('troca a velocidade pelo menu', (tester) async {
      final motor = await abrirCapitulo(tester);
      await tester.tap(find.byTooltip('Velocidade'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('1,5x').last);
      await tester.pumpAndSettle();
      expect(motor.vel, 1.5);
      expect(find.text('1,5x'), findsOneWidget);
    });

    testWidgets('timer de sono pelo menu mostra o tempo restante', (
      tester,
    ) async {
      await abrirCapitulo(tester);
      await tester.tap(find.byTooltip('Timer de sono'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('30 min'));
      await tester.pumpAndSettle();
      expect(find.text('Para em 30 min'), findsOneWidget);
      await tester.tap(find.byTooltip('Timer de sono'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Desligado'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Para em'), findsNothing);
    });

    testWidgets(
      'marcador pela folha de marcadores, e tocar nele leva ao ponto',
      (tester) async {
        final motor = await abrirCapitulo(tester, {
          'posicao:10': _posicao(2, 754000),
        });
        await tester.tap(find.byTooltip('Marcadores'));
        await tester.pumpAndSettle();
        expect(find.text('Nenhum marcador neste capítulo.'), findsOneWidget);
        await tester.tap(find.text('Marcar este trecho'));
        await tester.pumpAndSettle();
        expect(find.text('Marcador salvo em 12:34.'), findsOneWidget);
        expect(find.text('12:34'), findsWidgets);

        motor.avancarTempo(const Duration(minutes: 20));
        await tester.pump();
        await tester.tap(find.widgetWithIcon(ListTile, Icons.bookmark_outline));
        await tester.pumpAndSettle();
        expect(motor.chamadas.last, 'irPara 754s');
      },
    );

    group('leitura acompanhada (#32)', () {
      Color? fundo(WidgetTester tester, String texto) {
        final caixa = tester.widget<AnimatedContainer>(
          find
              .ancestor(
                of: find.text(texto),
                matching: find.byType(AnimatedContainer),
              )
              .first,
        );
        return (caixa.decoration as BoxDecoration?)?.color;
      }

      bool naTela(WidgetTester tester, String texto) {
        final r = tester.getRect(find.text(texto));
        final tela = tester.view.physicalSize / tester.view.devicePixelRatio;
        return r.top >= 0 && r.bottom <= tela.height;
      }

      testWidgets('destaca o trecho lido e rola até ele enquanto toca', (
        tester,
      ) async {
        final motor = await abrirCapitulo(tester);
        await tester.tap(find.byTooltip('Tocar'));
        await tester.pump();
        // A pergunta 60 começa em 60 × 20 s.
        motor.avancarTempo(const Duration(seconds: 1205));
        await tester.pumpAndSettle();

        expect(naTela(tester, 'Pergunta de exemplo 60?'), isTrue);
        expect(
          fundo(tester, 'Pergunta de exemplo 60?'),
          isNot(Colors.transparent),
        );
        expect(fundo(tester, '“Resposta de exemplo 60.”'), Colors.transparent);

        // 10 s depois, a leitura passa para a resposta.
        motor.avancarTempo(const Duration(seconds: 1211));
        await tester.pumpAndSettle();
        expect(fundo(tester, 'Pergunta de exemplo 60?'), Colors.transparent);
        expect(
          fundo(tester, '“Resposta de exemplo 60.”'),
          isNot(Colors.transparent),
        );
      });

      testWidgets(
        'rolar com o dedo para de acompanhar; o botão volta à leitura',
        (tester) async {
          final motor = await abrirCapitulo(tester);
          await tester.tap(find.byTooltip('Tocar'));
          await tester.pump();
          motor.avancarTempo(const Duration(seconds: 1205));
          await tester.pumpAndSettle();
          expect(find.text('Acompanhar a leitura'), findsNothing);

          await tester.drag(
            find.text('Pergunta de exemplo 60?'),
            const Offset(0, 2000),
          );
          await tester.pumpAndSettle();
          expect(naTela(tester, 'Pergunta de exemplo 60?'), isFalse);
          expect(find.text('Acompanhar a leitura'), findsOneWidget);

          // A leitura segue, mas a tela fica onde a pessoa deixou.
          motor.avancarTempo(const Duration(seconds: 1225));
          await tester.pumpAndSettle();
          expect(naTela(tester, 'Pergunta de exemplo 61?'), isFalse);

          await tester.tap(find.text('Acompanhar a leitura'));
          await tester.pumpAndSettle();
          expect(naTela(tester, 'Pergunta de exemplo 61?'), isTrue);
          expect(find.text('Acompanhar a leitura'), findsNothing);
        },
      );

      testWidgets('tocar num trecho leva o áudio até ele', (tester) async {
        final motor = await abrirCapitulo(tester);
        await tester.tap(find.text('Pergunta de exemplo 3?'));
        await tester.pump();
        expect(motor.chamadas.last, 'irPara 60s');

        // Segmento sem marcação (o título) não reage ao toque.
        final antes = motor.chamadas.length;
        await tester.tap(find.text('De Deus').last);
        await tester.pump();
        expect(motor.chamadas.length, antes);
      });
    });

    testWidgets('"continuar ouvindo" aparece no início e reabre o capítulo', (
      tester,
    ) async {
      tester.platformDispatcher.localesTestValue = const [Locale('pt', 'BR')];
      addTearDown(tester.platformDispatcher.clearLocalesTestValue);
      SharedPreferences.setMockInitialValues({
        'ultimo_ouvido': jsonEncode({
          'capitulo': {
            'id': 10,
            'ordem': 1,
            'titulo': 'Capítulo I — De Deus',
            'referencia_canonica': 'LE-C001',
          },
          'titulo': 'Capítulo I — De Deus',
          'edicao': 'O Livro dos Espíritos',
          'autor': 'Allan Kardec',
        }),
      });
      final idioma = await PreferenciaIdioma.carregar();
      final (player, motor) = await playerFalso();
      await tester.pumpWidget(
        CentelhaApp(api: apiFalsa(), idioma: idioma, player: player),
      );
      await tester.pumpAndSettle();
      expect(find.text('Continuar ouvindo'), findsOneWidget);
      await tester.tap(find.text('Continuar ouvindo'));
      await tester.pumpAndSettle();
      expect(find.text('De Deus'), findsOneWidget);
      expect(motor.chamadas, contains('carregar'));
    });
  });
}
