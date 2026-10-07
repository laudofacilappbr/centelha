// StreamAudioSource é a via do just_audio para áudio gerado pelo app; marcado como
// experimental desde 2021 e estável na prática. Se mudar, só esta classe muda.
// ignore_for_file: experimental_member_use

import 'dart:async';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:just_audio/just_audio.dart';

import 'cent.dart';

/// Lê um intervalo de bytes do .cent: da CDN por Range, ou de um arquivo baixado.
abstract interface class LeitorCent {
  /// Bytes de [inicio] (inclusive) a [fim] (exclusivo).
  Future<Uint8List> ler(int inicio, int fim);
}

class LeitorHttp implements LeitorCent {
  LeitorHttp(this.url, {http.Client? cliente})
    : _cliente = cliente ?? http.Client();

  final Uri url;
  final http.Client _cliente;

  @override
  Future<Uint8List> ler(int inicio, int fim) async {
    final r = await _cliente.get(
      url,
      headers: {'Range': 'bytes=$inicio-${fim - 1}'},
    );
    // 200 com o arquivo inteiro também serve: um proxy no caminho pode ignorar Range.
    if (r.statusCode == 200 && r.bodyBytes.length >= fim) {
      return Uint8List.sublistView(r.bodyBytes, inicio, fim);
    }
    if (r.statusCode != 206 || r.bodyBytes.length != fim - inicio) {
      throw ErroCifra(
        'a CDN respondeu ${r.statusCode} para os bytes $inicio-$fim',
      );
    }
    return r.bodyBytes;
  }
}

/// Fonte do player para a faixa .cent: o player pede bytes do áudio aberto, e esta
/// classe baixa só os blocos que cobrem o pedido e os decifra em memória. Nada aberto
/// vai para o disco. Avançar e recuar baixam só o trecho novo.
class FonteCent extends StreamAudioSource {
  FonteCent(this._leitor, this._chave, {super.tag});

  final LeitorCent _leitor;
  final Uint8List _chave;
  CabecalhoCent? _cabecalho;

  /// Blocos baixados por pedido à CDN: 16 x 64 KiB = 1 MiB, menos idas e voltas.
  static const blocosPorLeitura = 16;

  Future<CabecalhoCent> _cab() async =>
      _cabecalho ??= CabecalhoCent.ler(await _leitor.ler(0, tamanhoCabecalho));

  @override
  Future<StreamAudioResponse> request([int? start, int? end]) async {
    final cab = await _cab();
    final total = cab.tamanhoClaro;
    final inicio = start ?? 0;
    final fim = end == null || end > total ? total : end;
    return StreamAudioResponse(
      sourceLength: total,
      contentLength: fim - inicio,
      offset: inicio,
      contentType: 'audio/mp4',
      stream: _claro(cab, inicio, fim),
    );
  }

  /// Áudio aberto de [inicio] a [fim], bloco a bloco, à medida que o player consome.
  Stream<List<int>> _claro(CabecalhoCent cab, int inicio, int fim) async* {
    if (inicio >= fim) return;
    var bloco = cab.blocoDe(inicio);
    final ultimo = cab.blocoDe(fim - 1);
    while (bloco <= ultimo) {
      final ate = bloco + blocosPorLeitura - 1 < ultimo
          ? bloco + blocosPorLeitura - 1
          : ultimo;
      final (de, _) = cab.posicaoBloco(bloco);
      final (inicioFim, nFim) = cab.posicaoBloco(ate);
      final cifrado = await _leitor.ler(de, inicioFim + nFim);
      for (var i = bloco; i <= ate; i++) {
        final (p, n) = cab.posicaoBloco(i);
        final claro = cab.decifrarBloco(
          i,
          Uint8List.sublistView(cifrado, p - de, p - de + n),
          _chave,
        );
        final base = i * cab.tamanhoBloco;
        final a = inicio > base ? inicio - base : 0;
        final b = fim < base + claro.length ? fim - base : claro.length;
        yield Uint8List.sublistView(claro, a, b);
      }
      bloco = ate + 1;
    }
  }
}
