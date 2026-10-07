// Conta opcional de quem lê (#43, 1A): entrar por código no e-mail, sem senha.
//
//   POST   /v1/conta/codigo   {email}           manda o código
//   POST   /v1/conta/sessao   {email, codigo}   → token de sessão
//   GET    /v1/conta                            e-mail e exportacao_aberta
//   POST   /v1/conta/sair                       revoga a sessão
//   DELETE /v1/conta                            exclui a conta e tudo dela
//
// E, só na conta liberada pelo suporte por acessibilidade (#134, 2D):
//   GET /v1/conta/exportacao/capitulos/{id}          o .m4a aberto
//   GET /v1/conta/exportacao/edicoes/{id}/leiame     o LEIAME do pedido
//
// O app funciona inteiro sem conta. O token fica no Keychain ou no Keystore, como o
// do aparelho. O Kids não tem conta: este arquivo não entra lá.
import 'dart:convert';
import 'dart:io';

import 'package:flutter/widgets.dart';
import 'package:http/http.dart' as http;

import '../api/catalogo_api.dart';
import '../chave/chaves.dart' show Cofre;

class ErroConta implements Exception {
  ErroConta(this.mensagem, {this.status});
  final String mensagem;

  /// Status HTTP, quando houve resposta (400 = código errado, 429 = muitos pedidos).
  final int? status;

  @override
  String toString() => 'ErroConta: $mensagem';
}

class Conta extends ChangeNotifier {
  Conta({required this._cofre, http.Client? cliente, String? base})
    : _cliente = cliente ?? http.Client(),
      _base = Uri.parse(base ?? urlApiPadrao);

  final Cofre _cofre;
  final http.Client _cliente;
  final Uri _base;

  static const _nomeToken = 'centelha.token-conta';

  String? _token;
  String? _email;
  bool _exportacaoAberta = false;

  /// E-mail da conta; null sem conta (ou antes de [carregar]).
  String? get email => _email;
  bool get entrou => _email != null;

  /// O suporte liberou o download em formato aberto para esta conta (#134).
  bool get exportacaoAberta => _exportacaoAberta;

  /// Lê a sessão guardada e confere com o servidor. Sessão vencida ou revogada sai do
  /// aparelho; sem internet, fica como está e tenta na próxima vez.
  Future<void> carregar() async {
    _token = await _cofre.ler(_nomeToken);
    if (_token == null) return;
    try {
      final j = await _json('GET', '/v1/conta') as Map<String, dynamic>;
      _definir(j);
    } on ErroConta catch (e) {
      if (e.status == 401) await _esquecer();
    }
  }

  Future<void> pedirCodigo(String email) async {
    await _json('POST', '/v1/conta/codigo', corpo: {'email': email.trim()});
  }

  Future<void> entrar(String email, String codigo) async {
    final j = await _json(
      'POST',
      '/v1/conta/sessao',
      corpo: {'email': email.trim(), 'codigo': codigo.trim()},
    ) as Map<String, dynamic>;
    _token = j['token'] as String;
    await _cofre.gravar(_nomeToken, _token!);
    _email = j['email'] as String;
    // A sessão nova não diz se há liberação: pergunta.
    try {
      _definir(await _json('GET', '/v1/conta') as Map<String, dynamic>);
    } on ErroConta {
      notifyListeners();
    }
  }

  /// Sai deste aparelho. Mesmo sem internet a sessão sai daqui; o servidor a revoga
  /// quando der, ou ela vence sozinha.
  Future<void> sair() async {
    try {
      await _json('POST', '/v1/conta/sair');
    } on ErroConta {
      // Segue: o que importa é o aparelho não guardar mais o token.
    }
    await _esquecer();
  }

  /// Exclui a conta no servidor. Aqui o erro sobe: sem confirmação do servidor, a
  /// pessoa precisa saber que a conta continua lá.
  Future<void> excluir() async {
    await _json('DELETE', '/v1/conta');
    await _esquecer();
  }

