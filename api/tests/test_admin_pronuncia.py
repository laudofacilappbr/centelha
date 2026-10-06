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
    Pronuncia,
    RegistroAuditoria,
    Segmento,
    TipoSegmento,
    Usuario,
    Voz,
)
from centelha_api.pipeline.pronuncia import EntradaPronuncia, termos_usados

E = EstadoCapitulo
SENHA = "cavalo correto bateria grampo"


def test_termos_usados_segue_a_regra_da_sintese():
    """Com "Allan Kardec" no dicionário, o trecho "Allan Kardec" não usa a entrada
    "Kardec"; e "Kardecismo" não é "Kardec". Mesma regra de aplicar()."""
    d = [EntradaPronuncia("Allan Kardec", "Alan Kardéc"), EntradaPronuncia("Kardec", "Kardéc")]
    assert termos_usados("Allan Kardec disse", d) == {"Allan Kardec"}
    assert termos_usados("Disse Kardec.", d) == {"Kardec"}
    assert termos_usados("O kardecismo e o Kardecismo", d) == set()


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
def acervo(session):
    """Capítulos em vários estados e idiomas, todos citando Kardec de algum jeito."""
    obra = Obra(
        slug="o-evangelho",
        autor="Allan Kardec",
        titulo_original="L'Évangile",
        idioma_original="fr",
        sigla="ESE",
    )
    pt = Edicao(obra=obra, idioma="pt-BR", titulo="O Evangelho", fonte="t")
    fr = Edicao(obra=obra, idioma="fr", titulo="L'Évangile", fonte="t")

    def cap(ed, ordem, estado, texto):
        c = Capitulo(
            ordem=ordem, titulo=f"C{ordem}", referencia_canonica=f"ESE-C{ordem:03d}", estado=estado
        )
        c.segmentos = [Segmento(ordem=1, tipo=TipoSegmento.PARAGRAFO, texto=texto)]
        ed.capitulos.append(c)
        return c

    caps = {
        "revisado": cap(pt, 1, E.AUDIO_REVISADO, "Disse Kardec que a caridade..."),
        "so_nome_completo": cap(pt, 2, E.AUDIO_GERADO, "Allan Kardec escreveu."),
        "sem_audio": cap(pt, 3, E.TEXTO_REVISADO, "Kardec ainda sem áudio."),
        "publicado": cap(pt, 4, E.PUBLICADO, "Kardec publicado."),
        "sem_job": cap(pt, 5, E.AUDIO_GERADO, "Kardec gerado por fora da fila."),
        "frances": cap(fr, 1, E.AUDIO_GERADO, "Kardec en français."),
    }
    voz = Voz(idioma="pt-BR", motor="falso", voz_id="n", papel=PapelVoz.NARRADOR)
    session.add_all(
        [pt, fr, voz, Pronuncia(idioma="pt-BR", termo="Allan Kardec", substituicao="Alan Kardéc")]
    )
    session.flush()
    # Geração anterior concluída: a regeneração repete estas vozes.
    for k in ("revisado", "so_nome_completo", "publicado"):
        session.add(
            JobAudio(
                capitulo_id=caps[k].id,
                motor="falso",
                voz_narrador_id=voz.id,
                estado=EstadoJob.CONCLUIDO,
            )
        )
    session.commit()
    return {**{k: c.id for k, c in caps.items()}, "voz": voz.id}


def _criar(client, hx, **kw):
    corpo = {"idioma": "pt-BR", "termo": "Kardec", "substituicao": "Kardéc", **kw}
    return client.post("/v1/admin/pronuncias", json=corpo, headers=hx)


def test_nova_entrada_lista_so_os_capitulos_que_ela_muda(client, h, acervo):
    """Fora: sem áudio (nada a refazer), outro idioma, e o capítulo que só cita
    "Allan Kardec" (a entrada mais longa continua valendo ali)."""
    r = _criar(client, h[PapelUsuario.REVISOR_AUDIO], capitulo_id=acervo["revisado"])
    assert r.status_code == 201, r.text
    afetados = {a["capitulo_id"] for a in r.json()["capitulos_afetados"]}
    assert afetados == {acervo["revisado"], acervo["publicado"], acervo["sem_job"]}


