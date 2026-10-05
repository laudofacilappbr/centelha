import json

from centelha_api import lgpd
from centelha_api.models import InscricaoListaEspera


def _inscrever(session, *emails):
    for e in emails:
        session.add(InscricaoListaEspera(email=e, origem="site"))
    session.commit()


def test_exportar_traz_finalidade_e_base_legal(session):
    _inscrever(session, "maria@exemplo.com", "joao@exemplo.com")
    dados = lgpd.exportar(session, " Maria@Exemplo.com ")
    assert dados["titular"] == "maria@exemplo.com"
    [registro] = dados["lista_de_espera"]
    assert registro["email"] == "maria@exemplo.com"
    assert "consentimento" in registro["base_legal"]


def test_exportar_titular_sem_dados(session):
    assert lgpd.exportar(session, "ninguem@exemplo.com")["lista_de_espera"] == []


def test_excluir_so_o_titular(session):
    _inscrever(session, "maria@exemplo.com", "joao@exemplo.com")
    assert lgpd.excluir(session, "MARIA@exemplo.com") == 1
    assert [i.email for i in session.query(InscricaoListaEspera)] == ["joao@exemplo.com"]
    assert lgpd.excluir(session, "maria@exemplo.com") == 0


def test_cli_excluir_nao_imprime_o_email(session, capsys):
    _inscrever(session, "maria@exemplo.com")
    assert lgpd.main(["excluir", "maria@exemplo.com"]) == 0
    saida = capsys.readouterr().out
    assert "maria" not in saida
    assert "registros=1" in saida


def test_cli_exportar(session, capsys):
    _inscrever(session, "maria@exemplo.com")
    lgpd.main(["exportar", "maria@exemplo.com"])
    assert json.loads(capsys.readouterr().out)["lista_de_espera"][0]["origem"] == "site"
