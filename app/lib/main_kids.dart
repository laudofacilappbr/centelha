// Entrada do Centelhar Kids (#50, ADR 0006):
//   flutter run -t lib/main_kids.dart
//   flutter build apk --flavor kids -t lib/main_kids.dart
//
// Comparado ao main.dart: sem atestação nem downloads (o player só toca .m4a aberto
// até a atestação valer também aqui, decisão 4A da #73), sem apoio e sem campanhas.
import 'package:flutter/widgets.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api/catalogo_api.dart';
import 'idioma/preferencia_idioma.dart';
import 'kids/app_kids.dart';
import 'player/controle_player.dart';
import 'player/progresso.dart';
import 'player/reprodutor.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final player = ControlePlayer(
    await ReprodutorAudioService.iniciar(),
    ArmazemProgresso(await SharedPreferences.getInstance()),
  );
  runApp(
    CentelhaKidsApp(
      api: CatalogoApi(),
      idioma: await PreferenciaIdioma.carregar(),
      player: player,
    ),
  );
}
