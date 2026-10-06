"""Transparência: custos e arrecadação do mês (#36).

Admin lança os valores e publica o mês; o site e o app leem GET /v1/transparencia.
Os valores públicos são os lançados à mão (a fatura de cada fornecedor), não
estimativas: a estimativa de TTS aparece só no admin, como referência para lançar.
"""

import re
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..dominio import contas
from ..dominio.permissoes import Permissao
from ..models import (
    EstadoJob,
    JobAudio,
    LancamentoTransparencia,
    MesTransparencia,
    TipoLancamento,
    Usuario,
)
from ..ratelimit import ip_do_cliente
from .admin import exigir
from .admin_custos import _custo
from .catalogo import _cache

publico = APIRouter(prefix="/v1", tags=["site"])
admin = APIRouter(prefix="/v1/admin/transparencia", tags=["admin"])
pode_editar = exigir(Permissao.EDITAR_TRANSPARENCIA)

MES = Path(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", examples=["2026-10"])


def _mes(texto: str) -> date:
    ano, mes = map(int, re.match(r"(\d{4})-(\d{2})", texto).groups())
    return date(ano, mes, 1)


def _rotulo(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


# --- Esquemas ---------------------------------------------------------------


class Lancamento(BaseModel):
    tipo: TipoLancamento
    item: str = Field(min_length=1, max_length=120)
    valor_centavos: int = Field(ge=0, le=10**12)
    nota: str | None = Field(default=None, max_length=300)


class LancamentoSaida(Lancamento):
    id: int


class ItemPublico(BaseModel):
    item: str
    valor_centavos: int
    nota: str | None


class MesPublico(BaseModel):
    mes: str
    publicado_em: datetime
    custos: list[ItemPublico]
    arrecadacao: list[ItemPublico]
    total_custos_centavos: int
    total_arrecadacao_centavos: int


class EstimativaTTS(BaseModel):
    caracteres: int
    # Soma dos motores com preço configurado; None se algum motor usado não tem preço.
    custo_estimado: float | None


class MesAdmin(BaseModel):
    mes: str
    publicado_em: datetime | None
    lancamentos: list[LancamentoSaida]
    total_custos_centavos: int
    total_arrecadacao_centavos: int
    estimativa_tts: EstimativaTTS


def _totais(lancs) -> tuple[int, int]:
    custos = sum(x.valor_centavos for x in lancs if x.tipo == TipoLancamento.CUSTO)
    arrec = sum(x.valor_centavos for x in lancs if x.tipo == TipoLancamento.ARRECADACAO)
    return custos, arrec


def _estimativa_tts(session: Session, mes: date) -> EstimativaTTS:
    fim = date(mes.year + (mes.month == 12), mes.month % 12 + 1, 1)
    por_motor = session.execute(
        select(JobAudio.motor, func.coalesce(func.sum(JobAudio.caracteres), 0))
        .where(
            JobAudio.estado == EstadoJob.CONCLUIDO,
            JobAudio.concluido_em >= mes,
            JobAudio.concluido_em < fim,
        )
        .group_by(JobAudio.motor)
    ).all()
    total_car = sum(c for _, c in por_motor)
    custos = [_custo(m, c)[1] for m, c in por_motor]
    custo = None if any(c is None for c in custos) else round(sum(custos), 2)
    return EstimativaTTS(caracteres=total_car, custo_estimado=custo)


def _mes_admin(session: Session, m: MesTransparencia) -> MesAdmin:
    c, a = _totais(m.lancamentos)
    return MesAdmin(
        mes=_rotulo(m.mes),
        publicado_em=m.publicado_em,
        lancamentos=[
            LancamentoSaida.model_validate(x, from_attributes=True) for x in m.lancamentos
        ],
        total_custos_centavos=c,
        total_arrecadacao_centavos=a,
        estimativa_tts=_estimativa_tts(session, m.mes),
    )


def _editavel(m: MesTransparencia) -> None:
    # Mês publicado não muda em silêncio: para corrigir, despublica (fica no log),
    # corrige e publica de novo.
    if m.publicado_em is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{_rotulo(m.mes)} está publicado; despublique para corrigir"
        )


# --- Público ----------------------------------------------------------------


@publico.get("/transparencia")
def transparencia(response: Response, session: Session = Depends(get_session)) -> list[MesPublico]:
    """Meses publicados, do mais recente ao mais antigo."""
    _cache(response)
    meses = session.scalars(
        select(MesTransparencia)
        .where(MesTransparencia.publicado_em.is_not(None))
        .options(selectinload(MesTransparencia.lancamentos))
        .order_by(MesTransparencia.mes.desc())
    ).all()
    saida = []
    for m in meses:
        c, a = _totais(m.lancamentos)

        def itens(tipo, m=m):
            return [
                ItemPublico(item=x.item, valor_centavos=x.valor_centavos, nota=x.nota)
                for x in m.lancamentos
                if x.tipo == tipo
            ]

        saida.append(
            MesPublico(
                mes=_rotulo(m.mes),
                publicado_em=m.publicado_em,
                custos=itens(TipoLancamento.CUSTO),
                arrecadacao=itens(TipoLancamento.ARRECADACAO),
                total_custos_centavos=c,
                total_arrecadacao_centavos=a,
            )
        )
    return saida


# --- Admin ------------------------------------------------------------------


@admin.get("/meses")
def listar_meses(
    _: Usuario = Depends(pode_editar), session: Session = Depends(get_session)
) -> list[MesAdmin]:
    meses = session.scalars(
        select(MesTransparencia)
        .options(selectinload(MesTransparencia.lancamentos))
        .order_by(MesTransparencia.mes.desc())
    ).all()
    return [_mes_admin(session, m) for m in meses]


@admin.get("/meses/{mes}")
def ver_mes(
    mes: str = MES, _: Usuario = Depends(pode_editar), session: Session = Depends(get_session)
) -> MesAdmin:
    d = _mes(mes)
    m = session.get(MesTransparencia, d) or MesTransparencia(mes=d, lancamentos=[])
    return _mes_admin(session, m)


@admin.post("/meses/{mes}/lancamentos", status_code=status.HTTP_201_CREATED)
def lancar(
    dados: Lancamento,
    request: Request,
    mes: str = MES,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> LancamentoSaida:
    d = _mes(mes)
    m = session.get(MesTransparencia, d, with_for_update=True)
    if m is None:
        m = MesTransparencia(mes=d)
        session.add(m)
    _editavel(m)
    lanc = LancamentoTransparencia(mes_ref=m, **dados.model_dump())
    session.add(lanc)
    session.flush()
    contas.registrar(
        session,
        "transparencia_lancada",
        autor,
        "lancamento_transparencia",
        lanc.id,
        ip_do_cliente(request),
        mes=mes,
        **dados.model_dump(mode="json"),
    )
    session.commit()
    return LancamentoSaida.model_validate(lanc, from_attributes=True)


def _lancamento(session: Session, lancamento_id: int) -> LancamentoTransparencia:
    lanc = session.get(LancamentoTransparencia, lancamento_id)
    if lanc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "lançamento não encontrado")
    _editavel(session.get(MesTransparencia, lanc.mes, with_for_update=True))
    return lanc


@admin.put("/lancamentos/{lancamento_id}")
def corrigir(
    lancamento_id: int,
    dados: Lancamento,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> LancamentoSaida:
    lanc = _lancamento(session, lancamento_id)
    antes = Lancamento.model_validate(lanc, from_attributes=True).model_dump(mode="json")
    for k, v in dados.model_dump().items():
        setattr(lanc, k, v)
    contas.registrar(
        session,
        "transparencia_corrigida",
        autor,
        "lancamento_transparencia",
        lanc.id,
        ip_do_cliente(request),
        antes=antes,
        depois=dados.model_dump(mode="json"),
    )
    session.commit()
    return LancamentoSaida.model_validate(lanc, from_attributes=True)


@admin.delete("/lancamentos/{lancamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(
    lancamento_id: int,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> None:
    lanc = _lancamento(session, lancamento_id)
    contas.registrar(
        session,
        "transparencia_apagada",
        autor,
        "lancamento_transparencia",
        lanc.id,
        ip_do_cliente(request),
        **Lancamento.model_validate(lanc, from_attributes=True).model_dump(mode="json"),
    )
    session.delete(lanc)
    session.commit()


@admin.post("/meses/{mes}/publicar")
def publicar(
    request: Request,
    mes: str = MES,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> MesAdmin:
    m = session.get(MesTransparencia, _mes(mes), with_for_update=True)
    if m is None or not m.lancamentos:
        # Mês vazio publicado mostraria custo zero, que é falso.
        raise HTTPException(status.HTTP_409_CONFLICT, f"{mes} não tem lançamentos")
    _editavel(m)
    m.publicado_em = func.now()
    m.publicado_por_id = autor.id
    c, a = _totais(m.lancamentos)
    contas.registrar(
        session,
        "transparencia_publicada",
        autor,
        "mes_transparencia",
        None,
        ip_do_cliente(request),
        mes=mes,
        total_custos_centavos=c,
        total_arrecadacao_centavos=a,
    )
    session.commit()
    session.refresh(m)
    return _mes_admin(session, m)


@admin.post("/meses/{mes}/despublicar")
def despublicar(
    request: Request,
    mes: str = MES,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> MesAdmin:
    m = session.get(MesTransparencia, _mes(mes), with_for_update=True)
    if m is None or m.publicado_em is None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{mes} não está publicado")
    m.publicado_em = None
    m.publicado_por_id = None
    contas.registrar(
        session,
        "transparencia_despublicada",
        autor,
        "mes_transparencia",
        None,
        ip_do_cliente(request),
        mes=mes,
    )
    session.commit()
    return _mes_admin(session, m)
