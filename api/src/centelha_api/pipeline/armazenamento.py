"""Onde ficam os arquivos de áudio.

v1: pasta local (volume Docker) servida pelo Caddy em audio.{domínio}, com a Cloudflare
fazendo cache. Para mover para S3/R2 basta outra classe com o mesmo método.
"""

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..config import get_settings

_CHAVE_VALIDA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


class Armazenamento(Protocol):
    def salvar(self, origem: Path, chave: str) -> str:
        """Copia o arquivo para a chave e devolve a URL pública."""
        ...


@dataclass
class ArmazenamentoLocal:
    raiz: Path
    url_base: str

    def salvar(self, origem: Path, chave: str) -> str:
        # Chave vem do código, mas uma referência canônica malformada não pode escrever
        # fora da pasta do áudio.
        if not _CHAVE_VALIDA.match(chave) or ".." in chave.split("/"):
            raise ValueError(f"chave inválida: {chave!r}")
        destino = self.raiz / chave
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_suffix(destino.suffix + ".parcial")
        shutil.copyfile(origem, temporario)
        # Troca atômica: o Caddy nunca serve arquivo pela metade.
        temporario.replace(destino)
        return f"{self.url_base.rstrip('/')}/{chave}"


def armazenamento_padrao() -> Armazenamento:
    cfg = get_settings()
    return ArmazenamentoLocal(Path(cfg.audio_dir), cfg.audio_url_base)
