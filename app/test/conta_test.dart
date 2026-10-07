import 'dart:convert';
import 'dart:io';

import 'package:centelha/app.dart';
import 'package:centelha/chave/chaves.dart';
import 'package:centelha/conta/conta.dart';
import 'package:centelha/idioma/preferencia_idioma.dart';
import 'package:centelha/l10n/app_localizations.dart';
import 'package:centelha/tela/conta.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_falsa.dart';
import 'reprodutor_falso.dart';

class _CofreMemoria implements Cofre {
  final dados = <String, String>{};
  @override
  Future<String?> ler(String nome) async => dados[nome];
  @override
  Future<void> gravar(String nome, String valor) async => dados[nome] = valor;
  @override
  Future<void> apagar(String nome) async => dados.remove(nome);
}

/// Servidor de mentira com as rotas de routers/conta.py, no mesmo formato.
class _Servidor {
  final pedidos = <String>[];
  final tokens = <String>{};
  bool liberada = false;
  bool foraDoAr = false;
  int? statusDownload;

  late final cliente = MockClient((r) async {
    pedidos.add('${r.method} ${r.url.path}');
    if (foraDoAr) throw const SocketException('sem rede');
    final token = r.headers['Authorization']?.replaceFirst('Bearer ', '');
    final autenticado = token != null && tokens.contains(token);
    http.Response json(Object? o, [int status = 200]) => http.Response(
      jsonEncode(o),
      status,
      headers: {'content-type': 'application/json'},
    );
    switch ((r.method, r.url.path)) {
      case ('POST', '/v1/conta/codigo'):
        return json({'status': 'enviado'}, 202);
      case ('POST', '/v1/conta/sessao'):
        final corpo = jsonDecode(r.body) as Map;
        if (corpo['codigo'] != '123456') return json({'detail': 'x'}, 400);
        tokens.add('t1');
        return json({'token': 't1', 'email': 'leitora@exemplo.org'});
      case ('GET', '/v1/conta'):
        if (!autenticado) return json({'detail': 'x'}, 401);
        return json({
          'email': 'leitora@exemplo.org',
          'exportacao_aberta': liberada,
        });
      case ('POST', '/v1/conta/sair'):
        tokens.remove(token);
        return http.Response('', 204);
      case ('DELETE', '/v1/conta'):
        tokens.clear();
        return http.Response('', 204);
    }
    if (r.url.path.startsWith('/v1/conta/exportacao/')) {
      if (!autenticado) return json({'detail': 'x'}, 401);
      if (!liberada) return json({'detail': 'x'}, 403);
      if (statusDownload case final s?) return json({'detail': 'x'}, s);
      if (r.url.path.endsWith('/leiame')) {
        return http.Response.bytes(
          utf8.encode('Pedido S-1. Não redistribua.'),
          200,
          headers: {'content-disposition': 'attachment; filename="LEIAME.txt"'},
        );
      }
      return http.Response.bytes(
        [0, 0, 0, 0x1c, ...'ftypM4A '.codeUnits],
        200,
        headers: {
          'content-type': 'audio/mp4',
          'content-disposition':
              'attachment; filename="1-capitulo-i-de-deus.m4a"',
        },
      );
    }
    return json({'detail': 'não encontrado'}, 404);
  });

  Conta conta(_CofreMemoria cofre) =>
      Conta(cofre: cofre, cliente: cliente, base: 'https://api.exemplo');
}

