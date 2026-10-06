import pytest
from sqlalchemy import select

from centelha_api.dominio import contas
from centelha_api.models import (
    Capitulo,
    Edicao,
    EstadoCapitulo,
    Obra,
    PapelUsuario,
    RegistroAuditoria,
    StatusDireitos,
    Usuario,
)

SENHA = "cavalo correto bateria grampo"
COMPLETO = {
    "falecimento_tradutor": "1943-10-26",
    "base_legal": "Lei 9.610/98, art. 41: tradutor falecido em 1943, domínio público desde 2014.",
    "documento_url": "https://exemplo.org/parecer-le.pdf",
}


@pytest.fixture
def h_admin(client, session):
    return _login(client, session, "ana@exemplo.org", PapelUsuario.ADMINISTRADOR)


def _login(client, session, email, papel):
    session.add(Usuario(email=email, nome=email, papel=papel, senha_hash=contas.gerar_hash(SENHA)))
    session.commit()
    r = client.post("/v1/admin/sessoes", json={"email": email, "senha": SENHA})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def edicao(session):
    """Tradução pronta para publicar, exceto pelos direitos."""
    obra = Obra(
        slug="o-livro-dos-espiritos",
        autor="Allan Kardec",
        titulo_original="Le Livre des Esprits",
        idioma_original="fr",
        sigla="LE",
    )
    e = Edicao(
        obra=obra,
        idioma="pt-BR",
        titulo="O Livro dos Espíritos",
        tradutor="Guillon Ribeiro",
        fonte="teste",
    )
    e.capitulos.append(
        Capitulo(
            ordem=1, titulo="I", referencia_canonica="LE-C001", estado=EstadoCapitulo.AUDIO_REVISADO
        )
    )
    session.add(e)
    session.commit()
    return e


def _url(e, sufixo=""):
    return f"/v1/admin/edicoes/{e.id}/direitos{sufixo}"


def _aprovar_e_publicar(client, h, e):
    assert client.put(_url(e), json=COMPLETO, headers=h).status_code == 200
    assert client.post(_url(e, "/aprovar"), headers=h).status_code == 200
    assert client.post(f"/v1/admin/edicoes/{e.id}/publicar", headers=h).status_code == 200


def _log(session, acao):
    session.expire_all()
    return session.scalars(select(RegistroAuditoria).where(RegistroAuditoria.acao == acao)).all()


def test_sem_cadastro_mostra_o_que_falta(client, h_admin, edicao):
    r = client.get(_url(edicao), headers=h_admin).json()
    assert r["status"] == "pendente"
    assert r["pendencias"] == ["base_legal", "documento_url", "falecimento_tradutor"]


def test_nao_aprova_sem_a_prova(client, h_admin, edicao):
    """Aprovar sem base legal e documento é exatamente o "depois a gente vê" que a
    regra de direitos existe para impedir."""
    client.put(_url(edicao), json={"base_legal": "domínio público"}, headers=h_admin)
    r = client.post(_url(edicao, "/aprovar"), headers=h_admin)
    assert r.status_code == 422
    assert r.json()["detail"]["pendencias"] == ["documento_url", "falecimento_tradutor"]
    assert client.get(_url(edicao), headers=h_admin).json()["status"] == "pendente"


def test_original_sem_tradutor_dispensa_falecimento(client, session, h_admin, edicao):
    edicao.tradutor = None
    session.commit()
    sem_data = {k: v for k, v in COMPLETO.items() if k != "falecimento_tradutor"}
    client.put(_url(edicao), json=sem_data, headers=h_admin)
    assert client.post(_url(edicao, "/aprovar"), headers=h_admin).status_code == 200


def test_aprovacao_registra_quem_e_a_prova_vista(client, session, h_admin, edicao):
    _aprovar_e_publicar(client, h_admin, edicao)
    r = client.get(_url(edicao), headers=h_admin).json()
    assert (r["status"], r["aprovado_por"], r["publicada"]) == ("aprovado", "ana@exemplo.org", True)
    [registro] = _log(session, "direitos_aprovados")
    assert registro.detalhes["documento_url"] == COMPLETO["documento_url"]
    assert registro.detalhes["falecimento_tradutor"] == "1943-10-26"


