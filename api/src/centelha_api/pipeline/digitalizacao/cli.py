"""Digitalização de um exemplar: do escaneado ao texto pronto para a ingestão.

    centelha-digitalizar ocr exemplar.pdf -o le-1944.paginas.txt
    centelha-digitalizar processar le-1944.paginas.txt --saida acervo/le-1944 \\
        [--perfil perguntas] [--referencia texto-digital.txt] [--sem-ortografia] \\
        [--correcoes docs/digitalizacao/correcoes/le-1944.txt]
    centelha-digitalizar tudo exemplar.pdf --saida acervo/le-1944 --perfil perguntas

"processar" grava, na pasta de saída:
  texto.txt    parágrafos limpos e com a grafia atualizada (entrada da centelha-ingestao)
  revisao.md   o que conferir no exemplar, com a página: suspeitas de OCR, questões,
               diferenças contra a referência, trocas de grafia

Passo a passo completo na skill .claude/skills/centelha-digitalizacao.
"""

import argparse
import sys
from pathlib import Path

from .correcoes import ErroCorrecao, aplicar, ler
from .limpeza import Paragrafo, como_texto, limpar_paginas
from .ocr import ErroOCR, ocr
from .ortografia import atualizar
from .revisao import como_markdown, revisar

# Modelos instalados na imagem de digitalização (Dockerfile).
IDIOMAS = ("por", "fra")


def _progresso(i: int, total: int) -> None:
    print(f"\rOCR: página {i}/{total}", end="" if i < total else "\n", file=sys.stderr)


def processar(
    paginas: str,
    saida: Path,
    titulo: str,
    perfil: str | None = None,
    referencia: str | None = None,
    ortografia: bool = True,
    idioma: str = "por",
    correcoes: str | None = None,
) -> Path:
    paragrafos = limpar_paginas(paginas)
    trocas = []
    # A atualização de grafia é da língua portuguesa (1943 → atual); em francês não se aplica.
    if ortografia and idioma == "por":
        novos = []
        for p in paragrafos:
            texto, t = atualizar(p.texto)
            novos.append(Paragrafo(p.pagina, texto))
            trocas += t
        paragrafos = novos
    # Depois da grafia: quem revisa escreve as correções olhando o texto.txt final.
    lista = ler(correcoes) if correcoes else []
    paragrafos = aplicar(paragrafos, lista)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "texto.txt").write_text(como_texto(paragrafos), encoding="utf-8")
    relatorio = revisar(paragrafos, trocas, referencia, perfil, idioma)
    (saida / "revisao.md").write_text(como_markdown(relatorio, titulo), encoding="utf-8")
    print(
        f"{len(paragrafos)} parágrafos, {len(relatorio.achados)} achados, "
        f"{len(trocas)} trocas de grafia, {len(lista)} correções → {saida}",
        file=sys.stderr,
    )
    return saida


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="centelha-digitalizar",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    o = sub.add_parser("ocr", help="PDF ou pasta de imagens → páginas de texto")
    o.add_argument("origem", type=Path)
    o.add_argument("-o", "--saida", type=Path, required=True)
    o.add_argument("--dpi", type=int, default=300)
    o.add_argument("--idioma", choices=IDIOMAS, default="por")

    def opcoes_processar(p: argparse.ArgumentParser) -> None:
        p.add_argument("--saida", type=Path, required=True, help="pasta de saída")
        p.add_argument("--perfil", choices=["generico", "perguntas"])
        p.add_argument("--referencia", type=Path, help="texto digital para comparar (só apoio)")
        p.add_argument("--sem-ortografia", action="store_true")
        p.add_argument(
            "--correcoes",
            type=Path,
            help="correções da revisão (p. N: lido => certo), versionadas; ver correcoes.py",
        )
        p.add_argument(
            "--idioma",
            choices=IDIOMAS,
            default="por",
            help="modelo do Tesseract; fra: originais de Kardec (#45), sem atualizar a grafia",
        )

    p = sub.add_parser("processar", help="páginas → texto.txt e revisao.md")
    p.add_argument("paginas", type=Path)
    opcoes_processar(p)

    t = sub.add_parser("tudo", help="ocr e processar de uma vez")
    t.add_argument("origem", type=Path)
    t.add_argument("--dpi", type=int, default=300)
    opcoes_processar(t)

    a = parser.parse_args(argv)
    try:
        if a.comando == "ocr":
            a.saida.write_text(ocr(a.origem, a.idioma, a.dpi, _progresso), encoding="utf-8")
            print(f"páginas gravadas em {a.saida}", file=sys.stderr)
            return 0
        if a.comando == "tudo":
            a.saida.mkdir(parents=True, exist_ok=True)
            paginas = ocr(a.origem, a.idioma, a.dpi, _progresso)
            (a.saida / "paginas.txt").write_text(paginas, encoding="utf-8")
            titulo = a.origem.stem
        else:
            paginas = a.paginas.read_text(encoding="utf-8")
            titulo = a.paginas.stem
    except ErroOCR as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    referencia = a.referencia.read_text(encoding="utf-8") if a.referencia else None
    correcoes = a.correcoes.read_text(encoding="utf-8") if a.correcoes else None
    try:
        processar(
            paginas,
            a.saida,
            titulo,
            a.perfil,
            referencia,
            not a.sem_ortografia,
            a.idioma,
            correcoes,
        )
    except ErroCorrecao as e:
        # Nada é gravado: um texto.txt sem parte da revisão pareceria revisado.
        print(f"correções que não se aplicam:\n{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