  /// Baixa o capítulo em .m4a aberto e o LEIAME do pedido para [pasta]. Devolve os
  /// dois arquivos, para entregar ao sistema ("Salvar em Arquivos", "Abrir com…").
  Future<List<File>> baixarAberto({
    required int capituloId,
    required int edicaoId,
    required Directory pasta,
  }) async {
    final audio = await _baixar('/v1/conta/exportacao/capitulos/$capituloId');
    final leiame = await _baixar(
      '/v1/conta/exportacao/edicoes/$edicaoId/leiame',
    );
    await pasta.create(recursive: true);
    final arquivos = <File>[];
    for (final (r, padrao) in [
      (audio, 'capitulo.m4a'),
      (leiame, 'LEIAME.txt'),
    ]) {
      final f = File('${pasta.path}/${nomeDoAnexo(r, padrao)}');
      await f.writeAsBytes(r.bodyBytes, flush: true);
      arquivos.add(f);
    }
    return arquivos;
  }

  Future<http.Response> _baixar(String caminho) async {
    try {
      return await _pedir('GET', caminho, tempo: const Duration(minutes: 5));
    } on ErroConta catch (e) {
      // Revogada pelo suporte: o botão some.
      if (e.status == 403 && _exportacaoAberta) {
        _exportacaoAberta = false;
        notifyListeners();
      }
      if (e.status == 401) await _esquecer();
      rethrow;
    }
  }

  void _definir(Map<String, dynamic> j) {
    _email = j['email'] as String;
    _exportacaoAberta = j['exportacao_aberta'] as bool? ?? false;
    notifyListeners();
  }

  Future<void> _esquecer() async {
    await _cofre.apagar(_nomeToken);
    _token = null;
    _email = null;
    _exportacaoAberta = false;
    notifyListeners();
  }

  Future<Object?> _json(
    String metodo,
    String caminho, {
    Map<String, Object?>? corpo,
  }) async {
    final r = await _pedir(metodo, caminho, corpo: corpo);
    if (r.bodyBytes.isEmpty) return null;
    return jsonDecode(utf8.decode(r.bodyBytes));
  }

  Future<http.Response> _pedir(
    String metodo,
    String caminho, {
    Map<String, Object?>? corpo,
    Duration tempo = const Duration(seconds: 15),
  }) async {
    final pedido = http.Request(metodo, _base.resolve(caminho));
    if (_token case final token?) {
      pedido.headers['Authorization'] = 'Bearer $token';
    }
    if (corpo != null) {
      pedido.headers['Content-Type'] = 'application/json';
      pedido.body = jsonEncode(corpo);
    }
    final http.Response r;
    try {
      r = await http.Response.fromStream(await _cliente.send(pedido))
          .timeout(tempo);
    } on Exception catch (e) {
      throw ErroConta('$caminho: $e');
    }
    if (r.statusCode >= 300) {
      throw ErroConta('$caminho: HTTP ${r.statusCode}', status: r.statusCode);
    }
    return r;
  }
}

/// Nome do arquivo pelo Content-Disposition da API; sem ele, [padrao]. Só o nome:
/// barra ou ".." no cabeçalho não escolhem pasta.
String nomeDoAnexo(http.Response r, String padrao) {
  final m = RegExp(r'filename="([^"]+)"')
      .firstMatch(r.headers['content-disposition'] ?? '');
  final nome = m?.group(1)?.split(RegExp(r'[/\\]')).last ?? '';
  return nome.isEmpty || nome.startsWith('.') ? padrao : nome;
}

/// A conta para as telas do app principal. O Kids não tem: [maybeOf] dá null lá.
class EscopoConta extends InheritedNotifier<Conta> {
  const EscopoConta({super.key, required Conta conta, required super.child})
    : super(notifier: conta);

  static Conta? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<EscopoConta>()?.notifier;
}
