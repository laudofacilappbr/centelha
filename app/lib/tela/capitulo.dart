import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart' show ScrollDirection;

import '../api/catalogo_api.dart';
import '../l10n/app_localizations.dart';
import '../player/barra_player.dart';
import '../player/controle_player.dart';
import '../player/reprodutor.dart';
import '../tema/centelha_tema.dart';
import 'comum.dart';
import 'compartilhar.dart';
import 'conta.dart';
import 'trocar_edicao.dart';

/// Texto do capítulo por segmento. Com [questao], rola até ela e a destaca.
class TelaCapitulo extends StatefulWidget {
  const TelaCapitulo({
    super.key,
    required this.api,
    required this.resumo,
    required this.edicao,
    required this.autor,
    this.questao,
    this.subquestao,
    this.citacao,
    this.origem,
    this.pronto,
  });

  final CatalogoApi api;
  final CapituloResumo resumo;

  /// Para a tela de bloqueio: título da edição e autor.
  final String edicao;
  final String autor;
  final int? questao;
  final String? subquestao;

  /// Sem citação (edição juvenil ou infantil, ou origem desconhecida), não há
  /// compartilhar.
  final Citacao? citacao;

  /// Capítulo já em mãos (o baixado): abre sem pedir à API, sem internet.
  final Capitulo? pronto;

  /// Obra e edição de onde o capítulo veio. Sem ela (o "continuar ouvindo" da tela
  /// inicial não sabe), não há troca de idioma.
  final OrigemCapitulo? origem;

  @override
  State<TelaCapitulo> createState() => _TelaCapituloState();
}

class _TelaCapituloState extends State<TelaCapitulo> {
  final _posicao = PosicaoNoTexto();

  /// Troca de idioma (#47): abre a outra edição na mesma questão, ou no capítulo de
  /// mesma referência canônica, no lugar desta tela.
  Future<void> _trocarEdicao(OrigemCapitulo origem) async {
    final t = AppLocalizations.of(context);
    final mensagens = ScaffoldMessenger.of(context);
    final navegador = Navigator.of(context);
    void avisar(String texto) => mensagens
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(texto)));

    final escolhida = await escolherOutraEdicao(context, origem);
    if (escolhida == null || !mounted) return;
    final aVista = _posicao.questao;
    final Destino? destino;
    try {
      destino = await mesmaPosicao(
        widget.api,
        escolhida,
        capitulo: widget.resumo,
        questao: aVista?.numero,
        subquestao: aVista?.sub,
      );
    } on ErroCatalogo {
      return avisar(t.erroCarregar);
    }
    if (!mounted) return;
    if (destino == null) {
      return avisar(t.posicaoNaoEncontrada(escolhida.titulo));
    }
    final obra = origem.obra;
    navegador.pushReplacement(
      MaterialPageRoute<void>(
        builder: (_) => TelaCapitulo(
          api: widget.api,
          resumo: destino!.capitulo,
          edicao: escolhida.titulo,
          autor: obra.autor,
          questao: destino.questao,
          subquestao: destino.subquestao,
          citacao: Citacao.daEdicao(obra, escolhida),
          origem: OrigemCapitulo(obra: obra, edicao: escolhida),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final origem = widget.origem;
    final citacao = widget.citacao;
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.resumo.titulo),
        actions: [
          if (origem != null && origem.outras.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.translate),
              tooltip: t.lerEmOutroIdioma,
              onPressed: () => _trocarEdicao(origem),
            ),
          BotaoFormatoAberto(
            capituloId: widget.resumo.id,
            edicaoId: () async =>
                (widget.pronto ?? await widget.api.capitulo(widget.resumo.id))
                    .edicaoId,
          ),
        ],
      ),
      body: Carregavel<Capitulo>(
        carregar: () async =>
            widget.pronto ?? await widget.api.capitulo(widget.resumo.id),
        construir: (context, capitulo) => Column(
          children: [
            Expanded(
              child: TextoCapitulo(
                segmentos: capitulo.segmentos,
                questao: widget.questao,
                subquestao: widget.subquestao,
                capitulo: capitulo,
                posicao: _posicao,
                compartilhar: citacao == null
                    ? null
                    : (contexto, trecho) => oferecerCompartilhar(
                        contexto,
                        citacao: citacao,
                        capitulo: widget.resumo,
                        trecho: trecho,
                      ),
              ),
            ),
            if (capitulo.faixa != null)
              BarraPlayer(
                capitulo: capitulo,
                info: InfoFaixa(
                  titulo: widget.resumo.titulo,
                  edicao: widget.edicao,
                  autor: widget.autor,
                ),
              )
            else
              const AvisoSemNarracao(),
          ],
        ),
      ),
    );
  }
}

