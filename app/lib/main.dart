import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

import 'api/catalogo_api.dart';
import 'app.dart';
import 'idioma/preferencia_idioma.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  _registrarLicencasDasFontes();
  runApp(
    CentelhaApp(api: CatalogoApi(), idioma: await PreferenciaIdioma.carregar()),
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
