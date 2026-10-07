import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../conta/conta.dart';
import '../l10n/app_localizations.dart';

/// Entrar, sair e excluir a conta opcional (#43). Sem senha: código no e-mail.
class TelaConta extends StatefulWidget {
  const TelaConta({super.key, required this.conta});

  final Conta conta;

  @override
  State<TelaConta> createState() => _TelaContaState();
}

class _TelaContaState extends State<TelaConta> {
  final _email = TextEditingController();
  final _codigo = TextEditingController();
  String? _enviadoPara;
  bool _ocupado = false;

  @override
  void dispose() {
    _email.dispose();
    _codigo.dispose();
    super.dispose();
  }

  Future<void> _fazer(Future<void> Function() acao) async {
    final t = AppLocalizations.of(context);
    final mensagens = ScaffoldMessenger.of(context);
    setState(() => _ocupado = true);
    try {
      await acao();
    } on ErroConta catch (e) {
      mensagens
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content: Text(switch (e.status) {
              400 => t.contaCodigoInvalido,
              429 => t.contaMuitosPedidos,
              _ => t.contaErro,
            }),
          ),
        );
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  Future<void> _pedirCodigo() => _fazer(() async {
    await widget.conta.pedirCodigo(_email.text);
    _codigo.clear();
    setState(() => _enviadoPara = _email.text.trim());
  });

  /// Saiu ou excluiu: a tela volta ao começo, sem o código pedido antes.
  Future<void> _encerrar(Future<void> Function() acao) async {
    await acao();
    _email.clear();
    _codigo.clear();
    _enviadoPara = null;
  }

  Future<void> _excluir() async {
    final t = AppLocalizations.of(context);
    final sim = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        content: Text(t.contaExcluirPergunta),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(t.cancelar),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(t.contaExcluir),
          ),
        ],
      ),
    );
    if (sim == true) await _fazer(() => _encerrar(widget.conta.excluir));
  }

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final tema = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(t.conta)),
      body: ListenableBuilder(
        listenable: widget.conta,
        builder: (context, _) {
          final conta = widget.conta;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (conta.email case final email?) ...[
                Text(
                  t.contaEntrouComo(email),
                  style: tema.textTheme.titleMedium,
                ),
                const SizedBox(height: 16),
                Text(
                  conta.exportacaoAberta
                      ? t.contaExportacaoLiberada
                      : t.contaExportacaoComoPedir,
                ),
                const SizedBox(height: 24),
                OutlinedButton(
                  onPressed: _ocupado
                      ? null
                      : () => _fazer(() => _encerrar(conta.sair)),
                  child: Text(t.contaSair),
                ),
                TextButton(
                  onPressed: _ocupado ? null : _excluir,
                  child: Text(t.contaExcluir),
                ),
              ] else ...[
                Text(t.contaExplicacao),
                const SizedBox(height: 16),
                TextField(
                  controller: _email,
                  enabled: !_ocupado,
                  keyboardType: TextInputType.emailAddress,
                  autofillHints: const [AutofillHints.email],
                  decoration: InputDecoration(labelText: t.contaEmail),
                ),
                const SizedBox(height: 12),
                if (_enviadoPara case final para?) ...[
                  Text(t.contaCodigoEnviado(para)),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _codigo,
                    enabled: !_ocupado,
                    keyboardType: TextInputType.number,
                    autofillHints: const [AutofillHints.oneTimeCode],
                    maxLength: 6,
                    decoration: InputDecoration(labelText: t.contaCodigo),
                  ),
                  FilledButton(
                    onPressed: _ocupado
                        ? null
                        : () => _fazer(
                            () => conta.entrar(_enviadoPara!, _codigo.text),
                          ),
                    child: Text(t.contaEntrar),
                  ),
                  TextButton(
                    onPressed: _ocupado ? null : _pedirCodigo,
                    child: Text(t.contaOutroCodigo),
                  ),
                ] else
                  FilledButton(
                    onPressed: _ocupado ? null : _pedirCodigo,
                    child: Text(t.contaPedirCodigo),
                  ),
              ],
            ],
          );
        },
      ),
    );
  }
}

/// Entrega os arquivos ao sistema: "Salvar em Arquivos", "Abrir com…". Trocável nos
/// testes.
Future<void> Function(List<File> arquivos, Rect? origem) entregarArquivos =
    (arquivos, origem) => SharePlus.instance.share(
      ShareParams(
        files: [for (final f in arquivos) XFile(f.path)],
        sharePositionOrigin: origem,
      ),
    );

/// Pasta temporária dos arquivos abertos: o sistema a limpa, e o app não guarda
/// cópia aberta junto dos baixados.
Future<Directory> Function() pastaFormatoAberto = () async =>
    Directory('${(await getTemporaryDirectory()).path}/formato-aberto');

/// "Baixar em formato aberto" (#134): só na conta que o suporte liberou, por
/// acessibilidade. Fora dela (e no Kids, que não tem conta) não aparece.
class BotaoFormatoAberto extends StatefulWidget {
  const BotaoFormatoAberto({
    super.key,
    required this.capituloId,
    required this.edicaoId,
  });

  final int capituloId;
  final Future<int> Function() edicaoId;

  @override
  State<BotaoFormatoAberto> createState() => _BotaoFormatoAbertoState();
}

class _BotaoFormatoAbertoState extends State<BotaoFormatoAberto> {
  bool _baixando = false;

  Future<void> _baixar(Conta conta) async {
    final t = AppLocalizations.of(context);
    final mensagens = ScaffoldMessenger.of(context);
    final caixa = context.findRenderObject() as RenderBox?;
    final origem = caixa == null
        ? null
        : caixa.localToGlobal(Offset.zero) & caixa.size;
    setState(() => _baixando = true);
    mensagens
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(t.formatoAbertoBaixando)));
    try {
      final pasta = await pastaFormatoAberto();
      final arquivos = await conta.baixarAberto(
        capituloId: widget.capituloId,
        edicaoId: await widget.edicaoId(),
        pasta: pasta,
      );
      mensagens.hideCurrentSnackBar();
      await entregarArquivos(arquivos, origem);
    } on Exception catch (e) {
      final status = e is ErroConta ? e.status : null;
      mensagens
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content: Text(switch (status) {
              403 => t.formatoAbertoRevogado,
              429 => t.formatoAbertoLimite,
              _ => t.downloadFalhou,
            }),
          ),
        );
    } finally {
      if (mounted) setState(() => _baixando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final conta = EscopoConta.maybeOf(context);
    // Na web não há arquivo local para entregar ao sistema.
    if (kIsWeb || conta == null || !conta.exportacaoAberta) {
      return const SizedBox.shrink();
    }
    final t = AppLocalizations.of(context);
    return IconButton(
      tooltip: t.formatoAberto,
      icon: const Icon(Icons.file_download_outlined),
      onPressed: _baixando ? null : () => _baixar(conta),
    );
  }
}
