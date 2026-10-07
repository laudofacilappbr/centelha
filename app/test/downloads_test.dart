import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:centelha/api/catalogo_api.dart';
import 'package:centelha/chave/chaves.dart';
import 'package:centelha/cifra/fonte_cent.dart';
import 'package:centelha/l10n/app_localizations.dart';
import 'package:centelha/offline/downloads.dart';
import 'package:centelha/player/barra_player.dart';
import 'package:centelha/player/carro.dart';
import 'package:centelha/player/controle_player.dart';
import 'package:centelha/player/progresso.dart';
import 'package:centelha/player/reprodutor.dart';
import 'package:centelha/tela/baixados.dart';
import 'package:audio_service/audio_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'reprodutor_falso.dart';

// test/fixtures/amostra.cent: gerado pelo cifra.py com a chave 00 01 … 1f.
final _cent = File('test/fixtures/amostra.cent').readAsBytesSync();
final _chave = Uint8List.fromList(List.generate(32, (i) => i));
final _claro = Uint8List.fromList(
  List.generate(200000, (i) => (i * 31 + 7) % 256),
);

Faixa _faixa({int versao = 2, String formato = 'cent1'}) => Faixa(
  id: 7,
  url: 'https://audio.exemplo/le/c1-v$versao.cent',
  versao: versao,
  duracaoMs: 60000,
  marcacoes: const [],
  formato: formato,
);

const _info = InfoFaixa(
  titulo: 'Capítulo I',
  edicao: 'O Livro dos Espíritos',
  autor: 'Allan Kardec',
);

Capitulo _cap({int versao = 2}) => Capitulo(
  resumo: CapituloResumo(
    id: 1,
    ordem: 1,
    titulo: 'Capítulo I — De Deus',
    referencia: 'LE-C001',
  ),
  edicaoId: 1,
  segmentos: [
    Segmento(
      id: 10,
      ordem: 1,
      tipo: TipoSegmento.pergunta,
      texto: 'Que é Deus?',
      numeroQuestao: 1,
      subquestao: null,
    ),
  ],
  faixa: _faixa(versao: versao),
);

class _Cofre implements Cofre {
  final dados = <String, String>{};
  @override
  Future<String?> ler(String nome) async => dados[nome];
  @override
  Future<void> gravar(String nome, String valor) async => dados[nome] = valor;
  @override
  Future<void> apagar(String nome) async => dados.remove(nome);
}

/// API das chaves e CDN numa coisa só, para contar o que foi pedido.
class _Rede {
  final pedidos = <String>[];
  bool foraDoAr = false;
  int statusChave = 200;
  int statusCdn = 200;
  Uint8List corpoCdn = _cent;

  MockClient get cliente => MockClient((r) async {
    if (foraDoAr) throw http.ClientException('sem rede');
    pedidos.add(r.url.path);
    final json = {'content-type': 'application/json'};
    return switch (r.url.path) {
      '/v1/dispositivos/desafio' => http.Response(
        jsonEncode({'desafio': 'd'}),
        201,
        headers: json,
      ),
      '/v1/dispositivos' => http.Response(
        jsonEncode({'token': 't'}),
        201,
        headers: json,
      ),
      '/v1/faixas/7/chave' =>
        statusChave != 200
            ? http.Response('{}', statusChave)
            : http.Response(
                jsonEncode({
                  'chave': base64Encode(_chave),
                  'valida_ate': DateTime.now()
                      .add(const Duration(days: 90))
                      .toUtc()
                      .toIso8601String(),
                }),
                200,
                headers: json,
              ),
      _ => http.Response.bytes(statusCdn == 200 ? corpoCdn : [], statusCdn),
    };
  });
}

