import 'dart:async';
import 'dart:typed_data';

import 'package:centelha/api/catalogo_api.dart';
import 'package:centelha/player/controle_player.dart';
import 'package:centelha/player/progresso.dart';
import 'package:centelha/player/reprodutor.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Motor de áudio de mentira: guarda o que pediram e deixa o teste mover o tempo.
class ReprodutorFalso implements Reprodutor {
  final _posicao = StreamController<Duration>.broadcast(sync: true);
  final _tocando = StreamController<bool>.broadcast(sync: true);
  final _terminou = StreamController<void>.broadcast(sync: true);

  final chamadas = <String>[];
  Faixa? faixa;
  Uint8List? chave;
  InfoFaixa? info;
  Duration inicio = Duration.zero;
  double vel = 1.0;
  Duration _atual = Duration.zero;
  bool _tocandoAgora = false;

  /// Simula o áudio andando até [p].
  void avancarTempo(Duration p) {
    _atual = p;
    _posicao.add(p);
  }

  void chegarAoFim() => _terminou.add(null);

  @override
  Stream<Duration> get posicao => _posicao.stream;
  @override
  Stream<bool> get tocando => _tocando.stream;
  @override
  Stream<void> get terminou => _terminou.stream;
  @override
  Duration get posicaoAtual => _atual;
  @override
  bool get estaTocando => _tocandoAgora;

  @override
  Future<void> carregar(
    Faixa faixa,
    InfoFaixa info,
    Duration inicio, {
    Uint8List? chave,
  }) async {
    chamadas.add('carregar');
    this.faixa = faixa;
    this.chave = chave;
    this.info = info;
    this.inicio = _atual = inicio;
  }

  @override
  Future<void> tocar() async {
    chamadas.add('tocar');
    _tocandoAgora = true;
    _tocando.add(true);
  }

  @override
  Future<void> pausar() async {
    chamadas.add('pausar');
    _tocandoAgora = false;
    _tocando.add(false);
  }

  @override
  Future<void> irPara(Duration posicao) async {
    chamadas.add('irPara ${posicao.inSeconds}s');
    avancarTempo(posicao);
  }

  @override
  Future<void> velocidade(double v) async {
    chamadas.add('velocidade $v');
    vel = v;
  }

  @override
  Future<void> parar() async => chamadas.add('parar');
}

/// Player com motor falso e progresso no SharedPreferences de teste (chame depois de
/// SharedPreferences.setMockInitialValues).
Future<(ControlePlayer, ReprodutorFalso)> playerFalso() async {
  final motor = ReprodutorFalso();
  final player = ControlePlayer(
    motor,
    ArmazemProgresso(await SharedPreferences.getInstance()),
  );
  return (player, motor);
}
