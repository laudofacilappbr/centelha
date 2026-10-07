import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/catalogo_api.dart';
import '../idioma/preferencia_idioma.dart';
import '../l10n/app_localizations.dart';
import 'comum.dart';
import 'compartilhar.dart';
import 'obra.dart';
import 'trocar_edicao.dart';

/// Planos de estudo (#43): a lista dos planos que a API serve.
class TelaPlanos extends StatelessWidget {
  const TelaPlanos({super.key, required this.api, required this.obras});

  final CatalogoApi api;

  /// As obras do catálogo, para abrir a leitura do dia na edição de quem lê.
  final List<Obra> obras;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(t.planosDeEstudo)),
      body: Carregavel<List<PlanoResumo>>(
        carregar: api.planos,
        construir: (context, planos) => ListView(
          padding: const EdgeInsets.symmetric(vertical: 8),
          children: [
            for (final p in planos)
              ListTile(
                title: Text(p.titulo),
                subtitle: Text('${p.descricao}\n${t.planoDias(p.dias)}'),
                isThreeLine: true,
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) =>
                        TelaPlano(api: api, slug: p.slug, obras: obras),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Dias de um plano, com o que já foi lido. O progresso fica só no aparelho: sem conta
/// (a sincronização vem com a conta opcional da #43).
class TelaPlano extends StatefulWidget {
  const TelaPlano({
    super.key,
    required this.api,
    required this.slug,
    required this.obras,
  });

  final CatalogoApi api;
  final String slug;
  final List<Obra> obras;

  @override
  State<TelaPlano> createState() => _TelaPlanoState();
}

class _TelaPlanoState extends State<TelaPlano> {
  Set<int> _lidos = {};

  String get _chave => 'plano.${widget.slug}.lidos';

  @override
  void initState() {
    super.initState();
    SharedPreferences.getInstance().then((prefs) {
      final salvos = prefs.getStringList(_chave) ?? const [];
      if (mounted) setState(() => _lidos = {...salvos.map(int.parse)});
    });
  }

  Future<void> _marcar(int dia, bool lido) async {
    setState(() => lido ? _lidos.add(dia) : _lidos.remove(dia));
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_chave, [for (final d in _lidos) '$d']);
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Carregavel<Plano>(
      carregar: () => widget.api.plano(widget.slug),
      construir: (context, plano) => Scaffold(
        appBar: AppBar(title: Text(plano.titulo)),
        body: ListView(
          padding: const EdgeInsets.symmetric(vertical: 8),
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
              child: Text(
                t.planoProgresso(
                  _lidos.where((d) => d <= plano.dias.length).length,
                  plano.dias.length,
                ),
                style: Theme.of(context).textTheme.titleSmall,
              ),
            ),
            for (final dia in plano.dias)
              CheckboxListTile(
                value: _lidos.contains(dia.dia),
                onChanged: (v) => _marcar(dia.dia, v ?? false),
                controlAffinity: ListTileControlAffinity.leading,
                title: Text(t.planoDia(dia.dia)),
                subtitle: Text(dia.titulo),
                secondary: IconButton(
                  icon: const Icon(Icons.menu_book_outlined),
                  tooltip: t.planoLer,
                  onPressed: () => abrirLeituras(
                    context,
                    widget.api,
                    widget.obras,
                    dia.leituras,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Abre a primeira leitura do dia; com mais de uma, pergunta qual.
Future<void> abrirLeituras(
  BuildContext context,
  CatalogoApi api,
  List<Obra> obras,
  List<Leitura> leituras,
) async {
  var escolhida = leituras.first;
  if (leituras.length > 1) {
    final r = await showModalBottomSheet<Leitura>(
      context: context,
      showDragHandle: true,
      builder: (folha) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final l in leituras)
              ListTile(
                leading: const Icon(Icons.menu_book_outlined),
                title: Text(_descricao(AppLocalizations.of(folha), l)),
                onTap: () => Navigator.of(folha).pop(l),
              ),
          ],
        ),
      ),
    );
    if (r == null) return;
    escolhida = r;
  }
  if (!context.mounted) return;
  await abrirLeitura(context, api, obras, escolhida);
}

String _descricao(AppLocalizations t, Leitura l) => l.de != null
    ? '${l.sigla} ${t.questoesDeAte(l.de!, l.ate!)}'
    : '${l.sigla} ${l.capitulo}';

/// Resolve a referência canônica na edição do idioma de quem lê e abre o capítulo.
Future<void> abrirLeitura(
  BuildContext context,
  CatalogoApi api,
  List<Obra> obras,
  Leitura leitura,
) async {
  final t = AppLocalizations.of(context);
  final mensagens = ScaffoldMessenger.of(context);
  void avisar(String texto) => mensagens
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(texto)));

  final obra = obras.where((o) => o.sigla == leitura.sigla).firstOrNull;
  if (obra == null) return avisar(t.leituraIndisponivel);
  final edicao = obra.edicaoPara(
    idiomaDoConteudo(Localizations.localeOf(context)),
  );
  try {
    CapituloResumo? capitulo;
    if (leitura.de != null) {
      capitulo = (await api.questao(edicao.id, leitura.de!))?.capitulo;
    } else {
      final ed = await api.edicao(edicao.id);
      capitulo = ed.capitulos
          .where((c) => c.referencia == leitura.capitulo)
          .firstOrNull;
    }
    if (!context.mounted) return;
    if (capitulo == null) return avisar(t.leituraIndisponivel);
    abrirCapitulo(
      context,
      api,
      capitulo,
      edicao: edicao.titulo,
      autor: obra.autor,
      questao: leitura.de,
      citacao: Citacao.daEdicao(obra, edicao),
      origem: OrigemCapitulo(obra: obra, edicao: edicao),
    );
  } on ErroCatalogo {
    avisar(t.erroCarregar);
  }
}
