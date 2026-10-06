"""Monta um vídeo curto a partir de um trecho revisado (#44).

    centelha-video --capitulo 12 --questao 88 --saida videos/le-88
    centelha-video --capitulo 3 --segmentos 4-7 --saida videos/ese-c3 [--fundo cena.png]

Gera <saida>.mp4 (1080x1920) e <saida>.srt. A escolha do trecho é curadoria humana:
este comando só monta o que alguém escolheu.
"""

import argparse
import sys
import tempfile
import urllib.request
from pathlib import Path

from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..models import Capitulo, EstadoCapitulo, FaixaAudio, Publico, Segmento
from .audio import ErroPosProducao
from .video import ErroVideo, TrechoLegenda, montar_video

# Só trecho cujo áudio passou pela revisão humana vai para a rede.
ESTADOS_PERMITIDOS = {EstadoCapitulo.AUDIO_REVISADO, EstadoCapitulo.PUBLICADO}
CHAMADA = "Ouça o capítulo completo no app Centelha"


def _arquivo_local(url: str, tmp: Path) -> Path:
    """Arquivo da faixa: direto do disco quando é o armazenamento local, senão baixa."""
    cfg = get_settings()
    base = cfg.audio_url_base.rstrip("/") + "/"
    if url.startswith(base):
        caminho = Path(cfg.audio_dir) / url[len(base) :]
        if caminho.exists():
            return caminho
    destino = tmp / Path(url).name
    urllib.request.urlretrieve(url, destino)  # noqa: S310 (URL vem do próprio banco)
    return destino


def _segmentos(session, capitulo: Capitulo, questao: int | None, faixa: str | None):
    consulta = select(Segmento).where(Segmento.capitulo_id == capitulo.id)
    if questao is not None:
        consulta = consulta.where(Segmento.numero_questao == questao)
    if faixa:
        a, _, b = faixa.partition("-")
        consulta = consulta.where(Segmento.ordem.between(int(a), int(b or a)))
    return session.scalars(consulta.order_by(Segmento.ordem)).all()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="centelha-video", description=__doc__.splitlines()[0])
    p.add_argument("--capitulo", type=int, required=True)
    grupo = p.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--questao", type=int, help="todos os segmentos da questão (88 e 88a)")
    grupo.add_argument("--segmentos", help="faixa de ordens no capítulo, ex.: 4-7")
    p.add_argument("--saida", type=Path, required=True)
    p.add_argument("--fundo", type=Path, help="imagem de fundo; sem ela, azul-noite liso")
    p.add_argument("--sem-chamada", action="store_true")
    a = p.parse_args(argv)

    with SessionLocal() as s:
        capitulo = s.get(Capitulo, a.capitulo)
        if capitulo is None:
            print("capítulo não encontrado", file=sys.stderr)
            return 1
        if capitulo.estado not in ESTADOS_PERMITIDOS:
            print(
                f"capítulo em '{capitulo.estado.value}': só trecho com áudio revisado vira vídeo",
                file=sys.stderr,
            )
            return 1
        faixa = s.scalar(
            select(FaixaAudio)
            .where(FaixaAudio.capitulo_id == capitulo.id)
            .order_by(FaixaAudio.versao.desc(), FaixaAudio.id.desc())
            .limit(1)
        )
        segs = _segmentos(s, capitulo, a.questao, a.segmentos)
        if faixa is None or not segs:
            print("sem faixa de áudio ou sem segmentos nesse trecho", file=sys.stderr)
            return 1
        tempos = {m["segmento_id"]: m for m in faixa.marcacoes}
        sem_tempo = [x.ordem for x in segs if x.id not in tempos]
        if sem_tempo:
            print(f"segmentos sem marcação de tempo: {sem_tempo}", file=sys.stderr)
            return 1
        trechos = [
            TrechoLegenda(x.texto, tempos[x.id]["inicio_ms"], tempos[x.id]["fim_ms"]) for x in segs
        ]
        edicao = capitulo.edicao
        referencia = (
            f"{edicao.titulo}, questão {a.questao}"
            if a.questao is not None
            else f"{edicao.titulo} · {capitulo.titulo}"
        )
        # Perfil infantil: nenhuma chamada para baixar app nem link externo (CLAUDE.md).
        infantil = edicao.publico == Publico.INFANTIL
        chamada = None if (a.sem_chamada or infantil) else CHAMADA

        with tempfile.TemporaryDirectory() as tmp:
            audio = _arquivo_local(faixa.url, Path(tmp))
            try:
                video = montar_video(audio, trechos, referencia, chamada, a.saida, a.fundo)
            except (ErroVideo, ErroPosProducao) as e:
                print(str(e), file=sys.stderr)
                return 1
    print(
        f"{video} e {video.with_suffix('.srt')}" + (" (sem chamada: infantil)" if infantil else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
