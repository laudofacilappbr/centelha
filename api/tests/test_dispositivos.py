import base64
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from centelha_api.config import get_settings
from centelha_api.models import (
    Capitulo,
    DesafioAtestacao,
    Direitos,
    Dispositivo,
    Edicao,
    EntregaChave,
    EstadoCapitulo,
    FaixaAudio,
    Obra,
    PapelVoz,
    StatusDireitos,
    Voz,
)
from centelha_api.pipeline import cifra
from centelha_api.routers.dispositivos import limitador_desafio

MESTRA = cifra.nova_chave()
CHAVE_FAIXA = cifra.nova_chave()


@pytest.fixture(autouse=True)
def config(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "atestacao_falsa", True)
    monkeypatch.setattr(cfg, "ambiente", "desenvolvimento")
    monkeypatch.setattr(cfg, "audio_chave_mestra", base64.b64encode(MESTRA).decode())
    limitador_desafio.limpar()
    return cfg


@pytest.fixture
def faixas(session):
    """Faixa cifrada publicada, faixa aberta publicada e faixa cifrada não publicada."""
    edicao = Edicao(
        obra=Obra(
            slug="o-livro-dos-espiritos",
            autor="Allan Kardec",
            titulo_original="Le Livre des Esprits",
            idioma_original="fr",
            sigla="LE",
        ),
        idioma="pt-BR",
        titulo="O Livro dos Espíritos",
        fonte="edição-fonte",
        publicada_em=datetime(2026, 10, 5, tzinfo=UTC),
        direitos=Direitos(status=StatusDireitos.APROVADO),
    )
    caps = [
        Capitulo(ordem=i, titulo=f"Capítulo {i}", referencia_canonica=f"LE-C00{i}", estado=e)
        for i, e in (
            (1, EstadoCapitulo.PUBLICADO),
            (2, EstadoCapitulo.PUBLICADO),
            (3, EstadoCapitulo.AUDIO_GERADO),
        )
    ]
    edicao.capitulos = caps
    voz = Voz(idioma="pt-BR", motor="falso", voz_id="n", papel=PapelVoz.NARRADOR)
    session.add_all([edicao, voz])
    session.flush()
    embrulhada = cifra.embrulhar(CHAVE_FAIXA, MESTRA)

    def faixa(cap, cifrada):
        return FaixaAudio(
            capitulo_id=cap.id,
            voz_id=voz.id,
            versao=1,
            url=f"https://audio.exemplo/{cap.referencia_canonica}.{'cent' if cifrada else 'm4a'}",
            duracao_ms=1000,
            marcacoes=[],
            formato="cent1" if cifrada else "m4a",
            chave_cifrada=embrulhada if cifrada else None,
        )

    cifrada, aberta, rascunho = faixa(caps[0], True), faixa(caps[1], False), faixa(caps[2], True)
    session.add_all([cifrada, aberta, rascunho])
    session.commit()
    return {"cifrada": cifrada.id, "aberta": aberta.id, "rascunho": rascunho.id}


def _registrar(client) -> str:
    desafio = client.post("/v1/dispositivos/desafio").json()["desafio"]
    r = client.post(
        "/v1/dispositivos",
        json={"plataforma": "falso", "desafio": desafio, "atestado": f"falso:{desafio}"},
    )
    assert r.status_code == 201, r.text
    return r.json()["token"]


def _chave(client, faixa_id, token):
    return client.post(f"/v1/faixas/{faixa_id}/chave", headers={"Authorization": f"Bearer {token}"})


def test_fluxo_completo_entrega_a_chave_valida_por_90_dias(client, session, faixas):
    token = _registrar(client)
    r = _chave(client, faixas["cifrada"], token)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    corpo = r.json()
    assert base64.b64decode(corpo["chave"]) == CHAVE_FAIXA
    assert corpo["formato"] == "cent1"
    agora = session.scalar(select(func.now()))
    validade = datetime.fromisoformat(corpo["valida_ate"]) - agora
    assert timedelta(days=89, hours=23) < validade <= timedelta(days=90)

    # A chave entregue abre um .cent cifrado com a chave guardada da faixa.
    claro = b"audio de teste" * 100
    cent = cifra.cifrar(claro, CHAVE_FAIXA)
    assert cifra.decifrar(cent, base64.b64decode(corpo["chave"])) == claro

    dispositivo = session.scalar(select(Dispositivo))
    # O token não fica guardado, só o hash.
    assert token not in (dispositivo.token_hash, dispositivo.identificador)
    assert dispositivo.ultimo_uso_em is not None
    assert session.scalar(select(func.count(EntregaChave.id))) == 1


