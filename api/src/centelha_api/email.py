"""Envio de e-mail transacional: hoje, só o código de acesso da conta de quem lê (#43).

Provedor falso fora de produção: guarda as mensagens em memória (os testes leem) e põe
no log. Em produção não há falso: sem provedor configurado, enviar é erro, e o pedido de
código responde 503. Fingir que mandou deixaria a pessoa esperando um e-mail que não vem.
"""

import json
import logging
import urllib.request
from dataclasses import dataclass

from .config import get_settings

log = logging.getLogger(__name__)


class EnvioIndisponivel(Exception):
    pass


@dataclass
class Mensagem:
    para: str
    assunto: str
    texto: str


# Caixa do provedor falso.
enviadas: list[Mensagem] = []


def enviar(para: str, assunto: str, texto: str) -> None:
    cfg = get_settings()
    if cfg.email_provedor == "resend":
        _resend(Mensagem(para, assunto, texto))
        return
    if cfg.ambiente == "producao":
        raise EnvioIndisponivel("nenhum provedor de e-mail configurado (CENTELHA_EMAIL_PROVEDOR)")
    enviadas.append(Mensagem(para, assunto, texto))
    log.info("e-mail falso para %s: %s", para, assunto)


def _resend(m: Mensagem) -> None:
    cfg = get_settings()
    if not cfg.email_resend_chave or not cfg.email_remetente:
        raise EnvioIndisponivel("Resend sem chave ou sem remetente")
    pedido = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(
            {"from": cfg.email_remetente, "to": [m.para], "subject": m.assunto, "text": m.texto}
        ).encode(),
        headers={
            "Authorization": f"Bearer {cfg.email_resend_chave}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(pedido, timeout=15):  # noqa: S310 (URL fixa)
            pass
    except OSError as e:
        raise EnvioIndisponivel(f"Resend recusou o envio: {e}") from e
