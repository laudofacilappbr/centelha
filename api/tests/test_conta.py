"""Conta opcional de quem lê (#43, 1A): entrar por código no e-mail, sem senha."""

import re

import pytest
from sqlalchemy import select, text

from centelha_api import email as correio
from centelha_api import lgpd
from centelha_api.config import get_settings
from centelha_api.models import CodigoAcesso, ContaLeitor, SessaoConta
from centelha_api.routers import conta


@pytest.fixture(autouse=True)
def limpo():
    conta.limitador.limpar()
    correio.enviadas.clear()
    yield
    get_settings.cache_clear()


def _pedir(client, email="leitora@exemplo.org"):
    return client.post("/v1/conta/codigo", json={"email": email})


def _codigo(email="leitora@exemplo.org"):
    m = [m for m in correio.enviadas if m.para == email.strip().lower()][-1]
    return re.search(r"\b(\d{6})\b", m.texto).group(1)


def _entrar(client, email="leitora@exemplo.org"):
    assert _pedir(client, email).status_code == 202
    r = client.post("/v1/conta/sessao", json={"email": email, "codigo": _codigo(email)})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_entrar_com_o_codigo_do_email_cria_a_conta(client, session):
    h = _entrar(client, "Leitora@Exemplo.org ")
    assert client.get("/v1/conta", headers=h).json() == {"email": "leitora@exemplo.org"}
    assert session.scalar(select(ContaLeitor.email)) == "leitora@exemplo.org"
    # Só hashes no banco: nem o código nem o token aparecem.
    linha = session.execute(text("select codigo_hash, sal from codigo_acesso")).one()
    assert _codigo() not in linha.codigo_hash
    assert session.scalar(select(SessaoConta.token_hash)) != h["Authorization"][7:]


def test_pedido_nao_revela_se_o_email_tem_conta(client):
    _entrar(client)
    assert _pedir(client).json() == _pedir(client, "outra@exemplo.org").json()


def test_codigo_vale_uma_vez_e_o_novo_invalida_o_anterior(client, session):
    _pedir(client)
    _pedir(client)
    # O primeiro código foi encerrado pelo segundo pedido; só o último vale.
    abertos = session.scalars(select(CodigoAcesso).where(CodigoAcesso.usado_em.is_(None))).all()
    assert len(abertos) == 1
    dados = {"email": "leitora@exemplo.org", "codigo": _codigo()}
    assert client.post("/v1/conta/sessao", json=dados).status_code == 200
    assert client.post("/v1/conta/sessao", json=dados).status_code == 400


def test_cinco_erros_matam_o_codigo(client):
    """10⁶ combinações não aguentam força bruta sem limite de tentativas."""
    _pedir(client)
    certo = _codigo()
    errado = "000000" if certo != "000000" else "111111"
    dados = {"email": "leitora@exemplo.org"}
    for _ in range(5):
        assert client.post("/v1/conta/sessao", json={**dados, "codigo": errado}).status_code == 400
    assert client.post("/v1/conta/sessao", json={**dados, "codigo": certo}).status_code == 400


def test_codigo_expirado_nao_entra(client, session):
    _pedir(client)
    session.execute(text("update codigo_acesso set expira_em = now() - interval '1 minute'"))
    session.commit()
    r = client.post("/v1/conta/sessao", json={"email": "leitora@exemplo.org", "codigo": _codigo()})
    assert r.status_code == 400


def test_limite_de_pedidos_por_email(client):
    for _ in range(5):
        assert _pedir(client).status_code == 202
    assert _pedir(client).status_code == 429


def test_producao_sem_provedor_responde_503_e_nao_deixa_codigo(client, session, monkeypatch):
    """Fingir que mandou deixaria a pessoa esperando um e-mail que não vem."""
    monkeypatch.setenv("CENTELHA_AMBIENTE", "producao")
    monkeypatch.setenv("CENTELHA_ADMIN_SEGREDO", "x" * 40)
    get_settings.cache_clear()
    assert _pedir(client).status_code == 503
    assert correio.enviadas == []
    assert session.scalar(select(CodigoAcesso.id)) is None


def test_sair_revoga_a_sessao(client):
    h = _entrar(client)
    assert client.post("/v1/conta/sair", headers=h).status_code == 204
    assert client.get("/v1/conta", headers=h).status_code == 401


def test_excluir_apaga_conta_sessoes_e_codigos(client, session):
    """LGPD art. 18, VI, pelo próprio app."""
    h = _entrar(client)
    assert client.get("/v1/conta/exportar", headers=h).json()["email"] == "leitora@exemplo.org"
    assert client.delete("/v1/conta", headers=h).status_code == 204
    session.expire_all()
    assert session.scalar(select(ContaLeitor.id)) is None
    assert session.scalar(select(SessaoConta.id)) is None
    assert session.scalar(select(CodigoAcesso.id)) is None
    assert client.get("/v1/conta", headers=h).status_code == 401


def test_sem_sessao_401(client):
    assert client.get("/v1/conta").status_code == 401
    assert client.get("/v1/conta", headers={"Authorization": "Bearer x"}).status_code == 401


def test_lgpd_cli_cobre_a_conta(client, session):
    _entrar(client)
    assert lgpd.exportar(session, "leitora@exemplo.org")["conta"]["email"] == "leitora@exemplo.org"
    assert lgpd.excluir(session, "leitora@exemplo.org") == 1
    assert session.scalar(select(ContaLeitor.id)) is None


def test_codigos_com_mais_de_um_dia_sao_apagados_no_proximo_pedido(client, session):
    """O código guarda um e-mail e, vencido, não serve para nada (LGPD, necessidade)."""
    _pedir(client, "antiga@exemplo.org")
    session.execute(text("update codigo_acesso set criado_em = now() - interval '2 days'"))
    session.commit()
    _pedir(client)
    session.expire_all()
    emails = session.scalars(select(CodigoAcesso.email)).all()
    assert emails == ["leitora@exemplo.org"]