/// Pergunta ao texto qual questão está à vista, na hora da troca de idioma: a que a
/// narração está lendo ou, sem ela, a primeira que aparece na tela.
class PosicaoNoTexto {
  ({int numero, String? sub})? Function()? _ler;

  ({int numero, String? sub})? get questao => _ler?.call();
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
    this.compartilhar,
    this.posicao,
  });

  final List<Segmento> segmentos;
  final PosicaoNoTexto? posicao;
  final int? questao;
  final String? subquestao;
  final Capitulo? capitulo;

  /// Toque longo num trecho; null desliga.
  final void Function(BuildContext contexto, List<Segmento> trecho)?
  compartilhar;

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
    widget.posicao?._ler = _questaoAVista;
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

  ({int numero, String? sub})? _questaoAVista() {
    final lido = widget.segmentos.where((s) => s.id == _lendo).firstOrNull;
    if (lido?.numeroQuestao != null) {
      return (numero: lido!.numeroQuestao!, sub: lido.subquestao);
    }
    // A questão que cruza uma linha a um quarto da altura do texto. Pelo topo, o fim da
    // questão anterior, que a busca deixa à mostra acima da procurada (alinhamento
    // 0.1), ganharia; a um quarto, fica a que a pessoa está lendo.
    final caixa = context.findRenderObject() as RenderBox?;
    if (caixa == null || !caixa.attached) return null;
    final topo = caixa.localToGlobal(Offset.zero).dy + caixa.size.height / 4;
    for (final s in widget.segmentos) {
      if (s.numeroQuestao == null) continue;
      final r = _chaves[s.id]?.currentContext?.findRenderObject() as RenderBox?;
      if (r == null || !r.attached) continue;
      if (r.localToGlobal(Offset(0, r.size.height)).dy > topo) {
        return (numero: s.numeroQuestao!, sub: s.subquestao);
      }
    }
    return null;
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
                    compartilhar:
                        widget.compartilhar == null ||
                            s.tipo == TipoSegmento.titulo
                        ? null
                        : (contexto) => widget.compartilhar!(
                            contexto,
                            trechoDe(s, widget.segmentos),
                          ),
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
    this.compartilhar,
  });

  final Segmento segmento;

  /// Resultado da busca por questão.
  final bool destacado;

  /// Trecho que a narração está lendo agora.
  final bool lendo;
  final VoidCallback? ouvirDaqui;
  final void Function(BuildContext contexto)? compartilhar;

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
      onLongPressHint: compartilhar == null ? null : t.segurarParaCompartilhar,
      child: ouvirDaqui == null && compartilhar == null
          ? caixa
          : Builder(
              // Contexto do próprio trecho: a folha do iPad sai dele.
              builder: (contexto) => InkWell(
                onTap: ouvirDaqui,
                onLongPress: compartilhar == null
                    ? null
                    : () => compartilhar!(contexto),
                borderRadius: raio,
                child: caixa,
              ),
            ),
    );
  }
}

/// No lugar do player, quando o capítulo está publicado só com texto (#167): sem ele,
/// quem procura o play acha que o áudio quebrou.
class AvisoSemNarracao extends StatelessWidget {
  const AvisoSemNarracao({super.key});

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    return Material(
      color: esquema.surfaceContainerHigh,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            children: [
              Icon(Icons.menu_book_outlined, color: esquema.onSurfaceVariant),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  AppLocalizations.of(context).semNarracao,
                  style: TextStyle(color: esquema.onSurfaceVariant),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
