from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from centelha_api.dominio import contas
from centelha_api.models import (
    Capitulo,
    Direitos,
    Edicao,
    EstadoCapitulo,
    Obra,
    PapelUsuario,
    RegistroAuditoria,
    Segmento,
    StatusDireitos,
    TipoSegmento,
    Usuario,
)

SENHA = "cavalo correto bateria grampo"
URL = "/v1/admin/glossario"


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
def edicao(session):
    """LE publicado: capítulo 1 publicado (questão 93), capítulo 2 ainda em revisão (99)."""
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
        titulo="Perispírito",
        referencia_canonica="LE-C001",
        estado=EstadoCapitulo.PUBLICADO,
    )
    c1.segmentos = [
        Segmento(
            ordem=1,
            tipo=TipoSegmento.PERGUNTA,
            texto="O Espírito propriamente dito tem envoltório?",
            numero_questao=93,
        ),
    ]
    c2 = Capitulo(
        ordem=2, titulo="Outro", referencia_canonica="LE-C002", estado=EstadoCapitulo.AUDIO_REVISADO
    )
    c2.segmentos = [Segmento(ordem=1, tipo=TipoSegmento.PERGUNTA, texto="Q99?", numero_questao=99)]
    ed.capitulos = [c1, c2]
    session.add(ed)
    session.commit()
    return ed


PERISPIRITO = {
    "slug": "perispirito",
    "termo": "Perispírito",
    "definicao": "Envoltório semimaterial do Espírito.\n\nLiga o Espírito ao corpo.",
    "referencias": ["LE-93", "LE-99", "LE-C001"],
}


def test_so_publica_com_fonte_publicada(client, ha, edicao):
    """O glossário aponta onde Kardec ensina; definição sem trecho publicado seria a
    equipe ensinando doutrina por conta própria."""
    t = client.post(URL, json={**PERISPIRITO, "referencias": ["LE-99"]}, headers=ha).json()
    assert t["nao_resolvidas"] == ["LE-99"]
    r = client.post(f"{URL}/{t['id']}/publicar", headers=ha)
    assert r.status_code == 409
    assert client.get("/v1/glossario").json() == []


def test_site_ve_so_os_trechos_publicados(client, ha, edicao):
    r = client.post(URL, json=PERISPIRITO, headers=ha)
    assert r.status_code == 201
    t = r.json()
    # A não publicada fica sinalizada para quem edita.
    assert t["referencias"] == ["LE-93", "LE-99", "LE-C001"]
    assert t["nao_resolvidas"] == ["LE-99"]
    assert client.get("/v1/glossario/perispirito").status_code == 404

    assert client.post(f"{URL}/{t['id']}/publicar", headers=ha).status_code == 200
    [pub] = client.get("/v1/glossario").json()
    assert pub["termo"] == "Perispírito"
    assert [i["referencia"] for i in pub["itens"]] == ["LE-93", "LE-C001"]
    assert client.get("/v1/glossario/perispirito").json()["slug"] == "perispirito"


def test_direitos_revogados_tiram_a_fonte_do_ar(client, session, ha, edicao):
    """O glossário não reabre a porta que `_edicao_visivel` fecha."""
    t = client.post(URL, json=PERISPIRITO, headers=ha).json()
    client.post(f"{URL}/{t['id']}/publicar", headers=ha)
    edicao.direitos.status = StatusDireitos.RECUSADO
    session.commit()
    assert client.get("/v1/glossario/perispirito").json()["itens"] == []


def test_termo_repetido_ou_slug_repetido(client, ha, edicao):
    """ "Perispírito" e "perispírito" seriam duas páginas disputando a mesma busca."""
    assert client.post(URL, json=PERISPIRITO, headers=ha).status_code == 201
    outro = {**PERISPIRITO, "slug": "perispirito-2", "termo": " perispírito "}
    assert client.post(URL, json=outro, headers=ha).status_code == 409
    mesmo_slug = {**PERISPIRITO, "termo": "Fluido universal"}
    assert client.post(URL, json=mesmo_slug, headers=ha).status_code == 409


def test_termo_publicado_nao_troca_de_slug(client, ha, edicao):
    t = client.post(URL, json=PERISPIRITO, headers=ha).json()
    client.post(f"{URL}/{t['id']}/publicar", headers=ha)
    novo = {**PERISPIRITO, "slug": "o-perispirito"}
    assert client.put(f"{URL}/{t['id']}", json=novo, headers=ha).status_code == 409
    # Corrigir a definição mantendo o slug continua permitido, e a referência mantida
    # não bate no UNIQUE (termo_id, referencia).
    corrigido = {**PERISPIRITO, "definicao": "Laço fluídico entre Espírito e corpo."}
    r = client.put(f"{URL}/{t['id']}", json=corrigido, headers=ha)
    assert r.status_code == 200
    assert r.json()["definicao"] == "Laço fluídico entre Espírito e corpo."


def test_referencia_invalida(client, ha, edicao):
    r = client.post(URL, json={**PERISPIRITO, "referencias": ["questão 93"]}, headers=ha)
    assert r.status_code == 422


def test_so_administrador_edita_e_tudo_fica_no_log(client, session, ha, edicao):
    hr = _login(client, session, PapelUsuario.REVISOR_TEXTO)
    assert client.post(URL, json=PERISPIRITO, headers=hr).status_code == 403
    assert client.get(URL, headers=hr).status_code == 403

    t = client.post(URL, json=PERISPIRITO, headers=ha).json()
    client.post(f"{URL}/{t['id']}/publicar", headers=ha)
    client.post(f"{URL}/{t['id']}/despublicar", headers=ha)
    assert client.get("/v1/glossario").json() == []
    acoes = session.scalars(
        select(RegistroAuditoria.acao)
        .where(RegistroAuditoria.acao.like("termo_%"))
        .order_by(RegistroAuditoria.id)
    ).all()
    assert acoes == ["termo_criado", "termo_publicado", "termo_despublicado"]
