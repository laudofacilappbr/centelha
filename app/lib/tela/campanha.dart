import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/catalogo_api.dart';
import '../l10n/app_localizations.dart';
import 'apoio.dart' show AbrirLink;

/// Site do Centelhar, definido no build como a API: --dart-define=CENTELHA_SITE_URL=...
const urlSitePadrao = String.fromEnvironment(
  'CENTELHA_SITE_URL',
  defaultValue: 'https://centelhar.com.br',
);

const _chaveFechada = 'campanha_fechada';

/// Campanha a mostrar no início: só com `caridade` ligado na configuração remota e
/// se a pessoa não fechou esta campanha antes. Sem rede ou com erro, nenhuma.
// Quando houver perfil infantil (#50), lá não se busca nada disto.
Future<Campanha?> campanhaParaMostrar(CatalogoApi api) async {
  try {
    if (!(await api.config()).caridade) return null;
    final campanha = await api.campanhaAtiva();
    if (campanha == null) return null;
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_chaveFechada) == campanha.slug ? null : campanha;
  } catch (_) {
    return null;
  }
}

/// Fechada uma vez, a mesma campanha não volta; a próxima aparece.
Future<void> fecharCampanha(Campanha campanha) async =>
    (await SharedPreferences.getInstance()).setString(
      _chaveFechada,
      campanha.slug,
    );

/// "11222333000181" → "11.222.333/0001-81"; outro formato fica como veio.
String formatarCnpj(String cnpj) {
  final m = RegExp(r'^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$').firstMatch(cnpj);
  return m == null ? cnpj : '${m[1]}.${m[2]}.${m[3]}/${m[4]}-${m[5]}';
}

/// Cartão da campanha ativa na tela inicial.
class CartaoCampanha extends StatelessWidget {
  const CartaoCampanha({
    super.key,
    required this.campanha,
    required this.aoFechar,
    required this.abrirLink,
  });

  final Campanha campanha;
  final VoidCallback aoFechar;
  final AbrirLink abrirLink;

  // Na Apple, só entidade sem fins lucrativos aprovada por ela arrecada doação
  // dentro do app: no iOS o cartão leva à página da campanha no navegador.
  Future<void> _abrir(BuildContext context) async {
    if (defaultTargetPlatform != TargetPlatform.iOS) {
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) =>
              TelaCampanha(campanha: campanha, abrirLink: abrirLink),
        ),
      );
      return;
    }
    final t = AppLocalizations.of(context);
    final mensagens = ScaffoldMessenger.of(context);
    final ok = await abrirLink(
      Uri.parse(urlSitePadrao).resolve('/campanhas/${campanha.slug}'),
    );
    if (!ok) {
      mensagens
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(t.apoioLinkFalhou)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final tema = Theme.of(context);
    final data = DateFormat.yMMMMd(
      Localizations.localeOf(context).toLanguageTag(),
    ).format(campanha.fim);
    final cor = tema.colorScheme.onSecondaryContainer;
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Card(
        margin: EdgeInsets.zero,
        color: tema.colorScheme.secondaryContainer,
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => _abrir(context),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 4, 12),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Icon(Icons.volunteer_activism, color: cor, size: 32),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        t.campanhaRotulo,
                        style: tema.textTheme.labelSmall?.copyWith(color: cor),
                      ),
                      Text(
                        campanha.titulo,
                        style: tema.textTheme.titleSmall?.copyWith(color: cor),
                      ),
                      Text(
                        t.campanhaPara(campanha.instituicao, data),
                        style: tema.textTheme.bodySmall?.copyWith(color: cor),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  tooltip: t.campanhaFechar,
                  color: cor,
                  icon: const Icon(Icons.close),
                  onPressed: aoFechar,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Campanha de caridade (#41): o dinheiro cai na conta da instituição, pelo Pix
/// dela. Nunca no perfil infantil.
class TelaCampanha extends StatelessWidget {
  const TelaCampanha({
    super.key,
    required this.campanha,
    required this.abrirLink,
  });

  final Campanha campanha;
  final AbrirLink abrirLink;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final tema = Theme.of(context);
    final local = Localizations.localeOf(context).toLanguageTag();
    final moeda = NumberFormat.simpleCurrency(locale: local, name: 'BRL');
    final mensagens = ScaffoldMessenger.of(context);

    Future<void> abrir(String link) async {
      if (!await abrirLink(Uri.parse(link))) {
        mensagens
          ..hideCurrentSnackBar()
          ..showSnackBar(SnackBar(content: Text(t.apoioLinkFalhou)));
      }
    }

    return Scaffold(
      appBar: AppBar(title: Text(t.campanhaRotulo)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(campanha.titulo, style: tema.textTheme.titleLarge),
          const SizedBox(height: 4),
          Text(
            t.campanhaPara(
              campanha.instituicao,
              DateFormat.yMMMMd(local).format(campanha.fim),
            ),
            style: tema.textTheme.bodySmall,
          ),
          if (campanha.metaCentavos != null)
            Text(
              t.campanhaMeta(moeda.format(campanha.metaCentavos! / 100)),
              style: tema.textTheme.bodySmall,
            ),
          const SizedBox(height: 16),
          Text(campanha.texto, style: tema.textTheme.bodyLarge),
          const SizedBox(height: 16),
          Text(t.campanhaDireto, style: tema.textTheme.bodySmall),
          const SizedBox(height: 24),
          Text(campanha.instituicao, style: tema.textTheme.titleSmall),
          Text(
            t.campanhaCnpj(formatarCnpj(campanha.cnpj)),
            style: tema.textTheme.bodySmall,
          ),
          const SizedBox(height: 8),
          Text(campanha.descricaoInstituicao, style: tema.textTheme.bodyMedium),
          if (campanha.chavePix != null) ...[
            const SizedBox(height: 24),
            Text(t.apoioPix, style: tema.textTheme.titleSmall),
            const SizedBox(height: 8),
            SelectableText(campanha.chavePix!, style: tema.textTheme.bodyLarge),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              icon: const Icon(Icons.copy),
              label: Text(t.apoioCopiarPix),
              onPressed: () async {
                await Clipboard.setData(
                  ClipboardData(text: campanha.chavePix!),
                );
                mensagens
                  ..hideCurrentSnackBar()
                  ..showSnackBar(SnackBar(content: Text(t.apoioPixCopiada)));
              },
            ),
          ],
          if (campanha.paginaDoacao != null) ...[
            const SizedBox(height: 24),
            FilledButton.icon(
              icon: const Icon(Icons.open_in_new),
              label: Text(t.campanhaDoarSite),
              onPressed: () => abrir(campanha.paginaDoacao!),
            ),
          ],
          if (campanha.siteInstituicao != null) ...[
            const SizedBox(height: 8),
            TextButton.icon(
              icon: const Icon(Icons.open_in_new),
              label: Text(t.campanhaSiteInstituicao),
              onPressed: () => abrir(campanha.siteInstituicao!),
            ),
          ],
        ],
      ),
    );
  }
}
