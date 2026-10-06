import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'api/catalogo_api.dart';
import 'idioma/preferencia_idioma.dart';
import 'l10n/app_localizations.dart';
import 'tela/inicio.dart';
import 'tema/centelha_tema.dart';

class CentelhaApp extends StatelessWidget {
  const CentelhaApp({super.key, required this.api, required this.idioma});

  final CatalogoApi api;
  final PreferenciaIdioma idioma;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: idioma,
      builder: (context, _) => MaterialApp(
        onGenerateTitle: (context) => AppLocalizations.of(context).appTitulo,
        debugShowCheckedModeBanner: false,
        theme: TemaCentelha.claro,
        darkTheme: TemaCentelha.escuro,
        locale: idioma.locale,
        supportedLocales: AppLocalizations.supportedLocales,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        localeListResolutionCallback: resolverLocale,
        home: TelaInicio(api: api, idioma: idioma),
      ),
    );
  }
}
