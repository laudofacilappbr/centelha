// Chave da faixa cifrada (ADR 0004): o app prova que é uma instalação legítima,
// recebe um token de aparelho e, com ele, a chave de cada faixa, válida por 90 dias.
//
//   POST /v1/dispositivos/desafio      → valor de uso único
//   POST /v1/dispositivos              → atestado com o desafio dentro → token
//   POST /v1/faixas/{id}/chave         → chave (base64) e validade
//
// Token e chaves ficam no Keychain (iOS) ou no Keystore (Android), nunca em
// SharedPreferences: são o que abre o áudio.
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import '../api/catalogo_api.dart';

/// Prova de que o app é legítimo, para a plataforma informada ao servidor.
abstract interface class Atestador {
  String get plataforma;

  /// Atestado que amarra o [desafio] a esta instalação.
  Future<String> atestar(String desafio);
}

/// Só desenvolvimento: o servidor aceita com CENTELHA_ATESTACAO_FALSA e nunca em
/// produção. Entra no app só se compilado com --dart-define=CENTELHA_ATESTACAO_FALSA=true.
class AtestadorFalso implements Atestador {
  const AtestadorFalso();

  @override
  String get plataforma => 'falso';

  @override
  Future<String> atestar(String desafio) async => 'falso:$desafio';
}

const _atestacaoFalsa = bool.fromEnvironment('CENTELHA_ATESTACAO_FALSA');

/// Atestador deste aparelho; null enquanto não houver um (App Attest e Play
/// Integrity dependem do passo manual da #73). Sem atestador, a faixa .cent não toca.
Atestador? atestadorDoAparelho() =>
    _atestacaoFalsa ? const AtestadorFalso() : null;

/// Onde ficam o token e as chaves.
abstract interface class Cofre {
  Future<String?> ler(String nome);
  Future<void> gravar(String nome, String valor);
  Future<void> apagar(String nome);
}

class CofreSeguro implements Cofre {
  CofreSeguro([FlutterSecureStorage? armazenamento])
    : _a = armazenamento ?? const FlutterSecureStorage();

  final FlutterSecureStorage _a;

  @override
  Future<String?> ler(String nome) => _a.read(key: nome);

  @override
  Future<void> gravar(String nome, String valor) =>
      _a.write(key: nome, value: valor);

  @override
  Future<void> apagar(String nome) => _a.delete(key: nome);
}

class ErroChave implements Exception {
  ErroChave(this.mensagem);
  final String mensagem;

  @override
  String toString() => 'ErroChave: $mensagem';
}

class ClienteChaves {
  ClienteChaves({
    required this._atestador,
    required this._cofre,
    http.Client? cliente,
    String? base,
    DateTime Function()? agora,
  }) : _cliente = cliente ?? http.Client(),
       _base = Uri.parse(base ?? urlApiPadrao),
       _agora = agora ?? DateTime.now;

  final Atestador _atestador;
  final Cofre _cofre;
  final http.Client _cliente;
  final Uri _base;
  final DateTime Function() _agora;

  static const _nomeToken = 'centelha.token-aparelho';

  /// Renova com esta folga antes de vencer, para não deixar sem áudio quem fica
  /// offline logo depois (decisão 2B: a chave vale 90 dias).
  static const folgaRenovacao = Duration(days: 7);

  String _nomeChave(Faixa f) => 'centelha.chave.${f.id}.v${f.versao}';

  /// Chave AES-256 da [faixa]. Usa a guardada enquanto vale; perto de vencer, tenta
  /// renovar e, sem internet, segue com a guardada até a validade.
  Future<Uint8List> chave(Faixa faixa) async {
    final id = faixa.id;
    if (id == null) throw ErroChave('faixa sem id: API anterior à #73');
    final guardada = await _guardada(faixa);
    final agora = _agora();
    if (guardada != null &&
        guardada.validaAte.isAfter(agora.add(folgaRenovacao))) {
      return guardada.chave;
    }
    try {
      return await _pedir(faixa, id);
    } on ErroChave {
      if (guardada != null && guardada.validaAte.isAfter(agora)) {
        return guardada.chave;
      }
      rethrow;
    }
  }

  Future<({Uint8List chave, DateTime validaAte})?> _guardada(Faixa f) async {
    final texto = await _cofre.ler(_nomeChave(f));
    if (texto == null) return null;
    try {
      final j = jsonDecode(texto) as Map<String, dynamic>;
      return (
        chave: base64Decode(j['chave'] as String),
        validaAte: DateTime.parse(j['valida_ate'] as String),
      );
    } on FormatException {
      return null;
    }
  }

  Future<Uint8List> _pedir(Faixa faixa, int id) async {
    var token = await _cofre.ler(_nomeToken) ?? await _registrar();
    var r = await _post('/v1/faixas/$id/chave', token: token);
    if (r.statusCode == 401) {
      // Token revogado ou de outro servidor: registra de novo, uma vez.
      await _cofre.apagar(_nomeToken);
      token = await _registrar();
      r = await _post('/v1/faixas/$id/chave', token: token);
    }
    if (r.statusCode != 200) {
      throw ErroChave('chave da faixa $id: HTTP ${r.statusCode}');
    }
    final j = _json(r);
    final chave = base64Decode(j['chave'] as String);
    if (chave.length != 32) throw ErroChave('chave com tamanho errado');
    await _cofre.gravar(
      _nomeChave(faixa),
      jsonEncode({'chave': j['chave'], 'valida_ate': j['valida_ate']}),
    );
    return chave;
  }

  Future<String> _registrar() async {
    final d = await _post('/v1/dispositivos/desafio');
    if (d.statusCode != 201) throw ErroChave('desafio: HTTP ${d.statusCode}');
    final desafio = _json(d)['desafio'] as String;
    final r = await _post(
      '/v1/dispositivos',
      corpo: {
        'plataforma': _atestador.plataforma,
        'desafio': desafio,
        'atestado': await _atestador.atestar(desafio),
      },
    );
    if (r.statusCode != 201) throw ErroChave('registro: HTTP ${r.statusCode}');
    final token = _json(r)['token'] as String;
    await _cofre.gravar(_nomeToken, token);
    return token;
  }

  Future<http.Response> _post(
    String caminho, {
    String? token,
    Map<String, Object?>? corpo,
  }) async {
    try {
      return await _cliente.post(
        _base.resolve(caminho),
        headers: {
          'Content-Type': 'application/json',
          if (token != null) 'Authorization': 'Bearer $token',
        },
        body: corpo == null ? null : jsonEncode(corpo),
      );
    } on http.ClientException catch (e) {
      throw ErroChave('sem conexão: ${e.message}');
    }
  }

  Map<String, dynamic> _json(http.Response r) =>
      jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>;
}
