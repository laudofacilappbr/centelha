import 'dart:convert';
import 'dart:typed_data';

import 'package:centelha/api/catalogo_api.dart';
import 'package:centelha/chave/chaves.dart';
import 'package:centelha/player/controle_player.dart';
import 'package:centelha/player/progresso.dart';
import 'package:centelha/player/reprodutor.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_falsa.dart';
import 'reprodutor_falso.dart';

final _chave = Uint8List.fromList(List.generate(32, (i) => 100 + i));
final _agora = DateTime.utc(2026, 10, 7, 12);

Faixa _faixa({int? id = 7, String formato = 'cent1'}) => Faixa(
  id: id,
  url: 'https://audio.exemplo/le/c1-v2.cent',
  versao: 2,
  duracaoMs: 60000,
  marcacoes: const [],
  formato: formato,
);

class _CofreMemoria implements Cofre {
  final dados = <String, String>{};
  @override
  Future<String?> ler(String nome) async => dados[nome];
  @override
  Future<void> gravar(String nome, String valor) async => dados[nome] = valor;
  @override
  Future<void> apagar(String nome) async => dados.remove(nome);
}

/// Servidor de mentira com as três rotas, no formato de routers/dispositivos.py.
class _Servidor {
  final pedidos = <String>[];
  var tokensValidos = <String>{};
  var registros = 0;
  bool foraDoAr = false;
  int? statusChave;
  Duration validade = const Duration(days: 90);

  MockClient get cliente => MockClient((r) async {
    if (foraDoAr) throw http.ClientException('sem rede');
    pedidos.add(r.url.path);
    final json = {'content-type': 'application/json'};
    switch (r.url.path) {
      case '/v1/dispositivos/desafio':
        return http.Response(
          jsonEncode({'desafio': 'd${registros + 1}'}),
          201,
          headers: json,
        );
      case '/v1/dispositivos':
        final corpo = jsonDecode(r.body) as Map<String, dynamic>;
        if (corpo['atestado'] != 'falso:${corpo['desafio']}' ||
            corpo['plataforma'] != 'falso') {
          return http.Response('{}', 403);
        }
        registros++;
        final token = 't$registros';
        tokensValidos.add(token);
        return http.Response(jsonEncode({'token': token}), 201, headers: json);
      default:
        final token = r.headers['Authorization']?.replaceFirst('Bearer ', '');
        if (!tokensValidos.contains(token)) return http.Response('{}', 401);
        if (statusChave != null) return http.Response('{}', statusChave!);
        return http.Response(
          jsonEncode({
            'faixa_id': 7,
            'versao': 2,
            'formato': 'cent1',
            'chave': base64Encode(_chave),
            'valida_ate': _agora.add(validade).toIso8601String(),
          }),
          200,
          headers: json,
        );
    }
  });
}

ClienteChaves _cliente(_Servidor s, _CofreMemoria cofre, [DateTime? agora]) =>
    ClienteChaves(
      atestador: const AtestadorFalso(),
      cofre: cofre,
      cliente: s.cliente,
      base: 'https://api.exemplo',
      agora: () => agora ?? _agora,
    );

