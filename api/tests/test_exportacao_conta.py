"""Download em formato aberto pela conta do app, liberado pelo suporte (#134, 1A e 2D)."""

import urllib.error
import urllib.request

import pytest
from sqlalchemy import select
from test_admin_audio import _login
from test_conta import _entrar
from test_exportar import edicao  # noqa: F401  (fixture: edição publicada com 4 capítulos)

from centelha_api import email as correio
from centelha_api import lgpd
from centelha_api.config import get_settings
from centelha_api.models import (
    DownloadAberto,
    EstadoCapitulo,
    ExportacaoLiberada,
    PapelUsuario,
    RegistroAuditoria,
    StatusDireitos,
)
from centelha_api.routers import conta

EMAIL = "leitora@exemplo.org"


@pytest.fixture(autouse=True)
def limpo():
    conta.limitador.limpar()
    correio.enviadas.clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def admin(client, session):
    return _login(client, session, PapelUsuario.ADMINISTRADOR)


@pytest.fixture
def leitora(client):
    return _entrar(client, EMAIL)


def _liberar(client, admin, email=EMAIL, pedido="S-2026-014"):
    return client.post(
        "/v1/admin/exportacoes", headers=admin, json={"email": email, "pedido": pedido}
    )


def _baixar(client, h, capitulo):
    return client.get(f"/v1/conta/exportacao/capitulos/{capitulo.id}", headers=h)


def test_sem_liberacao_a_conta_nao_ve_nem_baixa(client, edicao, leitora):  # noqa: F811
    assert client.get("/v1/conta", headers=leitora).json() == {
        "email": EMAIL,
        "exportacao_aberta": False,
    }
    assert _baixar(client, leitora, edicao.capitulos[0]).status_code == 403
    sem_conta = client.get(f"/v1/conta/exportacao/capitulos/{edicao.capitulos[0].id}")
    assert sem_conta.status_code == 401


def test_liberada_baixa_o_capitulo_aberto_e_fica_registrado(
    client,
    session,
    edicao,  # noqa: F811
    leitora,
    admin,
):
    r = _liberar(client, admin)
    assert r.status_code == 201, r.text
    assert r.json()["email"] == EMAIL and r.json()["liberada_por"] == "administrador@exemplo.org"
    assert client.get("/v1/conta", headers=leitora).json()["exportacao_aberta"] is True

    c1 = edicao.capitulos[0]
    r = _baixar(client, leitora, c1)
    assert r.status_code == 200
    # A .cent saiu decifrada: AAC que qualquer player abre, como anexo, nunca em cache.
    assert r.content[4:8] == b"ftyp"
    assert r.headers["content-type"] == "audio/mp4"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["content-disposition"] == 'attachment; filename="1-capitulo-i-de-deus.m4a"'
    assert session.scalar(select(DownloadAberto.faixa_id)) is not None

    leiame = client.get(f"/v1/conta/exportacao/edicoes/{edicao.id}/leiame", headers=leitora)
    assert leiame.status_code == 200
    assert "S-2026-014" in leiame.text and "Não redistribua" in leiame.text

    assert client.get("/v1/admin/exportacoes", headers=admin).json()[0]["capitulos_baixados"] == 1
    # Auditoria sem o e-mail: o log fica, a conta pode sumir.
    registro = session.scalar(
        select(RegistroAuditoria).where(RegistroAuditoria.acao == "exportacao_liberada")
    )
    assert registro.detalhes == {"pedido": "S-2026-014"}
    assert EMAIL not in str(registro.detalhes)


def test_so_sai_o_que_a_exportacao_do_suporte_entregaria(
    client,
    session,
    edicao,  # noqa: F811
    leitora,
    admin,
):
    _liberar(client, admin)
    c1, c2, c3, c4 = edicao.capitulos
    assert _baixar(client, leitora, c2).status_code == 200
    # Capítulo não publicado e capítulo só com faixa de motor sem licença: não saem.
    assert _baixar(client, leitora, c3).status_code == 404
    assert _baixar(client, leitora, c4).status_code == 404
    # Direitos revogados tiram a edição inteira, também daqui.
    edicao.direitos.status = StatusDireitos.PENDENTE
    session.commit()
    assert _baixar(client, leitora, c1).status_code == 404
    leiame = client.get(f"/v1/conta/exportacao/edicoes/{edicao.id}/leiame", headers=leitora)
    assert leiame.status_code == 404
    assert c3.estado == EstadoCapitulo.AUDIO_GERADO


