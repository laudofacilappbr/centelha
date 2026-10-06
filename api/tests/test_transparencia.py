from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from centelha_api.dominio import contas
from centelha_api.models import (
    Capitulo,
    Edicao,
    EstadoCapitulo,
    EstadoJob,
    JobAudio,
    Obra,
    PapelUsuario,
    PapelVoz,
    RegistroAuditoria,
    Usuario,
    Voz,
)

SENHA = "cavalo correto bateria grampo"
URL = "/v1/admin/transparencia"


def _login(client, session, papel):
    email = f"{papel.value}@exemplo.org"
    session.add(Usuario(email=email, nome=email, papel=papel, senha_hash=contas.gerar_hash(SENHA)))
    session.commit()
    r = client.post("/v1/admin/sessoes", json={"email": email, "senha": SENHA})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def h(client, session):
    return {p: _login(client, session, p) for p in PapelUsuario}


def _lancar(client, h, mes="2026-10", **kw):
    corpo = {"tipo": "custo", "item": "Servidor", "valor_centavos": 4990, **kw}
    return client.post(f"{URL}/meses/{mes}/lancamentos", json=corpo, headers=h)


def test_mes_so_aparece_no_site_depois_de_publicado(client, h):
    """Mês pela metade daria um custo menor que o real, e é essa a conta que a página
    existe para mostrar."""
    ha = h[PapelUsuario.ADMINISTRADOR]
    assert _lancar(client, ha).status_code == 201
    _lancar(client, ha, item="Narração por IA", valor_centavos=1210)
    _lancar(client, ha, tipo="arrecadacao", item="Apoio voluntário", valor_centavos=3000)
    assert client.get("/v1/transparencia").json() == []

    r = client.post(f"{URL}/meses/2026-10/publicar", headers=ha)
    assert r.status_code == 200
    [mes] = client.get("/v1/transparencia").json()
    assert mes["mes"] == "2026-10"
    assert [c["item"] for c in mes["custos"]] == ["Servidor", "Narração por IA"]
    assert (mes["total_custos_centavos"], mes["total_arrecadacao_centavos"]) == (6200, 3000)


def test_mes_publicado_nao_muda_em_silencio(client, session, h):
    """Corrigir exige despublicar, e as duas coisas ficam no log."""
    ha = h[PapelUsuario.ADMINISTRADOR]
    lid = _lancar(client, ha).json()["id"]
    client.post(f"{URL}/meses/2026-10/publicar", headers=ha)

    assert _lancar(client, ha, item="Outro").status_code == 409
    corpo = {"tipo": "custo", "item": "Servidor", "valor_centavos": 1}
    assert client.put(f"{URL}/lancamentos/{lid}", json=corpo, headers=ha).status_code == 409
    assert client.delete(f"{URL}/lancamentos/{lid}", headers=ha).status_code == 409

    assert client.post(f"{URL}/meses/2026-10/despublicar", headers=ha).status_code == 200
    assert client.get("/v1/transparencia").json() == []
    r = client.put(f"{URL}/lancamentos/{lid}", json=corpo, headers=ha)
    assert r.json()["valor_centavos"] == 1
    acoes = session.scalars(
        select(RegistroAuditoria.acao).where(RegistroAuditoria.acao.like("transparencia_%"))
    ).all()
    assert acoes == [
        "transparencia_lancada",
        "transparencia_publicada",
        "transparencia_despublicada",
        "transparencia_corrigida",
    ]


def test_mes_vazio_nao_publica(client, h):
    r = client.post(f"{URL}/meses/2026-09/publicar", headers=h[PapelUsuario.ADMINISTRADOR])
    assert r.status_code == 409


@pytest.mark.parametrize("papel", [PapelUsuario.REVISOR_TEXTO, PapelUsuario.REVISOR_AUDIO])
def test_so_administrador(client, h, papel):
    assert _lancar(client, h[papel]).status_code == 403
    assert client.get(f"{URL}/meses", headers=h[papel]).status_code == 403


@pytest.mark.parametrize(
    "mes,corpo",
    [
        ("2026-13", {}),
        ("26-10", {}),
        ("2026-10", {"valor_centavos": -1}),
        ("2026-10", {"tipo": "doacao"}),
        ("2026-10", {"item": ""}),
    ],
)
def test_entrada_invalida(client, h, mes, corpo):
    assert _lancar(client, h[PapelUsuario.ADMINISTRADOR], mes=mes, **corpo).status_code == 422


def test_estimativa_de_tts_do_mes_no_admin(client, session, h):
    """Referência para lançar a fatura, nunca o valor público: só jobs concluídos no
    mês, pelo preço configurado do motor."""
    obra = Obra(slug="x", autor="A", titulo_original="X", idioma_original="fr", sigla="X")
    ed = Edicao(obra=obra, idioma="pt-BR", titulo="X", fonte="t")
    cap = Capitulo(
        ordem=1, titulo="I", referencia_canonica="X-1", estado=EstadoCapitulo.AUDIO_GERADO
    )
    ed.capitulos = [cap]
    voz = Voz(idioma="pt-BR", motor="falso", voz_id="n", papel=PapelVoz.NARRADOR)
    session.add_all([ed, voz])
    session.flush()
    for quando, car in [
        (datetime(2026, 10, 3, tzinfo=UTC), 1000),
        (datetime(2026, 10, 30, tzinfo=UTC), 500),
        (datetime(2026, 11, 1, tzinfo=UTC), 9999),
    ]:
        session.add(
            JobAudio(
                capitulo_id=cap.id,
                motor="falso",
                voz_narrador_id=voz.id,
                estado=EstadoJob.CONCLUIDO,
                caracteres=car,
                concluido_em=quando,
            )
        )
    session.commit()
    r = client.get(f"{URL}/meses/2026-10", headers=h[PapelUsuario.ADMINISTRADOR]).json()
    assert r["estimativa_tts"] == {"caracteres": 1500, "custo_estimado": 0.0}
    assert r["lancamentos"] == []
    # Não vaza para o público.
    assert client.get("/v1/transparencia").json() == []


def test_resposta_publica_tem_cache(client, h):
    r = client.get("/v1/transparencia")
    assert "s-maxage" in r.headers["cache-control"]
