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
URL = "/v1/admin/posts"


def _login(client, session, papel, email):
    session.add(Usuario(email=email, nome=email, papel=papel, senha_hash=contas.gerar_hash(SENHA)))
    session.commit()
    r = client.post("/v1/admin/sessoes", json={"email": email, "senha": SENHA})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def h(client, session):
    return {
        "autor": _login(client, session, PapelUsuario.ADMINISTRADOR, "ana@exemplo.org"),
        "outro_admin": _login(client, session, PapelUsuario.ADMINISTRADOR, "bia@exemplo.org"),
        "revisor": _login(client, session, PapelUsuario.REVISOR_TEXTO, "rev@exemplo.org"),
        "audio": _login(client, session, PapelUsuario.REVISOR_AUDIO, "aud@exemplo.org"),
    }


@pytest.fixture
def acervo(session):
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
    c = Capitulo(
        ordem=1, titulo="I", referencia_canonica="LE-C001", estado=EstadoCapitulo.PUBLICADO
    )
    c.segmentos = [
        Segmento(
            ordem=1, tipo=TipoSegmento.PERGUNTA, texto="Os Espíritos sonham?", numero_questao=402
        )
    ]
    ed.capitulos = [c]
    session.add(ed)
    session.commit()


def _corpo(**kw):
    return {
        "slug": "kardec-e-os-sonhos",
        "titulo": "O que O Livro dos Espíritos diz sobre sonhos",
        "resumo": "A questão 402 e o que ela ensina.",
        "texto": "Parágrafo.\n\n## Subtítulo\n\nOutro.",
        "linha": "kardec_responde",
        "referencias": ["LE-402"],
        **kw,
    }


def _ciclo(client, h):
    pid = client.post(URL, json=_corpo(), headers=h["autor"]).json()["id"]
    assert client.post(f"{URL}/{pid}/revisar", headers=h["revisor"]).status_code == 200
    assert client.post(f"{URL}/{pid}/publicar", headers=h["autor"]).status_code == 200
    return pid


def test_caminho_completo_ate_o_site(client, h, acervo):
    assert client.get("/v1/posts").json() == []
    _ciclo(client, h)
    [resumo] = client.get("/v1/posts").json()
    assert resumo["slug"] == "kardec-e-os-sonhos"
    post = client.get("/v1/posts/kardec-e-os-sonhos").json()
    assert [(f["referencia"], f["titulo"]) for f in post["fontes"]] == [
        ("LE-402", "Os Espíritos sonham?")
    ]


def test_nao_publica_sem_revisao(client, h, acervo):
    """Especificação: revisão doutrinária humana antes de publicar é obrigatória."""
    pid = client.post(URL, json=_corpo(), headers=h["autor"]).json()["id"]
    assert client.post(f"{URL}/{pid}/publicar", headers=h["autor"]).status_code == 409


def test_autor_nao_revisa_o_proprio_post(client, h, acervo):
    """Revisão é um segundo par de olhos, mesmo para administrador."""
    pid = client.post(URL, json=_corpo(), headers=h["autor"]).json()["id"]
    assert client.post(f"{URL}/{pid}/revisar", headers=h["autor"]).status_code == 403
    assert client.post(f"{URL}/{pid}/revisar", headers=h["outro_admin"]).status_code == 200


def test_revisor_de_audio_nao_revisa_post(client, h, acervo):
    pid = client.post(URL, json=_corpo(), headers=h["autor"]).json()["id"]
    assert client.post(f"{URL}/{pid}/revisar", headers=h["audio"]).status_code == 403


def test_revisor_de_texto_nao_escreve_nem_publica(client, h, acervo):
    assert client.post(URL, json=_corpo(), headers=h["revisor"]).status_code == 403


def test_nao_publica_sem_fonte_publicada(client, h, acervo):
    """Todo post cita a fonte exata e linka para ela."""
    pid = client.post(URL, json=_corpo(referencias=["LE-999"]), headers=h["autor"]).json()["id"]
    client.post(f"{URL}/{pid}/revisar", headers=h["revisor"])
    r = client.post(f"{URL}/{pid}/publicar", headers=h["autor"])
    assert r.status_code == 409
    assert "trecho publicado" in r.json()["detail"]


def test_editar_desfaz_a_revisao(client, session, h, acervo):
    """A revisão vale para o texto lido; mudou o texto, revisa de novo."""
    pid = client.post(URL, json=_corpo(), headers=h["autor"]).json()["id"]
    client.post(f"{URL}/{pid}/revisar", headers=h["revisor"])
    r = client.put(f"{URL}/{pid}", json=_corpo(texto="Texto trocado."), headers=h["autor"])
    assert (r.json()["estado"], r.json()["revisado_por_id"]) == ("rascunho", None)
    assert client.post(f"{URL}/{pid}/publicar", headers=h["autor"]).status_code == 409
    [log] = session.scalars(
        select(RegistroAuditoria).where(RegistroAuditoria.acao == "post_alterado")
    ).all()
    assert log.detalhes["revisao_desfeita"] is True


def test_publicado_nao_se_edita_e_despublicar_exige_nova_revisao(client, h, acervo):
    pid = _ciclo(client, h)
    assert client.put(f"{URL}/{pid}", json=_corpo(), headers=h["autor"]).status_code == 409
    r = client.post(f"{URL}/{pid}/despublicar", headers=h["autor"])
    assert r.json()["estado"] == "rascunho"
    assert client.get("/v1/posts/kardec-e-os-sonhos").status_code == 404
    assert client.post(f"{URL}/{pid}/publicar", headers=h["autor"]).status_code == 409


@pytest.mark.parametrize(
    "campo",
    [
        {"capa_url": "http://exemplo.org/c.png"},
        {"linha": "polemica"},
        {"slug": "Com Espaco"},
        {"referencias": ["le 402"]},
    ],
)
def test_entrada_invalida(client, h, acervo, campo):
    assert client.post(URL, json=_corpo(**campo), headers=h["autor"]).status_code == 422


def test_seo_do_post_passa_pela_revisao(client, h, acervo):
    """SEO do post aparece na busca como o texto: entra pela mesma revisão."""
    corpo = _corpo(seo_titulo="Sonhos segundo Kardec", seo_descricao="A questão 402.")
    pid = client.post(URL, json=corpo, headers=h["autor"]).json()["id"]
    client.post(f"{URL}/{pid}/revisar", headers=h["revisor"])
    client.post(f"{URL}/{pid}/publicar", headers=h["autor"])
    pub = client.get("/v1/posts/kardec-e-os-sonhos").json()
    assert (pub["seo_titulo"], pub["seo_descricao"]) == ("Sonhos segundo Kardec", "A questão 402.")
    # Mudar só o SEO também devolve o post a rascunho, como qualquer edição.
    client.post(f"{URL}/{pid}/despublicar", headers=h["autor"])
    r = client.put(f"{URL}/{pid}", json={**corpo, "seo_titulo": "Outro"}, headers=h["autor"])
    assert r.json()["estado"] == "rascunho"