def test_revogar_corta_o_download(client, session, edicao, leitora, admin):  # noqa: F811
    liberacao = _liberar(client, admin).json()
    assert _liberar(client, admin).status_code == 409
    assert (
        client.delete(f"/v1/admin/exportacoes/{liberacao['id']}", headers=admin).status_code == 204
    )
    assert client.get("/v1/conta", headers=leitora).json()["exportacao_aberta"] is False
    assert _baixar(client, leitora, edicao.capitulos[0]).status_code == 403
    assert client.get("/v1/admin/exportacoes", headers=admin).json() == []
    assert (
        client.delete(f"/v1/admin/exportacoes/{liberacao['id']}", headers=admin).status_code == 409
    )
    # A revogada fica, com quem revogou; e dá para liberar de novo depois.
    revogada = session.get(ExportacaoLiberada, liberacao["id"])
    assert revogada.revogada_em is not None and revogada.revogada_por_id is not None
    assert _liberar(client, admin, pedido="S-2026-020").status_code == 201


def test_limite_diario(client, edicao, leitora, admin, monkeypatch):  # noqa: F811
    monkeypatch.setenv("CENTELHA_EXPORTACAO_DOWNLOADS_POR_DIA", "2")
    get_settings.cache_clear()
    _liberar(client, admin)
    c1 = edicao.capitulos[0]
    assert _baixar(client, leitora, c1).status_code == 200
    assert _baixar(client, leitora, c1).status_code == 200
    assert _baixar(client, leitora, c1).status_code == 429


def test_liberar_exige_conta_e_administrador(client, session, edicao, admin):  # noqa: F811
    assert _liberar(client, admin, email="sem-conta@exemplo.org").status_code == 404
    _entrar(client, EMAIL)
    for papel in (PapelUsuario.REVISOR_TEXTO, PapelUsuario.REVISOR_AUDIO):
        assert _liberar(client, _login(client, session, papel)).status_code == 403
    assert (
        client.post("/v1/admin/exportacoes", json={"email": EMAIL, "pedido": "S"}).status_code
        == 401
    )


def test_excluir_a_conta_leva_a_liberacao_e_o_lgpd_exporta(
    client,
    session,
    edicao,  # noqa: F811
    leitora,
    admin,
):
    _liberar(client, admin)
    _baixar(client, leitora, edicao.capitulos[0])
    dados = client.get("/v1/conta/exportar", headers=leitora).json()
    assert dados["exportacao_aberta"][0]["pedido"] == "S-2026-014"
    assert dados["exportacao_aberta"][0]["capitulos_baixados"] == 1
    assert lgpd.exportar(session, EMAIL)["conta"]["exportacao_aberta"]

    assert client.delete("/v1/conta", headers=leitora).status_code == 204
    session.expire_all()
    assert session.scalar(select(ExportacaoLiberada.id)) is None
    assert session.scalar(select(DownloadAberto.id)) is None


def test_armazenamento_fora_do_ar_e_503_e_nao_conta(
    client,
    session,
    edicao,  # noqa: F811
    leitora,
    admin,
    tmp_path,
    monkeypatch,
):
    _liberar(client, admin)
    # Fora do disco local o arquivo vem da URL; com ela fora do ar, o erro é do servidor.
    (tmp_path / "audio" / "c1.cent").unlink()

    def fora_do_ar(*_, **__):
        raise urllib.error.URLError("fora do ar")

    monkeypatch.setattr(urllib.request, "urlopen", fora_do_ar)
    assert _baixar(client, leitora, edicao.capitulos[0]).status_code == 503
    assert session.scalar(select(DownloadAberto.id)) is None
