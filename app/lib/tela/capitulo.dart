import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart' show ScrollDirection;

import '../api/catalogo_api.dart';
import '../l10n/app_localizations.dart';
import '../player/barra_player.dart';
import '../player/controle_player.dart';
import '../player/reprodutor.dart';
import '../tema/centelha_tema.dart';
import 'comum.dart';

/// Texto do capítulo por segmento. Com [questao], rola até ela e a destaca.
class TelaCapitulo extends StatelessWidget {
  const TelaCapitulo({
    super.key,
    required this.api,
    required this.resumo,
    required this.edicao,
    required this.autor,
    this.questao,
    this.subquestao,
  });

  final CatalogoApi api;
  final CapituloResumo resumo;

  /// Para a tela de bloqueio: título da edição e autor.
  final String edicao;
  final String autor;
  final int? questao;
  final String? subquestao;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(resumo.titulo)),
      body: Carregavel<Capitulo>(
        carregar: () => api.capitulo(resumo.id),
        construir: (context, capitulo) => Column(
          children: [
            Expanded(
              child: TextoCapitulo(
                segmentos: capitulo.segmentos,
                questao: questao,
                subquestao: subquestao,
                capitulo: capitulo,
              ),
            ),
            if (capitulo.faixa != null)
              BarraPlayer(
                capitulo: capitulo,
                info: InfoFaixa(
                  titulo: resumo.titulo,
                  edicao: edicao,
                  autor: autor,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Leitura acompanhada (#32): com o [capitulo] tocando no player, destaca o segmento
/// que está sendo lido, rola até ele e leva o áudio ao segmento tocado na tela.
class TextoCapitulo extends StatefulWidget {
  const TextoCapitulo({
    super.key,
    required this.segmentos,
    this.questao,
    this.subquestao,
    this.capitulo,
  });

  final List<Segmento> segmentos;
  final int? questao;
  final String? subquestao;
  final Capitulo? capitulo;

  @override
  State<TextoCapitulo> createState() => _TextoCapituloState();
}

class _TextoCapituloState extends State<TextoCapitulo> {
  final _chaves = <int, GlobalKey>{};
  ControlePlayer? _player;
  int? _lendo;
  bool _carregado = false;

  /// Rolar sozinho atrás da leitura. Desliga quando a pessoa rola com o dedo, para não
  /// tomar a tela de quem quer reler um trecho; o botão "Acompanhar a leitura" religa.
  bool _seguir = true;

  GlobalKey _chave(int segmentoId) =>
      _chaves.putIfAbsent(segmentoId, GlobalKey.new);

  @override
  void initState() {
    super.initState();
    if (widget.questao != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final primeiro = widget.segmentos.where(_daBusca).firstOrNull;
        if (primeiro != null) _rolarAte(primeiro.id, alinhamento: 0.1);
      });
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Sem dependência do EscopoPlayer: ele avisa a cada tique de posição, e o texto
    // só precisa ser refeito quando o segmento lido muda.
    final player = context
        .getInheritedWidgetOfExactType<EscopoPlayer>()
        ?.notifier;
    if (player != _player) {
      _player?.removeListener(_aoMudarPlayer);
      _player = player?..addListener(_aoMudarPlayer);
      _lendo = _segmentoLido();
      _carregado = _tocandoEste;
    }
  }

  @override
  void dispose() {
    _player?.removeListener(_aoMudarPlayer);
    super.dispose();
  }

  bool get _tocandoEste {
    final c = widget.capitulo;
    return c != null && (_player?.carregado(c.resumo.id) ?? false);
  }

  int? _segmentoLido() => _tocandoEste ? _player!.segmentoAtual : null;

  void _aoMudarPlayer() {
    final lido = _segmentoLido();
    final carregado = _tocandoEste;
    if (lido == _lendo && carregado == _carregado) return;
    // Carregar o capítulo no player liga o toque nos trechos, mesmo antes da primeira
    // marcação (posição 0, nenhum trecho lido ainda).
    setState(() {
      _lendo = lido;
      _carregado = carregado;
    });
    if (lido != null && _seguir && _player!.tocando) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _rolarAte(lido));
    }
  }

  void _rolarAte(int segmentoId, {double alinhamento = 0.3}) {
    final alvo = _chaves[segmentoId]?.currentContext;
    if (alvo == null || !mounted) return;
    Scrollable.ensureVisible(
      alvo,
      alignment: alinhamento,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOut,
    );
  }

  void _voltarALeitura() {
    setState(() => _seguir = true);
    final lido = _lendo;
    if (lido != null) _rolarAte(lido);
  }

  /// Leva o áudio ao começo do segmento; null quando ele não tem marcação.
  VoidCallback? _ouvirDaqui(Segmento s) {
    final inicio = _tocandoEste
        ? widget.capitulo!.faixa?.inicioDoSegmento(s.id)
        : null;
    if (inicio == null) return null;
    return () {
      setState(() => _seguir = true);
      _player!.irPara(Duration(milliseconds: inicio));
    };
  }

  // Subquestão pedida que não existe: destaca a questão inteira.
  late final bool _temSub =
      widget.subquestao != null &&
      widget.segmentos.any(
        (x) =>
            x.numeroQuestao == widget.questao &&
            x.subquestao == widget.subquestao,
      );

  bool _daBusca(Segmento s) =>
      widget.questao != null &&
      s.numeroQuestao == widget.questao &&
      (!_temSub || s.subquestao == widget.subquestao);

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final mostrarVoltar = !_seguir && _lendo != null;

    // Coluna e não lista preguiçosa: o alvo da busca e o segmento lido precisam existir
    // para rolar até eles, e um capítulo tem no máximo algumas centenas de segmentos.
    return Stack(
      children: [
        NotificationListener<UserScrollNotification>(
          onNotification: (n) {
            if (_seguir &&
                _lendo != null &&
                n.direction != ScrollDirection.idle) {
              setState(() => _seguir = false);
            }
            return false;
          },
          child: SingleChildScrollView(
            padding: EdgeInsets.fromLTRB(16, 8, 16, mostrarVoltar ? 88 : 32),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final s in widget.segmentos)
                  _Segmento(
                    key: _chave(s.id),
                    segmento: s,
                    destacado: _daBusca(s),
                    lendo: s.id == _lendo,
                    ouvirDaqui: _ouvirDaqui(s),
                  ),
              ],
            ),
          ),
        ),
        if (mostrarVoltar)
          Positioned(
            left: 0,
            right: 0,
            bottom: 16,
            child: Center(
              child: FilledButton.tonalIcon(
                onPressed: _voltarALeitura,
                icon: const Icon(Icons.my_location),
                label: Text(t.acompanharLeitura),
              ),
            ),
          ),
      ],
    );
  }
}

