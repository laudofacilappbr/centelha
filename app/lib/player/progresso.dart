// Progresso e marcadores no aparelho (MVP sem login). Uma chave por capítulo.
import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../api/catalogo_api.dart';
import 'reprodutor.dart';

/// Onde parou. Guarda também o segmento: se o áudio for regenerado (versão nova,
/// tempos novos), retoma no começo do mesmo segmento em vez de num ponto qualquer.
class Posicao {
  const Posicao({required this.versao, required this.ms, this.segmentoId});

  factory Posicao.deJson(Map<String, dynamic> j) => Posicao(
    versao: j['versao'] as int,
    ms: j['ms'] as int,
    segmentoId: j['segmento'] as int?,
  );

  final int versao;
  final int ms;
  final int? segmentoId;

  Map<String, dynamic> paraJson() => {
    'versao': versao,
    'ms': ms,
    'segmento': segmentoId,
  };

  /// Posição equivalente na [faixa] atual.
  int naFaixa(Faixa faixa) {
    if (versao == faixa.versao) return ms.clamp(0, faixa.duracaoMs);
    final inicio = segmentoId == null
        ? null
        : faixa.inicioDoSegmento(segmentoId!);
    return inicio ?? 0;
  }
}

class Marcador {
  const Marcador({required this.posicao, required this.criadoEm});

  factory Marcador.deJson(Map<String, dynamic> j) => Marcador(
    posicao: Posicao.deJson(j['posicao'] as Map<String, dynamic>),
    criadoEm: DateTime.parse(j['criado_em'] as String),
  );

  final Posicao posicao;
  final DateTime criadoEm;

  Map<String, dynamic> paraJson() => {
    'posicao': posicao.paraJson(),
    'criado_em': criadoEm.toIso8601String(),
  };
}

/// Último capítulo ouvido, para o "continuar ouvindo" do início.
class UltimoOuvido {
  const UltimoOuvido({required this.capitulo, required this.info});

  factory UltimoOuvido.deJson(Map<String, dynamic> j) => UltimoOuvido(
    capitulo: CapituloResumo.deJson(j['capitulo'] as Map<String, dynamic>),
    info: InfoFaixa(
      titulo: j['titulo'] as String? ?? '',
      edicao: j['edicao'] as String,
      autor: j['autor'] as String? ?? '',
    ),
  );

  final CapituloResumo capitulo;
  final InfoFaixa info;

  Map<String, dynamic> paraJson() => {
    'capitulo': {
      'id': capitulo.id,
      'ordem': capitulo.ordem,
      'titulo': capitulo.titulo,
      'referencia_canonica': capitulo.referencia,
    },
    'titulo': info.titulo,
    'edicao': info.edicao,
    'autor': info.autor,
  };
}

class ArmazemProgresso {
  ArmazemProgresso(this._prefs);

  final SharedPreferences _prefs;

  static String _chavePosicao(int capituloId) => 'posicao:$capituloId';
  static String _chaveMarcadores(int capituloId) => 'marcadores:$capituloId';
  static const _chaveUltimo = 'ultimo_ouvido';
  static const _chaveVelocidade = 'velocidade';

  double get velocidade => _prefs.getDouble(_chaveVelocidade) ?? 1.0;

  Future<void> salvarVelocidade(double v) =>
      _prefs.setDouble(_chaveVelocidade, v);

  Map<String, dynamic>? _ler(String chave) {
    final texto = _prefs.getString(chave);
    if (texto == null) return null;
    try {
      return jsonDecode(texto) as Map<String, dynamic>;
    } on FormatException {
      return null;
    }
  }

  Posicao? posicao(int capituloId) {
    final j = _ler(_chavePosicao(capituloId));
    return j == null ? null : Posicao.deJson(j);
  }

  Future<void> salvarPosicao(int capituloId, Posicao p) =>
      _prefs.setString(_chavePosicao(capituloId), jsonEncode(p.paraJson()));

  Future<void> esquecerPosicao(int capituloId) =>
      _prefs.remove(_chavePosicao(capituloId));

  UltimoOuvido? ultimo() {
    final j = _ler(_chaveUltimo);
    return j == null ? null : UltimoOuvido.deJson(j);
  }

  Future<void> salvarUltimo(UltimoOuvido u) =>
      _prefs.setString(_chaveUltimo, jsonEncode(u.paraJson()));

  List<Marcador> marcadores(int capituloId) {
    final texto = _prefs.getString(_chaveMarcadores(capituloId));
    if (texto == null) return [];
    return [
      for (final m in jsonDecode(texto) as List)
        Marcador.deJson(m as Map<String, dynamic>),
    ]..sort((a, b) => a.posicao.ms.compareTo(b.posicao.ms));
  }

  Future<void> _gravarMarcadores(int capituloId, List<Marcador> lista) =>
      _prefs.setString(
        _chaveMarcadores(capituloId),
        jsonEncode([for (final m in lista) m.paraJson()]),
      );

  Future<void> adicionarMarcador(int capituloId, Marcador m) =>
      _gravarMarcadores(capituloId, [...marcadores(capituloId), m]);

  Future<void> removerMarcador(int capituloId, Marcador m) =>
      _gravarMarcadores(capituloId, [
        for (final x in marcadores(capituloId))
          if (x.criadoEm != m.criadoEm) x,
      ]);
}
