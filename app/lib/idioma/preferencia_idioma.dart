// Idioma da interface: o do aparelho por padrão, ou o escolhido nas configurações.
// Fica no aparelho (sem login), como o resto do progresso no MVP.
import 'package:flutter/widgets.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../l10n/app_localizations.dart';

class PreferenciaIdioma extends ChangeNotifier {
  PreferenciaIdioma._(this._prefs, this._locale);

  static const _chave = 'idioma';

  final SharedPreferences _prefs;
  Locale? _locale;

  /// null = seguir o idioma do aparelho.
  Locale? get locale => _locale;

  static Future<PreferenciaIdioma> carregar() async {
    final prefs = await SharedPreferences.getInstance();
    final salvo = prefs.getString(_chave);
    final suportado =
        salvo != null &&
        AppLocalizations.supportedLocales.any((l) => l.languageCode == salvo);
    return PreferenciaIdioma._(prefs, suportado ? Locale(salvo) : null);
  }

  Future<void> definir(Locale? locale) async {
    if (locale?.languageCode == _locale?.languageCode) return;
    _locale = locale;
    if (locale == null) {
      await _prefs.remove(_chave);
    } else {
      await _prefs.setString(_chave, locale.languageCode);
    }
    notifyListeners();
  }
}

/// Escolhe entre os idiomas da interface pelo idioma do aparelho; sem nenhum
/// suportado, português, que é o idioma do catálogo inicial.
Locale resolverLocale(List<Locale>? doAparelho, Iterable<Locale> suportados) {
  for (final pedido in doAparelho ?? const <Locale>[]) {
    for (final s in suportados) {
      if (s.languageCode == pedido.languageCode) return s;
    }
  }
  return const Locale('pt');
}

// Nome de cada idioma nele mesmo: quem não entende a interface atual ainda acha o seu.
const _nomes = {
  'pt': 'Português',
  'es': 'Español',
  'fr': 'Français',
  'en': 'English',
};

/// "pt-BR" → "Português"; idioma sem nome conhecido fica com o próprio código.
String nomeDoIdioma(String idioma) => _nomes[idioma.split('-').first] ?? idioma;

/// Idioma das edições (BCP 47, como na API) que combina com o da interface.
String idiomaDoConteudo(Locale interface) =>
    interface.languageCode == 'pt' ? 'pt-BR' : interface.languageCode;
