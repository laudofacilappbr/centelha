from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from centelha_api.dominio import contas, editorial
from centelha_api.models import (
    Capitulo,
    Direitos,
    Edicao,
    EstadoCapitulo,
    FaixaAudio,
    Obra,
    PapelUsuario,
    PapelVoz,
    Publico,
    RegistroAuditoria,
    Segmento,
    StatusDireitos,
    TipoSegmento,
    Usuario,
    Voz,
)

E = EstadoCapitulo
SENHA = "cavalo correto bateria grampo"
ORDEM = [E.IMPORTADO, E.TEXTO_REVISADO, E.AUDIO_GERADO, E.AUDIO_REVISADO, E.PUBLICADO]
# Adaptação juvenil ou infantil tem a revisão doutrinária antes do áudio (#49).
ORDEM_ADAPTACAO = [*ORDEM[:2], E.DOUTRINA_REVISADA, *ORDEM[2:]]


# --- Tabela de transições ---------------------------------------------------


def test_toda_reprovacao_volta_exatamente_um_passo():
    """Especificação: "qualquer reprovação volta o capítulo um passo". Uma transição
    que pulasse dois passos para trás descartaria trabalho aprovado sem ninguém pedir."""
    for publico in Publico:
        ordem = ORDEM if publico == Publico.ADULTO else ORDEM_ADAPTACAO
        for nome, t in editorial.TRANSICOES.items():
            if publico not in t.publicos:
                continue
            i_de, i_para = ordem.index(t.de), ordem.index(t.destino(publico))
            if i_para < i_de:
                assert i_de - i_para == 1, (nome, publico)
                assert t.exige_motivo, f"{nome} volta sem motivo"
            else:
                assert i_para - i_de == 1, (nome, publico)


def test_ninguem_aprova_o_proprio_passo_de_outro_papel():
    texto, audio = PapelUsuario.REVISOR_TEXTO, PapelUsuario.REVISOR_AUDIO
    cap = Capitulo(estado=E.IMPORTADO, edicao=Edicao(publico=Publico.ADULTO))
    assert editorial.acoes_possiveis(cap, texto) == ["aprovar_texto"]
    assert editorial.acoes_possiveis(cap, audio) == []
    cap.estado = E.AUDIO_GERADO
    assert editorial.acoes_possiveis(cap, texto) == []
    assert editorial.acoes_possiveis(cap, audio) == ["aprovar_audio", "reprovar_audio"]
    cap.estado = E.PUBLICADO
    assert editorial.acoes_possiveis(cap, audio) == []
    assert editorial.acoes_possiveis(cap, PapelUsuario.ADMINISTRADOR) == ["despublicar"]


def test_nenhuma_acao_leva_a_audio_gerado_a_partir_do_texto():
    """ "Áudio gerado" significa que existe faixa. Só o worker pode afirmar isso; um
    botão que marcasse o estado sem áudio levaria a aprovar e publicar silêncio."""
    assert not any(
        t.para == E.AUDIO_GERADO and t.de == E.TEXTO_REVISADO for t in editorial.TRANSICOES.values()
    )


# --- API --------------------------------------------------------------------


def _login(client, session, papel, email=None):
    email = email or f"{papel.value}@exemplo.org"
    session.add(Usuario(email=email, nome=email, papel=papel, senha_hash=contas.gerar_hash(SENHA)))
    session.commit()
    r = client.post("/v1/admin/sessoes", json={"email": email, "senha": SENHA})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def h(client, session):
    return {p: _login(client, session, p) for p in PapelUsuario}


