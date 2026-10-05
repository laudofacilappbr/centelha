from datetime import UTC, datetime

import pytest

from centelha_api.models import (
    Capitulo,
    Edicao,
    EstadoCapitulo,
    FaixaAudio,
    Obra,
    PapelVoz,
    Segmento,
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
    voz = Voz(idioma="pt-BR", motor="piper", voz_id="x", papel=PapelVoz.NARRADOR)
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
