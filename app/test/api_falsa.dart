// API falsa com o formato real das respostas (routers/catalogo.py), por caminho.
import 'package:centelha/api/catalogo_api.dart';
import 'package:http/testing.dart';

import 'catalogo_api_test.dart' show obrasJson, respostaJson;

Map<String, dynamic> _capitulo(int id, int ordem, String titulo) => {
  'id': id,
  'ordem': ordem,
  'titulo': titulo,
  'referencia_canonica': 'LE-C00$ordem',
};

Map<String, dynamic> _segmento(
  int id,
  String tipo,
  String texto, [
  int? questao,
  String? sub,
]) => {
  'id': id,
  'ordem': id,
  'tipo': tipo,
  'texto': texto,
  'numero_questao': questao,
  'subquestao': sub,
};

/// Capítulo com as questões 1 a 120: a 88 fica bem abaixo da primeira tela.
final capituloLongo = {
  ..._capitulo(10, 1, 'Capítulo I — De Deus'),
  'edicao_id': 1,
  'faixa': null,
  'segmentos': [
    _segmento(1, 'titulo', 'De Deus'),
    for (var n = 1; n <= 120; n++) ...[
      _segmento(n * 10, 'pergunta', 'Pergunta de exemplo $n?', n),
      _segmento(n * 10 + 1, 'resposta', '“Resposta de exemplo $n.”', n),
    ],
    _segmento(5000, 'pergunta', 'Subquestão de exemplo?', 88, 'a'),
    _segmento(5001, 'tipo_que_ainda_nao_existe', 'Lido como parágrafo.'),
  ],
};

final _rotas = <String, Object>{
  '/v1/obras': obrasJson,
  '/v1/edicoes/1': {
    'id': 1,
    'idioma': 'pt-BR',
    'publico': 'adulto',
    'titulo': 'O Livro dos Espíritos',
    'tradutor': 'Guillon Ribeiro',
    'publicada_em': '2026-10-01T12:00:00Z',
    'obra_slug': 'o-livro-dos-espiritos',
    'fonte': 'FEB, 1944',
    'capitulos': [
      _capitulo(10, 1, 'Capítulo I — De Deus'),
      _capitulo(11, 2, 'Capítulo II — Dos elementos gerais'),
    ],
  },
  '/v1/edicoes/2': {
    'id': 2,
    'idioma': 'fr-FR',
    'publico': 'adulto',
    'titulo': 'Le Livre des Esprits',
    'tradutor': null,
    'publicada_em': '2026-10-02T12:00:00Z',
    'obra_slug': 'o-livro-dos-espiritos',
    'fonte': 'Didier, 1860',
    'capitulos': [_capitulo(20, 1, 'Chapitre premier — Dieu')],
  },
  '/v1/capitulos/10': capituloLongo,
  '/v1/edicoes/1/questoes/88': {
    'edicao_id': 1,
    'numero': 88,
    'referencia': 'LE-88',
    'capitulo': _capitulo(10, 1, 'Capítulo I — De Deus'),
    'segmentos': <Object>[],
  },
};

/// Caminhos pedidos, na ordem, para conferir o que o app buscou.
CatalogoApi apiFalsa({List<String>? pedidos, Set<String> falham = const {}}) =>
    CatalogoApi(
      cliente: MockClient((r) async {
        pedidos?.add(r.url.path);
        if (falham.contains(r.url.path)) return respostaJson({}, 500);
        final corpo = _rotas[r.url.path];
        return corpo == null
            ? respostaJson({'detail': 'não encontrado'}, 404)
            : respostaJson(corpo);
      }),
    );
