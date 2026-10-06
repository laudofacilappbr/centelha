import pytest
from sqlalchemy import select

from centelha_api.dominio import contas
from centelha_api.models import PapelUsuario, RegistroAuditoria, Usuario

SENHA = "cavalo correto bateria grampo"
URL = "/v1/admin/apoio"
LIGADO = {
    "ligado": True,
    "recebedor": "Fulana de Tal (pessoa física)",
    "mensagem": "Ajude a cobrir a narração e o servidor.",
    "valores_centavos": [2500, 500, 1000, 1000],
    "compra_no_app": True,
    "chave_pix": "123e4567-E89B-12d3-a456-426614174000",
    "link_externo": None,
}


def _login(client, session, papel):
    email = f"{papel.value}@exemplo.org"
    session.add(Usuario(email=email, nome=email, papel=papel, senha_hash=contas.gerar_hash(SENHA)))
    session.commit()
    r = client.post("/v1/admin/sessoes", json={"email": email, "senha": SENHA})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def h(client, session):
    return {p: _login(client, session, p) for p in PapelUsuario}


def test_apoio_nasce_desligado_e_nada_vaza(client):
    """Ligar depende de quem recebe estar resolvido (#4): sem ação do dono, o app e o
    site não mostram nenhum botão nem chave."""
    assert client.get("/v1/config").json()["apoio"] is False
    assert client.get("/v1/apoio").json() == {
        "ligado": False,
        "recebedor": None,
        "mensagem": None,
        "valores_centavos": [],
        "compra_no_app": False,
        "chave_pix": None,
        "link_externo": None,
    }


def test_ligar_aparece_no_config_do_app_e_no_site(client, session, h):
    ha = h[PapelUsuario.ADMINISTRADOR]
    r = client.put(URL, json=LIGADO, headers=ha)
    assert r.status_code == 200
    # Valores ordenados e sem repetição; chave aleatória normalizada.
    assert r.json()["valores_centavos"] == [500, 1000, 2500]
    assert r.json()["chave_pix"] == "123e4567-e89b-12d3-a456-426614174000"

    assert client.get("/v1/config").json()["apoio"] is True
    pub = client.get("/v1/apoio").json()
    assert pub["recebedor"] == "Fulana de Tal (pessoa física)"
    assert pub["valores_centavos"] == [500, 1000, 2500]

    # Desligar some com tudo do público, mas guarda a configuração para religar.
    assert client.put(URL, json={**LIGADO, "ligado": False}, headers=ha).status_code == 200
    assert client.get("/v1/apoio").json()["chave_pix"] is None
    assert client.get(URL, headers=ha).json()["chave_pix"] == LIGADO["chave_pix"].lower()

    log = session.scalars(
        select(RegistroAuditoria).where(RegistroAuditoria.acao == "apoio_alterado")
    ).all()
    assert len(log) == 2
    assert log[0].detalhes["antes"] is None
    assert log[1].detalhes["antes"]["ligado"] is True


@pytest.mark.parametrize(
    ("campo", "valor", "falta"),
    [
        ("recebedor", None, "quem recebe"),
        ("valores_centavos", [], "valor sugerido"),
    ],
)
def test_ligar_exige_recebedor_meio_e_valor(client, h, campo, valor, falta):
    """Dinheiro que fica com o projeto não pode parecer caridade: a página diz para
    quem vai. Ligado sem meio seria um botão que não leva a lugar nenhum."""
    ha = h[PapelUsuario.ADMINISTRADOR]
    r = client.put(URL, json={**LIGADO, campo: valor}, headers=ha)
    assert r.status_code == 422
    assert falta in r.json()["detail"]


def test_ligar_sem_nenhum_meio_e_recusado(client, h):
    corpo = {**LIGADO, "compra_no_app": False, "chave_pix": None, "link_externo": None}
    r = client.put(URL, json=corpo, headers=h[PapelUsuario.ADMINISTRADOR])
    assert r.status_code == 422
    assert "meio" in r.json()["detail"]
    assert client.get("/v1/config").json()["apoio"] is False


@pytest.mark.parametrize(
    "chave",
    ["123.456.789-09", "12345678909", "não é chave", "+5511"],
)
def test_chave_pix_cpf_ou_invalida_e_recusada(client, h, chave):
    """Chave CPF publicaria o documento de quem recebe (pessoa física, #4)."""
    r = client.put(URL, json={**LIGADO, "chave_pix": chave}, headers=h[PapelUsuario.ADMINISTRADOR])
    assert r.status_code == 422


@pytest.mark.parametrize(
    ("chave", "gravada"),
    [
        ("apoio@centelha.app", "apoio@centelha.app"),
        ("+55 11 91234-5678".replace("-", ""), "+5511912345678"),
        ("12.345.678/0001-95", "12345678000195"),
    ],
)
def test_chaves_pix_aceitas(client, h, chave, gravada):
    r = client.put(URL, json={**LIGADO, "chave_pix": chave}, headers=h[PapelUsuario.ADMINISTRADOR])
    assert r.status_code == 200
    assert r.json()["chave_pix"] == gravada


@pytest.mark.parametrize(
    "link", ["http://apoie.exemplo.org", "javascript:alert(1)", 'https://x.org/"onclick']
)
def test_link_externo_so_https(client, h, link):
    r = client.put(
        URL, json={**LIGADO, "link_externo": link}, headers=h[PapelUsuario.ADMINISTRADOR]
    )
    assert r.status_code == 422


def test_valores_fora_da_faixa(client, h):
    ha = h[PapelUsuario.ADMINISTRADOR]
    assert client.put(URL, json={**LIGADO, "valores_centavos": [50]}, headers=ha).status_code == 422
    seis = [100, 200, 300, 400, 500, 600, 700]
    assert client.put(URL, json={**LIGADO, "valores_centavos": seis}, headers=ha).status_code == 422


def test_so_administrador_mexe_no_apoio(client, h):
    for papel in (PapelUsuario.REVISOR_TEXTO, PapelUsuario.REVISOR_AUDIO):
        assert client.get(URL, headers=h[papel]).status_code == 403
        assert client.put(URL, json=LIGADO, headers=h[papel]).status_code == 403
    assert client.put(URL, json=LIGADO).status_code == 401
    assert client.get("/v1/config").json()["apoio"] is False
