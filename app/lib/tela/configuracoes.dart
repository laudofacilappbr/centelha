import 'package:flutter/material.dart';

import '../api/catalogo_api.dart';
import '../idioma/preferencia_idioma.dart';
import '../l10n/app_localizations.dart';
import '../player/controle_player.dart';
import 'apoio.dart';
import 'baixados.dart';

class TelaConfiguracoes extends StatelessWidget {
  const TelaConfiguracoes({super.key, required this.idioma, required this.api});

  final PreferenciaIdioma idioma;
  final CatalogoApi api;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final tema = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(t.configuracoes)),
      body: ListenableBuilder(
        listenable: idioma,
        builder: (context, _) => ListView(
          children: [
            _Secao(t.idioma),
            RadioGroup<String>(
              groupValue: idioma.locale?.languageCode ?? '',
              onChanged: (v) =>
                  idioma.definir(v == null || v.isEmpty ? null : Locale(v)),
              child: Column(
                children: [
                  RadioListTile<String>(
                    value: '',
                    title: Text(t.idiomaDoAparelho),
                  ),
                  for (final locale in AppLocalizations.supportedLocales)
                    RadioListTile<String>(
                      value: locale.languageCode,
                      title: Text(nomeDoIdioma(locale.languageCode)),
                    ),
                ],
              ),
            ),
            if (EscopoPlayer.of(context).downloads case final d?) ...[
              const Divider(),
              ListTile(
                leading: const Icon(Icons.download_done),
                title: Text(t.baixados),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => TelaBaixados(api: api, downloads: d),
                  ),
                ),
              ),
            ],
            const Divider(),
            _Secao(t.sobre),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                t.avisoVozSintetica,
                style: tema.textTheme.bodyMedium,
              ),
            ),
            _EntradaApoio(api: api),
            ListTile(
              title: Text(t.licencas),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => showLicensePage(
                context: context,
                applicationName: t.appTitulo,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Secao extends StatelessWidget {
  const _Secao(this.titulo);

  final String titulo;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),
      child: Text(titulo, style: Theme.of(context).textTheme.titleLarge),
    );
  }
}

/// Só aparece com o apoio ligado na configuração remota. Sem rede ou com erro, some:
/// o resto das configurações não depende disso.
class _EntradaApoio extends StatefulWidget {
  const _EntradaApoio({required this.api});

  final CatalogoApi api;

  @override
  State<_EntradaApoio> createState() => _EntradaApoioState();
}

class _EntradaApoioState extends State<_EntradaApoio> {
  late final Future<bool> _ligado = widget.api
      .config()
      .then((c) => c.apoio)
      .catchError((_) => false);

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return FutureBuilder<bool>(
      future: _ligado,
      builder: (context, snap) => snap.data == true
          ? ListTile(
              leading: const Icon(Icons.favorite_outline),
              title: Text(t.apoieTitulo),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => TelaApoio(api: widget.api),
                ),
              ),
            )
          : const SizedBox.shrink(),
    );
  }
}
