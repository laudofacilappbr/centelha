import 'package:audio_service/audio_service.dart';
import 'package:centelha/api/catalogo_api.dart';
import 'package:centelha/l10n/app_localizations.dart';
import 'package:centelha/player/carro.dart';
import 'package:centelha/player/progresso.dart';
import 'package:centelha/player/reprodutor.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_falsa.dart';
import 'reprodutor_falso.dart';

void main() {
  late List<String> pedidos;

  Future<(NavegacaoCarro, ReprodutorFalso)> montar() async {
    final (player, motor) = await playerFalso();
    pedidos = [];
    return (
      NavegacaoCarro(
        api: apiFalsa(pedidos: pedidos),
        player: player,
        textos: () => lookupAppLocalizations(const Locale('pt')),
      ),
      motor,
    );
  }

  test('sem nada ouvido e sem downloads, o carro fica vazio', () async {
    SharedPreferences.setMockInitialValues({});
    final (carro, _) = await montar();
    expect(await carro.filhos(AudioService.browsableRootId), isEmpty);
    expect(await carro.filhos(AudioService.recentRootId), isEmpty);
  });

  test('continuar ouvindo busca o capítulo na API e toca', () async {
    SharedPreferences.setMockInitialValues({});
    await ArmazemProgresso(await SharedPreferences.getInstance()).salvarUltimo(
      UltimoOuvido(
        capitulo: CapituloResumo(
          id: 10,
          ordem: 1,
          titulo: 'Capítulo I — De Deus',
          referencia: 'LE-C001',
        ),
        info: const InfoFaixa(
          titulo: 'Capítulo I — De Deus',
          edicao: 'O Livro dos Espíritos',
          autor: 'Allan Kardec',
        ),
      ),
    );
    final (carro, motor) = await montar();
    final raiz = await carro.filhos(AudioService.browsableRootId);
    expect(raiz.single.title, 'Continuar ouvindo');
    expect(raiz.single.album, 'O Livro dos Espíritos');

    await carro.tocar('ultimo');
    expect(pedidos, ['/v1/capitulos/10']);
    expect(motor.faixa?.url, endsWith('le-c001-v2.m4a'));
    expect(motor.estaTocando, isTrue);

    // Pedir de novo não pausa: "tocar" no carro não é alternar.
    await carro.tocar('ultimo');
    expect(motor.estaTocando, isTrue);
  });

  test('item desconhecido não faz nada', () async {
    SharedPreferences.setMockInitialValues({});
    final (carro, motor) = await montar();
    await carro.tocar('qualquer');
    expect(motor.chamadas, isEmpty);
  });
}
