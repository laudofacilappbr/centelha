"""Áudio aberto de uma faixa, para quem trabalha no servidor (vídeo, escuta no admin).

Com a cifragem ligada (ADR 0004) o arquivo publicado é .cent: o ffmpeg e o navegador
não o leem. Aqui a faixa volta a ser o .m4a, só em memória ou em pasta temporária.
"""

import urllib.request
from pathlib import Path

from ..config import get_settings
from ..models import FaixaAudio
from . import cifra


def _bytes_publicados(url: str) -> bytes:
    """Arquivo da faixa: direto do disco quando é o armazenamento local, senão baixa."""
    cfg = get_settings()
    base = cfg.audio_url_base.rstrip("/") + "/"
    if url.startswith(base):
        caminho = Path(cfg.audio_dir) / url[len(base) :]
        if caminho.exists():
            return caminho.read_bytes()
    with urllib.request.urlopen(url) as r:  # noqa: S310 (URL vem do próprio banco)
        return r.read()


def audio_aberto(faixa: FaixaAudio) -> bytes:
    """O .m4a da faixa, decifrado se for .cent.

    ErroCifra se o arquivo ou a chave não abrem; ValueError se falta a chave-mestra.
    """
    dados = _bytes_publicados(faixa.url)
    if faixa.formato != cifra.FORMATO:
        return dados
    if faixa.chave_cifrada is None:
        raise cifra.ErroCifra("faixa .cent sem chave")
    chave = cifra.desembrulhar(faixa.chave_cifrada, get_settings().chave_mestra())
    return cifra.decifrar(dados, chave)