def test_mudar_a_prova_desfaz_a_aprovacao_e_tira_do_ar(client, session, h_admin, edicao):
    """A aprovação vale para o documento que o aprovador viu. Trocar o documento e
    continuar "aprovado" publicaria com uma prova que ninguém conferiu."""
    _aprovar_e_publicar(client, h_admin, edicao)
    assert client.get(f"/v1/edicoes/{edicao.id}").status_code == 200

    outro = {**COMPLETO, "documento_url": "https://exemplo.org/outro.pdf"}
    r = client.put(_url(edicao), json=outro, headers=h_admin).json()
    assert (r["status"], r["aprovado_por"], r["aprovado_em"]) == ("pendente", None, None)
    assert client.get(f"/v1/edicoes/{edicao.id}").status_code == 404
    registro = _log(session, "direitos_alterados")[-1]
    assert registro.detalhes["status"] == ["aprovado", "pendente"]


def test_salvar_sem_mudar_nada_mantem_a_aprovacao(client, session, h_admin, edicao):
    """Reenviar o mesmo formulário não pode derrubar um livro publicado."""
    _aprovar_e_publicar(client, h_admin, edicao)
    r = client.put(_url(edicao), json=COMPLETO, headers=h_admin).json()
    assert r["status"] == "aprovado"
    assert _log(session, "direitos_alterados")[1:] == []  # só o cadastro inicial


def test_recusar_edicao_publicada_tira_do_ar(client, session, h_admin, edicao):
    _aprovar_e_publicar(client, h_admin, edicao)
    r = client.post(_url(edicao, "/recusar"), json={"motivo": "parecer revisto"}, headers=h_admin)
    assert r.json()["status"] == "recusado"
    assert client.get(f"/v1/edicoes/{edicao.id}").status_code == 404
    [registro] = _log(session, "direitos_recusados")
    assert registro.detalhes == {"motivo": "parecer revisto", "estava_publicada": True}


def test_publicar_bloqueado_ate_aprovar(client, h_admin, edicao):
    r = client.post(f"/v1/admin/edicoes/{edicao.id}/publicar", headers=h_admin)
    assert r.status_code == 409


@pytest.mark.parametrize(
    "url", ["http://exemplo.org/parecer.pdf", "javascript:alert(1)", "ftp://exemplo.org/x"]
)
def test_documento_so_por_https(client, h_admin, edicao, url):
    r = client.put(_url(edicao), json={**COMPLETO, "documento_url": url}, headers=h_admin)
    assert r.status_code == 422


@pytest.mark.parametrize("papel", [PapelUsuario.REVISOR_TEXTO, PapelUsuario.REVISOR_AUDIO])
def test_revisor_ve_mas_nao_mexe(client, session, edicao, papel):
    h = _login(client, session, "rev@exemplo.org", papel)
    assert client.get(_url(edicao), headers=h).status_code == 200
    assert client.put(_url(edicao), json=COMPLETO, headers=h).status_code == 403
    assert client.post(_url(edicao, "/aprovar"), headers=h).status_code == 403
    assert client.post(_url(edicao, "/recusar"), json={"motivo": "x"}, headers=h).status_code == 403


def test_sem_sessao(client, edicao):
    assert client.get(_url(edicao)).status_code == 401


def test_edicao_inexistente(client, h_admin):
    assert client.get("/v1/admin/edicoes/999/direitos", headers=h_admin).status_code == 404


def test_status_inicial_pendente_no_banco(client, session, h_admin, edicao):
    client.put(_url(edicao), json=COMPLETO, headers=h_admin)
    session.refresh(edicao)
    assert edicao.direitos.status == StatusDireitos.PENDENTE
