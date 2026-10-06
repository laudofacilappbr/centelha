// Tema do app a partir dos tokens da marca (docs-iniciais/centelha-brand/tokens).
// Mudou a cor na marca? Mude aqui e no site (site/src/styles/global.css).
import 'package:flutter/material.dart';

abstract final class CoresCentelha {
  static const noite950 = Color(0xFF000F3B);
  static const noite900 = Color(0xFF06184D);
  static const noite800 = Color(0xFF0B2270);
  static const bordaEscura = Color(0xFF26417D);
  static const ouro = Color(0xFFFFD84D);
  static const ouroForte = Color(0xFF8A5A00);
  static const creme = Color(0xFFFFF6C8);
  static const textoCreme = Color(0xFFFBF5E6);
  static const neutro50 = Color(0xFFFFFDF8);
  static const neutro300 = Color(0xFFDCD5C9);
  static const neutro700 = Color(0xFF4B4947);
  static const superficieElevadaClara = Color(0xFFF7F2E7);
  static const foco = Color(0xFFD99A00);
  static const erro = Color(0xFFB64750);
}

abstract final class Raios {
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 20.0;
}

const _fonteTitulo = 'Comfortaa';
const _fonteTexto = 'AtkinsonHyperlegible';

TextTheme _texto(Color primario, Color secundario) {
  TextStyle titulo(double tamanho, double linha) => TextStyle(
    fontFamily: _fonteTitulo,
    fontSize: tamanho,
    height: linha / tamanho,
    fontWeight: FontWeight.w700,
    color: primario,
  );
  TextStyle corpo(double tamanho, double linha, [Color? cor]) => TextStyle(
    fontFamily: _fonteTexto,
    fontSize: tamanho,
    height: linha / tamanho,
    color: cor ?? primario,
  );
  return TextTheme(
    displaySmall: titulo(40, 48),
    headlineMedium: titulo(32, 40),
    headlineSmall: titulo(24, 32),
    titleLarge: titulo(20, 28),
    titleMedium: corpo(18, 28).copyWith(fontWeight: FontWeight.w700),
    titleSmall: corpo(16, 24).copyWith(fontWeight: FontWeight.w700),
    bodyLarge: corpo(18, 28),
    bodyMedium: corpo(16, 24),
    bodySmall: corpo(14, 20, secundario),
    labelLarge: corpo(16, 24).copyWith(fontWeight: FontWeight.w700),
    labelMedium: corpo(14, 20),
    labelSmall: corpo(12, 16, secundario),
  );
}

ThemeData _tema({
  required Brightness brilho,
  required Color fundo,
  required Color superficie,
  required Color superficieElevada,
  required Color destaque,
  required Color textoNoDestaque,
  required Color texto,
  required Color textoSecundario,
  required Color borda,
  required Color foco,
}) {
  final cores = ColorScheme(
    brightness: brilho,
    primary: destaque,
    onPrimary: textoNoDestaque,
    secondary: destaque,
    onSecondary: textoNoDestaque,
    error: CoresCentelha.erro,
    onError: Colors.white,
    surface: superficie,
    onSurface: texto,
    onSurfaceVariant: textoSecundario,
    surfaceContainerHighest: superficieElevada,
    outline: borda,
    outlineVariant: borda,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: cores,
    scaffoldBackgroundColor: fundo,
    fontFamily: _fonteTexto,
    textTheme: _texto(texto, textoSecundario),
    focusColor: foco.withValues(alpha: 0.4),
    appBarTheme: AppBarTheme(
      backgroundColor: fundo,
      foregroundColor: texto,
      elevation: 0,
      scrolledUnderElevation: 0,
      titleTextStyle: TextStyle(
        fontFamily: _fonteTitulo,
        fontSize: 20,
        fontWeight: FontWeight.w700,
        color: texto,
      ),
    ),
    cardTheme: CardThemeData(
      color: superficie,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(Raios.md),
        side: BorderSide(color: borda),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Raios.md),
        ),
        minimumSize: const Size(48, 48),
      ),
    ),
    dividerTheme: DividerThemeData(color: borda),
  );
}

abstract final class TemaCentelha {
  static final escuro = _tema(
    brilho: Brightness.dark,
    fundo: CoresCentelha.noite950,
    superficie: CoresCentelha.noite900,
    superficieElevada: CoresCentelha.noite800,
    destaque: CoresCentelha.ouro,
    textoNoDestaque: CoresCentelha.noite950,
    texto: CoresCentelha.textoCreme,
    textoSecundario: CoresCentelha.neutro300,
    borda: CoresCentelha.bordaEscura,
    foco: CoresCentelha.creme,
  );

  static final claro = _tema(
    brilho: Brightness.light,
    fundo: CoresCentelha.neutro50,
    superficie: Colors.white,
    superficieElevada: CoresCentelha.superficieElevadaClara,
    destaque: CoresCentelha.ouroForte,
    textoNoDestaque: Colors.white,
    texto: CoresCentelha.noite950,
    textoSecundario: CoresCentelha.neutro700,
    borda: CoresCentelha.neutro300,
    foco: CoresCentelha.foco,
  );
}
