from datetime import date, timedelta

import pytest
from sqlalchemy import select

from centelha_api.dominio import contas
from centelha_api.models import PapelUsuario, RegistroAuditoria, Usuario

SENHA = "cavalo correto bateria grampo"
# Datas a vários dias de hoje: o banco e o host podem estar em fusos diferentes.
HOJE = date.today()


def _d(dias: int) -> str:
    return (HOJE + timedelta(days=dias)).isoformat()


def _login(client, session, papel):
    email = f"{papel.value}@exemplo.org"
    session.add(Usuario(email=email, nome=email, papel=papel, senha_hash=contas.gerar_hash(SENHA)))
    session.commit()
    r = client.post("/v1/admin/sessoes", json={"email": email, "senha": SENHA})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def ha(client, session):
    return _login(client, session, PapelUsuario.ADMINISTRADOR)


INSTITUICAO = {
    "nome": "Casa Espírita Exemplo",
    "cnpj": "11.222.333/0001-81",
    "descricao": "Atende 200 famílias com cestas básicas e evangelização infantil.",
    "chave_pix": "doacoes@casaexemplo.org.br",
    "pagina_doacao": "https://casaexemplo.org.br/doe",
    "site": None,
}


@pytest.fixture
def inst(client, ha):
    r = client.post("/v1/admin/instituicoes", json=INSTITUICAO, headers=ha)
    assert r.status_code == 201
    return r.json()


def _campanha(client, ha, inst, slug="agasalho", inicio=-3, fim=10, **kw):
    corpo = {
        "slug": slug,
        "titulo": "Campanha do agasalho",
        "texto": "Cobertores para o inverno.",
        "instituicao_id": inst["id"],
        "inicio": _d(inicio),
        "fim": _d(fim),
        "meta_centavos": 500000,
        **kw,
    }
    return client.post("/v1/admin/campanhas", json=corpo, headers=ha)


def test_campanha_ativa_liga_caridade_no_app(client, ha, inst):
    """O cartão do app aparece só durante uma campanha publicada; fora dela, só o item
    discreto do menu (especificação, Calendário de campanhas)."""
    c = _campanha(client, ha, inst).json()
    assert client.get("/v1/config").json()["caridade"] is False
    assert client.get("/v1/campanhas").json() == []

    assert client.post(f"/v1/admin/campanhas/{c['id']}/publicar", headers=ha).status_code == 200
    assert client.get("/v1/config").json()["caridade"] is True
    [pub] = client.get("/v1/campanhas").json()
    assert pub["situacao"] == "ativa"
    # Quem doa confere para quem: nome, CNPJ e o Pix da instituição.
    assert pub["instituicao"]["cnpj"] == "11222333000181"
    assert pub["instituicao"]["chave_pix"] == "doacoes@casaexemplo.org.br"


def test_campanha_futura_nao_liga_caridade(client, ha, inst):
    c = _campanha(client, ha, inst, inicio=20, fim=30).json()
    client.post(f"/v1/admin/campanhas/{c['id']}/publicar", headers=ha)
    assert client.get("/v1/config").json()["caridade"] is False
    assert client.get("/v1/campanhas/agasalho").json()["situacao"] == "futura"


def test_uma_campanha_por_vez(client, ha, inst):
    """Duas campanhas no mesmo período viram pedido permanente, que o calendário existe
    para evitar."""
    a = _campanha(client, ha, inst).json()
    b = _campanha(client, ha, inst, slug="natal", inicio=5, fim=40).json()
    client.post(f"/v1/admin/campanhas/{a['id']}/publicar", headers=ha)
    r = client.post(f"/v1/admin/campanhas/{b['id']}/publicar", headers=ha)
    assert r.status_code == 409
    assert "agasalho" in r.json()["detail"]

    # Encostada depois do fim, pode.
    corpo = {**b, "instituicao_id": inst["id"], "inicio": _d(11), "fim": _d(40)}
    corpo = {k: corpo[k] for k in ("slug", "titulo", "texto", "instituicao_id", "inicio", "fim")}
    assert client.put(f"/v1/admin/campanhas/{b['id']}", json=corpo, headers=ha).status_code == 200
    assert client.post(f"/v1/admin/campanhas/{b['id']}/publicar", headers=ha).status_code == 200

    # E publicada não pode ser esticada para cima da outra.
    corpo["inicio"] = _d(8)
    assert client.put(f"/v1/admin/campanhas/{b['id']}", json=corpo, headers=ha).status_code == 409


