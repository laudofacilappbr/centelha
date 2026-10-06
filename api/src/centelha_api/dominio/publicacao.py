from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import object_session

from ..config import get_settings
from ..models import Edicao, EstadoCapitulo, FaixaAudio, StatusDireitos, Voz


class PublicacaoBloqueada(Exception):
    pass


def faixa_atual(capitulo_id: int) -> Select[tuple[FaixaAudio]]:
    """A versão mais recente da faixa que pode ir ao ar. Faixa de motor sem licença
    liberada não conta: nem para publicar, nem para o catálogo entregar."""
    return (
        select(FaixaAudio)
        .join(Voz, Voz.id == FaixaAudio.voz_id)
        .where(
            FaixaAudio.capitulo_id == capitulo_id,
            Voz.motor.not_in(get_settings().tts_motores_sem_licenca),
        )
        .order_by(FaixaAudio.versao.desc(), FaixaAudio.id.desc())
        .limit(1)
    )


def _motores_sem_licenca(edicao: Edicao) -> list[int]:
    """Capítulos cuja faixa mais recente é de motor sem licença liberada."""
    bloqueados = get_settings().tts_motores_sem_licenca
    session = object_session(edicao)
    if not bloqueados or session is None:
        return []
    ordens = []
    for c in edicao.capitulos:
        motor = session.scalar(
            select(Voz.motor)
            .join(FaixaAudio, FaixaAudio.voz_id == Voz.id)
            .where(FaixaAudio.capitulo_id == c.id)
            .order_by(FaixaAudio.versao.desc(), FaixaAudio.id.desc())
            .limit(1)
        )
        if motor in bloqueados:
            ordens.append(c.ordem)
    return ordens


def publicar_edicao(edicao: Edicao, agora: datetime | None = None) -> None:
    """Só publica edição com direitos aprovados, todos os capítulos com áudio revisado e
    nenhum áudio de motor sem licença liberada."""
    if edicao.direitos is None or edicao.direitos.status != StatusDireitos.APROVADO:
        raise PublicacaoBloqueada("edição sem direitos aprovados")
    if not edicao.capitulos:
        raise PublicacaoBloqueada("edição sem capítulos")
    pendentes = [
        c.ordem
        for c in edicao.capitulos
        if c.estado not in (EstadoCapitulo.AUDIO_REVISADO, EstadoCapitulo.PUBLICADO)
    ]
    if pendentes:
        raise PublicacaoBloqueada(f"capítulos sem áudio revisado: {pendentes}")
    if sem_licenca := _motores_sem_licenca(edicao):
        raise PublicacaoBloqueada(
            f"capítulos com áudio de motor sem licença liberada (#1, #3): {sem_licenca}"
        )
    for c in edicao.capitulos:
        c.estado = EstadoCapitulo.PUBLICADO
    edicao.publicada_em = agora or datetime.now(UTC)
