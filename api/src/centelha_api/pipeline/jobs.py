"""Fila de geração de áudio no PostgreSQL.

enfileirar  → cria o job (um ativo por capítulo)
pegar       → worker reserva o próximo com FOR UPDATE SKIP LOCKED e um lease
executar    → gera, grava a faixa, avança o capítulo para "áudio gerado"
falhar      → volta à fila com espera crescente, até max_tentativas
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..dominio import editorial
from ..dominio.contas import registrar
from ..models import (
    Capitulo,
    EstadoCapitulo,
    EstadoJob,
    FaixaAudio,
    JobAudio,
    Pronuncia,
    Usuario,
    Voz,
)
from . import cifra
from .armazenamento import Armazenamento
from .pronuncia import EntradaPronuncia
from .tts.gerar import SegmentoParaVoz, Vozes, gerar_capitulo
from .tts.motores import Motor
from .tts.motores import motor as motor_por_nome


class JobRecusado(Exception):
    pass


def _agora():
    # Relógio do banco, não do processo: worker e banco em containers diferentes podem
    # ter relógios divergentes, e a fila compara datas gravadas pelo banco.
    return func.now()


def enfileirar(
    session: Session,
    capitulo: Capitulo,
    motor: str,
    narrador: Voz,
    pergunta: Voz | None = None,
    resposta: Voz | None = None,
    usuario: Usuario | None = None,
) -> JobAudio:
    # Regra no fluxo editorial: texto revisado, e na adaptação também a doutrina.
    if not editorial.pode_gerar_audio(capitulo):
        raise JobRecusado(
            f"capítulo {capitulo.id} em '{capitulo.estado.value}': "
            "áudio só sai de texto revisado, e na adaptação juvenil ou infantil de doutrina "
            "revisada (publicado exige despublicar antes)"
        )
    edicao = capitulo.edicao
    for voz in (narrador, pergunta, resposta):
        if voz is None:
            continue
        if voz.idioma != edicao.idioma:
            raise JobRecusado(f"voz {voz.id} é {voz.idioma}, capítulo é {edicao.idioma}")
        # Cada público tem a sua narração (especificação: infantil com voz calorosa e
        # ritmo lento, juvenil mais dinâmica); voz adulta numa história infantil passaria.
        if voz.publico != edicao.publico:
            raise JobRecusado(
                f"voz {voz.id} é do público {voz.publico.value}, a edição é {edicao.publico.value}"
            )
    motor_por_nome(motor)  # valida o nome cedo, não no worker
    job = JobAudio(
        capitulo_id=capitulo.id,
        motor=motor,
        voz_narrador_id=narrador.id,
        voz_pergunta_id=pergunta.id if pergunta else None,
        voz_resposta_id=resposta.id if resposta else None,
        solicitado_por_id=usuario.id if usuario else None,
    )
    session.add(job)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise JobRecusado(f"capítulo {capitulo.id} já tem geração na fila") from e
    registrar(
        session, "audio.enfileirar", usuario, "capitulo", capitulo.id, motor=motor, job=job.id
    )
    return job


def pegar(session: Session, agora: datetime | None = None) -> JobAudio | None:
    """Reserva o próximo job. Faz commit: a reserva precisa valer fora desta transação.
    `agora` só existe para testes; em produção vale o relógio do banco."""
    agora = agora if agora is not None else _agora()
    job = session.scalar(
        select(JobAudio)
        .where(
            or_(
                (JobAudio.estado == EstadoJob.PENDENTE) & (JobAudio.disponivel_em <= agora),
                # Worker que morreu: lease vencido volta a ser pegável.
                (JobAudio.estado == EstadoJob.EXECUTANDO) & (JobAudio.lease_ate < agora),
            )
        )
        .order_by(JobAudio.disponivel_em, JobAudio.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        session.rollback()
        return None
    job.estado = EstadoJob.EXECUTANDO
    job.tentativas += 1
    job.iniciado_em = agora
    job.lease_ate = agora + timedelta(minutes=get_settings().worker_lease_minutos)
    session.commit()
    return job


def _dicionario(session: Session, idioma: str) -> list[EntradaPronuncia]:
    linhas = session.scalars(select(Pronuncia).where(Pronuncia.idioma == idioma)).all()
    return [EntradaPronuncia(p.termo, p.substituicao, p.ipa) for p in linhas]


def executar(
    session: Session,
    job: JobAudio,
    armazenamento: Armazenamento,
    motor: Motor | None = None,
) -> FaixaAudio:
    capitulo = job.capitulo
    edicao = capitulo.edicao
    vozes_por_id = {
        v.id: v
        for v in session.scalars(
            select(Voz).where(
                Voz.id.in_(
                    [
                        i
                        for i in (job.voz_narrador_id, job.voz_pergunta_id, job.voz_resposta_id)
                        if i
                    ]
                )
            )
        )
    }

    def voz_id(i: int | None) -> str | None:
        return vozes_por_id[i].voz_id if i else None

    vozes = Vozes(
        voz_id(job.voz_narrador_id), voz_id(job.voz_pergunta_id), voz_id(job.voz_resposta_id)
    )
    segmentos = [SegmentoParaVoz(s.id, s.tipo, s.texto) for s in capitulo.segmentos]
    versao = (
        session.scalar(
            select(func.max(FaixaAudio.versao)).where(FaixaAudio.capitulo_id == capitulo.id)
        )
        or 0
    ) + 1
    settings = get_settings()
    # Cifrar exige a chave-mestra; falhar aqui, antes de gastar TTS, e não depois.
    mestra = settings.chave_mestra() if settings.audio_cifrar else None
    base = (
        f"{edicao.obra.sigla.lower()}/{edicao.idioma}/e{edicao.id}/"
        f"{capitulo.referencia_canonica.lower()}-v{versao}"
    )
    with tempfile.TemporaryDirectory() as tmp:
        resultado = gerar_capitulo(
            segmentos,
            motor or motor_por_nome(job.motor),
            vozes,
            _dicionario(session, edicao.idioma),
            Path(tmp) / "capitulo.m4a",
            idioma=edicao.idioma,
            modo=settings.tts_modo,
            limite_bloco_bytes=settings.tts_limite_bloco_bytes,
        )
        arquivo, formato, chave_cifrada = resultado.faixa.arquivo, "m4a", None
        if mestra is not None:
            chave_faixa = cifra.nova_chave()
            arquivo = Path(tmp) / "capitulo.cent"
            arquivo.write_bytes(cifra.cifrar(resultado.faixa.arquivo.read_bytes(), chave_faixa))
            formato, chave_cifrada = cifra.FORMATO, cifra.embrulhar(chave_faixa, mestra)
        url = armazenamento.salvar(arquivo, f"{base}.{'m4a' if formato == 'm4a' else 'cent'}")
    faixa = FaixaAudio(
        capitulo_id=capitulo.id,
        voz_id=job.voz_narrador_id,
        versao=versao,
        url=url,
        duracao_ms=resultado.faixa.duracao_ms,
        marcacoes=resultado.faixa.marcacoes,
        formato=formato,
        chave_cifrada=chave_cifrada,
    )
    session.add(faixa)
    session.flush()
    # Áudio novo sempre volta para revisão, mesmo que o anterior estivesse revisado.
    capitulo.estado = EstadoCapitulo.AUDIO_GERADO
    job.estado = EstadoJob.CONCLUIDO
    job.concluido_em = _agora()
    job.lease_ate = None
    job.caracteres = resultado.caracteres
    job.faixa_id = faixa.id
    job.erro = None
    registrar(
        session,
        "audio.gerado",
        None,
        "capitulo",
        capitulo.id,
        job=job.id,
        versao=versao,
        caracteres=resultado.caracteres,
    )
    session.commit()
    return faixa


def falhar(session: Session, job: JobAudio, erro: str, agora: datetime | None = None) -> None:
    session.rollback()
    job = session.get(JobAudio, job.id)
    agora = agora if agora is not None else _agora()
    job.erro = erro[-2000:]
    job.lease_ate = None
    if job.tentativas >= job.max_tentativas:
        job.estado = EstadoJob.FALHOU
        job.concluido_em = agora
    else:
        # 1, 4, 9 minutos: dá tempo de um provedor instável voltar.
        job.estado = EstadoJob.PENDENTE
        job.disponivel_em = agora + timedelta(minutes=job.tentativas**2)
    registrar(
        session, "audio.falhou", None, "capitulo", job.capitulo_id, job=job.id, erro=erro[:200]
    )
    session.commit()