def test_publicada_nao_troca_slug_nem_instituicao(client, ha, inst):
    """Quem doou ou compartilhou o link conferiu aquela instituição."""
    outra = client.post(
        "/v1/admin/instituicoes",
        json={**INSTITUICAO, "nome": "Outra", "cnpj": "11.444.777/0001-61"},
        headers=ha,
    ).json()
    c = _campanha(client, ha, inst).json()
    client.post(f"/v1/admin/campanhas/{c['id']}/publicar", headers=ha)
    corpo = {k: c[k] for k in ("slug", "titulo", "texto", "inicio", "fim")}
    corpo["instituicao_id"] = outra["id"]
    assert client.put(f"/v1/admin/campanhas/{c['id']}", json=corpo, headers=ha).status_code == 409
    corpo = {**corpo, "instituicao_id": inst["id"], "slug": "outro-slug"}
    assert client.put(f"/v1/admin/campanhas/{c['id']}", json=corpo, headers=ha).status_code == 409
    # Nem a instituição troca de CNPJ por baixo da campanha.
    novo = {**INSTITUICAO, "cnpj": "11.444.777/0001-61"}
    r = client.put(f"/v1/admin/instituicoes/{inst['id']}", json=novo, headers=ha)
    assert r.status_code == 409


def test_sem_pix_nem_pagina_nao_publica(client, ha):
    i = client.post(
        "/v1/admin/instituicoes",
        json={**INSTITUICAO, "chave_pix": None, "pagina_doacao": None},
        headers=ha,
    ).json()
    c = _campanha(client, ha, i).json()
    assert client.post(f"/v1/admin/campanhas/{c['id']}/publicar", headers=ha).status_code == 409


def test_resultado_so_depois_do_fim(client, session, ha, inst):
    """Resultado parcial publicado como final engana quem doou."""
    ativa = _campanha(client, ha, inst).json()
    r = client.put(
        f"/v1/admin/campanhas/{ativa['id']}/resultado",
        json={"arrecadado_centavos": 1000, "resultado": "parcial"},
        headers=ha,
    )
    assert r.status_code == 409

    velha = _campanha(client, ha, inst, slug="natal-passado", inicio=-60, fim=-30).json()
    # Encerrada não se publica de novo como se fosse começar.
    assert client.post(f"/v1/admin/campanhas/{velha['id']}/publicar", headers=ha).status_code == 409
    r = client.put(
        f"/v1/admin/campanhas/{velha['id']}/resultado",
        json={"arrecadado_centavos": 1234500, "resultado": "180 cestas entregues."},
        headers=ha,
    )
    assert r.status_code == 200
    assert r.json()["arrecadado_centavos"] == 1234500
    log = session.scalars(
        select(RegistroAuditoria.acao).where(RegistroAuditoria.acao == "campanha_resultado")
    ).all()
    assert log == ["campanha_resultado"]


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("cnpj", "11.222.333/0001-82"),
        ("cnpj", "00000000000000"),
        ("chave_pix", "123.456.789-09"),
        ("pagina_doacao", "http://casaexemplo.org.br/doe"),
        ("pagina_doacao", "javascript:alert(1)"),
    ],
)
def test_dados_da_instituicao_validados(client, ha, campo, valor):
    r = client.post("/v1/admin/instituicoes", json={**INSTITUICAO, campo: valor}, headers=ha)
    assert r.status_code == 422


def test_cnpj_repetido(client, ha, inst):
    r = client.post(
        "/v1/admin/instituicoes", json={**INSTITUICAO, "nome": "Outra casa"}, headers=ha
    )
    assert r.status_code == 409


def test_fim_antes_do_inicio(client, ha, inst):
    assert _campanha(client, ha, inst, inicio=5, fim=1).status_code == 422


def test_so_administrador(client, session, ha, inst):
    for papel in (PapelUsuario.REVISOR_TEXTO, PapelUsuario.REVISOR_AUDIO):
        h = _login(client, session, papel)
        assert client.get("/v1/admin/campanhas", headers=h).status_code == 403
        assert client.post("/v1/admin/instituicoes", json=INSTITUICAO, headers=h).status_code == 403
