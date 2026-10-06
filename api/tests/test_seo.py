from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from centelha_api.dominio import contas
from centelha_api.models import (
    Capitulo,
    Direitos,
    Edicao,
    EstadoCapitulo,
    Obra,
    PapelUsuario,
    RegistroAuditoria,
    StatusDireitos,
    Usuario,
)

SENHA = "cavalo correto bateria grampo"


def _login(client, session, papel):
    email = f"{papel.value}@exemplo.org"
    session.add(Usuario(email=email, nome=email, papel=papel, senha_hash=contas.gerar_hash(SENHA)))
    session.commit()
    r = client.post("/v1/admin/sessoes", json={"email": email, "senha": SENHA})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def ha(client, session):
    return _login(client, session, PapelUsuario.ADMINISTRADOR)


@pytest.fixture
def edicao(session):
    obra = Obra(
        slug="o-livro-dos-espiritos",
        autor="Allan Kardec",
        titulo_original="LE",
        idioma_original="fr",
        sigla="LE",
    )
    ed = Edicao(
        obra=obra,
        idioma="pt-BR",
        titulo="O Livro dos Espíritos",
        fonte="t",
        publicada_em=datetime.now(UTC),
        direitos=Direitos(status=StatusDireitos.APROVADO),
    )
    ed.capitulos = [
        Capitulo(
            ordem=1,
            titulo="Dos Espíritos",
            referencia_canonica="LE-C001",
            estado=EstadoCapitulo.PUBLICADO,
        )
    ]
    session.add(ed)
    session.commit()
    return ed


def test_sem_seo_o_site_usa_o_modelo(client, edicao):
    """Campo vazio é None na API: o site sabe que deve cair no título-modelo."""
    [obra] = client.get("/v1/obras").json()
    assert obra["edicoes"][0]["seo_titulo"] is None
    assert obra["edicoes"][0]["seo_descricao"] is None


def test_seo_da_edicao_e_do_capitulo_chega_ao_catalogo(client, session, ha, edicao):
    seo = {"seo_titulo": "O Livro dos Espíritos em áudio, grátis", "seo_descricao": "Ouça."}
    r = client.put(f"/v1/admin/edicoes/{edicao.id}/seo", json=seo, headers=ha)
    assert r.status_code == 200
    assert client.get("/v1/obras").json()[0]["edicoes"][0]["seo_titulo"] == seo["seo_titulo"]
    assert client.get(f"/v1/edicoes/{edicao.id}").json()["seo_descricao"] == "Ouça."

    cap = edicao.capitulos[0]
    corpo = {"seo_titulo": "  Dos Espíritos:\n o que são  ", "seo_descricao": ""}
    r = client.put(f"/v1/admin/capitulos/{cap.id}/seo", json=corpo, headers=ha)
    # Quebra de linha e espaço sobrando saem; vazio vira None (volta ao modelo).
    assert r.json() == {"seo_titulo": "Dos Espíritos: o que são", "seo_descricao": None}
    assert client.get(f"/v1/capitulos/{cap.id}").json()["seo_titulo"] == "Dos Espíritos: o que são"
    assert client.get(f"/v1/edicoes/{edicao.id}").json()["capitulos"][0]["seo_titulo"] == (
        "Dos Espíritos: o que são"
    )

    log = session.scalars(
        select(RegistroAuditoria).where(RegistroAuditoria.acao == "seo_alterado")
    ).all()
    assert [(x.alvo_tipo, x.detalhes["antes"]["seo_titulo"]) for x in log] == [
        ("edicao", None),
        ("capitulo", None),
    ]


@pytest.mark.parametrize(("campo", "tamanho"), [("seo_titulo", 61), ("seo_descricao", 161)])
def test_tamanho_maximo(client, ha, edicao, campo, tamanho):
    """O site acrescenta " | Centelha" ao título; a busca corta descrição longa."""
    r = client.put(f"/v1/admin/edicoes/{edicao.id}/seo", json={campo: "x" * tamanho}, headers=ha)
    assert r.status_code == 422


def test_so_quem_edita_conteudo(client, session, ha, edicao):
    for papel in (PapelUsuario.REVISOR_TEXTO, PapelUsuario.REVISOR_AUDIO):
        h = _login(client, session, papel)
        r = client.put(f"/v1/admin/edicoes/{edicao.id}/seo", json={}, headers=h)
        assert r.status_code == 403
    assert client.put("/v1/admin/capitulos/999/seo", json={}, headers=ha).status_code == 404
