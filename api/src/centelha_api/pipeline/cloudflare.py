"""Purga do cache da Cloudflare por URL (API v4, purge_cache com "files")."""

import json
import logging
import urllib.request

from ..config import get_settings

log = logging.getLogger(__name__)

# Limite da Cloudflare por pedido de purga por URL.
LOTE = 30


class ErroPurga(Exception):
    pass


def configurada() -> bool:
    cfg = get_settings()
    return bool(cfg.cloudflare_zona and cfg.cloudflare_token)


def purgar(urls: list[str]) -> bool:
    """Tira as URLs do cache. False sem zona e token configurados; ErroPurga se a
    Cloudflare recusar."""
    if not urls or not configurada():
        return False
    cfg = get_settings()
    endereco = f"https://api.cloudflare.com/client/v4/zones/{cfg.cloudflare_zona}/purge_cache"
    for i in range(0, len(urls), LOTE):
        pedido = urllib.request.Request(
            endereco,
            data=json.dumps({"files": urls[i : i + LOTE]}).encode(),
            headers={
                "Authorization": f"Bearer {cfg.cloudflare_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(pedido, timeout=20) as r:  # noqa: S310 (endereço fixo)
                corpo = json.load(r)
        except OSError as e:
            raise ErroPurga(f"Cloudflare sem resposta: {e}") from e
        if not corpo.get("success"):
            raise ErroPurga(f"Cloudflare recusou a purga: {corpo.get('errors')}")
    return True