void main() {
  group('cliente de chaves', () {
    test('registra o aparelho uma vez e guarda a chave', () async {
      final s = _Servidor();
      final cofre = _CofreMemoria();
      expect(await _cliente(s, cofre).chave(_faixa()), _chave);
      expect(s.pedidos, [
        '/v1/dispositivos/desafio',
        '/v1/dispositivos',
        '/v1/faixas/7/chave',
      ]);
      // De novo, mesmo em outro ClienteChaves: vem do cofre, sem rede.
      s.pedidos.clear();
      expect(await _cliente(s, cofre).chave(_faixa()), _chave);
      expect(s.pedidos, isEmpty);
      expect(cofre.dados.keys, contains('centelha.token-aparelho'));
    });

    test('perto de vencer, renova sem registrar de novo', () async {
      final s = _Servidor();
      final cofre = _CofreMemoria();
      await _cliente(s, cofre).chave(_faixa());
      s.pedidos.clear();
      final quaseVencendo = _agora.add(const Duration(days: 85));
      await _cliente(s, cofre, quaseVencendo).chave(_faixa());
      expect(s.pedidos, ['/v1/faixas/7/chave']);
    });

    test('offline, segue com a chave guardada até a validade', () async {
      final s = _Servidor();
      final cofre = _CofreMemoria();
      await _cliente(s, cofre).chave(_faixa());
      s.foraDoAr = true;
      final quaseVencendo = _agora.add(const Duration(days: 85));
      expect(await _cliente(s, cofre, quaseVencendo).chave(_faixa()), _chave);
      final vencida = _agora.add(const Duration(days: 91));
      expect(
        _cliente(s, cofre, vencida).chave(_faixa()),
        throwsA(isA<ErroChave>()),
      );
    });

    test('token recusado: registra de novo, uma vez', () async {
      final s = _Servidor();
      final cofre = _CofreMemoria()..dados['centelha.token-aparelho'] = 'velho';
      expect(await _cliente(s, cofre).chave(_faixa()), _chave);
      expect(s.registros, 1);
      expect(cofre.dados['centelha.token-aparelho'], 't1');
    });

    test('limite diário ou servidor sem chave viram ErroChave', () async {
      for (final status in [429, 503, 409]) {
        final s = _Servidor()..statusChave = status;
        expect(
          _cliente(s, _CofreMemoria()).chave(_faixa()),
          throwsA(isA<ErroChave>()),
        );
      }
    });

    test('faixa sem id (API antiga) não pede chave', () async {
      final s = _Servidor();
      expect(
        _cliente(s, _CofreMemoria()).chave(_faixa(id: null)),
        throwsA(isA<ErroChave>()),
      );
      expect(s.pedidos, isEmpty);
    });

    test('versão nova da faixa pede chave nova', () async {
      final s = _Servidor();
      final cofre = _CofreMemoria();
      await _cliente(s, cofre).chave(_faixa());
      s.pedidos.clear();
      final v3 = Faixa(
        id: 7,
        url: 'https://audio.exemplo/le/c1-v3.cent',
        versao: 3,
        duracaoMs: 60000,
        marcacoes: const [],
        formato: 'cent1',
      );
      await _cliente(s, cofre).chave(v3);
      expect(s.pedidos, ['/v1/faixas/7/chave']);
    });
  });

  group('player', () {
    Capitulo capituloCifrado() {
      final json = {
        ...capituloLongo,
        'faixa': {
          ...(capituloLongo['faixa'] as Map<String, dynamic>),
          'id': 7,
          'formato': 'cent1',
        },
      };
      return Capitulo.deJson(json);
    }

    const info = InfoFaixa(titulo: 'I', edicao: 'LE', autor: 'Kardec');

    Future<(ControlePlayer, ReprodutorFalso)> player(ClienteChaves? c) async {
      SharedPreferences.setMockInitialValues({});
      final motor = ReprodutorFalso();
      final armazem = ArmazemProgresso(await SharedPreferences.getInstance());
      return (ControlePlayer(motor, armazem, chaves: c), motor);
    }

    test('com atestador, a faixa .cent carrega com a chave', () async {
      final (p, motor) = await player(_cliente(_Servidor(), _CofreMemoria()));
      final cap = capituloCifrado();
      expect(p.podeTocar(cap.faixa!), isTrue);
      await p.abrir(cap, info);
      expect(motor.chamadas.first, 'carregar');
      expect(motor.chave, _chave);
    });

    test('sem atestador, a .cent não toca e o .m4a toca sem chave', () async {
      final (p, motor) = await player(null);
      final cap = capituloCifrado();
      expect(p.podeTocar(cap.faixa!), isFalse);
      await p.abrir(cap, info);
      expect(motor.chamadas, isEmpty);

      await p.abrir(Capitulo.deJson(capituloLongo), info);
      expect(motor.chamadas.first, 'carregar');
      expect(motor.chave, isNull);
    });

    test('sem chave, o capítulo que tocava continua carregado', () async {
      final s = _Servidor();
      final (p, motor) = await player(_cliente(s, _CofreMemoria()));
      final aberto = Capitulo.deJson(capituloLongo);
      await p.abrir(aberto, info);
      motor.chamadas.clear();
      s.foraDoAr = true;
      final cifrado = Capitulo.deJson({
        ...capituloLongo,
        'id': 99,
        'faixa': {
          ...(capituloLongo['faixa'] as Map<String, dynamic>),
          'id': 7,
          'formato': 'cent1',
        },
      });
      await expectLater(p.abrir(cifrado, info), throwsA(isA<ErroChave>()));
      expect(motor.chamadas, isEmpty);
      expect(p.carregado(aberto.resumo.id), isTrue);
    });
  });
}
