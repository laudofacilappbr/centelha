"""Entrega da chave da faixa ao app atestado (ADR 0004, #73).

    POST /v1/dispositivos/desafio      → valor de uso único, vale minutos
    POST /v1/dispositivos              → atestado com o desafio dentro → token do aparelho
    POST /v1/faixas/{id}/chave         → com o token: chave da faixa .cent, válida 90 dias

O arquivo .cent é público na CDN; sem a chave ele é ilegível. A chave só sai para
aparelho que provou ser o app legítimo, até um limite por dia (contra raspagem).
"""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..atestacao import AtestacaoIndisponivel, AtestacaoRecusada, verificador
from ..config import get_settings
from ..db import get_session
from ..models import (
    Capitulo,
    DesafioAtestacao,
    Dispositivo,
    Edicao,
    EntregaChave,
    FaixaAudio,
)
from ..pipeline import cifra
from ..ratelimit import JanelaDeslizante, ip_do_cliente
from .catalogo import _publicado

router = APIRouter(prefix="/v1", tags=["app"])
limitador_desafio = JanelaDeslizante()


class DesafioOut(BaseModel):
    desafio: str
    expira_em: datetime


class Registro(BaseModel):
    plataforma: str = Field(max_length=10)
    desafio: str = Field(max_length=64)
    # Atestado do App Attest (CBOR em base64) ou token do Play Integrity.
    atestado: str = Field(max_length=20000)


class TokenOut(BaseModel):
    token: str


class ChaveOut(BaseModel):
    faixa_id: int
    versao: int
    formato: str
    # 32 bytes em base64: a chave AES-256 da faixa.
    chave: str
    # Depois disso o app precisa pedir de novo, online (decisão 2B).
    valida_ate: datetime


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/dispositivos/desafio", status_code=status.HTTP_201_CREATED)
def criar_desafio(request: Request, session: Session = Depends(get_session)) -> DesafioOut:
    cfg = get_settings()
    if not limitador_desafio.permitir(
        ip_do_cliente(request), cfg.desafio_limite_por_ip, cfg.desafio_janela_segundos
    ):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "muitas tentativas")
    desafio = DesafioAtestacao(
        valor=secrets.token_urlsafe(32),
        # Relógio do banco: o do container pode estar minutos à frente.
        expira_em=func.now() + timedelta(seconds=cfg.desafio_validade_segundos),
    )
    session.add(desafio)
    session.commit()
    return DesafioOut(desafio=desafio.valor, expira_em=desafio.expira_em)


@router.post("/dispositivos", status_code=status.HTTP_201_CREATED)
def registrar(dados: Registro, session: Session = Depends(get_session)) -> TokenOut:
    try:
        v = verificador(dados.plataforma, get_settings())
    except AtestacaoIndisponivel as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e
    except AtestacaoRecusada as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    # Consome o desafio antes de verificar: tentativa recusada também o gasta, e um
    # atestado capturado não serve de novo.
    consumido = session.scalar(
        update(DesafioAtestacao)
        .where(
            DesafioAtestacao.valor == dados.desafio,
            DesafioAtestacao.usado_em.is_(None),
            DesafioAtestacao.expira_em > func.now(),
        )
        .values(usado_em=func.now())
        .returning(DesafioAtestacao.id)
    )
    session.commit()
    if consumido is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "desafio inválido, usado ou vencido")
    try:
        resultado = v.verificar(dados.atestado, dados.desafio)
    except AtestacaoRecusada as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e

    token = secrets.token_urlsafe(32)
    session.add(
        Dispositivo(
            plataforma=dados.plataforma,
            token_hash=_hash(token),
            identificador=resultado.identificador,
        )
    )
    session.commit()
    return TokenOut(token=token)


def _dispositivo(session: Session, autorizacao: str | None) -> Dispositivo:
    esquema, _, token = (autorizacao or "").partition(" ")
    dispositivo = (
        session.scalar(
            select(Dispositivo).where(
                Dispositivo.token_hash == _hash(token), Dispositivo.revogado_em.is_(None)
            )
        )
        if esquema.lower() == "bearer" and token
        else None
    )
    if dispositivo is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "aparelho não registrado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return dispositivo


@router.post("/faixas/{faixa_id}/chave")
def entregar_chave(
    faixa_id: int,
    response: Response,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> ChaveOut:
    # A chave nunca fica em cache: nem na Cloudflare, nem em proxy no caminho.
    response.headers["Cache-Control"] = "no-store"
    cfg = get_settings()
    dispositivo = _dispositivo(session, authorization)
    faixa = session.scalar(
        select(FaixaAudio)
        .join(Capitulo, FaixaAudio.capitulo_id == Capitulo.id)
        .join(Edicao, Capitulo.edicao_id == Edicao.id)
        .where(FaixaAudio.id == faixa_id, _publicado())
    )
    if faixa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "faixa não encontrada")
    if faixa.chave_cifrada is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "faixa sem cifra: toca direto pela url")

    entregues = session.scalar(
        select(func.count(EntregaChave.id)).where(
            EntregaChave.dispositivo_id == dispositivo.id,
            EntregaChave.criado_em > func.now() - timedelta(days=1),
        )
    )
    if entregues >= cfg.chave_limite_por_dia:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "limite diário de chaves")

    try:
        chave = cifra.desembrulhar(faixa.chave_cifrada, cfg.chave_mestra())
    except (ValueError, cifra.ErroCifra) as e:
        # Chave-mestra ausente ou trocada: erro do servidor, não do app.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "chave indisponível") from e

    session.add(EntregaChave(dispositivo_id=dispositivo.id, faixa_id=faixa.id))
    dispositivo.ultimo_uso_em = func.now()
    valida_ate = session.scalar(select(func.now() + timedelta(days=cfg.chave_validade_dias)))
    session.commit()
    return ChaveOut(
        faixa_id=faixa.id,
        versao=faixa.versao,
        formato=faixa.formato,
        chave=base64.b64encode(chave).decode(),
        valida_ate=valida_ate,
    )
