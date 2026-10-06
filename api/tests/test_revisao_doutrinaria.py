import pytest

from centelha_api.dominio import contas
from centelha_api.models import (
    Capitulo,
    Edicao,
    EstadoCapitulo,
    Obra,
    PapelUsuario,
    PapelVoz,
    Publico,
    Segmento,
    TipoSegmento,
    Usuario,
    Voz,
)

SENHA = "cavalo correto bateria grampo"


def _login(client, session, papel):
    email = f"{papel.value}@exemplo.org"
    session.add(Usuario(email=email, nome=email, papel=papel, senha_hash=contas.gerar_hash(SENHA)))
    session.commit()
    r = client.post("/v1/admin/sessoes", json={"email": email, "senha": SENHA})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def h(client, session):
    return {p: _login(client, session, p) for p in PapelUsuario}


def _edicao(session, publico: Publico) -> dict:
    obra = Obra(
        slug=f"le-{publico.value}",
        autor="Allan Kardec",
        titulo_original="Le Livre des Esprits",
        idioma_original="fr",
        sigla=f"L{publico.value[0].upper()}",
    )
    ed = Edicao(obra=obra, idioma="pt-BR", titulo="O Livro", fonte="t", publico=publico)
    cap = Capitulo(
        ordem=1, titulo="I", referencia_canonica="X-C001", estado=EstadoCapitulo.IMPORTADO
    )
    cap.segmentos = [Segmento(ordem=1, tipo=TipoSegmento.PARAGRAFO, texto="Deus é bom.")]
    ed.capitulos = [cap]
    vozes = {
        p: Voz(idioma="pt-BR", motor="falso", voz_id=p.value, papel=PapelVoz.NARRADOR, publico=p)
        for p in Publico
    }
    session.add_all([ed, *vozes.values()])
    session.commit()
    return {"cap": cap, **{p: v.id for p, v in vozes.items()}}


@pytest.fixture
def infantil(session):
    return _edicao(session, Publico.INFANTIL)


@pytest.fixture
def adulta(session):
    return _edicao(session, Publico.ADULTO)


def _acao(client, hx, cap, acao, motivo=None):
    return client.post(
        f"/v1/admin/capitulos/{cap.id}/transicoes",
        json={"acao": acao, "motivo": motivo},
        headers=hx,
    )


def _acoes(client, hx, cap):
    return client.get(f"/v1/admin/capitulos/{cap.id}", headers=hx).json()["acoes"]


def _gerar(client, hx, base, voz):
    corpo = {"voz_narrador_id": voz}
    return client.post(f"/v1/admin/capitulos/{base['cap'].id}/gerar-audio", json=corpo, headers=hx)


def _estado(session, cap):
    session.expire_all()
    return session.get(Capitulo, cap.id).estado


def test_adaptacao_nao_vira_audio_sem_revisao_doutrinaria(client, session, h, infantil):
    """Especificação: toda adaptação passa por revisão doutrinária e de linguagem antes
    de publicar. Texto aprovado não basta para gerar o áudio de uma história infantil."""
    ha = h[PapelUsuario.ADMINISTRADOR]
    cap = infantil["cap"]
    assert _acao(client, ha, cap, "aprovar_texto").status_code == 200
    assert _gerar(client, ha, infantil, infantil[Publico.INFANTIL]).status_code == 409

    # Revisor de texto não aprova doutrina; nem vê o botão.
    hr = h[PapelUsuario.REVISOR_TEXTO]
    assert "aprovar_doutrina" not in _acoes(client, hr, cap)
    assert _acao(client, hr, cap, "aprovar_doutrina").status_code == 403

    assert "aprovar_doutrina" in _acoes(client, ha, cap)
    assert _acao(client, ha, cap, "aprovar_doutrina").status_code == 200
    assert _estado(session, cap) == EstadoCapitulo.DOUTRINA_REVISADA
    assert _gerar(client, ha, infantil, infantil[Publico.INFANTIL]).status_code == 202


def test_edicao_adulta_nao_tem_o_passo(client, session, h, adulta):
    ha = h[PapelUsuario.ADMINISTRADOR]
    cap = adulta["cap"]
    _acao(client, ha, cap, "aprovar_texto")
    assert "aprovar_doutrina" not in _acoes(client, ha, cap)
    assert _acao(client, ha, cap, "aprovar_doutrina").status_code == 409
    assert _gerar(client, ha, adulta, adulta[Publico.ADULTO]).status_code == 202


def test_reprovar_doutrina_volta_um_passo_e_o_texto_reabre(client, session, h, infantil):
    """Como toda reprovação, volta um passo. O texto se corrige em "importado", que
    reabrir_texto alcança em seguida."""
    ha = h[PapelUsuario.ADMINISTRADOR]
    cap = infantil["cap"]
    _acao(client, ha, cap, "aprovar_texto")
    _acao(client, ha, cap, "aprovar_doutrina")
    assert _acao(client, ha, cap, "reprovar_doutrina").status_code == 409  # sem motivo
    motivo = "Resposta atribuída a Kardec, não aos Espíritos"
    assert _acao(client, ha, cap, "reprovar_doutrina", motivo).status_code == 200
    assert _estado(session, cap) == EstadoCapitulo.TEXTO_REVISADO
    assert _acao(client, ha, cap, "reabrir_texto", motivo).status_code == 200
    assert _estado(session, cap) == EstadoCapitulo.IMPORTADO


def test_audio_reprovado_da_adaptacao_volta_para_doutrina_revisada(client, session, h, infantil):
    """O texto e a doutrina continuam aprovados; só o áudio é refeito."""
    ha = h[PapelUsuario.ADMINISTRADOR]
    cap = infantil["cap"]
    cap_db = session.get(Capitulo, cap.id)
    cap_db.estado = EstadoCapitulo.AUDIO_GERADO
    session.commit()
    assert _acao(client, ha, cap, "reprovar_audio", "ritmo rápido demais").status_code == 200
    assert _estado(session, cap) == EstadoCapitulo.DOUTRINA_REVISADA


def test_voz_do_publico_errado_e_recusada(client, session, h, infantil, adulta):
    """Infantil pede voz calorosa e ritmo lento (especificação); voz adulta numa história
    infantil, ou voz infantil numa obra adulta, passaria sem ninguém notar."""
    ha = h[PapelUsuario.ADMINISTRADOR]
    _acao(client, ha, infantil["cap"], "aprovar_texto")
    _acao(client, ha, infantil["cap"], "aprovar_doutrina")
    r = _gerar(client, ha, infantil, infantil[Publico.ADULTO])
    assert r.status_code == 409
    assert "público" in r.json()["detail"]

    _acao(client, ha, adulta["cap"], "aprovar_texto")
    assert _gerar(client, ha, adulta, adulta[Publico.INFANTIL]).status_code == 409
