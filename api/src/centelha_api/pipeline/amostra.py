"""Amostra aberta de uma questão, para o player da landing (ADR 0004).

    python -m centelha_api.pipeline.amostra --capitulo 12 --questao 88

Com a faixa cifrada, o site não toca o capítulo; a landing toca só a questão de
demonstração, num .m4a aberto e curto, cortado do áudio decifrado. Vai ao lado da
faixa, em caminho fixo (<faixa>.q<N>.m4a): o build do site acha a amostra pela URL da
faixa, sem coluna nova no banco. Regenerar o áudio cria faixa nova, sem amostra:
rode o comando de novo.

A escolha da questão é curadoria humana, como no vídeo (#44).
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..models import Capitulo, FaixaAudio, Segmento
from . import cifra
from .armazenamento import Armazenamento, armazenamento_padrao
from .audio import ffmpeg_exe
from .faixa import audio_aberto
from .video_cli import ESTADOS_PERMITIDOS

# Respiro antes e depois da questão, para a voz não começar nem terminar cortada.
MARGEM_MS = 150


class ErroAmostra(Exception):
    pass


def chave_da_amostra(url_faixa: str, questao: int) -> str:
    """Caminho da amostra no volume do áudio, derivado da URL da faixa."""
    base = get_settings().audio_url_base.rstrip("/") + "/"
    if not url_faixa.startswith(base):
        raise ErroAmostra("faixa fora do armazenamento local")
    relativo = url_faixa[len(base) :]
    raiz, _, _ = relativo.rpartition(".")
    return f"{raiz}.q{questao}.m4a"


def url_da_amostra(url_faixa: str, questao: int) -> str:
    """Mesma regra de site/src/lib/demo.ts (urlDaAmostra)."""
    raiz, _, _ = url_faixa.rpartition(".")
    return f"{raiz}.q{questao}.m4a"


def gerar(
    session,
    capitulo_id: int,
    questao: int,
    armazenamento: Armazenamento | None = None,
) -> str:
    """Corta a [questao] do áudio do capítulo e grava a amostra aberta. Devolve a URL."""
    capitulo = session.get(Capitulo, capitulo_id)
    if capitulo is None:
        raise ErroAmostra("capítulo não encontrado")
    if capitulo.estado not in ESTADOS_PERMITIDOS:
        raise ErroAmostra(f"capítulo em '{capitulo.estado.value}': só áudio revisado vira amostra")
    faixa = session.scalar(
        select(FaixaAudio)
        .where(FaixaAudio.capitulo_id == capitulo.id)
        .order_by(FaixaAudio.versao.desc(), FaixaAudio.id.desc())
        .limit(1)
    )
    if faixa is None:
        raise ErroAmostra("capítulo sem áudio")
    ids = set(
        session.scalars(
            select(Segmento.id).where(
                Segmento.capitulo_id == capitulo.id, Segmento.numero_questao == questao
            )
        )
    )
    tempos = [m for m in faixa.marcacoes if m["segmento_id"] in ids]
    if not ids or len(tempos) != len(ids):
        raise ErroAmostra(f"questão {questao} sem segmentos ou sem marcação de tempo")
    inicio = max(0, min(m["inicio_ms"] for m in tempos) - MARGEM_MS)
    fim = min(faixa.duracao_ms, max(m["fim_ms"] for m in tempos) + MARGEM_MS)

    chave = chave_da_amostra(faixa.url, questao)
    with tempfile.TemporaryDirectory() as tmp:
        claro = Path(tmp) / "capitulo.m4a"
        claro.write_bytes(audio_aberto(faixa))
        destino = Path(tmp) / "amostra.m4a"
        r = subprocess.run(
            [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
             "-ss", f"{inicio / 1000:.3f}", "-to", f"{fim / 1000:.3f}",
             "-i", str(claro), "-c:a", "aac", "-b:a", "96k",
             "-movflags", "+faststart", str(destino)],
            capture_output=True, text=True, encoding="utf-8",
        )  # fmt: skip
        if r.returncode != 0:
            raise ErroAmostra(f"ffmpeg: {r.stderr.strip()[:300]}")
        return (armazenamento or armazenamento_padrao()).salvar(destino, chave)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--capitulo", type=int, required=True)
    p.add_argument("--questao", type=int, required=True)
    a = p.parse_args(argv)
    with SessionLocal() as s:
        try:
            url = gerar(s, a.capitulo, a.questao)
        except (ErroAmostra, ValueError, cifra.ErroCifra) as e:
            print(str(e), file=sys.stderr)
            return 1
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