void main() {
  late Directory pasta;
  late _Rede rede;
  late _Cofre cofre;
  late ClienteChaves chaves;
  late Downloads downloads;
  var agora = DateTime.now();

  setUp(() {
    agora = DateTime.now();
    pasta = Directory.systemTemp.createTempSync('centelha-downloads');
    rede = _Rede();
    cofre = _Cofre();
    chaves = ClienteChaves(
      atestador: const AtestadorFalso(),
      cofre: cofre,
      cliente: rede.cliente,
      base: 'https://api.exemplo',
      agora: () => agora,
    );
    downloads = Downloads(pasta, chaves, cliente: rede.cliente);
  });
  tearDown(() => pasta.deleteSync(recursive: true));

  group('downloads', () {
    test('baixa o .cent com a chave e ele toca do arquivo', () async {
      final progresso = <double?>[];
      downloads.addListener(() => progresso.add(downloads.progresso(_faixa())));
      await downloads.baixar(_faixa());

      expect(downloads.baixado(_faixa()), isTrue);
      expect(rede.pedidos.last, '/le/c1-v2.cent');
      // A chave veio antes do arquivo e ficou no cofre, para tocar offline.
      expect(rede.pedidos.indexOf('/v1/faixas/7/chave'), lessThan(3));
      expect(cofre.dados.keys, contains('centelha.chave.7.v2'));
      expect(progresso.first, 0);
      expect(progresso.last, isNull);

      final fonte = FonteCent(
        LeitorArquivo(downloads.arquivo(_faixa())),
        _chave,
      );
      final r = await fonte.request(70000, 140000);
      final bytes = [for (final p in await r.stream.toList()) ...p];
      expect(bytes, _claro.sublist(70000, 140000));
      expect(pasta.listSync().map((e) => e.uri.pathSegments.last), [
        'faixa-7-v2.cent',
      ]);
    });

    test('.m4a aberto nunca vai para o aparelho', () async {
      final aberta = _faixa(formato: 'm4a');
      expect(downloads.podeBaixar(aberta), isFalse);
      await downloads.baixar(aberta);
      expect(rede.pedidos, isEmpty);
      expect(pasta.existsSync() && pasta.listSync().isNotEmpty, isFalse);
    });

    test('download cortado não passa por baixado', () async {
      rede.corpoCdn = Uint8List.sublistView(_cent, 0, 100000);
      await expectLater(
        downloads.baixar(_faixa()),
        throwsA(isA<ErroDownload>()),
      );
      expect(downloads.baixado(_faixa()), isFalse);
      expect(pasta.listSync(), isEmpty);
      expect(downloads.progresso(_faixa()), isNull);
    });

    test('CDN com erro e chave recusada viram ErroDownload', () async {
      rede.statusCdn = 404;
      await expectLater(
        downloads.baixar(_faixa()),
        throwsA(isA<ErroDownload>()),
      );
      rede
        ..statusCdn = 200
        ..statusChave = 503
        ..pedidos.clear();
      cofre.dados.clear();
      await expectLater(
        downloads.baixar(_faixa()),
        throwsA(isA<ErroDownload>()),
      );
      // Sem chave, o arquivo nem é pedido.
      expect(rede.pedidos.where((p) => p.endsWith('.cent')), isEmpty);
    });

    test('versão nova substitui a antiga; apagar remove', () async {
      await downloads.baixar(_faixa());
      await downloads.baixar(_faixa(versao: 3));
      expect(pasta.listSync().map((e) => e.uri.pathSegments.last), [
        'faixa-7-v3.cent',
      ]);
      await downloads.apagar(_faixa(versao: 3));
      expect(downloads.baixado(_faixa(versao: 3)), isFalse);
    });
  });

  group('lista e vencimento', () {
    test('o baixado guarda o capítulo e abre sem a API', () async {
      await downloads.baixar(_faixa(), capitulo: _cap(), info: _info);
      final [b] = await downloads.lista();
      expect(b.capitulo.resumo.titulo, 'Capítulo I — De Deus');
      expect(b.capitulo.segmentos.single.texto, 'Que é Deus?');
      expect(b.faixa.formato, 'cent1');
      expect(b.info.edicao, 'O Livro dos Espíritos');
      expect(b.validaAte!.isAfter(agora.add(const Duration(days: 89))), isTrue);

      await downloads.apagar(_faixa());
      expect(await downloads.lista(), isEmpty);
      expect(pasta.listSync(), isEmpty);
    });

    test('versão nova leva a ficha nova', () async {
      await downloads.baixar(_faixa(), capitulo: _cap(), info: _info);
      await downloads.baixar(
        _faixa(versao: 3),
        capitulo: _cap(versao: 3),
        info: _info,
      );
      expect(pasta.listSync().map((e) => e.uri.pathSegments.last).toSet(), {
        'faixa-7-v3.cent',
        'faixa-7-v3.json',
      });
    });

    test('vencendo: só a chave a menos de 7 dias do fim', () async {
      await downloads.baixar(_faixa(), capitulo: _cap(), info: _info);
      expect(await downloads.vencendo(agora), isEmpty);
      final perto = agora.add(const Duration(days: 85));
      expect(await downloads.vencendo(perto), hasLength(1));
    });

    test('ao abrir com internet, renova a chave que vai vencer', () async {
      await downloads.baixar(_faixa(), capitulo: _cap(), info: _info);
      final antes = (await downloads.lista()).single.validaAte!;
      agora = agora.add(const Duration(days: 85));
      rede.pedidos.clear();
      await downloads.renovarChaves();
      expect(rede.pedidos, ['/v1/faixas/7/chave']);
      final depois = (await downloads.lista()).single.validaAte!;
      expect(depois.isAfter(antes), isTrue);
    });

    test('sem internet, renovar não quebra e o aviso fica', () async {
      await downloads.baixar(_faixa(), capitulo: _cap(), info: _info);
      agora = agora.add(const Duration(days: 85));
      rede.foraDoAr = true;
      await downloads.renovarChaves();
      expect(await downloads.vencendo(agora), hasLength(1));
    });
  });

  testWidgets('tela dos baixados abre o capítulo sem a API', (tester) async {
    await tester.runAsync(
      () => downloads.baixar(_faixa(), capitulo: _cap(), info: _info),
    );
    // API que falha em tudo: como sem internet.
    final api = CatalogoApi(
      cliente: MockClient((_) async => throw http.ClientException('sem rede')),
    );
    SharedPreferences.setMockInitialValues({});
    final p = ControlePlayer(
      ReprodutorFalso(),
      ArmazemProgresso(await SharedPreferences.getInstance()),
      chaves: chaves,
      downloads: downloads,
    );
    await tester.pumpWidget(
      MaterialApp(
        locale: const Locale('pt'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        builder: (context, filho) => EscopoPlayer(player: p, child: filho!),
        home: TelaBaixados(api: api, downloads: downloads),
      ),
    );
    for (var i = 0; i < 5; i++) {
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 30)),
      );
      await tester.pump();
    }
    expect(find.text('Capítulo I — De Deus'), findsOneWidget);
    expect(find.textContaining('ouve sem internet até'), findsOneWidget);

    await tester.tap(find.text('Capítulo I — De Deus'));
    for (var i = 0; i < 5; i++) {
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 30)),
      );
      await tester.pump();
    }
    expect(find.text('Que é Deus?'), findsOneWidget);
  });

  group('player', () {
    test('capítulo baixado toca do arquivo, mesmo sem internet', () async {
      await downloads.baixar(_faixa());
      rede.foraDoAr = true;
      SharedPreferences.setMockInitialValues({});
      final motor = ReprodutorFalso();
      final p = ControlePlayer(
        motor,
        ArmazemProgresso(await SharedPreferences.getInstance()),
        chaves: chaves,
        downloads: downloads,
      );
      final cap = Capitulo(
        resumo: CapituloResumo(
          id: 1,
          ordem: 1,
          titulo: 'I',
          referencia: 'LE-C001',
        ),
        edicaoId: 1,
        segmentos: const [],
        faixa: _faixa(),
      );
      await p.abrir(
        cap,
        const InfoFaixa(titulo: 'I', edicao: 'LE', autor: 'K'),
      );
      expect(motor.chave, _chave);
      expect(motor.arquivo?.path, downloads.arquivo(_faixa()).path);
    });
  });

  testWidgets('botão: baixar, baixado e apagar com confirmação', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        locale: const Locale('pt'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: BotaoDownload(
            downloads: downloads,
            capitulo: _cap(),
            info: _info,
          ),
        ),
      ),
    );
    await tester.runAsync(() async {
      await tester.tap(find.byTooltip('Baixar para ouvir sem internet'));
      for (var i = 0; i < 50 && !downloads.baixado(_faixa()); i++) {
        await Future<void>.delayed(const Duration(milliseconds: 20));
      }
    });
    await tester.pump();
    expect(
      find.byTooltip('Baixado. Toque para apagar do aparelho'),
      findsOneWidget,
    );

    await tester.tap(find.byTooltip('Baixado. Toque para apagar do aparelho'));
    await tester.pumpAndSettle();
    expect(find.text('Apagar o capítulo baixado?'), findsOneWidget);
    await tester.tap(find.text('Apagar'));
    await tester.pumpAndSettle();
    expect(downloads.baixado(_faixa()), isFalse);
    expect(find.byIcon(Icons.download_outlined), findsOneWidget);
  });

  group('Android Auto (#43)', () {
    test('baixados aparecem no carro e tocam sem rede', () async {
      SharedPreferences.setMockInitialValues({});
      await downloads.baixar(_faixa(), capitulo: _cap(), info: _info);
      rede.foraDoAr = true;
      final motor = ReprodutorFalso();
      final player = ControlePlayer(
        motor,
        ArmazemProgresso(await SharedPreferences.getInstance()),
        chaves: chaves,
        downloads: downloads,
      );
      final carro = NavegacaoCarro(
        api: CatalogoApi(cliente: rede.cliente),
        player: player,
        textos: () => lookupAppLocalizations(const Locale('pt')),
      );

      final raiz = await carro.filhos(AudioService.browsableRootId);
      expect(raiz.map((m) => (m.id, m.playable)), [('baixados', false)]);
      final baixados = await carro.filhos('baixados');
      expect(baixados.single.title, 'Capítulo I — De Deus');

      await carro.tocar(baixados.single.id);
      // Estrada sem sinal: tocou do arquivo, com a chave do cofre.
      expect(motor.arquivo?.path, downloads.arquivo(_faixa()).path);
      expect(motor.chave, _chave);
      expect(motor.estaTocando, isTrue);

      // O que tocou vira o "Continuar ouvindo", também nas sugestões do sistema.
      final recentes = await carro.filhos(AudioService.recentRootId);
      expect(recentes.single.id, 'ultimo');
      expect(recentes.single.artist, 'Capítulo I — De Deus');
    });
  });
}
