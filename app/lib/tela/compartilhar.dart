import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';

import '../api/catalogo_api.dart';
import '../l10n/app_localizations.dart';
import 'campanha.dart' show urlSitePadrao;

/// De onde o trecho vem, para a citação que acompanha o texto compartilhado.
///
/// Só existe para edição adulta: o compartilhar leva link para fora do app, e o perfil
/// infantil não tem link externo. Sem [Citacao], a tela não oferece compartilhar.
class Citacao {
  const Citacao({
    required this.autor,
    required this.obra,
    required this.slugObra,
    this.tradutor,
    this.comLink = true,
  });

  /// Edição adulta vira citação; juvenil e infantil, null.
  static Citacao? daEdicao(Obra obra, EdicaoResumo edicao) {
    if (edicao.publico != 'adulto') return null;
    return Citacao(
      autor: obra.autor,
      obra: edicao.titulo,
      slugObra: obra.slug,
      tradutor: edicao.tradutor,
      // O site só publica a edição pt-BR adulta; link para outra apontaria para um
      // texto diferente do compartilhado.
      comLink: edicao.idioma == 'pt-BR',
    );
  }

  final String autor;
  final String obra;
  final String slugObra;
  final String? tradutor;
  final bool comLink;
}

/// Abre a folha de compartilhar do sistema. Trocável nos testes, que não têm o canal
/// nativo do share_plus.
typedef Compartilhador = Future<void> Function(String texto, Rect? origem);

@visibleForTesting
Compartilhador compartilhador = (texto, origem) => SharePlus.instance.share(
  ShareParams(text: texto, sharePositionOrigin: origem),
);

const _obraComQuestoes = 'o-livro-dos-espiritos';

/// O que vai junto quando a pessoa compartilha [escolhido]: a questão inteira (pergunta
/// e resposta, que separadas não fazem sentido) ou o trecho sozinho.
List<Segmento> trechoDe(Segmento escolhido, List<Segmento> segmentos) {
  final n = escolhido.numeroQuestao;
  final questao =
      escolhido.tipo == TipoSegmento.pergunta ||
      escolhido.tipo == TipoSegmento.resposta;
  if (n == null || !questao) return [escolhido];
  return [
    for (final s in segmentos)
      if (s.numeroQuestao == n &&
          s.subquestao == escolhido.subquestao &&
          (s.tipo == TipoSegmento.pergunta || s.tipo == TipoSegmento.resposta))
        s,
  ];
}

/// Link permanente no site: a página da questão no LE, senão a do capítulo. Os
/// caminhos seguem site/src/lib (urlQuestao e slugCapitulo) e não mudam depois de
/// publicados.
Uri? linkNoSite(
  Citacao citacao,
  CapituloResumo capitulo,
  List<Segmento> trecho, {
  String site = urlSitePadrao,
}) {
  if (!citacao.comLink) return null;
  final base = Uri.parse(site);
  final n = trecho.first.numeroQuestao;
  if (citacao.slugObra == _obraComQuestoes && n != null) {
    return base.resolve('/livro-dos-espiritos/questao/$n');
  }
  return base.resolve('/obras/${citacao.slugObra}/capitulo-${capitulo.ordem}');
}

String textoParaCompartilhar(
  AppLocalizations t,
  Citacao citacao,
  CapituloResumo capitulo,
  List<Segmento> trecho, {
  String site = urlSitePadrao,
}) {
  final linhas = <String>[
    for (final s in trecho)
      s.tipo == TipoSegmento.pergunta && s.numeroQuestao != null
          ? '${s.numeroQuestao}${s.subquestao ?? ''}. ${s.texto}'
          : s.texto,
  ];
  final n = trecho.first.numeroQuestao;
  final onde = n != null ? t.citacaoQuestao(citacao.obra, n) : citacao.obra;
  final traducao = citacao.tradutor != null
      ? ' ${t.citacaoTradutor(citacao.tradutor!)}'
      : '';
  final link = linkNoSite(citacao, capitulo, trecho, site: site);
  return [
    linhas.join('\n\n'),
    '',
    '— ${citacao.autor}, $onde.$traducao',
    if (link != null) link.toString(),
  ].join('\n');
}

/// Folha com "Compartilhar" e "Copiar" para o trecho tocado e segurado.
Future<void> oferecerCompartilhar(
  BuildContext context, {
  required Citacao citacao,
  required CapituloResumo capitulo,
  required List<Segmento> trecho,
}) async {
  final t = AppLocalizations.of(context);
  final texto = textoParaCompartilhar(t, citacao, capitulo, trecho);
  // iPad abre a folha do sistema como popover e precisa saber de onde ela sai.
  final caixa = context.findRenderObject() as RenderBox?;
  final origem = caixa == null
      ? null
      : caixa.localToGlobal(Offset.zero) & caixa.size;
  final mensageiro = ScaffoldMessenger.of(context);

  await showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    builder: (folha) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            leading: const Icon(Icons.share_outlined),
            title: Text(t.compartilharTrecho),
            onTap: () {
              Navigator.of(folha).pop();
              compartilhador(texto, origem);
            },
          ),
          ListTile(
            leading: const Icon(Icons.copy_outlined),
            title: Text(t.copiarTrecho),
            onTap: () async {
              Navigator.of(folha).pop();
              await Clipboard.setData(ClipboardData(text: texto));
              mensageiro
                ..hideCurrentSnackBar()
                ..showSnackBar(SnackBar(content: Text(t.trechoCopiado)));
            },
          ),
        ],
      ),
    ),
  );
}
