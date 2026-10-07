// Android Auto (#43): o que o carro mostra e como toca.
import 'package:audio_service/audio_service.dart';

import '../api/catalogo_api.dart';
import '../l10n/app_localizations.dart';
import '../offline/downloads.dart';
import 'controle_player.dart';

/// A árvore que o Android Auto navega, e o toque num item.
///
/// No carro não se lê nem se busca: só "Continuar ouvindo" e os capítulos baixados, que
/// tocam sem rede (estrada sem sinal é o caso comum). Tocar passa pelo mesmo
/// [ControlePlayer] do app: posição salva, velocidade e chave da faixa cifrada valem
/// igual.
class NavegacaoCarro {
  NavegacaoCarro({
    required this.api,
    required this.player,
    required this.textos,
  });

  final CatalogoApi api;
  final ControlePlayer player;

  /// Textos no idioma atual do app (pode mudar com o app aberto).
  final AppLocalizations Function() textos;

  static const _ultimo = 'ultimo';
  static const _baixados = 'baixados';
  static const _baixado = 'baixado:';

  Future<List<MediaItem>> filhos(String pai) async {
    final t = textos();
    final ultimo = player.armazem.ultimo();
    final itemUltimo = ultimo == null
        ? null
        : MediaItem(
            id: _ultimo,
            title: t.continuarOuvindo,
            artist: ultimo.capitulo.titulo,
            album: ultimo.info.edicao,
            playable: true,
          );
    switch (pai) {
      // Sugestões de retomada do sistema: só o último ouvido.
      case AudioService.recentRootId:
        return [?itemUltimo];
      case AudioService.browsableRootId:
        return [
          ?itemUltimo,
          if (player.downloads != null)
            MediaItem(id: _baixados, title: t.baixados, playable: false),
        ];
      case _baixados:
        final baixados = await player.downloads?.lista() ?? const [];
        return [
          for (final b in baixados)
            MediaItem(
              id: '$_baixado${b.capitulo.resumo.id}',
              title: b.capitulo.resumo.titulo,
              artist: b.info.autor,
              album: b.info.edicao,
              playable: true,
            ),
        ];
    }
    return const [];
  }

  Future<void> tocar(String id) async {
    if (id == _ultimo) {
      final ultimo = player.armazem.ultimo();
      if (ultimo == null) return;
      // Baixado toca sem rede; senão, busca o capítulo na API.
      final baixado = await _baixadoDe(ultimo.capitulo.id);
      final capitulo =
          baixado?.capitulo ?? await api.capitulo(ultimo.capitulo.id);
      await player.abrir(capitulo, ultimo.info);
    } else if (id.startsWith(_baixado)) {
      final b = await _baixadoDe(int.parse(id.substring(_baixado.length)));
      if (b == null) return;
      await player.abrir(b.capitulo, b.info);
    } else {
      return;
    }
    await player.tocar();
  }

  Future<Baixado?> _baixadoDe(int capituloId) async {
    final lista = await player.downloads?.lista() ?? const <Baixado>[];
    return lista.where((b) => b.capitulo.resumo.id == capituloId).firstOrNull;
  }
}
