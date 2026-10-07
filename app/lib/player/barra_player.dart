import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../api/catalogo_api.dart';
import '../chave/chaves.dart';
import '../l10n/app_localizations.dart';
import '../offline/downloads.dart';
import 'controle_player.dart';
import 'reprodutor.dart';

String formatarTempo(Duration d) {
  final h = d.inHours;
  final m = d.inMinutes.remainder(60).toString().padLeft(2, '0');
  final s = d.inSeconds.remainder(60).toString().padLeft(2, '0');
  return h > 0 ? '$h:$m:$s' : '$m:$s';
}

String _velocidadeTexto(BuildContext context, double v) {
  final local = Localizations.localeOf(context).languageCode;
  final numero = v == v.roundToDouble()
      ? v.toStringAsFixed(0)
      : v.toString().replaceAll(RegExp(r'0+$'), '');
  // Vírgula decimal em pt, es e fr: "1,25x".
  return '${local == 'en' ? numero : numero.replaceAll('.', ',')}x';
}

/// Player do capítulo, no pé da tela. Abre o capítulo no ponto em que parou, sem
/// tocar; se outro capítulo estiver tocando, oferece trocar em vez de interromper.
class BarraPlayer extends StatefulWidget {
  const BarraPlayer({super.key, required this.capitulo, required this.info});

  final Capitulo capitulo;
  final InfoFaixa info;

  @override
  State<BarraPlayer> createState() => _BarraPlayerState();
}

class _BarraPlayerState extends State<BarraPlayer> {
  double? _arrastando;

  @override
  void initState() {
    super.initState();
    // Depois do primeiro quadro: abrir notifica os ouvintes, o que não pode
    // acontecer no meio de um build.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final player = EscopoPlayer.of(context);
      if (!player.tocando && !player.carregado(widget.capitulo.resumo.id)) {
        player.abrir(widget.capitulo, widget.info);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final tema = Theme.of(context);
    final player = EscopoPlayer.of(context);
    final faixa = widget.capitulo.faixa!;

    final Widget conteudo;
    if (!player.podeTocar(faixa)) {
      conteudo = Text(t.audioIndisponivel, textAlign: TextAlign.center);
    } else if (!player.carregado(widget.capitulo.resumo.id)) {
      conteudo = FilledButton.icon(
        onPressed: () async {
          final mensagens = ScaffoldMessenger.of(context);
          try {
            await player.abrir(widget.capitulo, widget.info);
          } on ErroChave {
            mensagens
              ..hideCurrentSnackBar()
              ..showSnackBar(SnackBar(content: Text(t.chaveIndisponivel)));
            return;
          }
          await player.alternar();
        },
        icon: const Icon(Icons.play_arrow),
        label: Text(t.ouvirEsteCapitulo),
      );
    } else {
      conteudo = _Controles(
        player: player,
        arrastando: _arrastando,
        aoArrastar: (v) => setState(() => _arrastando = v),
      );
    }

    final downloads = player.downloads;
    final comDownload =
        downloads != null &&
        downloads.podeBaixar(faixa) &&
        player.podeTocar(faixa);
    return Material(
      color: tema.colorScheme.surface,
      elevation: 8,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
          child: comDownload
              ? Row(
                  children: [
                    Expanded(child: conteudo),
                    BotaoDownload(
                      downloads: downloads,
                      capitulo: widget.capitulo,
                      info: widget.info,
                    ),
                  ],
                )
              : conteudo,
        ),
      ),
    );
  }
}

class _Controles extends StatelessWidget {
  const _Controles({
    required this.player,
    required this.arrastando,
    required this.aoArrastar,
  });

  final ControlePlayer player;
  final double? arrastando;
  final ValueChanged<double?> aoArrastar;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final tema = Theme.of(context);
    final cor = tema.colorScheme.onSurface;
    final total = player.duracao.inMilliseconds.toDouble();
    final valor = (arrastando ?? player.posicao.inMilliseconds.toDouble())
        .clamp(0.0, total > 0 ? total : 1.0);
    final fimTimer = player.fimTimerSono;

