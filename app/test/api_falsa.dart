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
  'faixa': {
    'url': 'https://audio.exemplo.org/le/pt-BR/e1/le-c001-v2.m4a',
    'versao': 2,
    'duracao_ms': 2500000,
    // A pergunta n começa em n * 20 s; a resposta, 10 s depois.
    'marcacoes': [
      for (var n = 1; n <= 120; n++) ...[
        {
          'segmento_id': n * 10,
          'inicio_ms': n * 20000,
          'fim_ms': n * 20000 + 9000,
        },
        {
          'segmento_id': n * 10 + 1,
          'inicio_ms': n * 20000 + 10000,
          'fim_ms': n * 20000 + 19000,
        },
      ],
    ],
  },
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
  '/v1/planos': [
    {
      'slug': 'teste',
      'titulo': 'Plano de teste',
      'descricao': 'Três dias para o teste.',
      'dias': 3,
    },
  ],
  '/v1/planos/teste': {
    'slug': 'teste',
    'titulo': 'Plano de teste',
    'descricao': 'Três dias para o teste.',
    'dias': [
      {
        'dia': 1,
        'titulo': 'A questão 88',
        'leituras': [
          {'sigla': 'LE', 'capitulo': null, 'de': 88, 'ate': 90},
        ],
      },
      {
        'dia': 2,
        'titulo': 'O capítulo II',
        'leituras': [
          {'sigla': 'LE', 'capitulo': 'LE-C002', 'de': null, 'ate': null},
        ],
      },
      {
        'dia': 3,
        'titulo': 'Uma obra que o catálogo não tem',
        'leituras': [
          {'sigla': 'ESE', 'capitulo': 'ESE-C003', 'de': null, 'ate': null},
        ],
      },
    ],
  },
  '/v1/capitulos/20': {
    ..._capitulo(20, 1, 'Chapitre premier — Dieu'),
    'edicao_id': 2,
    'faixa': null,
    'segmentos': [
      _segmento(21, 'titulo', 'Dieu'),
      _segmento(22, 'paragrafo', 'Paragraphe d’exemple sur Dieu.'),
    ],
  },
  '/v1/edicoes/1/questoes/88': {
    'edicao_id': 1,
    'numero': 88,
    'referencia': 'LE-88',
    'capitulo': _capitulo(10, 1, 'Capítulo I — De Deus'),
    'segmentos': <Object>[],
  },
  // A questão 88 existe na edição francesa; a 1, não (cai no capítulo de mesma
  // referência).
  '/v1/edicoes/2/questoes/88': {
    'edicao_id': 2,
    'numero': 88,
    'referencia': 'LE-88',
    'capitulo': _capitulo(20, 1, 'Chapitre premier — Dieu'),
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
