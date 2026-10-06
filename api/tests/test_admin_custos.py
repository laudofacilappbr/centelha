import pytest

from centelha_api.config import get_settings
from centelha_api.db import SessionLocal
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
    Segmento,
    TipoSegmento,
    Usuario,
    Voz,
)
from centelha_api.pipeline import jobs, worker
from centelha_api.pipeline.armazenamento import ArmazenamentoLocal
from centelha_api.pipeline.tts.motores import MotorFalso

SENHA = "cavalo correto bateria grampo"


def _login(client, session, papel):
    email = f"{papel.value}@exemplo.org"
    session.add(Usuario(email=email, nome=email, papel=papel, senha_hash=contas.gerar_hash(SENHA)))
    session.commit()
    r = client.post("/v1/admin/sessoes", json={"email": email, "senha": SENHA})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def h(client, session):
    return {p: _login(client, session, p) for p in PapelUsuario}


@pytest.fixture
def gerado(session, tmp_path):
    """Capítulo 1 gerado duas vezes (motor falso), capítulo 2 uma vez e um job falho."""
    ed = Edicao(
        obra=Obra(
            slug="le",
            autor="Allan Kardec",
            titulo_original="Le Livre des Esprits",
            idioma_original="fr",
            sigla="LE",
        ),
        idioma="pt-BR",
        titulo="O Livro dos Espíritos",
        fonte="teste",
    )
    for ordem in (1, 2):
        cap = Capitulo(
            ordem=ordem,
            titulo=f"Capítulo {ordem}",
            referencia_canonica=f"LE-C00{ordem}",
            estado=EstadoCapitulo.TEXTO_REVISADO,
        )
        cap.segmentos = [Segmento(ordem=1, tipo=TipoSegmento.PARAGRAFO, texto="x" * 50 * ordem)]
        ed.capitulos.append(cap)
    voz = Voz(idioma="pt-BR", motor="falso", voz_id="n", papel=PapelVoz.NARRADOR)
    session.add_all([ed, voz])
    session.commit()
    armazenamento = ArmazenamentoLocal(tmp_path, "https://audio.exemplo")

    def gerar(cap):
        jobs.enfileirar(session, cap, "falso", voz)
        session.commit()
        assert worker.processar_um(SessionLocal, armazenamento, MotorFalso())

    c1, c2 = ed.capitulos
    gerar(c1)
    gerar(c1)
    gerar(c2)
    session.add(
        JobAudio(
            capitulo_id=c2.id,
            motor="azure",
            voz_narrador_id=voz.id,
            estado=EstadoJob.FALHOU,
            erro="provedor fora",
        )
    )
    session.commit()
    return {"ed": ed, "c1": c1, "c2": c2}


def test_versoes_do_capitulo_da_mais_nova_para_a_mais_antiga(client, h, gerado):
    r = client.get(
        f"/v1/admin/capitulos/{gerado['c1'].id}/faixas", headers=h[PapelUsuario.REVISOR_AUDIO]
    )
    assert r.status_code == 200
    versoes = r.json()
    assert [(v["versao"], v["atual"]) for v in versoes] == [(2, True), (1, False)]
    assert all(v["motor"] == "falso" and v["caracteres"] == 50 for v in versoes)
    assert versoes[0]["url"].endswith("le-c001-v2.m4a")


def test_versoes_de_capitulo_inexistente(client, h):
    assert (
        client.get(
            "/v1/admin/capitulos/999/faixas", headers=h[PapelUsuario.ADMINISTRADOR]
        ).status_code
        == 404
    )


def test_custo_soma_todas_as_geracoes(client, h, gerado):
    r = client.get(
        f"/v1/admin/edicoes/{gerado['ed'].id}/custo", headers=h[PapelUsuario.ADMINISTRADOR]
    )
    assert r.status_code == 200
    c = r.json()
    # Duas gerações do capítulo 1 (50 + 50) e uma do 2 (100): regenerar também custa.
    assert c["caracteres"] == 200
    assert [(x["ordem"], x["geracoes"], x["caracteres"]) for x in c["por_capitulo"]] == [
        (1, 2, 100),
        (2, 1, 100),
    ]
    assert c["por_motor"] == [
        {
            "motor": "falso",
            "jobs": 3,
            "caracteres": 200,
            "preco_por_milhao": 0.0,
            "custo_estimado": 0.0,
        }
    ]
    assert c["custo_estimado"] == 0.0
    assert c["jobs_falhos"] == 1
    assert c["moeda"] == "BRL"


def test_custo_com_preco_configurado_e_sem_preco(client, h, gerado, monkeypatch, session):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "tts_preco_por_milhao", {"falso": 100.0})
    url = f"/v1/admin/edicoes/{gerado['ed'].id}/custo"
    c = client.get(url, headers=h[PapelUsuario.ADMINISTRADOR]).json()
    assert c["custo_estimado"] == pytest.approx(0.02)

    # Motor sem preço: o total vira nulo em vez de parecer completo.
    job = session.query(JobAudio).filter_by(estado=EstadoJob.CONCLUIDO).first()
    job.motor = "azure"
    session.commit()
    c = client.get(url, headers=h[PapelUsuario.ADMINISTRADOR]).json()
    azure = next(m for m in c["por_motor"] if m["motor"] == "azure")
    assert azure["custo_estimado"] is None
    assert c["custo_estimado"] is None
    assert c["caracteres"] == 200


@pytest.mark.parametrize("papel", [PapelUsuario.REVISOR_TEXTO, PapelUsuario.REVISOR_AUDIO])
def test_custo_so_para_administrador(client, h, gerado, papel):
    r = client.get(f"/v1/admin/edicoes/{gerado['ed'].id}/custo", headers=h[papel])
    assert r.status_code == 403
