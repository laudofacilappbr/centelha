import pytest

from centelha_api.dominio.publicacao import PublicacaoBloqueada, publicar_edicao
from centelha_api.models import (
    Capitulo,
    Direitos,
    Edicao,
    EstadoCapitulo,
    Obra,
    StatusDireitos,
)


def _edicao(session, estados, status_direitos=None):
    obra = Obra(
        slug="o-livro-dos-espiritos",
        autor="Allan Kardec",
        titulo_original="Le Livre des Esprits",
        ano=1857,
        idioma_original="fr",
        sigla="LE",
    )
    edicao = Edicao(
        obra=obra,
        idioma="pt-BR",
        titulo="O Livro dos Espíritos",
        tradutor="Guillon Ribeiro",
        fonte="edição-fonte a definir (#2)",
    )
    for i, estado in enumerate(estados, start=1):
        edicao.capitulos.append(
            Capitulo(ordem=i, titulo=f"Capítulo {i}", referencia_canonica=f"LE-C{i}", estado=estado)
        )
    if status_direitos:
        edicao.direitos = Direitos(status=status_direitos)
    session.add(edicao)
    session.commit()
    return edicao


def test_bloqueia_sem_direitos(session):
    edicao = _edicao(session, [EstadoCapitulo.AUDIO_REVISADO])
    with pytest.raises(PublicacaoBloqueada, match="direitos"):
        publicar_edicao(edicao)
    assert edicao.publicada_em is None


@pytest.mark.parametrize("status", [StatusDireitos.PENDENTE, StatusDireitos.RECUSADO])
def test_bloqueia_direitos_nao_aprovados(session, status):
    edicao = _edicao(session, [EstadoCapitulo.AUDIO_REVISADO], status)
    with pytest.raises(PublicacaoBloqueada, match="direitos"):
        publicar_edicao(edicao)


def test_bloqueia_capitulo_sem_audio_revisado(session):
    edicao = _edicao(
        session,
        [EstadoCapitulo.AUDIO_REVISADO, EstadoCapitulo.AUDIO_GERADO],
        StatusDireitos.APROVADO,
    )
    with pytest.raises(PublicacaoBloqueada, match=r"\[2\]"):
        publicar_edicao(edicao)
    assert edicao.capitulos[0].estado == EstadoCapitulo.AUDIO_REVISADO


def test_publica_com_direitos_aprovados(session):
    edicao = _edicao(
        session,
        [EstadoCapitulo.AUDIO_REVISADO, EstadoCapitulo.AUDIO_REVISADO],
        StatusDireitos.APROVADO,
    )
    publicar_edicao(edicao)
    session.commit()
    session.refresh(edicao)
    assert edicao.publicada_em is not None
    assert {c.estado for c in edicao.capitulos} == {EstadoCapitulo.PUBLICADO}