class _Segmento extends StatelessWidget {
  const _Segmento({
    super.key,
    required this.segmento,
    required this.destacado,
    this.lendo = false,
    this.ouvirDaqui,
  });

  final Segmento segmento;

  /// Resultado da busca por questão.
  final bool destacado;

  /// Trecho que a narração está lendo agora.
  final bool lendo;
  final VoidCallback? ouvirDaqui;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final tema = Theme.of(context);
    final texto = tema.textTheme;
    final s = segmento;

    final Widget conteudo = switch (s.tipo) {
      TipoSegmento.titulo => Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Semantics(
          header: true,
          child: Text(s.texto, style: texto.headlineSmall),
        ),
      ),
      TipoSegmento.pergunta => Semantics(
        label: s.numeroQuestao != null
            ? t.questao(s.numeroQuestao!)
            : t.pergunta,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (s.numeroQuestao != null)
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: Text(
                  '${s.numeroQuestao}${s.subquestao ?? ''}.',
                  style: texto.titleMedium?.copyWith(
                    color: tema.colorScheme.primary,
                  ),
                ),
              ),
            Expanded(child: Text(s.texto, style: texto.titleMedium)),
          ],
        ),
      ),
      TipoSegmento.resposta => Semantics(
        label: t.resposta,
        child: Container(
          padding: const EdgeInsets.only(left: 12),
          decoration: BoxDecoration(
            border: Border(
              left: BorderSide(color: tema.colorScheme.primary, width: 3),
            ),
          ),
          child: Text(s.texto, style: texto.bodyLarge),
        ),
      ),
      TipoSegmento.nota => Text(s.texto, style: texto.bodySmall),
      TipoSegmento.comentario ||
      TipoSegmento.paragrafo => Text(s.texto, style: texto.bodyLarge),
    };

    // Mesmo recuo com ou sem destaque: o trecho lido muda a cada poucos segundos, e
    // recuo variável faria o texto pular enquanto a pessoa lê.
    final raio = BorderRadius.circular(Raios.sm);
    final caixa = AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      margin: const EdgeInsets.only(top: 4),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: lendo
            ? tema.colorScheme.primary.withValues(alpha: 0.16)
            : destacado
            ? tema.colorScheme.surfaceContainerHighest
            : Colors.transparent,
        borderRadius: raio,
      ),
      child: conteudo,
    );
    return Semantics(
      selected: lendo,
      hint: lendo ? t.lendoAgora : null,
      onTapHint: ouvirDaqui == null ? null : t.ouvirDaqui,
      child: ouvirDaqui == null
          ? caixa
          : InkWell(onTap: ouvirDaqui, borderRadius: raio, child: caixa),
    );
  }
}
