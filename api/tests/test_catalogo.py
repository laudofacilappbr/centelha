from datetime import UTC, datetime

import pytest

from centelha_api.config import get_settings
from centelha_api.models import (
    Capitulo,
    Direitos,
    Edicao,
    EstadoCapitulo,
    FaixaAudio,
    Obra,
    PapelVoz,
    Segmento,
    StatusDireitos,
    TipoSegmento,
    Voz,
)


@pytest.fixture
def catalogo(session):
    """Uma edição publicada (2 capítulos publicados, 1 não) e uma edição não publicada."""
    obra = Obra(
        slug="o-livro-dos-espiritos",
        autor="Allan Kardec",
        titulo_original="Le Livre des Esprits",
        ano=1857,
        idioma_original="fr",
        sigla="LE",
    )
    publicada = Edicao(
        obra=obra,
        idioma="pt-BR",
        titulo="O Livro dos Espíritos",
        tradutor="Guillon Ribeiro",
        fonte="edição-fonte",
        publicada_em=datetime(2026, 10, 5, tzinfo=UTC),
        direitos=Direitos(status=StatusDireitos.APROVADO),
    )
    rascunho = Edicao(obra=obra, idioma="fr", titulo="Le Livre des Esprits", fonte="original")
    c1 = Capitulo(
        ordem=1, titulo="Capítulo I", referencia_canonica="LE-C001", estado=EstadoCapitulo.PUBLICADO
    )
    c1.segmentos = [
        Segmento(ordem=1, tipo=TipoSegmento.TITULO, texto="Capítulo I"),
        Segmento(ordem=2, tipo=TipoSegmento.PERGUNTA, texto="Pergunta?", numero_questao=88),
        Segmento(ordem=3, tipo=TipoSegmento.RESPOSTA, texto="Resposta.", numero_questao=88),
        Segmento(
            ordem=4,
            tipo=TipoSegmento.PERGUNTA,
            texto="Sub?",
            numero_questao=88,
            subquestao="a",
        ),
    ]
    c2 = Capitulo(
        ordem=2,
        titulo="Capítulo II",
        referencia_canonica="LE-C002",
        estado=EstadoCapitulo.AUDIO_GERADO,
    )
    c2.segmentos = [
        Segmento(ordem=1, tipo=TipoSegmento.PERGUNTA, texto="Não revisada?", numero_questao=99)
    ]
    publicada.capitulos = [c1, c2]
    session.add_all([publicada, rascunho])
    session.flush()
    voz = Voz(idioma="pt-BR", motor="azure", voz_id="x", papel=PapelVoz.NARRADOR)
    session.add(voz)
    session.flush()
    for versao in (1, 2):
        session.add(
            FaixaAudio(
                capitulo_id=c1.id,
                voz_id=voz.id,
                versao=versao,
                url=f"https://audio.exemplo/le/c001-v{versao}.m4a",
                duracao_ms=1000 * versao,
                marcacoes=[{"segmento_id": 1, "inicio_ms": 0, "fim_ms": 500}],
            )
        )
    session.commit()
    return {"publicada": publicada, "rascunho": rascunho, "c1": c1, "c2": c2}


def test_obras_so_lista_edicoes_publicadas(client, catalogo):
    r = client.get("/v1/obras")
    assert r.status_code == 200
    assert "s-maxage" in r.headers["cache-control"]
    [obra] = r.json()
    assert obra["sigla"] == "LE"
    assert [e["idioma"] for e in obra["edicoes"]] == ["pt-BR"]


def test_obras_filtra_idioma(client, catalogo):
    assert client.get("/v1/obras", params={"idioma": "es"}).json() == []
    assert len(client.get("/v1/obras", params={"idioma": "pt-BR"}).json()) == 1


def test_edicao_esconde_capitulo_nao_publicado(client, catalogo):
    r = client.get(f"/v1/edicoes/{catalogo['publicada'].id}")
    assert [c["referencia_canonica"] for c in r.json()["capitulos"]] == ["LE-C001"]


def test_edicao_rascunho_e_404(client, catalogo):
    assert client.get(f"/v1/edicoes/{catalogo['rascunho'].id}").status_code == 404
    assert client.get("/v1/edicoes/999999").status_code == 404


def test_capitulo_traz_segmentos_e_faixa_mais_recente(client, catalogo):
    r = client.get(f"/v1/capitulos/{catalogo['c1'].id}").json()
    assert [s["tipo"] for s in r["segmentos"]] == ["titulo", "pergunta", "resposta", "pergunta"]
    assert r["segmentos"][3]["subquestao"] == "a"
    assert r["faixa"]["versao"] == 2
    assert r["faixa"]["marcacoes"][0]["fim_ms"] == 500
    assert r["faixa"]["formato"] == "m4a"
    assert isinstance(r["faixa"]["id"], int)
    # A chave da faixa nunca sai na API pública, nem com a faixa cifrada.
    assert "chave_cifrada" not in r["faixa"]