@pytest.fixture
def cap(session):
    obra = Obra(
        slug="o-evangelho",
        autor="Allan Kardec",
        titulo_original="L'Évangile",
        idioma_original="fr",
        sigla="ESE",
    )
    edicao = Edicao(obra=obra, idioma="pt-BR", titulo="O Evangelho", fonte="teste")
    c = Capitulo(ordem=1, titulo="I", referencia_canonica="ESE-C001", estado=E.IMPORTADO)
    c.segmentos = [
        Segmento(ordem=1, tipo=TipoSegmento.TITULO, texto="Capítulo I"),
        Segmento(ordem=2, tipo=TipoSegmento.PARAGRAFO, texto="Texto com erro de OCR rn."),
    ]
    edicao.capitulos.append(c)
    session.add(edicao)
    session.commit()
    return c


def _transicao(client, h, cap, acao, motivo=None):
    return client.post(
        f"/v1/admin/capitulos/{cap.id}/transicoes", json={"acao": acao, "motivo": motivo}, headers=h
    )


def _estado(session, cap):
    session.expire_all()
    return session.get(Capitulo, cap.id).estado


def test_revisao_de_texto_mostra_original_ao_lado(client, h, cap):
    seg = cap.segmentos[1]
    r = client.patch(
        f"/v1/admin/segmentos/{seg.id}",
        json={"texto": "Texto com erro de OCR."},
        headers=h[PapelUsuario.REVISOR_TEXTO],
    )
    assert r.status_code == 200
    assert r.json()["texto_importado"] == "Texto com erro de OCR rn."
    # Segunda edição: o "original" continua sendo o da ingestão, não o da edição anterior.
    client.patch(
        f"/v1/admin/segmentos/{seg.id}",
        json={"texto": "Texto corrigido."},
        headers=h[PapelUsuario.REVISOR_TEXTO],
    )
    detalhe = client.get(f"/v1/admin/capitulos/{cap.id}", headers=h[PapelUsuario.REVISOR_TEXTO])
    segs = detalhe.json()["segmentos"]
    assert (segs[1]["texto"], segs[1]["texto_importado"]) == (
        "Texto corrigido.",
        "Texto com erro de OCR rn.",
    )
    assert segs[0]["texto_importado"] is None


def test_texto_aprovado_nao_se_edita(client, h, cap, session):
    """Editar texto depois de aprovado descolaria o áudio (e as marcações de tempo) do
    texto mostrado na leitura acompanhada."""
    hx = h[PapelUsuario.REVISOR_TEXTO]
    assert _transicao(client, hx, cap, "aprovar_texto").status_code == 200
    r = client.patch(f"/v1/admin/segmentos/{cap.segmentos[1].id}", json={"texto": "x"}, headers=hx)
    assert r.status_code == 409
    # Caminho previsto: reabrir com motivo, editar, aprovar de novo.
    assert _transicao(client, hx, cap, "reabrir_texto", "faltou corrigir").status_code == 200
    r = client.patch(f"/v1/admin/segmentos/{cap.segmentos[1].id}", json={"texto": "x"}, headers=hx)
    assert r.status_code == 200


def test_revisor_de_audio_nao_edita_nem_aprova_texto(client, h, cap):
    ha = h[PapelUsuario.REVISOR_AUDIO]
    r = client.patch(f"/v1/admin/segmentos/{cap.segmentos[1].id}", json={"texto": "x"}, headers=ha)
    assert r.status_code == 403
    assert _transicao(client, ha, cap, "aprovar_texto").status_code == 403


def test_estado_errado(client, h, cap, session):
    r = _transicao(client, h[PapelUsuario.REVISOR_AUDIO], cap, "aprovar_audio")
    assert r.status_code == 409
    assert "importado" in r.json()["detail"]
    assert _estado(session, cap) == E.IMPORTADO


def test_acao_desconhecida(client, h, cap):
    assert _transicao(client, h[PapelUsuario.ADMINISTRADOR], cap, "publicar_ja").status_code == 409


