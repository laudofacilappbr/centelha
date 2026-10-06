import 'package:flutter/material.dart';

import '../api/catalogo_api.dart';
import '../l10n/app_localizations.dart';
import '../player/barra_player.dart';
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

class TextoCapitulo extends StatefulWidget {
  const TextoCapitulo({
    super.key,
    required this.segmentos,
    this.questao,
    this.subquestao,
  });

  final List<Segmento> segmentos;
  final int? questao;
  final String? subquestao;

  @override
  State<TextoCapitulo> createState() => _TextoCapituloState();
}

class _TextoCapituloState extends State<TextoCapitulo> {
  final _alvo = GlobalKey();

  @override
  void initState() {
    super.initState();
    if (widget.questao != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final alvo = _alvo.currentContext;
        if (alvo != null) {
          Scrollable.ensureVisible(alvo, alignment: 0.1);
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    // Subquestão pedida que não existe: destaca a questão inteira.
    final temSub =
        widget.subquestao != null &&
        widget.segmentos.any(
          (s) =>
              s.numeroQuestao == widget.questao &&
              s.subquestao == widget.subquestao,
        );
    bool destacado(Segmento s) =>
        widget.questao != null &&
        s.numeroQuestao == widget.questao &&
        (!temSub || s.subquestao == widget.subquestao);
    final primeiro = widget.segmentos.indexWhere(destacado);

    // Coluna e não lista preguiçosa: o alvo da busca precisa existir para rolar até
    // ele, e um capítulo tem no máximo algumas centenas de segmentos.
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final (i, s) in widget.segmentos.indexed)
            _Segmento(
              key: i == primeiro ? _alvo : null,
              segmento: s,
              destacado: destacado(s),
            ),
        ],
      ),
    );
  }
}

class _Segmento extends StatelessWidget {
  const _Segmento({super.key, required this.segmento, required this.destacado});

  final Segmento segmento;
  final bool destacado;

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

    return Container(
      margin: const EdgeInsets.only(top: 12),
      padding: destacado ? const EdgeInsets.all(8) : EdgeInsets.zero,
      decoration: destacado
          ? BoxDecoration(
              color: tema.colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(Raios.sm),
            )
          : null,
      child: conteudo,
    );
  }
}
