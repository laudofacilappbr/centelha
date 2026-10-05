from sqlalchemy import func, select

from centelha_api.models import InscricaoListaEspera


def _total(session):
    return session.scalar(select(func.count()).select_from(InscricaoListaEspera))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_inscreve_e_normaliza_email(client, session):
    r = client.post("/v1/waitlist", json={"email": "Maria@Exemplo.com.br", "origem": "site"})
    assert r.status_code == 202
    inscricao = session.scalar(select(InscricaoListaEspera))
    assert inscricao.email == "maria@exemplo.com.br"
    assert inscricao.origem == "site"


def test_duplicado_responde_igual_e_nao_duplica(client, session):
    for email in ("a@exemplo.com", "A@exemplo.com"):
        r = client.post("/v1/waitlist", json={"email": email})
        assert r.status_code == 202
        assert r.json() == {"status": "ok"}
    assert _total(session) == 1


def test_rejeita_email_invalido(client, session):
    assert client.post("/v1/waitlist", json={"email": "nao-e-email"}).status_code == 422
    assert (
        client.post("/v1/waitlist", json={"email": "a@b.com", "origem": "<x>"}).status_code == 422
    )
    assert _total(session) == 0


def test_limite_por_ip_usa_cf_connecting_ip(client):
    for i in range(5):
        r = client.post(
            "/v1/waitlist",
            json={"email": f"p{i}@exemplo.com"},
            headers={"cf-connecting-ip": "1.1.1.1"},
        )
        assert r.status_code == 202
    bloqueado = client.post(
        "/v1/waitlist", json={"email": "p9@exemplo.com"}, headers={"cf-connecting-ip": "1.1.1.1"}
    )
    assert bloqueado.status_code == 429
    outro_ip = client.post(
        "/v1/waitlist", json={"email": "p9@exemplo.com"}, headers={"cf-connecting-ip": "2.2.2.2"}
    )
    assert outro_ip.status_code == 202


def test_cors_permite_site(client):
    r = client.options(
        "/v1/waitlist",
        headers={"Origin": "http://localhost:4321", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:4321"