def test_reprovar_audio_exige_motivo_e_volta_um_passo(client, h, cap, session):
    cap.estado = E.AUDIO_GERADO
    session.commit()
    ha = h[PapelUsuario.REVISOR_AUDIO]
    assert _transicao(client, ha, cap, "reprovar_audio").status_code == 409
    assert _transicao(client, ha, cap, "reprovar_audio", "  ").status_code == 409
    r = _transicao(client, ha, cap, "reprovar_audio", "pronúncia de 'perispírito' no 0:42")
    assert r.status_code == 200
    assert r.json()["estado"] == "texto_revisado"
    [log] = session.scalars(
        select(RegistroAuditoria).where(RegistroAuditoria.acao == "capitulo_reprovar_audio")
    ).all()
    assert log.detalhes == {
        "de": "audio_gerado",
        "para": "texto_revisado",
        "motivo": "pronúncia de 'perispírito' no 0:42",
    }


def test_escuta_traz_a_faixa_mais_recente(client, h, cap, session):
    cap.estado = E.AUDIO_GERADO
    voz = Voz(idioma="pt-BR", motor="piper", voz_id="x", papel=PapelVoz.NARRADOR)
    session.add(voz)
    session.flush()
    for v in (1, 2):
        session.add(
            FaixaAudio(
                capitulo_id=cap.id,
                voz_id=voz.id,
                versao=v,
                url=f"https://a.exemplo/v{v}.m4a",
                duracao_ms=v,
                marcacoes=[],
            )
        )
    session.commit()
    r = client.get(f"/v1/admin/capitulos/{cap.id}", headers=h[PapelUsuario.REVISOR_AUDIO]).json()
    assert r["faixa"]["url"] == "https://a.exemplo/v2.m4a"
    assert r["acoes"] == ["aprovar_audio", "reprovar_audio"]


def test_despublicar_tira_o_capitulo_do_catalogo(client, h, cap, session):
    edicao = session.get(Edicao, cap.edicao_id)
    edicao.publicada_em = datetime.now(UTC)
    edicao.direitos = Direitos(status=StatusDireitos.APROVADO)
    cap.estado = E.PUBLICADO
    session.commit()
    assert client.get(f"/v1/capitulos/{cap.id}").status_code == 200
    assert (
        _transicao(client, h[PapelUsuario.REVISOR_AUDIO], cap, "despublicar", "x").status_code
        == 403
    )
    r = _transicao(client, h[PapelUsuario.ADMINISTRADOR], cap, "despublicar", "erro grave no 3:10")
    assert r.status_code == 200
    assert client.get(f"/v1/capitulos/{cap.id}").status_code == 404


def test_historico_junta_edicoes_e_transicoes(client, h, cap):
    hx = h[PapelUsuario.REVISOR_TEXTO]
    client.patch(f"/v1/admin/segmentos/{cap.segmentos[1].id}", json={"texto": "Ok."}, headers=hx)
    # Mesmo texto de novo: não é edição, não entra no histórico.
    client.patch(f"/v1/admin/segmentos/{cap.segmentos[1].id}", json={"texto": "Ok."}, headers=hx)
    _transicao(client, hx, cap, "aprovar_texto")
    eventos = client.get(f"/v1/admin/capitulos/{cap.id}/historico", headers=hx).json()
    assert [e["acao"] for e in eventos] == ["segmento_editado", "capitulo_aprovar_texto"]


def test_lista_de_edicoes_conta_capitulos_por_estado(client, h, cap):
    [ed] = client.get("/v1/admin/edicoes", headers=h[PapelUsuario.REVISOR_TEXTO]).json()
    assert ed["capitulos_por_estado"]["importado"] == 1
    assert ed["capitulos_por_estado"]["publicado"] == 0
    caps = client.get(
        f"/v1/admin/edicoes/{cap.edicao_id}/capitulos?estado=importado",
        headers=h[PapelUsuario.REVISOR_TEXTO],
    ).json()
    assert [c["id"] for c in caps] == [cap.id]


def test_sem_sessao(client, cap):
    assert client.get(f"/v1/admin/capitulos/{cap.id}").status_code == 401
