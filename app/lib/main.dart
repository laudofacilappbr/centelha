import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

import 'api/catalogo_api.dart';
import 'app.dart';
import 'idioma/preferencia_idioma.dart';
import 'player/controle_player.dart';
import 'player/progresso.dart';
import 'player/reprodutor.dart';

import 'package:shared_preferences/shared_preferences.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  _registrarLicencasDasFontes();
  final player = ControlePlayer(
    await ReprodutorAudioService.iniciar(),
    ArmazemProgresso(await SharedPreferences.getInstance()),
  );
  runApp(
    CentelhaApp(
      api: CatalogoApi(),
      idioma: await PreferenciaIdioma.carregar(),
      player: player,
    ),
  );
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
