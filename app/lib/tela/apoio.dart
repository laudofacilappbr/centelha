import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/catalogo_api.dart';
import '../l10n/app_localizations.dart';
import 'comum.dart';

/// Abre um link fora do app (navegador ou app do banco).
typedef AbrirLink = Future<bool> Function(Uri uri);

Future<bool> abrirNoNavegador(Uri uri) =>
    launchUrl(uri, mode: LaunchMode.externalApplication);

/// "Apoie o Centelha" (#40). Apoiar não libera nada: o app é o mesmo para todos.
/// Só aparece com o apoio ligado na configuração remota, e nunca no perfil infantil.
class TelaApoio extends StatelessWidget {
  const TelaApoio({
    super.key,
    required this.api,
    this.abrirLink = abrirNoNavegador,
  });

  final CatalogoApi api;
  final AbrirLink abrirLink;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(t.apoieTitulo)),
      body: Carregavel<Apoio>(
        carregar: api.apoio,
        construir: (context, apoio) => apoio.ligado
            ? _Conteudo(apoio: apoio, abrirLink: abrirLink)
            : Aviso(texto: t.apoioIndisponivel),
      ),
    );
  }
}

class _Conteudo extends StatelessWidget {
  const _Conteudo({required this.apoio, required this.abrirLink});

  final Apoio apoio;
  final AbrirLink abrirLink;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final tema = Theme.of(context);
    final moeda = NumberFormat.simpleCurrency(
      locale: Localizations.localeOf(context).toLanguageTag(),
      name: 'BRL',
    );
    final mensagens = ScaffoldMessenger.of(context);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          apoio.mensagem ?? t.apoioMensagemPadrao,
          style: tema.textTheme.bodyLarge,
        ),
        const SizedBox(height: 8),
        Text(t.apoioNaoLibera, style: tema.textTheme.bodySmall),
        if (apoio.recebedor != null) ...[
          const SizedBox(height: 16),
          Text(
            t.apoioRecebedor(apoio.recebedor!),
            style: tema.textTheme.bodyMedium,
          ),
        ],
        if (apoio.valoresCentavos.isNotEmpty) ...[
          const SizedBox(height: 24),
          Text(t.apoioValoresSugeridos, style: tema.textTheme.titleSmall),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final v in apoio.valoresCentavos)
                Chip(label: Text(moeda.format(v / 100))),
            ],
          ),
        ],
        if (apoio.chavePix != null) ...[
          const SizedBox(height: 24),
          Text(t.apoioPix, style: tema.textTheme.titleSmall),
          const SizedBox(height: 8),
          SelectableText(apoio.chavePix!, style: tema.textTheme.bodyLarge),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            icon: const Icon(Icons.copy),
            label: Text(t.apoioCopiarPix),
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: apoio.chavePix!));
              mensagens
                ..hideCurrentSnackBar()
                ..showSnackBar(SnackBar(content: Text(t.apoioPixCopiada)));
            },
          ),
        ],
        if (apoio.linkExterno != null) ...[
          const SizedBox(height: 24),
          FilledButton.icon(
            icon: const Icon(Icons.open_in_new),
            label: Text(t.apoioAbrirLink),
            onPressed: () async {
              final ok = await abrirLink(Uri.parse(apoio.linkExterno!));
              if (!ok) {
                mensagens
                  ..hideCurrentSnackBar()
                  ..showSnackBar(SnackBar(content: Text(t.apoioLinkFalhou)));
              }
            },
          ),
        ],
      ],
    );
  }
}
