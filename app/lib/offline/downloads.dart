// Capítulos baixados para ouvir sem internet (ADR 0004). Vai para o aparelho só o
// .cent, que sem a chave é ilegível, na pasta privada do app; a chave é pedida na
// hora do download e fica no Keychain/Keystore, válida por 90 dias.
import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

import '../api/catalogo_api.dart';
import '../chave/chaves.dart';
import '../cifra/cent.dart';
import '../cifra/fonte_cent.dart';

/// Lê o .cent baixado, bloco a bloco, como a CDN faria por Range.
class LeitorArquivo implements LeitorCent {
  LeitorArquivo(this.arquivo);
  final File arquivo;

  @override
  Future<Uint8List> ler(int inicio, int fim) async {
    final f = await arquivo.open();
    try {
      await f.setPosition(inicio);
      final dados = await f.read(fim - inicio);
      if (dados.length != fim - inicio) {
        throw ErroCifra('arquivo baixado menor que o esperado');
      }
      return dados;
    } finally {
      await f.close();
    }
  }
}

class ErroDownload implements Exception {
  ErroDownload(this.mensagem);
  final String mensagem;

  @override
  String toString() => 'ErroDownload: $mensagem';
}

class Downloads extends ChangeNotifier {
  Downloads(this.pasta, this._chaves, {http.Client? cliente})
    : _cliente = cliente ?? http.Client();

  /// Pasta de suporte do app: não aparece para o usuário nem vai para o backup da
  /// galeria, e some quando o app é desinstalado.
  static Future<Downloads> abrir(ClienteChaves chaves) async {
    final suporte = await getApplicationSupportDirectory();
    return Downloads(Directory('${suporte.path}/faixas'), chaves);
  }

  final Directory pasta;
  final ClienteChaves _chaves;
  final http.Client _cliente;
  final _progresso = <String, double>{};

  /// Só faixa cifrada com id: .m4a aberto nunca vai para o aparelho.
  bool podeBaixar(Faixa f) => f.cifrada && f.id != null;

  File arquivo(Faixa f) =>
      File('${pasta.path}/faixa-${f.id}-v${f.versao}.cent');

  bool baixado(Faixa f) => podeBaixar(f) && arquivo(f).existsSync();

  /// De 0 a 1 enquanto baixa; null fora disso.
  double? progresso(Faixa f) => _progresso[arquivo(f).path];

  Future<void> baixar(Faixa f) async {
    if (!podeBaixar(f) || baixado(f) || progresso(f) != null) return;
    final destino = arquivo(f);
    final parcial = File('${destino.path}.parcial');
    _progresso[destino.path] = 0;
    notifyListeners();
    try {
      // A chave antes do arquivo: baixado sem chave não tocaria offline.
      await _chaves.chave(f);
      await pasta.create(recursive: true);
      final resposta = await _cliente.send(
        http.Request('GET', Uri.parse(f.url)),
      );
      if (resposta.statusCode != 200) {
        throw ErroDownload('a CDN respondeu ${resposta.statusCode}');
      }
      final total = resposta.contentLength;
      var recebido = 0;
      final saida = parcial.openWrite();
      try {
        await for (final pedaco in resposta.stream) {
          saida.add(pedaco);
          recebido += pedaco.length;
          if (total != null && total > 0) {
            _progresso[destino.path] = recebido / total;
            notifyListeners();
          }
        }
      } finally {
        await saida.close();
      }
      await _conferir(parcial);
      await parcial.rename(destino.path);
      await _apagarVersoesAntigas(f);
    } on ErroChave catch (e) {
      throw ErroDownload(e.mensagem);
    } on http.ClientException catch (e) {
      throw ErroDownload('sem conexão: ${e.message}');
    } finally {
      _progresso.remove(destino.path);
      if (parcial.existsSync()) await parcial.delete();
      notifyListeners();
    }
  }

  /// Arquivo cortado no meio do download não pode passar por baixado.
  Future<void> _conferir(File f) async {
    final tamanho = await f.length();
    final cab = CabecalhoCent.ler(
      await LeitorArquivo(f).ler(0, tamanhoCabecalho),
    );
    if (tamanho != cab.tamanhoArquivo) {
      throw ErroDownload(
        'arquivo incompleto ($tamanho de ${cab.tamanhoArquivo})',
      );
    }
  }

  /// Regenerar o áudio cria versão nova; a antiga deixa de servir.
  Future<void> _apagarVersoesAntigas(Faixa f) async {
    await for (final e in pasta.list()) {
      final nome = e.uri.pathSegments.last;
      if (e is File &&
          nome.startsWith('faixa-${f.id}-v') &&
          nome != arquivo(f).uri.pathSegments.last) {
        await e.delete();
      }
    }
  }

  Future<void> apagar(Faixa f) async {
    final a = arquivo(f);
    // Um arquivo só: síncrono, para a tela mudar no mesmo quadro.
    if (a.existsSync()) a.deleteSync();
    notifyListeners();
  }
}
