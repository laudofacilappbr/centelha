// Cliente da API pública do catálogo (api/src/centelha_api/routers/catalogo.py).
// Só leitura e sem login: o app não manda nada que identifique quem ouve.
import 'dart:convert';

import 'package:http/http.dart' as http;

/// URL da API, definida no build: flutter run --dart-define=CENTELHA_API_URL=...
/// No emulador Android, o localhost do computador é 10.0.2.2.
const urlApiPadrao = String.fromEnvironment(
  'CENTELHA_API_URL',
  defaultValue: 'http://10.0.2.2:8000',
);

class ErroCatalogo implements Exception {
  ErroCatalogo(this.mensagem, {this.status});
  final String mensagem;

  /// Status HTTP, quando houve resposta (404 = não existe ou não publicado).
  final int? status;

  @override
  String toString() => 'ErroCatalogo: $mensagem';
}

class EdicaoResumo {
  EdicaoResumo({
    required this.id,
    required this.idioma,
    required this.publico,
    required this.titulo,
    required this.tradutor,
  });

  factory EdicaoResumo.deJson(Map<String, dynamic> j) => EdicaoResumo(
    id: j['id'] as int,
    idioma: j['idioma'] as String,
    publico: j['publico'] as String,
    titulo: j['titulo'] as String,
    tradutor: j['tradutor'] as String?,
  );

  final int id;
  final String idioma;
  final String publico;
  final String titulo;
  final String? tradutor;
}

class Obra {
  Obra({
    required this.slug,
    required this.sigla,
    required this.autor,
    required this.tituloOriginal,
    required this.ano,
    required this.edicoes,
  });

  factory Obra.deJson(Map<String, dynamic> j) => Obra(
    slug: j['slug'] as String,
    sigla: j['sigla'] as String,
    autor: j['autor'] as String,
    tituloOriginal: j['titulo_original'] as String,
    ano: j['ano'] as int?,
    edicoes: [
      for (final e in j['edicoes'] as List)
        EdicaoResumo.deJson(e as Map<String, dynamic>),
    ],
  );

  final String slug;
  final String sigla;
  final String autor;
  final String tituloOriginal;
  final int? ano;
  final List<EdicaoResumo> edicoes;

  /// Edição para mostrar: a do idioma pedido; senão a do mesmo idioma base ("fr" acha
  /// "fr-FR"); senão a primeira.
  EdicaoResumo edicaoPara(String idioma) {
    String base(String i) => i.split('-').first;
    return edicoes.firstWhere(
      (e) => e.idioma == idioma,
      orElse: () => edicoes.firstWhere(
        (e) => base(e.idioma) == base(idioma),
        orElse: () => edicoes.first,
      ),
    );
  }
}

class CatalogoApi {
  CatalogoApi({http.Client? cliente, String? base})
    : _cliente = cliente ?? http.Client(),
      _base = Uri.parse(base ?? urlApiPadrao);

  final http.Client _cliente;
  final Uri _base;

  Future<List<Obra>> obras() async {
    final dados = await _get('/v1/obras') as List;
    return [for (final o in dados) Obra.deJson(o as Map<String, dynamic>)];
  }

  Future<Edicao> edicao(int id) async =>
      Edicao.deJson(await _get('/v1/edicoes/$id') as Map<String, dynamic>);

  Future<Capitulo> capitulo(int id) async =>
      Capitulo.deJson(await _get('/v1/capitulos/$id') as Map<String, dynamic>);

  /// null quando a edição não tem essa questão publicada.
  Future<Questao?> questao(int edicaoId, int numero) async {
    try {
      final j = await _get('/v1/edicoes/$edicaoId/questoes/$numero');
      return Questao.deJson(j as Map<String, dynamic>);
    } on ErroCatalogo catch (e) {
      if (e.status == 404) return null;
      rethrow;
    }
  }

  Future<ConfigRemota> config() async =>
      ConfigRemota.deJson(await _get('/v1/config') as Map<String, dynamic>);

  Future<Apoio> apoio() async =>
      Apoio.deJson(await _get('/v1/apoio') as Map<String, dynamic>);

