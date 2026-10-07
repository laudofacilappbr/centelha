"""Exportação aberta de uma edição para quem pediu por acessibilidade (ADR 0004, 3B).

    python -m centelha_api.pipeline.exportar --edicao 3 --saida /tmp/exportacao --pedido S-2026-014

O app é acessível por inteiro; quem precisa de outro player pede ao suporte, e o
suporte roda este comando. Grava os capítulos publicados da edição em .m4a aberto
(a .cent é decifrada só aqui), numerados na ordem, e um LEIAME com o uso pessoal e o
número do pedido. Procedimento em docs/suporte/exportacao-acessibilidade.md.

Só sai o que o catálogo público mostraria: edição publicada com direitos aprovados,
capítulo publicado e faixa de motor com licença liberada. Nada aqui contorna isso.
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

from sqlalchemy import select

from ..db import SessionLocal
from ..dominio.publicacao import faixa_atual
from ..models import Capitulo, Edicao, EstadoCapitulo, StatusDireitos
from . import cifra
from .faixa import audio_aberto

LEIAME = """\
{titulo}
{autor}{tradutor}

Exportação para uso pessoal, feita a pedido por acessibilidade (pedido {pedido}).
Os arquivos são o mesmo áudio do app Centelha, em formato aberto, para tocar em
qualquer player. Não redistribua: o texto pode ter direitos de tradução, e o
Centelha só o oferece dentro do app.

Narração gerada por voz sintética e revisada por pessoas.
Fonte do texto: {fonte}
"""


class ErroExportacao(Exception):
    pass


def _nome(texto: str) -> str:
    """Nome de arquivo seguro em qualquer sistema: sem acento, sem barra, curto."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", sem_acento).strip("-").lower()[:60] or "capitulo"


def exportar(session, edicao_id: int, saida: Path, pedido: str) -> list[Path]:
    edicao = session.get(Edicao, edicao_id)
    if edicao is None:
        raise ErroExportacao("edição não encontrada")
    if edicao.publicada_em is None or (
        edicao.direitos is None or edicao.direitos.status != StatusDireitos.APROVADO
    ):
        raise ErroExportacao("só edição publicada, com direitos aprovados, é exportada")
    capitulos = session.scalars(
        select(Capitulo)
        .where(Capitulo.edicao_id == edicao.id, Capitulo.estado == EstadoCapitulo.PUBLICADO)
        .order_by(Capitulo.ordem)
    ).all()
    faixas = [(c, session.scalar(faixa_atual(c.id))) for c in capitulos]
    faixas = [(c, f) for c, f in faixas if f is not None]
    if not faixas:
        raise ErroExportacao("edição sem capítulo publicado com áudio")

    saida.mkdir(parents=True, exist_ok=True)
    largura = len(str(len(faixas)))
    gravados = []
    for i, (capitulo, faixa) in enumerate(faixas, 1):
        destino = saida / f"{i:0{largura}d}-{_nome(capitulo.titulo)}.m4a"
        destino.write_bytes(audio_aberto(faixa))
        gravados.append(destino)
    (saida / "LEIAME.txt").write_text(
        LEIAME.format(
            titulo=edicao.titulo,
            autor=edicao.obra.autor,
            tradutor=f" · tradução de {edicao.tradutor}" if edicao.tradutor else "",
            pedido=pedido,
            fonte=edicao.fonte,
        ),
        encoding="utf-8",
    )
    return gravados


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--edicao", type=int, required=True)
    p.add_argument("--saida", type=Path, required=True)
    p.add_argument("--pedido", required=True, help="número do pedido no suporte, vai no LEIAME")
    a = p.parse_args(argv)
    with SessionLocal() as s:
        try:
            arquivos = exportar(s, a.edicao, a.saida, a.pedido)
        except (ErroExportacao, ValueError, cifra.ErroCifra) as e:
            print(str(e), file=sys.stderr)
            return 1
    print(f"{len(arquivos)} capítulos em {a.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