def test_quem_edita_o_dicionario(client, h, acervo):
    """Especificação: o revisor de áudio edita o dicionário; o de texto, não."""
    assert _criar(client, h[PapelUsuario.REVISOR_TEXTO]).status_code == 403
    assert _criar(client, h[PapelUsuario.REVISOR_AUDIO]).status_code == 201


def test_entrada_precisa_de_grafia_ou_ipa(client, h, acervo):
    hx = h[PapelUsuario.REVISOR_AUDIO]
    assert _criar(client, hx, substituicao="  ").status_code == 422
    assert _criar(client, hx, substituicao=None, ipa="kaʁˈdɛk").status_code == 201


def test_termo_repetido(client, h, acervo):
    r = _criar(client, h[PapelUsuario.REVISOR_AUDIO], termo="Allan Kardec")
    assert r.status_code == 409


def test_alterar_e_apagar_ficam_na_auditoria(client, session, h, acervo):
    hx = h[PapelUsuario.REVISOR_AUDIO]
    pid = _criar(client, hx).json()["id"]
    r = client.patch(f"/v1/admin/pronuncias/{pid}", json={"substituicao": "Cardéc"}, headers=hx)
    assert r.json()["substituicao"] == "Cardéc"
    # Apagar devolve quem usava a entrada: é esse áudio que fica com a grafia antiga.
    r = client.delete(f"/v1/admin/pronuncias/{pid}", headers=hx)
    assert {a["capitulo_id"] for a in r.json()["capitulos_afetados"]} == {
        acervo["revisado"],
        acervo["publicado"],
        acervo["sem_job"],
    }
    acoes = session.scalars(
        select(RegistroAuditoria.acao).where(RegistroAuditoria.alvo_tipo == "pronuncia")
    ).all()
    assert acoes == ["pronuncia_criada", "pronuncia_alterada", "pronuncia_apagada"]
    assert session.get(Pronuncia, pid) is None


def test_regenerar_repete_as_vozes_e_explica_quem_ficou_de_fora(client, session, h, acervo):
    hx = h[PapelUsuario.REVISOR_AUDIO]
    pid = _criar(client, hx).json()["id"]
    r = client.post(f"/v1/admin/pronuncias/{pid}/regenerar", headers=hx)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["enfileirados"] == [acervo["revisado"]]
    assert "despublique" in corpo["pulados"][str(acervo["publicado"])]
    assert "anterior" in corpo["pulados"][str(acervo["sem_job"])]
    novo = session.scalar(
        select(JobAudio).where(
            JobAudio.capitulo_id == acervo["revisado"], JobAudio.estado == EstadoJob.PENDENTE
        )
    )
    assert (novo.motor, novo.voz_narrador_id) == ("falso", acervo["voz"])

    # De novo: o job ainda está na fila, não se cobra duas vezes.
    corpo = client.post(f"/v1/admin/pronuncias/{pid}/regenerar", headers=hx).json()
    assert corpo["enfileirados"] == []
    assert "fila" in corpo["pulados"][str(acervo["revisado"])]


def test_revisor_de_texto_nao_regenera(client, h, acervo):
    pid = _criar(client, h[PapelUsuario.REVISOR_AUDIO]).json()["id"]
    r = client.post(f"/v1/admin/pronuncias/{pid}/regenerar", headers=h[PapelUsuario.REVISOR_TEXTO])
    assert r.status_code == 403


def test_listar_por_idioma(client, h, acervo):
    r = client.get("/v1/admin/pronuncias?idioma=pt-BR", headers=h[PapelUsuario.REVISOR_TEXTO])
    assert [p["termo"] for p in r.json()] == ["Allan Kardec"]