  Future<Object?> _get(String caminho) async {
    final http.Response r;
    try {
      r = await _cliente
          .get(_base.resolve(caminho), headers: {'Accept': 'application/json'})
          .timeout(const Duration(seconds: 15));
    } on Exception catch (e) {
      throw ErroCatalogo('$caminho: $e');
    }
    if (r.statusCode != 200) {
      throw ErroCatalogo(
        '$caminho: HTTP ${r.statusCode}',
        status: r.statusCode,
      );
    }
    // A API responde em UTF-8; o http só assume isso se o charset vier no cabeçalho.
    return jsonDecode(utf8.decode(r.bodyBytes));
  }
}

class CapituloResumo {
  CapituloResumo({
    required this.id,
    required this.ordem,
    required this.titulo,
    required this.referencia,
  });

  factory CapituloResumo.deJson(Map<String, dynamic> j) => CapituloResumo(
    id: j['id'] as int,
    ordem: j['ordem'] as int,
    titulo: j['titulo'] as String,
    referencia: j['referencia_canonica'] as String,
  );

  final int id;
  final int ordem;
  final String titulo;

  /// Liga o mesmo capítulo entre idiomas, ex.: "LE-C001".
  final String referencia;
}

class Edicao {
  Edicao({
    required this.id,
    required this.idioma,
    required this.titulo,
    required this.tradutor,
    required this.fonte,
    required this.capitulos,
  });

  factory Edicao.deJson(Map<String, dynamic> j) => Edicao(
    id: j['id'] as int,
    idioma: j['idioma'] as String,
    titulo: j['titulo'] as String,
    tradutor: j['tradutor'] as String?,
    fonte: j['fonte'] as String,
    capitulos: [
      for (final c in j['capitulos'] as List)
        CapituloResumo.deJson(c as Map<String, dynamic>),
    ],
  );

  final int id;
  final String idioma;
  final String titulo;
  final String? tradutor;
  final String fonte;
  final List<CapituloResumo> capitulos;
}

enum TipoSegmento { titulo, pergunta, resposta, comentario, paragrafo, nota }

class Segmento {
  Segmento({
    required this.id,
    required this.ordem,
    required this.tipo,
    required this.texto,
    required this.numeroQuestao,
    required this.subquestao,
  });

  factory Segmento.deJson(Map<String, dynamic> j) => Segmento(
    id: j['id'] as int,
    ordem: j['ordem'] as int,
    // Tipo novo na API, que este app ainda não conhece, é lido como parágrafo.
    tipo: TipoSegmento.values.asNameMap()[j['tipo']] ?? TipoSegmento.paragrafo,
    texto: j['texto'] as String,
    numeroQuestao: j['numero_questao'] as int?,
    subquestao: j['subquestao'] as String?,
  );

  final int id;
  final int ordem;
  final TipoSegmento tipo;
  final String texto;
  final int? numeroQuestao;
  final String? subquestao;
}

/// Onde cada segmento começa e termina na faixa (leitura acompanhada e retomada).
class Marcacao {
  Marcacao({
    required this.segmentoId,
    required this.inicioMs,
    required this.fimMs,
  });

  factory Marcacao.deJson(Map<String, dynamic> j) => Marcacao(
    segmentoId: j['segmento_id'] as int,
    inicioMs: j['inicio_ms'] as int,
    fimMs: j['fim_ms'] as int,
  );

  final int segmentoId;
  final int inicioMs;
  final int fimMs;
}

class Faixa {
  Faixa({
    required this.url,
    required this.versao,
    required this.duracaoMs,
    required this.marcacoes,
    this.formato = 'm4a',
  });

  factory Faixa.deJson(Map<String, dynamic> j) => Faixa(
    url: j['url'] as String,
    versao: j['versao'] as int,
    duracaoMs: j['duracao_ms'] as int,
    marcacoes: [
      for (final m in j['marcacoes'] as List)
        Marcacao.deJson(m as Map<String, dynamic>),
    ],
    formato: j['formato'] as String? ?? 'm4a',
  );