def test_capitulo_nao_publicado_e_404(client, catalogo):
    assert client.get(f"/v1/capitulos/{catalogo['c2'].id}").status_code == 404


def test_busca_por_questao(client, catalogo):
    r = client.get(f"/v1/edicoes/{catalogo['publicada'].id}/questoes/88").json()
    assert r["referencia"] == "LE-88"
    assert r["capitulo"]["referencia_canonica"] == "LE-C001"
    assert [(s["tipo"], s["subquestao"]) for s in r["segmentos"]] == [
        ("pergunta", None),
        ("resposta", None),
        ("pergunta", "a"),
    ]


def test_questao_em_capitulo_nao_publicado_e_404(client, catalogo):
    url = f"/v1/edicoes/{catalogo['publicada'].id}/questoes/99"
    assert client.get(url).status_code == 404


def test_config_remota_mvp_tudo_desligado(client):
    assert client.get("/v1/config").json() == {"apoio": False, "caridade": False, "anuncios": False}


@pytest.mark.parametrize("status", [StatusDireitos.PENDENTE, StatusDireitos.RECUSADO])
def test_direitos_revogados_tiram_a_edicao_do_ar(client, session, catalogo, status):
    """Nada é publicado sem direitos aprovados, nem depois de publicado: se os direitos
    mudam, obra, edição, capítulo e questão somem do catálogo na mesma hora."""
    edicao, c1 = catalogo["publicada"], catalogo["c1"]
    assert client.get(f"/v1/capitulos/{c1.id}").status_code == 200
    edicao.direitos.status = status
    session.commit()
    assert client.get("/v1/obras").json() == []
    assert client.get(f"/v1/edicoes/{edicao.id}").status_code == 404
    assert client.get(f"/v1/capitulos/{c1.id}").status_code == 404
    assert client.get(f"/v1/edicoes/{edicao.id}/questoes/88").status_code == 404


def test_publicada_sem_registro_de_direitos_nao_aparece(client, session, catalogo):
    """publicada_em gravado por fora de publicar_edicao (script, SQL manual) não basta."""
    edicao = catalogo["publicada"]
    session.delete(edicao.direitos)
    session.commit()
    assert client.get(f"/v1/edicoes/{edicao.id}").status_code == 404


def test_faixa_de_motor_sem_licenca_nao_sai_no_catalogo(client, session, catalogo, monkeypatch):
    """Piper só em desenvolvimento até o parecer (#1, #3): regerar o capítulo no Piper
    não troca a faixa que o app recebe."""
    piper = Voz(idioma="pt-BR", motor="piper", voz_id="pt_BR-faber-medium", papel=PapelVoz.NARRADOR)
    session.add(piper)
    session.flush()
    session.add(
        FaixaAudio(
            capitulo_id=catalogo["c1"].id,
            voz_id=piper.id,
            versao=3,
            url="https://audio.exemplo/le/c001-v3.m4a",
            duracao_ms=3000,
            marcacoes=[],
        )
    )
    session.commit()
    url = f"/v1/capitulos/{catalogo['c1'].id}"
    assert client.get(url).json()["faixa"]["versao"] == 2

    monkeypatch.setattr(get_settings(), "tts_motores_sem_licenca", set())
    assert client.get(url).json()["faixa"]["versao"] == 3


def test_capitulo_so_com_faixa_sem_licenca_sai_sem_faixa(client, session, catalogo):
    session.query(Voz).update({Voz.motor: "piper"})
    session.commit()
    r = client.get(f"/v1/capitulos/{catalogo['c1'].id}").json()
    assert r["faixa"] is None
    assert r["segmentos"]


def test_edicao_diz_quais_capitulos_tem_audio(client, session, catalogo):
    """Capítulo publicado só com texto aparece na lista sem áudio, e o app avisa (#167).
    Faixa de motor sem licença liberada não conta como áudio."""
    edicao, c2 = catalogo["publicada"], catalogo["c2"]
    c2.estado = EstadoCapitulo.PUBLICADO
    session.commit()
    url = f"/v1/edicoes/{edicao.id}"
    tem = {c["referencia_canonica"]: c["tem_audio"] for c in client.get(url).json()["capitulos"]}
    assert tem == {"LE-C001": True, "LE-C002": False}

    session.query(Voz).update({Voz.motor: "piper"})
    session.commit()
    tem = {c["referencia_canonica"]: c["tem_audio"] for c in client.get(url).json()["capitulos"]}
    assert tem == {"LE-C001": False, "LE-C002": False}
