"""Ingestão de uma obra pela linha de comando.

centelha-ingestao arquivo.epub --perfil perguntas            # só mostra o resumo
centelha-ingestao arquivo.epub --perfil perguntas --json saida.json
centelha-ingestao arquivo.epub --perfil perguntas --edicao-id 1 [--substituir]
centelha-ingestao arquivo.pdf --paginas 13-494 --cortar-em "Nota Especial" ...
centelha-ingestao texto.txt --comecar-em "PRÉFACE" --cortar-em "TABLE DES MATIÈRES" ...

EPUB do Wikisource (#45) é reconhecido sozinho. Para baixar:
https://ws-export.wmcloud.org/?lang=fr&page=Le_Livre_des_Esprits&format=epub-3
Na edição, a fonte credita a transcrição: "Didier, 1860 (2e édition). Transcription :
Wikisource." (docs/juridico/fichas/le-livre-des-esprits-fr.md).
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .estrutura import estruturar, resumo
from .leitores import comecar_em, cortar_em, ler


def _faixa(valor: str) -> tuple[int, int]:
    try:
        primeira, ultima = (int(x) for x in valor.split("-"))
    except ValueError:
        raise argparse.ArgumentTypeError("use primeira-última, ex.: 13-494") from None
    return primeira, ultima


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="centelha-ingestao", description=__doc__)
    parser.add_argument("arquivo", type=Path)
    parser.add_argument("--perfil", choices=["generico", "perguntas"], default="generico")
    parser.add_argument("--json", type=Path, help="grava a estrutura para revisão")
    parser.add_argument("--edicao-id", type=int, help="grava no banco nesta edição")
    parser.add_argument("--substituir", action="store_true")
    parser.add_argument(
        "--paginas",
        type=_faixa,
        help="PDF: primeira-última página da obra (deixa de fora folha de rosto, nota da "
        "editora, sumário e índice)",
    )
    parser.add_argument(
        "--comecar-em",
        metavar="TEXTO",
        help="descarta o que vem antes do parágrafo que começa com TEXTO (folha de rosto)",
    )
    parser.add_argument(
        "--cortar-em",
        metavar="TEXTO",
        help="descarta do parágrafo que começa com TEXTO em diante (nota da editora no fim)",
    )
    args = parser.parse_args(argv)

    paragrafos = ler(args.arquivo, args.paginas)
    if args.comecar_em:
        paragrafos = comecar_em(paragrafos, args.comecar_em)
    if args.cortar_em:
        paragrafos = cortar_em(paragrafos, args.cortar_em)
    capitulos = estruturar(paragrafos, args.perfil)
    print(json.dumps(resumo(capitulos), ensure_ascii=False, indent=2))

    if args.json:
        args.json.write_text(
            json.dumps([asdict(c) for c in capitulos], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"estrutura gravada em {args.json}", file=sys.stderr)

    if args.edicao_id is not None:
        from ...db import SessionLocal
        from ...models import Edicao
        from .importar import importar

        with SessionLocal() as session:
            edicao = session.get(Edicao, args.edicao_id)
            if edicao is None:
                print(f"edição {args.edicao_id} não existe", file=sys.stderr)
                return 1
            criados = importar(session, edicao, capitulos, substituir=args.substituir)
            session.commit()
            print(f"{len(criados)} capítulos gravados na edição {edicao.id}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