    Widget icone(String nome, {double tamanho = 28, Color? corIcone}) =>
        SvgPicture.asset(
          'assets/icones/$nome.svg',
          width: tamanho,
          height: tamanho,
          colorFilter: ColorFilter.mode(corIcone ?? cor, BlendMode.srcIn),
        );

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Slider(
          value: valor,
          max: total > 0 ? total : 1.0,
          semanticFormatterCallback: (v) =>
              '${t.posicao} ${formatarTempo(Duration(milliseconds: v.round()))}',
          onChanged: total > 0 ? aoArrastar : null,
          onChangeEnd: (v) {
            aoArrastar(null);
            player.irPara(Duration(milliseconds: v.round()));
          },
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            children: [
              Text(
                formatarTempo(Duration(milliseconds: valor.round())),
                style: tema.textTheme.labelSmall,
              ),
              const Spacer(),
              if (fimTimer != null)
                Text(
                  t.timerRestante(
                    (fimTimer.difference(DateTime.now()).inSeconds / 60).ceil(),
                  ),
                  style: tema.textTheme.labelSmall,
                ),
              const Spacer(),
              Text(
                formatarTempo(player.duracao),
                style: tema.textTheme.labelSmall,
              ),
            ],
          ),
        ),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            PopupMenuButton<double>(
              tooltip: t.velocidade,
              initialValue: player.velocidade,
              onSelected: player.definirVelocidade,
              itemBuilder: (context) => [
                for (final v in ControlePlayer.velocidades)
                  PopupMenuItem(
                    value: v,
                    child: Text(_velocidadeTexto(context, v)),
                  ),
              ],
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  _velocidadeTexto(context, player.velocidade),
                  style: tema.textTheme.labelLarge,
                ),
              ),
            ),
            IconButton(
              tooltip: t.voltar15,
              onPressed: () => player.pular(-ControlePlayer.salto),
              icon: icone('back-15'),
            ),
            IconButton.filled(
              tooltip: player.tocando ? t.pausar : t.tocar,
              iconSize: 36,
              onPressed: player.alternar,
              icon: icone(
                player.tocando ? 'pause' : 'play',
                tamanho: 32,
                corIcone: tema.colorScheme.onPrimary,
              ),
            ),
            IconButton(
              tooltip: t.avancar15,
              onPressed: () => player.pular(ControlePlayer.salto),
              icon: icone('forward-15'),
            ),
            PopupMenuButton<int>(
              tooltip: t.timerSono,
              onSelected: (min) =>
                  player.timerSono(min == 0 ? null : Duration(minutes: min)),
              itemBuilder: (context) => [
                for (final min in const [15, 30, 45, 60])
                  PopupMenuItem(value: min, child: Text(t.timerMinutos(min))),
                PopupMenuItem(value: 0, child: Text(t.timerDesligado)),
              ],
              icon: icone(
                'sleep-timer',
                corIcone: fimTimer != null ? tema.colorScheme.primary : null,
              ),
            ),
            IconButton(
              tooltip: t.marcadores,
              onPressed: () => _mostrarMarcadores(context, player),
              icon: icone('favorite'),
            ),
          ],
        ),
      ],
    );
  }
}

void _mostrarMarcadores(BuildContext context, ControlePlayer player) {
  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    builder: (context) => ListenableBuilder(
      listenable: player,
      builder: (context, _) {
        final t = AppLocalizations.of(context);
        final faixa = player.faixa!;
        final marcadores = player.marcadores;
        return SafeArea(
          child: ListView(
            shrinkWrap: true,
            children: [
              ListTile(
                leading: const Icon(Icons.bookmark_add_outlined),
                title: Text(t.marcar),
                subtitle: Text(formatarTempo(player.posicao)),
                onTap: () async {
                  final tempo = formatarTempo(player.posicao);
                  await player.marcar();
                  if (context.mounted) {
                    ScaffoldMessenger.of(context)
                      ..hideCurrentSnackBar()
                      ..showSnackBar(
                        SnackBar(content: Text(t.marcadorSalvo(tempo))),
                      );
                  }
                },
              ),
              const Divider(),
              if (marcadores.isEmpty)
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(t.semMarcadores),
                ),
              for (final m in marcadores)
                ListTile(
                  leading: const Icon(Icons.bookmark_outline),
                  title: Text(
                    formatarTempo(
                      Duration(milliseconds: m.posicao.naFaixa(faixa)),
                    ),
                  ),
                  onTap: () {
                    player.irPara(
                      Duration(milliseconds: m.posicao.naFaixa(faixa)),
                    );
                    Navigator.of(context).pop();
                  },
                  trailing: IconButton(
                    tooltip: t.remover,
                    icon: const Icon(Icons.delete_outline),
                    onPressed: () => player.removerMarcador(m),
                  ),
                ),
            ],
          ),
        );
      },
    ),
  );
}

/// Baixar o capítulo para ouvir sem internet; baixado, tocar oferece apagar.
class BotaoDownload extends StatelessWidget {
  const BotaoDownload({
    super.key,
    required this.downloads,
    required this.capitulo,
    required this.info,
  });

  final Downloads downloads;
  final Capitulo capitulo;
  final InfoFaixa info;

  Faixa get faixa => capitulo.faixa!;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    return ListenableBuilder(
      listenable: downloads,
      builder: (context, _) {
        final progresso = downloads.progresso(faixa);
        if (progresso != null) {
          return Semantics(
            label: t.baixando((progresso * 100).round()),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: SizedBox.square(
                dimension: 24,
                child: CircularProgressIndicator(
                  value: progresso,
                  strokeWidth: 3,
                ),
              ),
            ),
          );
        }
        if (downloads.baixado(faixa)) {
          return IconButton(
            tooltip: t.baixadoApagar,
            icon: const Icon(Icons.download_done),
            onPressed: () => _apagar(context),
          );
        }
        return IconButton(
          tooltip: t.baixarCapitulo,
          icon: const Icon(Icons.download_outlined),
          onPressed: () async {
            final mensagens = ScaffoldMessenger.of(context);
            try {
              await downloads.baixar(faixa, capitulo: capitulo, info: info);
            } on ErroDownload {
              mensagens
                ..hideCurrentSnackBar()
                ..showSnackBar(SnackBar(content: Text(t.downloadFalhou)));
            }
          },
        );
      },
    );
  }

  Future<void> _apagar(BuildContext context) async {
    final t = AppLocalizations.of(context);
    final apagar = await showDialog<bool>(
      context: context,
      builder: (dialogo) => AlertDialog(
        title: Text(t.apagarDownloadTitulo),
        content: Text(t.apagarDownloadTexto),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogo).pop(false),
            child: Text(t.cancelar),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogo).pop(true),
            child: Text(t.apagar),
          ),
        ],
      ),
    );
    if (apagar ?? false) await downloads.apagar(faixa);
  }
}
