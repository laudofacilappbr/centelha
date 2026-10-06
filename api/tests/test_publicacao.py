import pytest

from centelha_api.config import get_settings
from centelha_api.dominio.publicacao import PublicacaoBloqueada, publicar_edicao
from centelha_api.models import (
    Capitulo,
    Direitos,
    Edicao,
    EstadoCapitulo,
    FaixaAudio,
    Obra,
    PapelVoz,
    StatusDireitos,
    Voz,
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


def _faixa(session, capitulo, motor, versao):
    voz = Voz(idioma="pt-BR", motor=motor, voz_id=f"{motor}-n", papel=PapelVoz.NARRADOR)
    session.add(voz)
    session.flush()
    session.add(
        FaixaAudio(
            capitulo_id=capitulo.id,
            voz_id=voz.id,
            versao=versao,
            url=f"https://audio.exemplo/{motor}-v{versao}.m4a",
            duracao_ms=1000,
            marcacoes=[],
        )
    )
    session.commit()


def test_bloqueia_audio_de_motor_sem_licenca(session):
    """Decisão do dono em #1 (opção A): nada do Piper vai ao ar até o parecer (#3)."""
    edicao = _edicao(
        session,
        [EstadoCapitulo.AUDIO_REVISADO, EstadoCapitulo.AUDIO_REVISADO],
        StatusDireitos.APROVADO,
    )
    _faixa(session, edicao.capitulos[0], "azure", 1)
    _faixa(session, edicao.capitulos[1], "azure", 1)
    _faixa(session, edicao.capitulos[1], "piper", 2)
    with pytest.raises(PublicacaoBloqueada, match=r"licença.*\[2\]"):
        publicar_edicao(edicao)
    assert edicao.publicada_em is None


def test_faixa_antiga_do_piper_nao_bloqueia(session):
    """Conta a faixa mais recente: regerado em motor liberado, o capítulo publica."""
    edicao = _edicao(session, [EstadoCapitulo.AUDIO_REVISADO], StatusDireitos.APROVADO)
    _faixa(session, edicao.capitulos[0], "piper", 1)
    _faixa(session, edicao.capitulos[0], "azure", 2)
    publicar_edicao(edicao)
    assert edicao.publicada_em is not None


def test_motor_liberado_depois_do_parecer_publica(session, monkeypatch):
    monkeypatch.setattr(get_settings(), "tts_motores_sem_licenca", set())
    edicao = _edicao(session, [EstadoCapitulo.AUDIO_REVISADO], StatusDireitos.APROVADO)
    _faixa(session, edicao.capitulos[0], "piper", 1)
    publicar_edicao(edicao)
    assert edicao.publicada_em is not None
