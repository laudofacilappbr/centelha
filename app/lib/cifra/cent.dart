// Formato .cent (ADR 0004), o mesmo de api/src/centelha_api/pipeline/cifra.py:
//
//   cabeçalho (32 bytes): "CENT", versão u8 = 1, 3 zeros, bloco claro u32 BE,
//   prefixo do nonce (8 bytes), tamanho claro u64 BE, 4 zeros
//   blocos: AES-256-GCM(bloco claro) + tag de 16 bytes; o último pode ser menor
//
// Nonce do bloco i = prefixo || i (u32 BE). Dado associado = cabeçalho || i (u32 BE)
// || 1 se é o último bloco, senão 0. Bloco trocado, reordenado ou cortado não abre.
import 'dart:typed_data';

import 'package:pointycastle/export.dart';

const tamanhoCabecalho = 32;
const tamanhoTag = 16;
const tamanhoChave = 32;
const _assinatura = [0x43, 0x45, 0x4E, 0x54]; // "CENT"
const _versao = 1;

class ErroCifra implements Exception {
  ErroCifra(this.mensagem);
  final String mensagem;

  @override
  String toString() => 'ErroCifra: $mensagem';
}

class CabecalhoCent {
  CabecalhoCent._(this.bytes, this.tamanhoBloco, this.tamanhoClaro);

  factory CabecalhoCent.ler(Uint8List dados) {
    if (dados.length < tamanhoCabecalho) {
      throw ErroCifra('arquivo menor que o cabeçalho');
    }
    for (var i = 0; i < 4; i++) {
      if (dados[i] != _assinatura[i]) throw ErroCifra('não é um arquivo .cent');
    }
    if (dados[4] != _versao) {
      throw ErroCifra('versão ${dados[4]} do .cent não suportada');
    }
    final d = ByteData.sublistView(dados, 0, tamanhoCabecalho);
    final bloco = d.getUint32(8);
    if (bloco == 0) throw ErroCifra('tamanho de bloco inválido');
    return CabecalhoCent._(
      Uint8List.fromList(dados.sublist(0, tamanhoCabecalho)),
      bloco,
      d.getUint64(20),
    );
  }

  final Uint8List bytes;
  final int tamanhoBloco;

  /// Tamanho do áudio aberto: é o que o player vê como tamanho do arquivo.
  final int tamanhoClaro;

  Uint8List get _prefixoNonce => bytes.sublist(12, 20);

  int get blocos {
    final n = (tamanhoClaro + tamanhoBloco - 1) ~/ tamanhoBloco;
    return n < 1 ? 1 : n;
  }

  /// Tamanho total do .cent que este cabeçalho descreve.
  int get tamanhoArquivo =>
      tamanhoCabecalho + tamanhoClaro + blocos * tamanhoTag;

  /// Bloco que contém o byte [posicaoClara] do áudio aberto.
  int blocoDe(int posicaoClara) => posicaoClara ~/ tamanhoBloco;

  /// Início e tamanho, no .cent, do bloco cifrado [indice].
  (int inicio, int tamanho) posicaoBloco(int indice) {
    if (indice < 0 || indice >= blocos) {
      throw ErroCifra('bloco $indice fora do arquivo ($blocos blocos)');
    }
    final inicio = tamanhoCabecalho + indice * (tamanhoBloco + tamanhoTag);
    final resto = tamanhoClaro - indice * tamanhoBloco;
    final claro = resto < tamanhoBloco ? resto : tamanhoBloco;
    return (inicio, claro + tamanhoTag);
  }

  Uint8List _nonce(int indice) {
    final n = Uint8List(12)..setRange(0, 8, _prefixoNonce);
    ByteData.sublistView(n).setUint32(8, indice);
    return n;
  }

  Uint8List _associado(int indice) {
    final a = Uint8List(tamanhoCabecalho + 5)
      ..setRange(0, tamanhoCabecalho, bytes);
    final d = ByteData.sublistView(a);
    d.setUint32(tamanhoCabecalho, indice);
    d.setUint8(tamanhoCabecalho + 4, indice == blocos - 1 ? 1 : 0);
    return a;
  }

  /// Abre o bloco [indice]. ErroCifra se a chave não é a da faixa ou o bloco mudou.
  Uint8List decifrarBloco(int indice, Uint8List cifrado, Uint8List chave) {
    if (chave.length != tamanhoChave) {
      throw ErroCifra('chave da faixa precisa ter $tamanhoChave bytes');
    }
    final gcm = GCMBlockCipher(AESEngine())
      ..init(
        false,
        AEADParameters(
          KeyParameter(chave),
          tamanhoTag * 8,
          _nonce(indice),
          _associado(indice),
        ),
      );
    try {
      return gcm.process(cifrado);
    } on InvalidCipherTextException {
      throw ErroCifra(
        'bloco $indice não confere (chave errada ou arquivo alterado)',
      );
    }
  }
}

/// O arquivo inteiro de uma vez. Para o player, use a fonte por blocos.
Uint8List decifrarCent(Uint8List dados, Uint8List chave) {
  final cab = CabecalhoCent.ler(dados);
  if (dados.length != cab.tamanhoArquivo) {
    throw ErroCifra(
      'arquivo com ${dados.length} bytes; o cabeçalho pede ${cab.tamanhoArquivo}',
    );
  }
  final saida = BytesBuilder(copy: false);
  for (var i = 0; i < cab.blocos; i++) {
    final (inicio, n) = cab.posicaoBloco(i);
    saida.add(
      cab.decifrarBloco(
        i,
        Uint8List.sublistView(dados, inicio, inicio + n),
        chave,
      ),
    );
  }
  return saida.takeBytes();
}
