// Estado do player para as telas: o que toca, onde está, velocidade, timer de sono e
// marcadores. Grava o progresso no aparelho enquanto toca.
import 'dart:async';

import 'package:flutter/widgets.dart';

import '../api/catalogo_api.dart';
import '../chave/chaves.dart';
import '../offline/downloads.dart';
import 'progresso.dart';
import 'reprodutor.dart';

class ControlePlayer extends ChangeNotifier {
  ControlePlayer(
    this._reprodutor,
    this._armazem, {
    this._chaves,
    this.downloads,
  }) {
    _velocidade = _armazem.velocidade;
    _inscricoes = [
      _reprodutor.posicao.listen(_aoMudarPosicao),
      _reprodutor.tocando.listen(_aoMudarTocando),
      _reprodutor.terminou.listen((_) => _aoTerminar()),
    ];
  }

  static const velocidades = [0.75, 1.0, 1.25, 1.5, 1.75, 2.0];
  static const salto = Duration(seconds: 15);

  /// Grava a posição a cada tanto tocando; pausar e trocar de capítulo gravam sempre.
  static const _intervaloGravacao = Duration(seconds: 5);

  final Reprodutor _reprodutor;
  final ArmazemProgresso _armazem;

  /// Sem atestador no aparelho, null: a faixa .cent fica indisponível.
  final ClienteChaves? _chaves;

  /// Capítulos baixados; existe junto com as chaves (só o .cent vai para o aparelho).
  final Downloads? downloads;
  late final List<StreamSubscription<Object?>> _inscricoes;

  Capitulo? _capitulo;
  Duration _posicao = Duration.zero;
  Duration _ultimaGravada = Duration.zero;
  bool _tocando = false;
  late double _velocidade;
  Timer? _timerSono;
  DateTime? _fimTimerSono;

  Capitulo? get capitulo => _capitulo;
  Faixa? get faixa => _capitulo?.faixa;
  Duration get posicao => _posicao;
  Duration get duracao => Duration(milliseconds: faixa?.duracaoMs ?? 0);
  bool get tocando => _tocando;
  double get velocidade => _velocidade;
  DateTime? get fimTimerSono => _fimTimerSono;
  ArmazemProgresso get armazem => _armazem;

  bool carregado(int capituloId) => _capitulo?.resumo.id == capituloId;

  bool podeTocar(Faixa faixa) =>
      faixa.tocavel || (faixa.cifrada && _chaves != null);

  /// Segmento tocando agora (para a leitura acompanhada, #32).
  int? get segmentoAtual => faixa?.segmentoEm(_posicao.inMilliseconds);

  /// Carrega o capítulo na posição em que parou. Não começa a tocar.
  /// ErroChave quando a faixa é .cent e a chave não veio (sem internet, por exemplo).
  Future<void> abrir(Capitulo capitulo, InfoFaixa info) async {
    final faixa = capitulo.faixa;
    if (faixa == null || !podeTocar(faixa) || carregado(capitulo.resumo.id)) {
      return;
    }
    // Antes de trocar o capítulo: sem chave, o que tocava continua carregado.
    final chave = faixa.cifrada ? await _chaves!.chave(faixa) : null;
    await _gravar();
    final salva = _armazem.posicao(capitulo.resumo.id);
    final inicio = Duration(milliseconds: salva?.naFaixa(faixa) ?? 0);
    _capitulo = capitulo;
    _posicao = _ultimaGravada = inicio;
    notifyListeners();
    final baixado = downloads?.baixado(faixa) ?? false;
    await _reprodutor.carregar(
      faixa,
      info,
      inicio,
      chave: chave,
      arquivo: baixado ? downloads!.arquivo(faixa) : null,
    );
    await _reprodutor.velocidade(_velocidade);
    await _armazem.salvarUltimo(
      UltimoOuvido(capitulo: capitulo.resumo, info: info),
    );
  }

  Future<void> alternar() =>
      _tocando ? _reprodutor.pausar() : _reprodutor.tocar();

  Future<void> pular(Duration delta) {
    final alvo = _posicao + delta;
    return irPara(
      alvo < Duration.zero ? Duration.zero : (alvo > duracao ? duracao : alvo),
    );
  }

  Future<void> irPara(Duration alvo) async {
    _posicao = alvo;
    notifyListeners();
    await _reprodutor.irPara(alvo);
    await _gravar();
  }

  Future<void> definirVelocidade(double v) async {
    _velocidade = v;
    notifyListeners();
    await _reprodutor.velocidade(v);
    await _armazem.salvarVelocidade(v);
  }

  /// null desliga o timer.
  void timerSono(Duration? duracao) {
    _timerSono?.cancel();
    _timerSono = null;
    _fimTimerSono = null;
    if (duracao != null) {
      _fimTimerSono = DateTime.now().add(duracao);
      _timerSono = Timer(duracao, () {
        _timerSono = null;
        _fimTimerSono = null;
        _reprodutor.pausar();
        notifyListeners();
      });
    }
    notifyListeners();
  }

  List<Marcador> get marcadores =>
      _capitulo == null ? [] : _armazem.marcadores(_capitulo!.resumo.id);

  Future<void> marcar() async {
    final c = _capitulo;
    if (c == null) return;
    await _armazem.adicionarMarcador(
      c.resumo.id,
      Marcador(posicao: _posicaoAtual(), criadoEm: DateTime.now()),
    );
    notifyListeners();
  }

  Future<void> removerMarcador(Marcador m) async {
    final c = _capitulo;
    if (c == null) return;
    await _armazem.removerMarcador(c.resumo.id, m);
    notifyListeners();
  }

  Posicao _posicaoAtual() => Posicao(
    versao: faixa!.versao,
    ms: _posicao.inMilliseconds,
    segmentoId: segmentoAtual,
  );

  Future<void> _gravar() async {
    final c = _capitulo;
    if (c == null || c.faixa == null) return;
    _ultimaGravada = _posicao;
    await _armazem.salvarPosicao(c.resumo.id, _posicaoAtual());
  }

  void _aoMudarPosicao(Duration p) {
    if (_capitulo == null) return;
    _posicao = p;
    if ((p - _ultimaGravada).abs() >= _intervaloGravacao) _gravar();
    notifyListeners();
  }

  void _aoMudarTocando(bool tocando) {
    _tocando = tocando;
    if (!tocando) _gravar();
    notifyListeners();
  }

  // Ouviu até o fim: a próxima vez começa do início.
  Future<void> _aoTerminar() async {
    final c = _capitulo;
    if (c == null) return;
    await _reprodutor.pausar();
    await _reprodutor.irPara(Duration.zero);
    _posicao = _ultimaGravada = Duration.zero;
    await _armazem.esquecerPosicao(c.resumo.id);
    notifyListeners();
  }

  @override
  void dispose() {
    _timerSono?.cancel();
    for (final i in _inscricoes) {
      i.cancel();
    }
    super.dispose();
  }
}

/// Dá o player às telas: EscopoPlayer.of(context).
class EscopoPlayer extends InheritedNotifier<ControlePlayer> {
  const EscopoPlayer({
    super.key,
    required ControlePlayer player,
    required super.child,
  }) : super(notifier: player);

  static ControlePlayer of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<EscopoPlayer>()!.notifier!;
}
