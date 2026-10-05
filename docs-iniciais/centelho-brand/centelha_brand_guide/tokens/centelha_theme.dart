// Generated convenience mapping from tokens.json. No font files are bundled.
import 'package:flutter/material.dart';
class CentelhaTheme {
 static const night = Color(0xFF000F3B); static const blue = Color(0xFF0B2270); static const gold = Color(0xFFFFD84D); static const amber = Color(0xFFF5A524); static const cream = Color(0xFFFBF5E6);
 static ThemeData dark() => ThemeData(brightness: Brightness.dark, scaffoldBackgroundColor: night, colorScheme: const ColorScheme.dark(primary: gold, onPrimary: night, surface: Color(0xFF06184D), onSurface: cream), useMaterial3: true);
 static ThemeData light() => ThemeData(brightness: Brightness.light, scaffoldBackgroundColor: const Color(0xFFFFFDF8), colorScheme: const ColorScheme.light(primary: Color(0xFF8A5A00), onPrimary: Colors.white, surface: Colors.white, onSurface: night), useMaterial3: true);
}
