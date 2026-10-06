from datetime import UTC, datetime

import pytest

from centelha_api.dominio import contas
from centelha_api.models import (
    Capitulo,
    Direitos,
    Edicao,
    EstadoCapitulo,
    Obra,
    PapelUsuario,
    Segmento,
    StatusDireitos,
    TipoSegmento,
    Usuario,
)

SENHA = "cavalo correto bateria grampo"
URL = "/v1/admin/temas"


def _login(client, session, papel):
    email = f"{papel.value}@exemplo.org"
    session.add(Usuario(email=email, nome=email, papel=papel, senha_hash=contas.gerar_hash(SENHA)))
    session.commit()
    r = client.post("/v1/admin/sessoes", json={"email": email, "senha": SENHA})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def ha(client, session):
    return _login(client, session, PapelUsuario.ADMINISTRADOR)


@pytest.fixture
def acervo(session):
    """LE publicado: capítulo 1 publicado (88, 88a), capítulo 2 ainda em revisão (99).
    ESE com capítulo publicado mas edição não publicada."""
    le = Obra(
        slug="o-livro-dos-espiritos",
        autor="Allan Kardec",
        titulo_original="LE",
        idioma_original="fr",
        sigla="LE",
    )
    ed = Edicao(
        obra=le,
        idioma="pt-BR",
        titulo="O Livro dos Espíritos",
        fonte="t",
        publicada_em=datetime.now(UTC),
        direitos=Direitos(status=StatusDireitos.APROVADO),
    )
    c1 = Capitulo(
        ordem=1,
        titulo="Dos Espíritos",
        referencia_canonica="LE-C001",
        estado=EstadoCapitulo.PUBLICADO,
    )
    c1.segmentos = [
        Segmento(
            ordem=1, tipo=TipoSegmento.PERGUNTA, texto="Os Espíritos têm forma?", numero_questao=88
        ),
        Segmento(ordem=2, tipo=TipoSegmento.RESPOSTA, texto="Para vós, não.", numero_questao=88),
        Segmento(
            ordem=3,
            tipo=TipoSegmento.PERGUNTA,
            texto="Essa chama tem cor?",
            numero_questao=88,
            subquestao="a",
        ),
    ]
    c2 = Capitulo(
        ordem=2, titulo="Outro", referencia_canonica="LE-C002", estado=EstadoCapitulo.AUDIO_REVISADO
    )
    c2.segmentos = [Segmento(ordem=1, tipo=TipoSegmento.PERGUNTA, texto="Q99?", numero_questao=99)]
    ed.capitulos = [c1, c2]
    ese = Obra(
        slug="o-evangelho",
        autor="Allan Kardec",
        titulo_original="ESE",
        idioma_original="fr",
        sigla="ESE",
    )
    ed_ese = Edicao(obra=ese, idioma="pt-BR", titulo="O Evangelho", fonte="t")
    ed_ese.capitulos = [
        Capitulo(
            ordem=1, titulo="I", referencia_canonica="ESE-C001", estado=EstadoCapitulo.PUBLICADO
        )
    ]
    session.add_all([ed, ed_ese])
    session.commit()
    return {"edicao": ed, "c1": c1}


REFS = ["LE-88", "LE-88a", "LE-C001", "LE-99", "ESE-C001", "LE-500"]


def _criar(client, ha, **kw):
    corpo = {
        "slug": "forma-dos-espiritos",
        "titulo": "A forma dos Espíritos",
        "resumo": "Texto da equipe.\n\nSegundo parágrafo.",
        "referencias": REFS,
        **kw,
    }
    return client.post(URL, json=corpo, headers=ha)


def test_so_resolve_o_que_esta_publicado(client, ha, acervo):
    """Tema não pode ser porta dos fundos para trecho que o catálogo esconde: capítulo
    em revisão, edição não publicada e questão inexistente ficam de fora."""
    r = _criar(client, ha)
    assert r.status_code == 201, r.text
    assert r.json()["nao_resolvidas"] == ["LE-99", "ESE-C001", "LE-500"]
    tid = r.json()["id"]
    assert client.post(f"{URL}/{tid}/publicar", headers=ha).status_code == 200

    tema = client.get("/v1/temas/forma-dos-espiritos").json()
    itens = [(i["referencia"], i["tipo"], i["titulo"]) for i in tema["itens"]]
    assert itens == [
        ("LE-88", "questao", "Os Espíritos têm forma?"),
        ("LE-88a", "questao", "Essa chama tem cor?"),
        ("LE-C001", "capitulo", "Dos Espíritos"),
    ]
    assert tema["itens"][0]["obra_slug"] == "o-livro-dos-espiritos"


def test_direitos_revogados_somem_do_tema(client, session, ha, acervo):
    tid = _criar(client, ha).json()["id"]
    client.post(f"{URL}/{tid}/publicar", headers=ha)
    acervo["edicao"].direitos.status = StatusDireitos.PENDENTE
    session.commit()
    assert client.get("/v1/temas/forma-dos-espiritos").json()["itens"] == []


def test_rascunho_nao_aparece(client, ha, acervo):
    _criar(client, ha)
    assert client.get("/v1/temas").json() == []
    assert client.get("/v1/temas/forma-dos-espiritos").status_code == 404


def test_nao_publica_tema_sem_trecho_publicado(client, ha, acervo):
    tid = _criar(client, ha, referencias=["LE-99"]).json()["id"]
    assert client.post(f"{URL}/{tid}/publicar", headers=ha).status_code == 409


@pytest.mark.parametrize("ref", ["le-88", "LE 88", "LE-C1", "LE-88ab", "<script>"])
def test_referencia_invalida(client, ha, acervo, ref):
    assert _criar(client, ha, referencias=[ref]).status_code == 422


def test_slug_nao_muda_depois_de_publicado(client, ha, acervo):
    """O slug é a URL; trocar depois de publicado quebra o que o Google indexou."""
    tid = _criar(client, ha).json()["id"]
    client.post(f"{URL}/{tid}/publicar", headers=ha)
    corpo = {"slug": "outro", "titulo": "X", "resumo": "Y", "referencias": ["LE-88"]}
    assert client.put(f"{URL}/{tid}", json=corpo, headers=ha).status_code == 409


def test_editar_mantendo_referencias(client, ha, acervo):
    """Trocar a lista com referências repetidas da anterior não pode bater no UNIQUE."""
    tid = _criar(client, ha).json()["id"]
    corpo = {
        "slug": "forma-dos-espiritos",
        "titulo": "Novo",
        "resumo": "Y",
        "referencias": ["LE-C001", "LE-88", "LE-88"],
    }
    r = client.put(f"{URL}/{tid}", json=corpo, headers=ha)
    assert r.status_code == 200, r.text
    assert r.json()["referencias"] == ["LE-C001", "LE-88"]


def test_lista_publica_traz_itens_para_temas_relacionados(client, ha, acervo):
    tid = _criar(client, ha).json()["id"]
    client.post(f"{URL}/{tid}/publicar", headers=ha)
    [t] = client.get("/v1/temas").json()
    assert {i["numero_questao"] for i in t["itens"] if i["tipo"] == "questao"} == {88}


@pytest.mark.parametrize("papel", [PapelUsuario.REVISOR_TEXTO, PapelUsuario.REVISOR_AUDIO])
def test_so_administrador(client, session, acervo, papel):
    h = _login(client, session, papel)
    assert _criar(client, h).status_code == 403
