// O que a tela e o controle do player precisam do motor de áudio. A implementação
// real usa just_audio dentro do audio_service (segundo plano e tela de bloqueio);
// os testes usam uma falsa.
import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:audio_service/audio_service.dart';
import 'package:audio_session/audio_session.dart';
import 'package:just_audio/just_audio.dart';

import '../api/catalogo_api.dart';
import '../cifra/fonte_cent.dart';
import '../offline/downloads.dart';

/// O que aparece na tela de bloqueio e na notificação.
class InfoFaixa {
  const InfoFaixa({
    required this.titulo,
    required this.edicao,
    required this.autor,
  });

  final String titulo;
  final String edicao;
  final String autor;
}

abstract interface class Reprodutor {
  Stream<Duration> get posicao;
  Stream<bool> get tocando;

  /// Emite quando a faixa chega ao fim.
  Stream<void> get terminou;

  Duration get posicaoAtual;
  bool get estaTocando;

  /// [chave]: a da faixa .cent, que só o app atestado recebe (ADR 0004).
  /// [arquivo]: o .cent baixado, quando o capítulo está no aparelho.
  Future<void> carregar(
    Faixa faixa,
    InfoFaixa info,
    Duration inicio, {
    Uint8List? chave,
    File? arquivo,
  });
  Future<void> tocar();
  Future<void> pausar();
  Future<void> irPara(Duration posicao);
  Future<void> velocidade(double v);
  Future<void> parar();
}

/// Origem do áudio de uma faixa: a URL do .m4a, ou o .cent decifrado bloco a bloco
/// (FonteCent), que baixa da CDN só o trecho que o player pede, ou lê do [arquivo]
/// baixado.
AudioSource fonteDe(Faixa faixa, {Uint8List? chave, File? arquivo}) =>
    faixa.cifrada
    ? FonteCent(
        arquivo != null
            ? LeitorArquivo(arquivo)
            : LeitorHttp(Uri.parse(faixa.url)),
        chave!,
      )
    : AudioSource.uri(Uri.parse(faixa.url));

class ReprodutorAudioService implements Reprodutor {
  ReprodutorAudioService._(this._manipulador);

  final _Manipulador _manipulador;
  AudioPlayer get _player => _manipulador.player;

  /// Chamar uma vez, no main, antes do runApp.
  static Future<ReprodutorAudioService> iniciar() async {
    // Sessão de fala: pausa com ligação e com fone desconectado.
    final sessao = await AudioSession.instance;
    await sessao.configure(const AudioSessionConfiguration.speech());
    final manipulador = await AudioService.init(
      builder: _Manipulador.new,
      config: const AudioServiceConfig(
        androidNotificationChannelId: 'app.centelha.audio',
        androidNotificationChannelName: 'Centelha',
        androidNotificationOngoing: true,
        androidStopForegroundOnPause: true,
        fastForwardInterval: Duration(seconds: 15),
        rewindInterval: Duration(seconds: 15),
      ),
    );
    return ReprodutorAudioService._(manipulador);
  }

  @override
  Stream<Duration> get posicao => _player.positionStream;

  @override
  Stream<bool> get tocando => _player.playingStream;

  @override
  Stream<void> get terminou => _player.processingStateStream.where(
    (s) => s == ProcessingState.completed,
  );

  @override
  Duration get posicaoAtual => _player.position;

  @override
  bool get estaTocando => _player.playing;

  @override
  Future<void> carregar(
    Faixa faixa,
    InfoFaixa info,
    Duration inicio, {
    Uint8List? chave,
    File? arquivo,
  }) => _manipulador.carregar(faixa, info, inicio, chave, arquivo);

  // play() do just_audio só termina quando a reprodução para; não esperar por ele.
  @override
  Future<void> tocar() async => unawaited(_manipulador.play());

  @override
  Future<void> pausar() => _manipulador.pause();

  @override
  Future<void> irPara(Duration posicao) => _manipulador.seek(posicao);

  @override
  Future<void> velocidade(double v) => _manipulador.setSpeed(v);

  @override
  Future<void> parar() => _manipulador.stop();
}

class _Manipulador extends BaseAudioHandler with SeekHandler {
  _Manipulador() {
    player.playbackEventStream.map(_estado).pipe(playbackState);
  }

  final player = AudioPlayer();

  Future<void> carregar(
    Faixa faixa,
    InfoFaixa info,
    Duration inicio,
    Uint8List? chave,
    File? arquivo,
  ) async {
    mediaItem.add(
      MediaItem(
        id: faixa.url,
        title: info.titulo,
        album: info.edicao,
        artist: info.autor,
        duration: Duration(milliseconds: faixa.duracaoMs),
      ),
    );
    await player.setAudioSource(
      fonteDe(faixa, chave: chave, arquivo: arquivo),
      initialPosition: inicio,
    );
  }

  PlaybackState _estado(PlaybackEvent evento) => PlaybackState(
    controls: [
      MediaControl.rewind,
      if (player.playing) MediaControl.pause else MediaControl.play,
      MediaControl.fastForward,
    ],
    systemActions: const {
      MediaAction.seek,
      MediaAction.seekForward,
      MediaAction.seekBackward,
    },
    androidCompactActionIndices: const [0, 1, 2],
    processingState: const {
      ProcessingState.idle: AudioProcessingState.idle,
      ProcessingState.loading: AudioProcessingState.loading,
      ProcessingState.buffering: AudioProcessingState.buffering,
      ProcessingState.ready: AudioProcessingState.ready,
      ProcessingState.completed: AudioProcessingState.completed,
    }[player.processingState]!,
    playing: player.playing,
    updatePosition: player.position,
    bufferedPosition: player.bufferedPosition,
    speed: player.speed,
  );

  @override
  Future<void> play() => player.play();

  @override
  Future<void> pause() => player.pause();

  @override
  Future<void> seek(Duration position) => player.seek(position);

  @override
  Future<void> setSpeed(double speed) => player.setSpeed(speed);

  @override
  Future<void> stop() async {
    await player.stop();
    await super.stop();
  }
}
