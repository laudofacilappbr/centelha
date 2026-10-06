from centelha_api.models import Capitulo, Edicao, EstadoCapitulo, Obra, Segmento, TipoSegmento


def _marca(client):
    r = client.get("/v1/site/marca")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    return r.json()["marca"]


def test_marca_estavel_sem_mudanca(client):
    assert _marca(client) == _marca(client)


def test_marca_muda_ao_incluir_alterar_e_excluir(client, session):
    vazia = _marca(client)
    obra = Obra(
        slug="o-livro-dos-espiritos",
        autor="Allan Kardec",
        titulo_original="Le Livre des Esprits",
        idioma_original="fr",
        sigla="LE",
    )
    edicao = Edicao(obra=obra, idioma="pt-BR", titulo="O Livro dos Espíritos", fonte="teste")
    cap = Capitulo(
        ordem=1, titulo="I", referencia_canonica="LE-C001", estado=EstadoCapitulo.PUBLICADO
    )
    seg = Segmento(ordem=1, tipo=TipoSegmento.PARAGRAFO, texto="Texto.")
    cap.segmentos = [seg]
    edicao.capitulos = [cap]
    session.add(edicao)
    session.commit()
    com_obra = _marca(client)
    assert com_obra != vazia

    # Segmento não tem carimbo de alteração: a marca vem do conteúdo das linhas.
    seg.texto = "Texto revisado."
    session.commit()
    revisado = _marca(client)
    assert revisado != com_obra

    cap.estado = EstadoCapitulo.AUDIO_REVISADO
    session.commit()
    despublicado = _marca(client)
    assert despublicado != revisado

    session.delete(seg)
    session.commit()
    assert _marca(client) != despublicado