  final String url;

  /// "m4a" (aberto) ou "cent1" (cifrado, #73). Sem o campo, a API é anterior à #73.
  final String formato;

  /// Este app só toca o formato aberto; a decifragem do .cent vem depois.
  bool get tocavel => formato == 'm4a';

  /// Regenerar o áudio cria versão nova, com outros tempos.
  final int versao;
  final int duracaoMs;
  final List<Marcacao> marcacoes;

  /// Segmento tocando em [ms]; null antes do primeiro ou sem marcações.
  int? segmentoEm(int ms) {
    int? atual;
    for (final m in marcacoes) {
      if (m.inicioMs > ms) break;
      atual = m.segmentoId;
    }
    return atual;
  }

  int? inicioDoSegmento(int segmentoId) {
    for (final m in marcacoes) {
      if (m.segmentoId == segmentoId) return m.inicioMs;
    }
    return null;
  }
}

class Capitulo {
  Capitulo({
    required this.resumo,
    required this.edicaoId,
    required this.segmentos,
    this.faixa,
  });

  factory Capitulo.deJson(Map<String, dynamic> j) => Capitulo(
    resumo: CapituloResumo.deJson(j),
    edicaoId: j['edicao_id'] as int,
    segmentos: [
      for (final s in j['segmentos'] as List)
        Segmento.deJson(s as Map<String, dynamic>),
    ],
    faixa: j['faixa'] == null
        ? null
        : Faixa.deJson(j['faixa'] as Map<String, dynamic>),
  );

  final CapituloResumo resumo;
  final int edicaoId;
  final List<Segmento> segmentos;

  /// null enquanto o capítulo não tem áudio.
  final Faixa? faixa;
}

/// Resultado de "questão 88": em que capítulo ela está.
class Questao {
  Questao({required this.numero, required this.capitulo});

  factory Questao.deJson(Map<String, dynamic> j) => Questao(
    numero: j['numero'] as int,
    capitulo: CapituloResumo.deJson(j['capitulo'] as Map<String, dynamic>),
  );

  final int numero;
  final CapituloResumo capitulo;
}

/// Lê "88", "questão 88", "q. 88" ou "88a". Devolve null se não houver número.
({int numero, String? sub})? lerBuscaQuestao(String texto) {
  final m = RegExp(r'(\d{1,4})\s*([a-z])?\b')
      .firstMatch(texto.toLowerCase().trim());
  if (m == null) return null;
  final numero = int.parse(m.group(1)!);
  if (numero < 1) return null;
  return (numero: numero, sub: m.group(2));
}

/// GET /v1/config: o que o app mostra além do catálogo. Tudo desligado por padrão.
class ConfigRemota {
  const ConfigRemota({this.apoio = false, this.caridade = false});

  factory ConfigRemota.deJson(Map<String, dynamic> j) => ConfigRemota(
    apoio: j['apoio'] as bool? ?? false,
    caridade: j['caridade'] as bool? ?? false,
  );

  final bool apoio;
  final bool caridade;
}

/// GET /v1/apoio. Desligado, só `ligado: false`.
class Apoio {
  const Apoio({
    required this.ligado,
    this.recebedor,
    this.mensagem,
    this.valoresCentavos = const [],
    this.chavePix,
    this.linkExterno,
  });

  factory Apoio.deJson(Map<String, dynamic> j) => Apoio(
    ligado: j['ligado'] as bool? ?? false,
    recebedor: j['recebedor'] as String?,
    mensagem: j['mensagem'] as String?,
    valoresCentavos: [
      for (final v in j['valores_centavos'] as List? ?? []) v as int,
    ],
    chavePix: j['chave_pix'] as String?,
    // Só https: o app não abre outro esquema vindo da rede.
    linkExterno: (j['link_externo'] as String?)?.startsWith('https://') == true
        ? j['link_externo'] as String
        : null,
  );

  final bool ligado;
  final String? recebedor;
  final String? mensagem;
  final List<int> valoresCentavos;
  final String? chavePix;
  final String? linkExterno;
}
