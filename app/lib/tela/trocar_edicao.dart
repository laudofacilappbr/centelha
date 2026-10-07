import 'package:flutter/material.dart';

import '../api/catalogo_api.dart';
import '../idioma/preferencia_idioma.dart';
import '../l10n/app_localizations.dart';

/// De qual obra e edição o capítulo aberto veio: o que a troca de idioma precisa.
class OrigemCapitulo {
  const OrigemCapitulo({required this.obra, required this.edicao});

  final Obra obra;
  final EdicaoResumo edicao;

  /// As outras edições da obra para o mesmo público. A troca nunca leva de uma edição
  /// infantil para uma adulta, nem o contrário.
  List<EdicaoResumo> get outras => [
    for (final e in obra.edicoes)
      if (e.id != edicao.id && e.publico == edicao.publico) e,
  ];
}

/// Onde a mesma posição fica na outra edição.
typedef Destino = ({CapituloResumo capitulo, int? questao, String? subquestao});

/// A mesma posição em [destino], pela referência canônica (#47).
///
/// Com questão (LE), pergunta à API em que capítulo a questão está na outra edição:
/// a numeração das questões é a mesma em todas as traduções, mas a divisão em
/// capítulos pode não ser. Sem questão, ou se a questão não estiver lá, vale o
/// capítulo de mesma referência ("LE-C003"). null quando nem isso existe.
Future<Destino?> mesmaPosicao(
  CatalogoApi api,
  EdicaoResumo destino, {
  required CapituloResumo capitulo,
  int? questao,
  String? subquestao,
}) async {
  if (questao != null) {
    final q = await api.questao(destino.id, questao);
    if (q != null) {
      return (capitulo: q.capitulo, questao: questao, subquestao: subquestao);
    }
  }
  final edicao = await api.edicao(destino.id);
  for (final c in edicao.capitulos) {
    if (c.referencia == capitulo.referencia) {
      return (capitulo: c, questao: null, subquestao: null);
    }
  }
  return null;
}

/// Folha com as outras edições; devolve a escolhida ou null.
Future<EdicaoResumo?> escolherOutraEdicao(
  BuildContext context,
  OrigemCapitulo origem,
) {
  final t = AppLocalizations.of(context);
  return showModalBottomSheet<EdicaoResumo>(
    context: context,
    showDragHandle: true,
    builder: (folha) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Text(
              t.lerEmOutroIdioma,
              style: Theme.of(folha).textTheme.titleMedium,
            ),
          ),
          for (final e in origem.outras)
            ListTile(
              leading: const Icon(Icons.translate),
              title: Text(nomeDoIdioma(e.idioma)),
              subtitle: Text(e.titulo),
              onTap: () => Navigator.of(folha).pop(e),
            ),
        ],
      ),
    ),
  );
}
