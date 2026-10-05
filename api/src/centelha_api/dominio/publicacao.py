from datetime import UTC, datetime

from ..models import Edicao, EstadoCapitulo, StatusDireitos


class PublicacaoBloqueada(Exception):
    pass


def publicar_edicao(edicao: Edicao, agora: datetime | None = None) -> None:
    """Só publica edição com direitos aprovados e todos os capítulos com áudio revisado."""
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
    for c in edicao.capitulos:
        c.estado = EstadoCapitulo.PUBLICADO
    edicao.publicada_em = agora or datetime.now(UTC)
