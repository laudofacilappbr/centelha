"""Admin: gerar áudio do capítulo (#64), acompanhar a fila e ouvir a faixa.

Só enfileira; quem sintetiza é o worker (pipeline/worker.py). As regras de estado,
idioma da voz e job duplicado ficam em pipeline.jobs.enfileirar, não aqui.
"""

import re
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_session
from ..dominio.permissoes import Permissao
from ..models import Capitulo, EstadoJob, FaixaAudio, JobAudio, PapelVoz, Segmento, Usuario, Voz
from ..pipeline import cifra, jobs
from ..pipeline.faixa import audio_aberto
from .admin import exigir, pode_ver_admin

router = APIRouter(prefix="/v1/admin", tags=["admin"])
pode_gerar_audio = exigir(Permissao.GERAR_AUDIO)
pode_ouvir_audio = exigir(Permissao.OUVIR_AUDIO)
_INTERVALO = re.compile(r"^bytes=(\d*)-(\d*)$")


class VozSaida(BaseModel):
    id: int
    idioma: str
    motor: str
    voz_id: str
    papel: PapelVoz


class PedidoGeracao(BaseModel):
    voz_narrador_id: int
    # Vozes de pergunta e resposta: O Livro dos Espíritos usa duas (especificação).
    voz_pergunta_id: int | None = None
    voz_resposta_id: int | None = None


class JobSaida(BaseModel):
    id: int
    estado: EstadoJob
    motor: str
    tentativas: int
    erro: str | None
    caracteres: int | None
    faixa_id: int | None
    solicitado_por_id: int | None
    criado_em: datetime
    concluido_em: datetime | None


class JobCriado(JobSaida):
    # Tamanho do texto que vai ao TTS: os motores em nuvem cobram por caractere.
    caracteres_estimados: int


@router.get("/vozes")
def listar_vozes(
    idioma: str | None = None,
    _: Usuario = Depends(pode_ver_admin),
    session: Session = Depends(get_session),
) -> list[VozSaida]:
    consulta = select(Voz).order_by(Voz.idioma, Voz.motor, Voz.id)
    if idioma:
        consulta = consulta.where(Voz.idioma == idioma)
    return [VozSaida.model_validate(v, from_attributes=True) for v in session.scalars(consulta)]


@router.post("/capitulos/{capitulo_id}/gerar-audio", status_code=status.HTTP_202_ACCEPTED)
def gerar_audio(
    capitulo_id: int,
    pedido: PedidoGeracao,
    request: Request,
    usuario: Usuario = Depends(pode_gerar_audio),
    session: Session = Depends(get_session),
) -> JobCriado:
    # Trava o capítulo como as transições do fluxo editorial: um "reabrir texto" ou um
    # "despublicar" simultâneo espera, em vez de o job entrar com o estado já mudado.
    capitulo = session.scalar(select(Capitulo).where(Capitulo.id == capitulo_id).with_for_update())
    if capitulo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "capítulo não encontrado")

    ids = [pedido.voz_narrador_id, pedido.voz_pergunta_id, pedido.voz_resposta_id]
    vozes = {v.id: v for v in session.scalars(select(Voz).where(Voz.id.in_([i for i in ids if i])))}
    faltam = [i for i in ids if i and i not in vozes]
    if faltam:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"vozes inexistentes: {faltam}")
    narrador = vozes[pedido.voz_narrador_id]
    pergunta = vozes.get(pedido.voz_pergunta_id) if pedido.voz_pergunta_id else None
    resposta = vozes.get(pedido.voz_resposta_id) if pedido.voz_resposta_id else None
    # O motor sai da voz, não de um campo do pedido: pedir a voz de um motor a outro
    # só falharia no worker, depois de o job ter ocupado a vez na fila.
    motores = {v.motor for v in (narrador, pergunta, resposta) if v}
    if len(motores) > 1:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"vozes de motores diferentes: {sorted(motores)}",
        )

    caracteres = session.scalar(
        select(func.coalesce(func.sum(func.length(Segmento.texto)), 0)).where(
            Segmento.capitulo_id == capitulo.id
        )
    )
    try:
        job = jobs.enfileirar(
            session, capitulo, narrador.motor, narrador, pergunta, resposta, usuario
        )
    except jobs.JobRecusado as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    session.commit()
    return JobCriado(
        **JobSaida.model_validate(job, from_attributes=True).model_dump(),
        caracteres_estimados=caracteres,
    )


@router.get("/capitulos/{capitulo_id}/jobs")
def listar_jobs(
    capitulo_id: int,
    _: Usuario = Depends(pode_ver_admin),
    session: Session = Depends(get_session),
) -> list[JobSaida]:
    if session.get(Capitulo, capitulo_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "capítulo não encontrado")
    consulta = (
        select(JobAudio)
        .where(JobAudio.capitulo_id == capitulo_id)
        .order_by(JobAudio.id.desc())
        .limit(20)
    )
    return [JobSaida.model_validate(j, from_attributes=True) for j in session.scalars(consulta)]


@router.get("/faixas/{faixa_id}/audio")
def ouvir_faixa(
    faixa_id: int,
    range_: str | None = Header(default=None, alias="Range"),
    _: Usuario = Depends(pode_ouvir_audio),
    session: Session = Depends(get_session),
) -> Response:
    """Faixa aberta para a escuta de revisão, mesmo quando o publicado é .cent.

    É o mesmo áudio que o app toca, sem cópia aberta guardada em lugar nenhum: decifra a
    cada pedido e nunca fica em cache. Aceita Range de um intervalo, para o revisor
    pular para o ponto do erro.
    """
    faixa = session.get(FaixaAudio, faixa_id)
    if faixa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "faixa não encontrada")
    try:
        dados = audio_aberto(faixa)
    except (ValueError, cifra.ErroCifra) as e:
        # Chave-mestra ausente ou trocada, ou arquivo corrompido: erro do servidor.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "áudio indisponível") from e
    cabecalhos = {"Cache-Control": "no-store", "Accept-Ranges": "bytes"}
    total = len(dados)
    pedido = _INTERVALO.match(range_.strip()) if range_ else None
    if range_ and not pedido:
        # Vários intervalos ou unidade desconhecida: o arquivo inteiro também é resposta válida.
        return Response(dados, media_type="audio/mp4", headers=cabecalhos)
    if pedido:
        a, b = pedido.groups()
        if a:
            inicio, fim = int(a), min(int(b), total - 1) if b else total - 1
        elif b:
            inicio, fim = max(total - int(b), 0), total - 1
        else:
            inicio, fim = total, total - 1
        if inicio > fim:
            raise HTTPException(
                status.HTTP_416_RANGE_NOT_SATISFIABLE,
                "intervalo fora do arquivo",
                headers={**cabecalhos, "Content-Range": f"bytes */{total}"},
            )
        return Response(
            dados[inicio : fim + 1],
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            media_type="audio/mp4",
            headers={**cabecalhos, "Content-Range": f"bytes {inicio}-{fim}/{total}"},
        )
    return Response(dados, media_type="audio/mp4", headers=cabecalhos)
