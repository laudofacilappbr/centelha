import 'package:flutter/material.dart';

import '../api/catalogo_api.dart';
import '../idioma/preferencia_idioma.dart';
import '../l10n/app_localizations.dart';
import 'capitulo.dart';
import 'comum.dart';
import 'compartilhar.dart';
import 'trocar_edicao.dart';

/// Uma obra: escolha da edição, busca por questão e lista de capítulos.
class TelaObra extends StatefulWidget {
  const TelaObra({
    super.key,
    required this.api,
    required this.obra,
    required this.edicaoInicial,
  });

  final CatalogoApi api;
  final Obra obra;
  final EdicaoResumo edicaoInicial;

  @override
  State<TelaObra> createState() => _TelaObraState();
}

class _TelaObraState extends State<TelaObra> {
  late EdicaoResumo _edicao = widget.edicaoInicial;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(_edicao.titulo)),
      body: Carregavel<Edicao>(
        // Trocar de edição recarrega; a chave descarta o Future da anterior.
        key: ValueKey(_edicao.id),
        carregar: () => widget.api.edicao(_edicao.id),
        construir: (context, edicao) {
          final citacao = Citacao.daEdicao(widget.obra, _edicao);
          final origem = OrigemCapitulo(obra: widget.obra, edicao: _edicao);
          return ListView(
            padding: const EdgeInsets.symmetric(vertical: 8),
            children: [
              _Creditos(obra: widget.obra, edicao: edicao),
              if (widget.obra.edicoes.length > 1)
                _EscolhaEdicao(
                  edicoes: widget.obra.edicoes,
                  atual: _edicao,
                  escolher: (e) => setState(() => _edicao = e),
                ),
              _BuscaQuestao(
                api: widget.api,
                edicaoId: edicao.id,
                edicao: edicao.titulo,
                autor: widget.obra.autor,
                citacao: citacao,
                origem: origem,
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
                child: Text(
                  t.capitulos,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              for (final c in edicao.capitulos)
                ListTile(
                  title: Text(c.titulo),
                  subtitle: c.temAudio ? null : Text(t.capituloSoTexto),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => abrirCapitulo(
                    context,
                    widget.api,
                    c,
                    edicao: edicao.titulo,
                    autor: widget.obra.autor,
                    citacao: citacao,
                    origem: origem,
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

void abrirCapitulo(
  BuildContext context,
  CatalogoApi api,
  CapituloResumo capitulo, {
  required String edicao,
  required String autor,
  int? questao,
  String? subquestao,
  Citacao? citacao,
  OrigemCapitulo? origem,
}) {
  Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => TelaCapitulo(
        api: api,
        resumo: capitulo,
        edicao: edicao,
        autor: autor,
        questao: questao,
        subquestao: subquestao,
        citacao: citacao,
        origem: origem,
      ),
    ),
  );
}

class _Creditos extends StatelessWidget {
  const _Creditos({required this.obra, required this.edicao});

  final Obra obra;
  final Edicao edicao;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final estilo = Theme.of(context).textTheme.bodySmall;
    // Autor, tradutor e fonte de cada edição sempre visíveis (especificação).
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            [obra.autor, if (obra.ano != null) '${obra.ano}'].join(' · '),
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          if (edicao.tradutor != null)
            Text(t.traducao(edicao.tradutor!), style: estilo),
          Text(t.fonte(edicao.fonte), style: estilo),
        ],
      ),
    );
  }
}

class _EscolhaEdicao extends StatelessWidget {
  const _EscolhaEdicao({
    required this.edicoes,
    required this.atual,
    required this.escolher,
  });

  final List<EdicaoResumo> edicoes;
  final EdicaoResumo atual;
  final ValueChanged<EdicaoResumo> escolher;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Semantics(
        label: t.outraEdicao,
        child: Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final e in edicoes)
              ChoiceChip(
                label: Text(nomeDoIdioma(e.idioma)),
                tooltip: e.titulo,
                selected: e.id == atual.id,
                onSelected: (_) => escolher(e),
              ),
          ],
        ),
      ),
    );
  }
}

class _BuscaQuestao extends StatefulWidget {
  const _BuscaQuestao({
    required this.api,
    required this.edicaoId,
    required this.edicao,
    required this.autor,
    this.citacao,
    this.origem,
  });

  final CatalogoApi api;
  final int edicaoId;
  final String edicao;
  final String autor;
  final Citacao? citacao;
  final OrigemCapitulo? origem;

  @override
  State<_BuscaQuestao> createState() => _BuscaQuestaoState();
}

class _BuscaQuestaoState extends State<_BuscaQuestao> {
  final _controle = TextEditingController();
  bool _buscando = false;

  @override
  void dispose() {
    _controle.dispose();
    super.dispose();
  }

  Future<void> _buscar() async {
    final t = AppLocalizations.of(context);
    final mensagens = ScaffoldMessenger.of(context);
    // Troca o aviso anterior em vez de enfileirar: cada busca responde na hora.
    void avisar(String texto) => mensagens
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(texto)));

    final busca = lerBuscaQuestao(_controle.text);
    if (busca == null) return avisar(t.numeroInvalido);
    setState(() => _buscando = true);
    try {
      final questao = await widget.api.questao(widget.edicaoId, busca.numero);
      if (!mounted) return;
      if (questao == null) return avisar(t.questaoNaoEncontrada(busca.numero));
      abrirCapitulo(
        context,
        widget.api,
        questao.capitulo,
        edicao: widget.edicao,
        autor: widget.autor,
        questao: busca.numero,
        subquestao: busca.sub,
        citacao: widget.citacao,
        origem: widget.origem,
      );
    } on ErroCatalogo {
      avisar(t.erroCarregar);
    } finally {
      if (mounted) setState(() => _buscando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      child: TextField(
        controller: _controle,
        // Texto, não só número: aceita "88a" e "questão 88".
        keyboardType: TextInputType.text,
        textInputAction: TextInputAction.search,
        onSubmitted: (_) => _buscar(),
        decoration: InputDecoration(
          labelText: t.buscaQuestao,
          hintText: t.buscaQuestaoDica,
          border: const OutlineInputBorder(),
          suffixIcon: IconButton(
            tooltip: t.buscaQuestao,
            onPressed: _buscando ? null : _buscar,
            icon: _buscando
                ? const SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.search),
          ),
        ),
      ),
    );
  }
}
