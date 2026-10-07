"""Conta opcional de quem lê (#43, decisão 1A): entrar por código no e-mail, sem senha.

POST   /v1/conta/codigo    {email}          manda o código; sempre 202
POST   /v1/conta/sessao    {email, codigo}  troca o código por um token de sessão
GET    /v1/conta                            a conta da sessão
GET    /v1/conta/exportar                   os dados guardados (LGPD art. 18, II e V)
POST   /v1/conta/sair                       revoga esta sessão
DELETE /v1/conta                            exclui a conta e tudo dela (LGPD art. 18, VI)

Só na conta com exportação liberada pelo suporte (#134, acessibilidade):
GET    /v1/conta/exportacao/capitulos/{id}  o capítulo em .m4a aberto, como anexo
GET    /v1/conta/exportacao/edicoes/{id}/leiame   o LEIAME com o pedido e o uso pessoal
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
from ..dominio import conta_leitor, exportacao_aberta
from ..models import Edicao, SessaoConta
from ..pipeline import cifra
from ..pipeline import exportar as exportacao
from ..pipeline.faixa import audio_aberto
from ..ratelimit import JanelaDeslizante, ip_do_cliente

router = APIRouter(prefix="/v1/conta", tags=["conta"])
limitador = JanelaDeslizante()
log = logging.getLogger(__name__)

_ASSUNTO = "Seu código de acesso ao Centelhar"
_TEXTO = """Seu código de acesso ao Centelhar: {codigo}

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
    # O app mostra "Baixar em formato aberto" só quando é True (#134).
    exportacao_aberta: bool = False


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
def ver(
    response: Response,
    sessao: SessaoConta = Depends(sessao_atual),
    session: Session = Depends(get_session),
) -> ContaOut:
    _sem_cache(response)
    liberada = exportacao_aberta.vigente(session, sessao.conta_id) is not None
    return ContaOut(email=sessao.conta.email, exportacao_aberta=liberada)


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


def _liberacao(session: Session, sessao: SessaoConta):
    liberacao = exportacao_aberta.vigente(session, sessao.conta_id)
    if liberacao is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "exportação aberta não liberada")
    return liberacao


@router.get("/exportacao/capitulos/{capitulo_id}")
def baixar_aberto(
    capitulo_id: int,
    sessao: SessaoConta = Depends(sessao_atual),
    session: Session = Depends(get_session),
) -> Response:
    """O mesmo áudio do app, decifrado a cada pedido: não há cópia aberta guardada em
    lugar nenhum. Só sai o que a exportação pelo suporte também entregaria."""
    liberacao = _liberacao(session, sessao)
    achado = exportacao.capitulo_exportavel(session, capitulo_id)
    if achado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "capítulo não encontrado")
    capitulo, faixa = achado
    if not exportacao_aberta.registrar_download(session, liberacao, faixa):
        session.rollback()
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "limite diário de downloads")
    try:
        dados = audio_aberto(faixa)
    except (ValueError, OSError, cifra.ErroCifra) as e:
        # Chave-mestra ausente ou trocada, arquivo que não abre ou armazenamento fora do
        # ar: erro do servidor, e o download não conta no limite.
        session.rollback()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "áudio indisponível") from e
    session.commit()
    nome = exportacao.nome_do_arquivo(
        capitulo, capitulo.ordem, len(str(len(capitulo.edicao.capitulos)))
    )
    return Response(
        dados,
        media_type="audio/mp4",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{nome}"',
        },
    )


@router.get("/exportacao/edicoes/{edicao_id}/leiame")
def leiame(
    edicao_id: int,
    sessao: SessaoConta = Depends(sessao_atual),
    session: Session = Depends(get_session),
) -> Response:
    liberacao = _liberacao(session, sessao)
    edicao = session.get(Edicao, edicao_id)
    if edicao is None or not exportacao.edicao_exportavel(edicao):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "edição não encontrada")
    return Response(
        exportacao.leiame(edicao, liberacao.pedido),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="LEIAME.txt"',
        },
    )