void main() {
  late _Servidor servidor;
  late _CofreMemoria cofre;

  setUp(() {
    servidor = _Servidor();
    cofre = _CofreMemoria();
  });

  test(
    'entrar guarda o token no cofre e lê se a exportação está liberada',
    () async {
      servidor.liberada = true;
      final conta = servidor.conta(cofre);
      await conta.pedirCodigo(' leitora@exemplo.org ');
      await expectLater(
        conta.entrar('leitora@exemplo.org', '000000'),
        throwsA(isA<ErroConta>().having((e) => e.status, 'status', 400)),
      );
      expect(conta.entrou, isFalse);
      await conta.entrar('leitora@exemplo.org', ' 123456 ');
      expect(conta.email, 'leitora@exemplo.org');
      expect(conta.exportacaoAberta, isTrue);
      expect(cofre.dados.values, ['t1']);

      // Ao abrir o app de novo, a sessão guardada vale.
      final outra = servidor.conta(cofre);
      await outra.carregar();
      expect(outra.email, 'leitora@exemplo.org');
    },
  );

  test('sessão revogada sai do aparelho; sem internet, fica', () async {
    cofre.dados['centelha.token-conta'] = 't1';
    servidor.tokens.add('t1');
    servidor.foraDoAr = true;
    final conta = servidor.conta(cofre);
    await conta.carregar();
    expect(cofre.dados, isNotEmpty);

    servidor
      ..foraDoAr = false
      ..tokens.clear();
    await conta.carregar();
    expect(conta.entrou, isFalse);
    expect(cofre.dados, isEmpty);
  });

  test(
    'sair sem internet apaga o token mesmo assim; excluir avisa o erro',
    () async {
      final conta = servidor.conta(cofre);
      await conta.entrar('leitora@exemplo.org', '123456');
      servidor.foraDoAr = true;
      await expectLater(conta.excluir(), throwsA(isA<ErroConta>()));
      expect(conta.entrou, isTrue);
      await conta.sair();
      expect(conta.entrou, isFalse);
      expect(cofre.dados, isEmpty);
    },
  );

  test('baixa o .m4a e o LEIAME com o nome que a API dá', () async {
    servidor.liberada = true;
    final conta = servidor.conta(cofre);
    await conta.entrar('leitora@exemplo.org', '123456');
    final pasta = await Directory.systemTemp.createTemp('formato-aberto');
    addTearDown(() => pasta.delete(recursive: true));
    final arquivos = await conta.baixarAberto(
      capituloId: 10,
      edicaoId: 1,
      pasta: pasta,
    );
    expect(arquivos.map((f) => f.uri.pathSegments.last), [
      '1-capitulo-i-de-deus.m4a',
      'LEIAME.txt',
    ]);
    expect(
      String.fromCharCodes(arquivos.first.readAsBytesSync(), 4, 8),
      'ftyp',
    );
    expect(servidor.pedidos, contains('GET /v1/conta/exportacao/capitulos/10'));
  });

  test('liberação revogada esconde o botão na hora', () async {
    servidor.liberada = true;
    final conta = servidor.conta(cofre);
    await conta.entrar('leitora@exemplo.org', '123456');
    servidor.liberada = false;
    await expectLater(
      conta.baixarAberto(
        capituloId: 10,
        edicaoId: 1,
        pasta: Directory.systemTemp,
      ),
      throwsA(isA<ErroConta>().having((e) => e.status, 'status', 403)),
    );
    expect(conta.exportacaoAberta, isFalse);
  });

  test('o nome do anexo não escolhe pasta', () {
    http.Response com(String v) =>
        http.Response('', 200, headers: {'content-disposition': v});
    expect(nomeDoAnexo(com('attachment; filename="a.m4a"'), 'p'), 'a.m4a');
    expect(
      nomeDoAnexo(com('attachment; filename="../../x.m4a"'), 'p'),
      'x.m4a',
    );
    expect(nomeDoAnexo(com('attachment; filename=".."'), 'p'), 'p');
    expect(nomeDoAnexo(http.Response('', 200), 'p'), 'p');
  });

  Future<void> abrirApp(WidgetTester tester, Conta conta) async {
    tester.platformDispatcher.localesTestValue = const [Locale('pt', 'BR')];
    addTearDown(tester.platformDispatcher.clearLocalesTestValue);
    SharedPreferences.setMockInitialValues({});
    final idioma = await PreferenciaIdioma.carregar();
    final (player, _) = await playerFalso();
    await tester.pumpWidget(
      CentelhaApp(
        api: apiFalsa(),
        idioma: idioma,
        player: player,
        conta: conta,
      ),
    );
    await tester.pumpAndSettle();
  }

  Future<void> abrirCapitulo(WidgetTester tester) async {
    await tester.tap(find.text('O Livro dos Espíritos'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Capítulo I — De Deus'));
    await tester.pumpAndSettle();
  }

  testWidgets('entrar pela tela da conta, com o código do e-mail', (
    tester,
  ) async {
    final conta = servidor.conta(cofre);
    await tester.pumpWidget(
      MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: const Locale('pt'),
        home: TelaConta(conta: conta),
      ),
    );
    expect(find.textContaining('A conta é opcional'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'leitora@exemplo.org');
    await tester.tap(find.text('Receber código'));
    await tester.pumpAndSettle();
    expect(
      find.text('Mandamos um código de 6 dígitos para leitora@exemplo.org.'),
      findsOneWidget,
    );

    await tester.enterText(find.byType(TextField).last, '000000');
    await tester.tap(find.text('Entrar'));
    await tester.pumpAndSettle();
    expect(find.text('Código inválido ou vencido.'), findsOneWidget);

    await tester.enterText(find.byType(TextField).last, '123456');
    await tester.tap(find.text('Entrar'));
    await tester.pumpAndSettle();
    expect(find.text('Você entrou como leitora@exemplo.org'), findsOneWidget);
    expect(find.textContaining('peça pelo suporte'), findsOneWidget);

    await tester.tap(find.text('Excluir conta'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Excluir conta').last);
    await tester.pumpAndSettle();
    expect(find.text('Receber código'), findsOneWidget);
    expect(servidor.pedidos, contains('DELETE /v1/conta'));
  });

  testWidgets('sem liberação, o capítulo não tem o botão de formato aberto', (
    tester,
  ) async {
    final conta = servidor.conta(cofre);
    await conta.entrar('leitora@exemplo.org', '123456');
    await abrirApp(tester, conta);
    await abrirCapitulo(tester);
    expect(find.byTooltip('Baixar em formato aberto'), findsNothing);
  });

  testWidgets('com liberação, baixa e entrega os dois arquivos ao sistema', (
    tester,
  ) async {
    servidor.liberada = true;
    final conta = servidor.conta(cofre);
    await conta.entrar('leitora@exemplo.org', '123456');
    final entregues = <String>[];
    final pasta = Directory.systemTemp.createTempSync('formato-aberto');
    addTearDown(() => pasta.deleteSync(recursive: true));
    final (entregarAntes, pastaAntes) = (entregarArquivos, pastaFormatoAberto);
    addTearDown(() {
      entregarArquivos = entregarAntes;
      pastaFormatoAberto = pastaAntes;
    });
    entregarArquivos = (arquivos, _) async =>
        entregues.addAll(arquivos.map((f) => f.uri.pathSegments.last));
    pastaFormatoAberto = () async => pasta;

    await abrirApp(tester, conta);
    await abrirCapitulo(tester);
    // Gravar arquivo é E/S de verdade: fora do relógio falso do teste.
    await tester.runAsync(() async {
      await tester.tap(find.byTooltip('Baixar em formato aberto'));
      for (var i = 0; i < 50 && entregues.isEmpty; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 20));
      }
    });
    expect(entregues, ['1-capitulo-i-de-deus.m4a', 'LEIAME.txt']);
    expect(
      servidor.pedidos,
      contains('GET /v1/conta/exportacao/edicoes/1/leiame'),
    );
  });

  testWidgets('a conta aparece nas configurações', (tester) async {
    await abrirApp(tester, servidor.conta(cofre));
    await tester.tap(find.byIcon(Icons.settings_outlined));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Conta'), 100);
    await tester.tap(find.text('Conta'));
    await tester.pumpAndSettle();
    expect(find.text('Receber código'), findsOneWidget);
  });
}
