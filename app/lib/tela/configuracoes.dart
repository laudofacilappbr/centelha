import 'package:flutter/material.dart';

import '../idioma/preferencia_idioma.dart';
import '../l10n/app_localizations.dart';

class TelaConfiguracoes extends StatelessWidget {
  const TelaConfiguracoes({super.key, required this.idioma});

  final PreferenciaIdioma idioma;

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
            const Divider(),
            _Secao(t.sobre),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                t.avisoVozSintetica,
                style: tema.textTheme.bodyMedium,
              ),
            ),
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
