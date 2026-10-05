"""Ingestão de uma obra pela linha de comando.

centelha-ingestao arquivo.epub --perfil perguntas            # só mostra o resumo
centelha-ingestao arquivo.epub --perfil perguntas --json saida.json
centelha-ingestao arquivo.epub --perfil perguntas --edicao-id 1 [--substituir]
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .estrutura import estruturar, resumo
from .leitores import ler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="centelha-ingestao", description=__doc__)
    parser.add_argument("arquivo", type=Path)
    parser.add_argument("--perfil", choices=["generico", "perguntas"], default="generico")
    parser.add_argument("--json", type=Path, help="grava a estrutura para revisão")
    parser.add_argument("--edicao-id", type=int, help="grava no banco nesta edição")
    parser.add_argument("--substituir", action="store_true")
    args = parser.parse_args(argv)

    capitulos = estruturar(ler(args.arquivo), args.perfil)
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
