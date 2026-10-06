"""Logs estruturados, id de requisição e Sentry opcional, para API e worker.

Logs vão para stdout em JSON (uma linha por evento); o Docker guarda com rotação e
`docker compose logs` lê. Cada linha leva o contexto do momento: request_id na API,
job_id e capitulo_id no worker, para cruzar com o que o admin mostra.

Sentry fica desligado sem CENTELHA_SENTRY_DSN. Ligar põe um terceiro recebendo dados
(subprocessador na LGPD): é decisão do dono, e a política de privacidade precisa citar.
"""

import json
import logging
import re
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime

from .config import get_settings

_contexto: ContextVar[dict[str, object]] = ContextVar("contexto_log", default={})  # noqa: B039

log_acesso = logging.getLogger("centelha.acesso")


@contextmanager
def contexto(**campos: object) -> Iterator[None]:
    """Acrescenta campos a todas as linhas de log dentro do bloco."""
    token = _contexto.set({**_contexto.get(), **campos})
    try:
        yield
    finally:
        _contexto.reset(token)


class FormatoJSON(logging.Formatter):
    def __init__(self, servico: str):
        super().__init__()
        self.servico = servico

    def format(self, registro: logging.LogRecord) -> str:
        linha: dict[str, object] = {
            "ts": datetime.fromtimestamp(registro.created, UTC).isoformat(timespec="milliseconds"),
            "nivel": registro.levelname.lower(),
            "servico": self.servico,
            "logger": registro.name,
            "msg": registro.getMessage(),
            **_contexto.get(),
        }
        extra = getattr(registro, "campos", None)
        if isinstance(extra, dict):
            linha.update(extra)
        if registro.exc_info:
            linha["erro"] = self.formatException(registro.exc_info)
        return json.dumps(linha, ensure_ascii=False, default=str)


class _SaidaPadrao(logging.StreamHandler):
    """Escreve no sys.stdout do momento, não no que existia quando foi criado."""

    def __init__(self):
        super().__init__()

    @property
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, _valor):
        pass


def configurar_logs(servico: str) -> None:
    """Idempotente: troca só o handler que ela mesma instalou, sem mexer nos de outros."""
    cfg = get_settings()
    raiz = logging.getLogger()
    for h in [h for h in raiz.handlers if isinstance(h, _SaidaPadrao)]:
        raiz.removeHandler(h)
    saida = _SaidaPadrao()
    if cfg.log_formato == "json":
        saida.setFormatter(FormatoJSON(servico))
    else:
        saida.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    raiz.addHandler(saida)
    raiz.setLevel(cfg.log_nivel.upper())
    # O log de acesso é nosso (com request_id); o do uvicorn sairia duplicado.
    logging.getLogger("uvicorn.access").disabled = True
    configurar_sentry(servico)


# --- id de requisição e log de acesso -----------------------------------------------------

# Só aceita id de fora se parecer um id; qualquer outra coisa é trocada (evita log
# injection e ids gigantes vindos do cliente).
_ID_VALIDO = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_SEM_LOG = {"/health"}


class MiddlewareRequisicao:
    """ASGI puro: não bufferiza resposta (ok para streaming)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        cabecalhos = dict(scope.get("headers") or [])
        recebido = (cabecalhos.get(b"x-request-id") or b"").decode("latin-1")
        # Atrás da Cloudflare, o cf-ray liga o nosso log ao painel dela.
        cf_ray = (cabecalhos.get(b"cf-ray") or b"").decode("latin-1")
        request_id = next((v for v in (recebido, cf_ray) if _ID_VALIDO.match(v)), uuid.uuid4().hex)
        status = 500
        inicio = time.perf_counter()

        async def enviar(mensagem):
            nonlocal status
            if mensagem["type"] == "http.response.start":
                status = mensagem["status"]
                mensagem["headers"] = [
                    *mensagem.get("headers", []),
                    (b"x-request-id", request_id.encode()),
                ]
            await send(mensagem)

        with contexto(request_id=request_id):
            try:
                await self.app(scope, receive, enviar)
            finally:
                if scope["path"] not in _SEM_LOG:
                    # Sem IP e sem query string: o IP já fica na Cloudflare, e query
                    # pode carregar dado pessoal. Minimização (LGPD).
                    log_acesso.info(
                        "%s %s %s",
                        scope["method"],
                        scope["path"],
                        status,
                        extra={
                            "campos": {
                                "metodo": scope["method"],
                                "caminho": scope["path"],
                                "status": status,
                                "duracao_ms": round((time.perf_counter() - inicio) * 1000, 1),
                            }
                        },
                    )


# --- Sentry --------------------------------------------------------------------------------

_SENSIVEIS = {"authorization", "cookie", "set-cookie", "x-api-key", "x-goog-api-key"}
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def limpar_evento(evento: dict, _hint: dict | None = None) -> dict:
    """Tira credenciais e e-mails antes de o evento sair para o Sentry."""
    requisicao = evento.get("request") or {}
    cabecalhos = requisicao.get("headers") or {}
    for chave in list(cabecalhos):
        if chave.lower() in _SENSIVEIS:
            cabecalhos[chave] = "[removido]"
    requisicao.pop("cookies", None)
    requisicao.pop("data", None)
    if isinstance(evento.get("message"), str):
        evento["message"] = _EMAIL.sub("[email]", evento["message"])
    for excecao in (evento.get("exception") or {}).get("values", []):
        if isinstance(excecao.get("value"), str):
            excecao["value"] = _EMAIL.sub("[email]", excecao["value"])
    evento.pop("user", None)
    return evento


def configurar_sentry(servico: str) -> bool:
    cfg = get_settings()
    if not cfg.sentry_dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=cfg.sentry_dsn,
        environment=cfg.ambiente,
        server_name=servico,
        send_default_pii=False,
        traces_sample_rate=0.0,
        before_send=limpar_evento,
    )
    return True
