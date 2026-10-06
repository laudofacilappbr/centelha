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
  ErroCatalogo(this.mensagem);
  final String mensagem;

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
      throw ErroCatalogo('$caminho: HTTP ${r.statusCode}');
    }
    // A API responde em UTF-8; o http só assume isso se o charset vier no cabeçalho.
    return jsonDecode(utf8.decode(r.bodyBytes));
  }
}
