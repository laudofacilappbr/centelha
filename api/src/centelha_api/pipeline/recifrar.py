"""Cifra as faixas .m4a que já existem (#73, ADR 0004).

    docker compose -f docker-compose.prod.yml exec worker \
        python -m centelha_api.pipeline.recifrar [--simular] [--limite 50]

Roda no worker, que tem o volume do áudio e a chave-mestra. Para cada faixa aberta,
de qualquer versão: grava o .cent ao lado, confere que ele volta ao mesmo .m4a,
atualiza a faixa e faz o commit; só então apaga o .m4a e pede à Cloudflare para tirar
do cache o arquivo antigo e o JSON do capítulo. Pode ser interrompido e rodado de novo:
faixa já cifrada fica como está. Ligue CENTELHA_AUDIO_CIFRAR antes, para o worker não
gerar mais .m4a enquanto isto roda.
"""

import argparse
import logging
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal
from ..models import FaixaAudio
from . import cifra, cloudflare
from .armazenamento import Armazenamento, armazenamento_padrao

log = logging.getLogger(__name__)


@dataclass
class Resultado:
    cifradas: int = 0
    puladas: list[str] = field(default_factory=list)
    a_purgar: list[str] = field(default_factory=list)


def _relativo(url: str) -> str | None:
    """Chave do arquivo no armazenamento local; None se a URL não é dele."""
    base = get_settings().audio_url_base.rstrip("/") + "/"
    return url[len(base) :] if url.startswith(base) else None


def recifrar_faixa(
    session: Session, faixa: FaixaAudio, armazenamento: Armazenamento, mestra: bytes
) -> list[str]:
    """Cifra uma faixa .m4a e devolve as URLs a purgar. ValueError se não dá."""
    rel = _relativo(faixa.url)
    if rel is None or not rel.endswith(".m4a"):
        raise ValueError(f"faixa {faixa.id}: {faixa.url} fora do armazenamento local")
    antigo = Path(get_settings().audio_dir) / rel
    claro = antigo.read_bytes()
    chave = cifra.nova_chave()
    cifrado = cifra.cifrar(claro, chave)
    # Conferência antes de apagar o único arquivo aberto.
    if cifra.decifrar(cifrado, chave) != claro:
        raise ValueError(f"faixa {faixa.id}: o .cent não volta ao .m4a")
    with tempfile.TemporaryDirectory() as tmp:
        arquivo = Path(tmp) / "faixa.cent"
        arquivo.write_bytes(cifrado)
        url = armazenamento.salvar(arquivo, rel[: -len(".m4a")] + ".cent")
    url_antiga = faixa.url
    faixa.url = url
    faixa.formato = cifra.FORMATO
    faixa.chave_cifrada = cifra.embrulhar(chave, mestra)
    session.commit()
    # Depois do commit: se o processo morrer antes, sobra só um .m4a órfão no disco.
    antigo.unlink(missing_ok=True)
    purgar = [url_antiga]
    api = get_settings().api_url_publica.rstrip("/")
    if api:
        purgar.append(f"{api}/v1/capitulos/{faixa.capitulo_id}")
    return purgar


def recifrar(
    session: Session,
    armazenamento: Armazenamento,
    mestra: bytes,
    limite: int | None = None,
    simular: bool = False,
) -> Resultado:
    r = Resultado()
    consulta = select(FaixaAudio).where(FaixaAudio.formato == "m4a").order_by(FaixaAudio.id)
    if limite:
        consulta = consulta.limit(limite)
    for faixa in session.scalars(consulta).all():
        if simular:
            r.cifradas += 1
            continue
        try:
            r.a_purgar += recifrar_faixa(session, faixa, armazenamento, mestra)
            r.cifradas += 1
        except (OSError, ValueError, cifra.ErroCifra) as e:
            session.rollback()
            r.puladas.append(str(e))
    return r


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="recifrar", description=__doc__.splitlines()[0])
    p.add_argument("--simular", action="store_true", help="só conta o que seria cifrado")
    p.add_argument("--limite", type=int, help="no máximo N faixas nesta rodada")
    a = p.parse_args(argv)
    try:
        mestra = get_settings().chave_mestra()
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    with SessionLocal() as s:
        r = recifrar(s, armazenamento_padrao(), mestra, a.limite, a.simular)
    verbo = "seriam cifradas" if a.simular else "cifradas"
    print(f"{r.cifradas} faixas {verbo}; {len(r.puladas)} puladas")
    for motivo in r.puladas:
        print(f"  pulada: {motivo}")
    if r.a_purgar:
        try:
            if cloudflare.purgar(r.a_purgar):
                print(f"cache da Cloudflare purgado: {len(r.a_purgar)} URLs")
            else:
                print("sem CENTELHA_CLOUDFLARE_ZONA/TOKEN: purgue estas URLs no painel:")
                for u in r.a_purgar:
                    print(f"  {u}")
        except cloudflare.ErroPurga as e:
            print(f"{e}; purgue estas URLs no painel:", file=sys.stderr)
            for u in r.a_purgar:
                print(f"  {u}", file=sys.stderr)
            return 1
    return 1 if r.puladas else 0


if __name__ == "__main__":
    sys.exit(main())
