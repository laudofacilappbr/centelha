"""Slug da edição para /fr, /es e /en no site (#48, decisão 2A)."""

import pytest

from centelha_api.dominio import contas
from centelha_api.dominio.publicacao import publicar_edicao
from centelha_api.dominio.slug import slugificar
from centelha_api.models import (
    Capitulo,
    Direitos,
    Edicao,
    EstadoCapitulo,
    Obra,
    PapelUsuario,
    StatusDireitos,
    Usuario,
)

SENHA = "cavalo correto bateria grampo"


def _login(client, session, email, papel):
    session.add(Usuario(email=email, nome=email, papel=papel, senha_hash=contas.gerar_hash(SENHA)))
    session.commit()
    r = client.post("/v1/admin/sessoes", json={"email": email, "senha": SENHA})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def h_admin(client, session):
    return _login(client, session, "ana@exemplo.org", PapelUsuario.ADMINISTRADOR)


@pytest.mark.parametrize(
    ("titulo", "slug"),
    [
        ("Le Livre des Esprits", "le-livre-des-esprits"),
        ("L'Évangile selon le Spiritisme", "l-evangile-selon-le-spiritisme"),
        ("El Libro de los Espíritus", "el-libro-de-los-espiritus"),
        ("  O Céu e o Inferno!  ", "o-ceu-e-o-inferno"),
    ],
)
def test_slugificar(titulo, slug):
    assert slugificar(titulo) == slug


def _edicao(session, titulo="Le Livre des Esprits", fonte="Didier, 1860", obra=None):
    obra = obra or Obra(
        slug="o-livro-dos-espiritos",
        autor="Allan Kardec",
        titulo_original="Le Livre des Esprits",
        idioma_original="fr",
        sigla="LE",
    )
    e = Edicao(
        obra=obra,
        idioma="fr",
        titulo=titulo,
        fonte=fonte,
        direitos=Direitos(status=StatusDireitos.APROVADO),
    )
    e.capitulos = [
        Capitulo(
            ordem=1,
            titulo="Dieu",
            referencia_canonica="LE-C001",
            estado=EstadoCapitulo.AUDIO_REVISADO,
        )
    ]
    session.add(e)
    session.commit()
    return e


def test_publicar_preenche_o_slug_e_evita_repetir(session):
    primeira = _edicao(session)
    publicar_edicao(primeira)
    session.commit()
    assert primeira.slug == "le-livre-des-esprits"

    # Outra tradução com o mesmo título, no mesmo idioma e público.
    segunda = _edicao(session, fonte="outra", obra=primeira.obra)
    publicar_edicao(segunda)
    session.commit()
    assert segunda.slug == "le-livre-des-esprits-2"


def test_slug_escolhido_antes_de_publicar_fica(session):
    e = _edicao(session)
    e.slug = "livre-des-esprits"
    publicar_edicao(e)
    assert e.slug == "livre-des-esprits"


def test_catalogo_entrega_o_slug(client, session):
    e = _edicao(session)
    publicar_edicao(e)
    session.commit()
    [obra] = client.get("/v1/obras").json()
    assert obra["edicoes"][0]["slug"] == "le-livre-des-esprits"
    assert client.get(f"/v1/edicoes/{e.id}").json()["slug"] == "le-livre-des-esprits"


def test_admin_muda_o_slug_so_antes_de_publicar(client, session, h_admin):
    e = _edicao(session)
    url = f"/v1/admin/edicoes/{e.id}/slug"
    r = client.put(url, json={"slug": "livre-des-esprits"}, headers=h_admin)
    assert r.status_code == 200, r.text
    assert client.put(url, json={"slug": "Com Espaço"}, headers=h_admin).status_code == 422

    outra = _edicao(session, fonte="outra", obra=e.obra)
    r = client.put(
        f"/v1/admin/edicoes/{outra.id}/slug", json={"slug": "livre-des-esprits"}, headers=h_admin
    )
    assert r.status_code == 409

    session.refresh(e)
    publicar_edicao(e)
    session.commit()
    r = client.put(url, json={"slug": "outro"}, headers=h_admin)
    assert r.status_code == 409
    session.refresh(e)
    assert e.slug == "livre-des-esprits"


def test_revisor_nao_muda_o_slug(client, session):
    e = _edicao(session)
    h = _login(client, session, "rev@exemplo.org", PapelUsuario.REVISOR_AUDIO)
    r = client.put(f"/v1/admin/edicoes/{e.id}/slug", json={"slug": "x-y"}, headers=h)
    assert r.status_code == 403