def test_sem_token_ou_com_token_errado_ou_revogado(client, session, faixas):
    assert client.post(f"/v1/faixas/{faixas['cifrada']}/chave").status_code == 401
    assert _chave(client, faixas["cifrada"], "inventado").status_code == 401
    token = _registrar(client)
    session.execute(update(Dispositivo).values(revogado_em=func.now()))
    session.commit()
    r = _chave(client, faixas["cifrada"], token)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_desafio_e_de_uso_unico(client):
    desafio = client.post("/v1/dispositivos/desafio").json()["desafio"]
    corpo = {"plataforma": "falso", "desafio": desafio, "atestado": f"falso:{desafio}"}
    assert client.post("/v1/dispositivos", json=corpo).status_code == 201
    assert client.post("/v1/dispositivos", json=corpo).status_code == 403


def test_atestado_recusado_tambem_gasta_o_desafio(client):
    desafio = client.post("/v1/dispositivos/desafio").json()["desafio"]
    errado = {"plataforma": "falso", "desafio": desafio, "atestado": "falso:outro"}
    assert client.post("/v1/dispositivos", json=errado).status_code == 403
    certo = {**errado, "atestado": f"falso:{desafio}"}
    assert client.post("/v1/dispositivos", json=certo).status_code == 403


def test_desafio_vencido_pelo_relogio_do_banco(client, session):
    desafio = client.post("/v1/dispositivos/desafio").json()["desafio"]
    session.execute(update(DesafioAtestacao).values(expira_em=func.now() - timedelta(seconds=1)))
    session.commit()
    corpo = {"plataforma": "falso", "desafio": desafio, "atestado": f"falso:{desafio}"}
    assert client.post("/v1/dispositivos", json=corpo).status_code == 403


def test_atestacao_falsa_nunca_vale_em_producao(client, config, monkeypatch):
    monkeypatch.setattr(config, "ambiente", "producao")
    desafio = client.post("/v1/dispositivos/desafio").json()["desafio"]
    corpo = {"plataforma": "falso", "desafio": desafio, "atestado": f"falso:{desafio}"}
    assert client.post("/v1/dispositivos", json=corpo).status_code == 400


@pytest.mark.parametrize("plataforma", ["ios", "android"])
def test_plataforma_sem_verificador_configurado_nao_libera(client, plataforma):
    desafio = client.post("/v1/dispositivos/desafio").json()["desafio"]
    corpo = {"plataforma": plataforma, "desafio": desafio, "atestado": "qualquer"}
    r = client.post("/v1/dispositivos", json=corpo)
    assert r.status_code == 503
    assert "não configurada" in r.json()["detail"]


def test_faixa_aberta_nao_publicada_ou_inexistente(client, faixas):
    token = _registrar(client)
    assert _chave(client, faixas["aberta"], token).status_code == 409
    # Capítulo ainda em revisão: a chave não sai, mesmo para aparelho legítimo.
    assert _chave(client, faixas["rascunho"], token).status_code == 404
    assert _chave(client, 999999, token).status_code == 404


def test_limite_diario_por_aparelho(client, config, monkeypatch, faixas):
    monkeypatch.setattr(config, "chave_limite_por_dia", 2)
    token = _registrar(client)
    assert _chave(client, faixas["cifrada"], token).status_code == 200
    assert _chave(client, faixas["cifrada"], token).status_code == 200
    assert _chave(client, faixas["cifrada"], token).status_code == 429
    # Outro aparelho tem o próprio limite.
    assert _chave(client, faixas["cifrada"], _registrar(client)).status_code == 200


def test_chave_mestra_ausente_e_erro_do_servidor(client, config, monkeypatch, faixas):
    token = _registrar(client)
    monkeypatch.setattr(config, "audio_chave_mestra", "")
    assert _chave(client, faixas["cifrada"], token).status_code == 503


def test_limite_de_desafios_por_ip(client, config, monkeypatch):
    monkeypatch.setattr(config, "desafio_limite_por_ip", 2)
    assert client.post("/v1/dispositivos/desafio").status_code == 201
    assert client.post("/v1/dispositivos/desafio").status_code == 201
    assert client.post("/v1/dispositivos/desafio").status_code == 429


def test_faixa_de_motor_sem_licenca_nao_recebe_chave(client, session, faixas):
    session.query(Voz).update({Voz.motor: "piper"})
    session.commit()
    assert _chave(client, faixas["cifrada"], _registrar(client)).status_code == 404
