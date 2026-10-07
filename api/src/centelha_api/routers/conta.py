"""Conta opcional de quem lê (#43, decisão 1A): entrar por código no e-mail, sem senha.

POST   /v1/conta/codigo    {email}          manda o código; sempre 202
POST   /v1/conta/sessao    {email, codigo}  troca o código por um token de sessão
GET    /v1/conta                            a conta da sessão
GET    /v1/conta/exportar                   os dados guardados (LGPD art. 18, II e V)
POST   /v1/conta/sair                       revoga esta sessão
DELETE /v1/conta                            exclui a conta e tudo dela (LGPD art. 18, VI)
"""

import hashlib
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import email as correio
from ..config import get_settings
from ..db import get_session
from ..dominio import conta_leitor
from ..models import SessaoConta
from ..ratelimit import JanelaDeslizante, ip_do_cliente

router = APIRouter(prefix="/v1/conta", tags=["conta"])
limitador = JanelaDeslizante()
log = logging.getLogger(__name__)

_ASSUNTO = "Seu código de acesso ao Centelha"
_TEXTO = """Seu código de acesso ao Centelha: {codigo}

Digite-o no app. Ele vale por {minutos} minutos e só uma vez.

Se não foi você que pediu, ignore este e-mail: sem o código, ninguém entra.
"""


class PedidoCodigo(BaseModel):
    email: EmailStr = Field(max_length=320)


class Confirmacao(BaseModel):
    email: EmailStr = Field(max_length=320)
    codigo: str = Field(pattern=r"^\s*\d{6}\s*$")


class SessaoOut(BaseModel):
    token: str
    email: str


class ContaOut(BaseModel):
    email: str


def _sem_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def sessao_atual(
    authorization: str = Header(default=""), session: Session = Depends(get_session)
) -> SessaoConta:
    token = authorization.removeprefix("Bearer ").strip()
    sessao = conta_leitor.resolver_sessao(session, token) if token else None
    if sessao is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessão inválida ou expirada")
    return sessao


@router.post("/codigo", status_code=status.HTTP_202_ACCEPTED)
def pedir_codigo(
    dados: PedidoCodigo, request: Request, session: Session = Depends(get_session)
) -> dict[str, str]:
    cfg = get_settings()
    email = conta_leitor.normalizar(dados.email)
    # Por e-mail (não vira spam contra alguém) e por IP (não varre muitos e-mails).
    for chave in (f"email:{hashlib.sha256(email.encode()).hexdigest()}", ip_do_cliente(request)):
        if not limitador.permitir(chave, cfg.conta_codigo_limite, cfg.conta_codigo_janela_segundos):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, "muitos pedidos; tente mais tarde"
            )
    codigo = conta_leitor.novo_codigo(session, email)
    try:
        correio.enviar(
            email, _ASSUNTO, _TEXTO.format(codigo=codigo, minutos=cfg.conta_codigo_minutos)
        )
    except correio.EnvioIndisponivel as e:
        session.rollback()
        log.error("código de acesso não enviado: %s", e)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "envio de e-mail indisponível"
        ) from None
    session.commit()
    # Mesma resposta para e-mail com ou sem conta: não revela quem usa o app.
    return {"status": "enviado"}


@router.post("/sessao", response_model=SessaoOut)
def entrar(
    dados: Confirmacao, response: Response, session: Session = Depends(get_session)
) -> SessaoOut:
    _sem_cache(response)
    conta = conta_leitor.confirmar_codigo(session, dados.email, dados.codigo)
    if conta is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "código inválido ou expirado")
    token, _ = conta_leitor.criar_sessao(session, conta)
    session.commit()
    return SessaoOut(token=token, email=conta.email)


@router.get("", response_model=ContaOut)
def ver(response: Response, sessao: SessaoConta = Depends(sessao_atual)) -> ContaOut:
    _sem_cache(response)
    return ContaOut(email=sessao.conta.email)


@router.get("/exportar")
def exportar(
    response: Response,
    sessao: SessaoConta = Depends(sessao_atual),
    session: Session = Depends(get_session),
) -> dict:
    _sem_cache(response)
    return conta_leitor.exportar(session, sessao.conta.email) or {}


@router.post("/sair", status_code=status.HTTP_204_NO_CONTENT)
def sair(sessao: SessaoConta = Depends(sessao_atual), session: Session = Depends(get_session)):
    sessao.revogada_em = func.now()
    session.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def excluir(sessao: SessaoConta = Depends(sessao_atual), session: Session = Depends(get_session)):
    conta_leitor.excluir(session, sessao.conta.email)
    session.commit()
