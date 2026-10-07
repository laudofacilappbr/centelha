import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'api/catalogo_api.dart';
import 'conta/conta.dart';
import 'idioma/preferencia_idioma.dart';
import 'l10n/app_localizations.dart';
import 'player/controle_player.dart';
import 'tela/inicio.dart';
import 'tema/centelha_tema.dart';

class CentelhaApp extends StatelessWidget {
  const CentelhaApp({
    super.key,
    required this.api,
    required this.idioma,
    required this.player,
    this.conta,
  });

  final CatalogoApi api;
  final PreferenciaIdioma idioma;
  final ControlePlayer player;

  /// Conta opcional (#43); null nos testes que não a usam.
  final Conta? conta;

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
        // Acima das rotas: o player continua o mesmo ao navegar entre telas.
        builder: (context, filho) {
          final comPlayer = EscopoPlayer(player: player, child: filho!);
          final c = conta;
          return c == null
              ? comPlayer
              : EscopoConta(conta: c, child: comPlayer);
        },
        home: TelaInicio(api: api, idioma: idioma),
      ),
    );
  }
}
