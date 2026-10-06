import 'dart:convert';

import 'package:centelha/api/catalogo_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

// Mesmo formato de GET /v1/obras (ObraOut na API).
final obrasJson = [
  {
    'slug': 'o-livro-dos-espiritos',
    'sigla': 'LE',
    'autor': 'Allan Kardec',
    'titulo_original': 'Le Livre des Esprits',
    'ano': 1857,
    'edicoes': [
      {
        'id': 1,
        'idioma': 'pt-BR',
        'publico': 'adulto',
        'titulo': 'O Livro dos Espíritos',
        'tradutor': 'Guillon Ribeiro',
        'publicada_em': '2026-10-01T12:00:00Z',
      },
      {
        'id': 2,
        'idioma': 'fr-FR',
        'publico': 'adulto',
        'titulo': 'Le Livre des Esprits',
        'tradutor': null,
        'publicada_em': '2026-10-02T12:00:00Z',
      },
    ],
  },
];

http.Response respostaJson(Object corpo, [int status = 200]) =>
    // Sem charset no cabeçalho, como a API pode responder: o cliente decodifica UTF-8.
    http.Response.bytes(
      utf8.encode(jsonEncode(corpo)),
      status,
      headers: {'content-type': 'application/json'},
    );

void main() {
  test('lê as obras e escolhe a edição pelo idioma', () async {
    late Uri pedida;
    final api = CatalogoApi(
      base: 'https://api.exemplo.org',
      cliente: MockClient((r) async {
        pedida = r.url;
        return respostaJson(obrasJson);
      }),
    );
    final obras = await api.obras();
    expect(pedida.toString(), 'https://api.exemplo.org/v1/obras');
    expect(obras.single.edicaoPara('pt-BR').titulo, 'O Livro dos Espíritos');
    expect(obras.single.edicaoPara('fr-FR').tradutor, isNull);
    // Sem edição no idioma pedido, mostra a primeira.
    expect(obras.single.edicaoPara('en').id, 1);
  });

  test('erro HTTP e falha de rede viram ErroCatalogo', () async {
    final com500 = CatalogoApi(
      cliente: MockClient((_) async => respostaJson({}, 500)),
    );
    await expectLater(com500.obras(), throwsA(isA<ErroCatalogo>()));
    final semRede = CatalogoApi(
      cliente: MockClient((_) async => throw http.ClientException('sem rede')),
    );
    await expectLater(semRede.obras(), throwsA(isA<ErroCatalogo>()));
  });
}
