"""Versões do áudio de cada capítulo e custo de TTS por edição.

Os caracteres vêm dos jobs concluídos (o que de fato foi enviado ao motor). O custo é
estimativa: caracteres × preço por milhão configurado em CENTELHA_TTS_PRECO_POR_MILHAO.
Preço de provedor muda e varia por contrato, por isso não há valor no código; sem preço
configurado para o motor, o custo sai nulo e só os caracteres aparecem. A conta real é a
fatura do provedor.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_session
from ..dominio.permissoes import Permissao
from ..models import Capitulo, Edicao, EstadoJob, FaixaAudio, JobAudio, Usuario
from .admin import exigir, pode_ver_admin

router = APIRouter(prefix="/v1/admin", tags=["admin"])
pode_ver_custos = exigir(Permissao.VER_CUSTOS)


class VersaoAudio(BaseModel):
    faixa_id: int
    versao: int
    url: str
    duracao_ms: int
    criado_em: datetime
    atual: bool
    job_id: int | None
    motor: str | None
    caracteres: int | None


@router.get("/capitulos/{capitulo_id}/faixas")
def versoes_audio(
    capitulo_id: int,
    _: Usuario = Depends(pode_ver_admin),
    session: Session = Depends(get_session),
) -> list[VersaoAudio]:
    """Todas as versões, da mais nova para a mais antiga. Regenerar nunca apaga a
    anterior: é possível ouvir e comparar antes de aprovar a nova."""
    if session.get(Capitulo, capitulo_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "capítulo não encontrado")
    linhas = session.execute(
        select(FaixaAudio, JobAudio)
        .outerjoin(JobAudio, JobAudio.faixa_id == FaixaAudio.id)
        .where(FaixaAudio.capitulo_id == capitulo_id)
        .order_by(FaixaAudio.versao.desc(), FaixaAudio.id.desc())
    ).all()
    return [
        VersaoAudio(
            faixa_id=f.id,
            versao=f.versao,
            url=f.url,
            duracao_ms=f.duracao_ms,
            criado_em=f.criado_em,
            # A API pública entrega a de maior versão; é essa a "atual".
            atual=i == 0,
            job_id=j.id if j else None,
            motor=j.motor if j else None,
            caracteres=j.caracteres if j else None,
        )
        for i, (f, j) in enumerate(linhas)
    ]


class CustoMotor(BaseModel):
    motor: str
    jobs: int
    caracteres: int
    preco_por_milhao: float | None
    custo_estimado: float | None


class CustoCapitulo(BaseModel):
    capitulo_id: int
    ordem: int
    titulo: str
    geracoes: int
    caracteres: int


class CustoEdicao(BaseModel):
    edicao_id: int
    titulo: str
    moeda: str
    caracteres: int
    # Nulo quando algum motor usado não tem preço configurado: somar só parte daria
    # um total que parece completo e não é.
    custo_estimado: float | None
    por_motor: list[CustoMotor]
    por_capitulo: list[CustoCapitulo]
    jobs_falhos: int


def _custo(motor: str, caracteres: int) -> tuple[float | None, float | None]:
    preco = get_settings().tts_preco_por_milhao.get(motor)
    if preco is None:
        return None, None
    return preco, round(caracteres * preco / 1_000_000, 4)


@router.get("/edicoes/{edicao_id}/custo")
def custo_edicao(
    edicao_id: int,
    _: Usuario = Depends(pode_ver_custos),
    session: Session = Depends(get_session),
) -> CustoEdicao:
    edicao = session.get(Edicao, edicao_id)
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "edição não encontrada")
    da_edicao = JobAudio.capitulo_id.in_(select(Capitulo.id).where(Capitulo.edicao_id == edicao_id))
    concluidos = da_edicao & (JobAudio.estado == EstadoJob.CONCLUIDO)

    por_motor = []
    for motor, jobs, caracteres in session.execute(
        select(JobAudio.motor, func.count(), func.coalesce(func.sum(JobAudio.caracteres), 0))
        .where(concluidos)
        .group_by(JobAudio.motor)
        .order_by(JobAudio.motor)
    ):
        preco, custo = _custo(motor, caracteres)
        por_motor.append(
            CustoMotor(
                motor=motor,
                jobs=jobs,
                caracteres=caracteres,
                preco_por_milhao=preco,
                custo_estimado=custo,
            )
        )

    por_capitulo = [
        CustoCapitulo(capitulo_id=cid, ordem=ordem, titulo=titulo, geracoes=n, caracteres=c)
        for cid, ordem, titulo, n, c in session.execute(
            select(
                Capitulo.id,
                Capitulo.ordem,
                Capitulo.titulo,
                func.count(JobAudio.id),
                func.coalesce(func.sum(JobAudio.caracteres), 0),
            )
            .join(JobAudio, JobAudio.capitulo_id == Capitulo.id)
            .where(concluidos)
            .group_by(Capitulo.id)
            .order_by(Capitulo.ordem)
        )
    ]
    jobs_falhos = session.scalar(
        select(func.count()).where(da_edicao & (JobAudio.estado == EstadoJob.FALHOU))
    )
    custos = [m.custo_estimado for m in por_motor]
    return CustoEdicao(
        edicao_id=edicao.id,
        titulo=edicao.titulo,
        moeda=get_settings().tts_moeda,
        caracteres=sum(m.caracteres for m in por_motor),
        custo_estimado=None if None in custos else round(sum(custos), 4),
        por_motor=por_motor,
        por_capitulo=por_capitulo,
        jobs_falhos=jobs_falhos,
    )
