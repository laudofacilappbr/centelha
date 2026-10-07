import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

import 'api/catalogo_api.dart';
import 'app.dart';
import 'chave/chaves.dart';
import 'idioma/preferencia_idioma.dart';
import 'l10n/app_localizations.dart';
import 'offline/downloads.dart';
import 'player/carro.dart';
import 'player/controle_player.dart';
import 'player/progresso.dart';
import 'player/reprodutor.dart';

import 'package:shared_preferences/shared_preferences.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  _registrarLicencasDasFontes();
  final atestador = atestadorDoAparelho();
  final chaves = atestador == null
      ? null
      : ClienteChaves(atestador: atestador, cofre: CofreSeguro());
  // Na web não há pasta privada nem arquivo local: lá o download não existe.
  final downloads = chaves == null || kIsWeb
      ? null
      : await Downloads.abrir(chaves);
  final reprodutor = await ReprodutorAudioService.iniciar();
  final player = ControlePlayer(
    reprodutor,
    ArmazemProgresso(await SharedPreferences.getInstance()),
    chaves: chaves,
    downloads: downloads,
  );
  // Com internet, renova as chaves dos baixados que vencem em até 7 dias.
  unawaited(downloads?.renovarChaves());
  final api = CatalogoApi();
  final idioma = await PreferenciaIdioma.carregar();
  // Android Auto (#43): continuar ouvindo e baixados, no idioma escolhido no app.
  final carro = NavegacaoCarro(
    api: api,
    player: player,
    textos: () => lookupAppLocalizations(
      idioma.locale ??
          resolverLocale(
            PlatformDispatcher.instance.locales,
            AppLocalizations.supportedLocales,
          ),
    ),
  );
  reprodutor.conectarCarro(filhos: carro.filhos, tocar: carro.tocar);
  runApp(CentelhaApp(api: api, idioma: idioma, player: player));
}

// As fontes vão empacotadas no app; a OFL pede que a licença vá junto.
void _registrarLicencasDasFontes() {
  LicenseRegistry.addLicense(() async* {
    for (final (fonte, arquivo) in [
      ('Comfortaa', 'OFL-Comfortaa.txt'),
      ('Atkinson Hyperlegible', 'OFL-AtkinsonHyperlegible.txt'),
    ]) {
      yield LicenseEntryWithLineBreaks([
        fonte,
      ], await rootBundle.loadString('assets/fonts/$arquivo'));
    }
  });
}
