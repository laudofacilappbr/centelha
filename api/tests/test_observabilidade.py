import json
import logging

from centelha_api import observabilidade
from centelha_api.observabilidade import FormatoJSON, contexto, limpar_evento


def _linhas_json(capsys):
    return [json.loads(linha) for linha in capsys.readouterr().out.splitlines() if linha]


def test_gera_request_id_e_devolve_no_cabecalho(client, capsys):
    r = client.get("/v1/config")
    rid = r.headers["x-request-id"]
    assert len(rid) == 32
    [acesso] = [linha for linha in _linhas_json(capsys) if linha["logger"] == "centelha.acesso"]
    assert acesso["request_id"] == rid
    assert acesso["metodo"] == "GET"
    assert acesso["caminho"] == "/v1/config"
    assert acesso["status"] == 200
    assert acesso["servico"] == "api"


def test_respeita_id_valido_e_troca_id_suspeito(client):
    bom = "abc123-def456"
    assert client.get("/v1/config", headers={"x-request-id": bom}).headers["x-request-id"] == bom
    ruim = "x\nnivel=critico"
    assert client.get("/v1/config", headers={"x-request-id": ruim}).headers["x-request-id"] != ruim
    ray = "8c1f2a3b4c5d6e7f-GRU"
    assert client.get("/v1/config", headers={"cf-ray": ray}).headers["x-request-id"] == ray


def test_acesso_sem_query_string_e_sem_health(client, capsys):
    client.get("/v1/obras?idioma=pt-BR&email=fulano@exemplo.com")
    client.get("/health")
    linhas = [linha for linha in _linhas_json(capsys) if linha["logger"] == "centelha.acesso"]
    assert [linha["caminho"] for linha in linhas] == ["/v1/obras"]
    assert "fulano" not in json.dumps(linhas)


def test_contexto_entra_nas_linhas_e_some_depois():
    registro = logging.LogRecord("t", logging.INFO, __file__, 1, "oi %s", ("x",), None)
    fmt = FormatoJSON("worker")
    with contexto(job_id=7, capitulo_id=3):
        dentro = json.loads(fmt.format(registro))
    fora = json.loads(fmt.format(registro))
    assert (dentro["job_id"], dentro["capitulo_id"], dentro["msg"]) == (7, 3, "oi x")
    assert "job_id" not in fora


def test_sentry_desligado_sem_dsn():
    assert observabilidade.configurar_sentry("api") is False


def test_limpar_evento_tira_credenciais_e_emails():
    evento = {
        "request": {
            "headers": {"Authorization": "Bearer segredo", "Accept": "json"},
            "cookies": {"s": "x"},
            "data": {"email": "a@b.com"},
        },
        "message": "falhou para maria@exemplo.com",
        "exception": {"values": [{"value": "erro com joao@exemplo.org"}]},
        "user": {"email": "x@y.com"},
    }
    limpo = limpar_evento(evento)
    assert limpo["request"]["headers"] == {"Authorization": "[removido]", "Accept": "json"}
    assert "cookies" not in limpo["request"] and "data" not in limpo["request"]
    assert limpo["message"] == "falhou para [email]"
    assert limpo["exception"]["values"][0]["value"] == "erro com [email]"
    assert "user" not in limpo
