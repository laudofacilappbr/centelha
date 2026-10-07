// Arquivos em test/fixtures gerados por api/src/centelha_api/pipeline/cifra.py, com a
// chave 00 01 02 … 1f e o áudio claro (i * 31 + 7) % 256: o Dart tem de abrir
// exatamente o que o worker grava.
import 'dart:io';
import 'dart:typed_data';

import 'package:centelha/cifra/cent.dart';
import 'package:centelha/cifra/fonte_cent.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

final _chave = Uint8List.fromList(List.generate(32, (i) => i));
Uint8List _claro(int n) =>
    Uint8List.fromList(List.generate(n, (i) => (i * 31 + 7) % 256));
Uint8List _fixture(String nome) =>
    File('test/fixtures/$nome').readAsBytesSync();

/// Leitor em memória que conta os pedidos, para conferir que só baixa o necessário.
class _LeitorMemoria implements LeitorCent {
  _LeitorMemoria(this.dados);
  final Uint8List dados;
  final pedidos = <(int, int)>[];

  @override
  Future<Uint8List> ler(int inicio, int fim) async {
    pedidos.add((inicio, fim));
    return Uint8List.sublistView(dados, inicio, fim);
  }
}

Future<Uint8List> _ler(FonteCent fonte, [int? inicio, int? fim]) async {
  final r = await fonte.request(inicio, fim);
  final partes = await r.stream.toList();
  return Uint8List.fromList([for (final p in partes) ...p]);
}

void main() {
  group('formato', () {
    test('abre o que o worker cifrou, com o último bloco parcial', () {
      final dados = _fixture('amostra.cent');
      final cab = CabecalhoCent.ler(dados);
      expect(
        (cab.tamanhoBloco, cab.tamanhoClaro, cab.blocos),
        (65536, 200000, 4),
      );
      expect(cab.tamanhoArquivo, dados.length);
      expect(decifrarCent(dados, _chave), _claro(200000));
    });

    test('blocos pequenos e arquivo vazio', () {
      expect(decifrarCent(_fixture('blocos16.cent'), _chave), _claro(100));
      expect(decifrarCent(_fixture('vazio.cent'), _chave), isEmpty);
    });

    test('chave errada não abre', () {
      final errada = Uint8List.fromList(List.filled(32, 7));
      expect(
        () => decifrarCent(_fixture('amostra.cent'), errada),
        throwsA(isA<ErroCifra>()),
      );
    });

    test('um byte trocado num bloco não abre', () {
      final dados = Uint8List.fromList(_fixture('amostra.cent'));
      dados[40000] ^= 1;
      expect(() => decifrarCent(dados, _chave), throwsA(isA<ErroCifra>()));
    });

    test('blocos trocados de lugar não abrem', () {
      final dados = Uint8List.fromList(_fixture('blocos16.cent'));
      final cab = CabecalhoCent.ler(dados);
      final (a, n) = cab.posicaoBloco(0);
      final (b, _) = cab.posicaoBloco(1);
      final primeiro = dados.sublist(a, a + n);
      dados.setRange(a, a + n, dados.sublist(b, b + n));
      dados.setRange(b, b + n, primeiro);
      expect(() => decifrarCent(dados, _chave), throwsA(isA<ErroCifra>()));
    });

    test('arquivo cortado no fim de um bloco não abre', () {
      // Sem o último bloco, o penúltimo seria aceito como fim se não autenticasse
      // a marca de último.
      final dados = _fixture('blocos16.cent');
      final cab = CabecalhoCent.ler(dados);
      final (inicio, n) = cab.posicaoBloco(5);
      final cortado = Uint8List.sublistView(dados, inicio, inicio + n);
      expect(
        () => cab.decifrarBloco(6, cortado, _chave),
        throwsA(isA<ErroCifra>()),
      );
      expect(
        () => decifrarCent(Uint8List.sublistView(dados, 0, inicio + n), _chave),
        throwsA(isA<ErroCifra>()),
      );
    });

    test('o que não é .cent é recusado', () {
      expect(
        () => CabecalhoCent.ler(Uint8List.fromList(List.filled(32, 0))),
        throwsA(isA<ErroCifra>()),
      );
      expect(() => CabecalhoCent.ler(Uint8List(10)), throwsA(isA<ErroCifra>()));
    });
  });

  group('fonte do player', () {
    test('o arquivo inteiro sai igual ao áudio aberto', () async {
      final fonte = FonteCent(_LeitorMemoria(_fixture('amostra.cent')), _chave);
      final r = await fonte.request();
      expect((r.sourceLength, r.contentLength, r.offset), (200000, 200000, 0));
      expect(r.contentType, 'audio/mp4');
      expect(await _ler(fonte), _claro(200000));
    });

    test('pular para o meio baixa só os blocos do trecho', () async {
      final leitor = _LeitorMemoria(_fixture('amostra.cent'));
      final fonte = FonteCent(leitor, _chave);
      // Bytes 70000 a 140000: blocos 1 e 2, atravessando a divisa entre eles.
      expect(
        await _ler(fonte, 70000, 140000),
        _claro(200000).sublist(70000, 140000),
      );
      final cab = CabecalhoCent.ler(_fixture('amostra.cent'));
      final (de, _) = cab.posicaoBloco(1);
      final (ate, n) = cab.posicaoBloco(2);
      expect(leitor.pedidos, [(0, tamanhoCabecalho), (de, ate + n)]);
    });

    test('pedido além do fim para no fim do áudio', () async {
      final fonte = FonteCent(_LeitorMemoria(_fixture('amostra.cent')), _chave);
      final r = await fonte.request(199990, 500000);
      expect(r.contentLength, 10);
      expect(await _ler(fonte, 199990, 500000), _claro(200000).sublist(199990));
    });

    test('muitos blocos vão em leituras de no máximo 16', () async {
      final leitor = _LeitorMemoria(_fixture('blocos16.cent'));
      // 7 blocos de 16 bytes cabem numa leitura só, além do cabeçalho.
      expect(await _ler(FonteCent(leitor, _chave)), _claro(100));
      expect(leitor.pedidos, hasLength(2));
    });

    test('pela CDN, com Range', () async {
      final dados = _fixture('amostra.cent');
      final pedidos = <String?>[];
      final cliente = MockClient((r) async {
        pedidos.add(r.headers['Range']);
        final m = RegExp(r'bytes=(\d+)-(\d+)').firstMatch(r.headers['Range']!)!;
        final a = int.parse(m[1]!), b = int.parse(m[2]!);
        return http.Response.bytes(dados.sublist(a, b + 1), 206);
      });
      final fonte = FonteCent(
        LeitorHttp(
          Uri.parse('https://audio.exemplo/le.cent'),
          cliente: cliente,
        ),
        _chave,
      );
      expect(await _ler(fonte, 0, 1000), _claro(1000));
      expect(pedidos, ['bytes=0-31', 'bytes=32-65583']);
    });

    test('CDN com erro vira ErroCifra, não áudio quebrado', () async {
      final cliente = MockClient((_) async => http.Response('não', 404));
      final fonte = FonteCent(
        LeitorHttp(Uri.parse('https://audio.exemplo/x.cent'), cliente: cliente),
        _chave,
      );
      expect(fonte.request(), throwsA(isA<ErroCifra>()));
    });
  });
}
