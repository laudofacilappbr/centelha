import pytest
from sqlalchemy import select

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
    RegistroAuditoria,
    Segmento,
    TipoSegmento,
    Usuario,
    Voz,
)
from centelha_api.pipeline import worker
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
def base(session):
    obra = Obra(
        slug="o-livro-dos-espiritos",
        autor="Allan Kardec",
        titulo_original="Le Livre des Esprits",
        idioma_original="fr",
        sigla="LE",
    )
    ed = Edicao(obra=obra, idioma="pt-BR", titulo="O Livro dos Espíritos", fonte="teste")
    cap = Capitulo(
        ordem=1, titulo="I", referencia_canonica="LE-C001", estado=EstadoCapitulo.TEXTO_REVISADO
    )
    cap.segmentos = [
        Segmento(ordem=1, tipo=TipoSegmento.PERGUNTA, texto="Que é Deus?", numero_questao=1),
        Segmento(
            ordem=2, tipo=TipoSegmento.RESPOSTA, texto="Inteligência suprema.", numero_questao=1
        ),
    ]
    ed.capitulos = [cap]
    vozes = {
        "narrador": Voz(idioma="pt-BR", motor="falso", voz_id="n", papel=PapelVoz.NARRADOR),
        "resposta": Voz(idioma="pt-BR", motor="falso", voz_id="r", papel=PapelVoz.RESPOSTA),
        "piper": Voz(idioma="pt-BR", motor="piper", voz_id="p", papel=PapelVoz.PERGUNTA),
        "frances": Voz(idioma="fr", motor="falso", voz_id="f", papel=PapelVoz.NARRADOR),
    }
    session.add_all([ed, *vozes.values()])
    session.commit()
    return {"cap": cap, **{k: v.id for k, v in vozes.items()}}


def _gerar(client, hx, base, **vozes):
    corpo = {"voz_narrador_id": base["narrador"], **vozes}
    return client.post(f"/v1/admin/capitulos/{base['cap'].id}/gerar-audio", json=corpo, headers=hx)


def test_revisor_de_audio_gera_e_o_worker_entrega(client, session, h, base, tmp_path):
    """Caminho inteiro da decisão de #64: o revisor de áudio pede, o worker sintetiza e
    o capítulo chega a "áudio gerado" com a faixa, pronto para a escuta."""
    hx = h[PapelUsuario.REVISOR_AUDIO]
    r = _gerar(client, hx, base, voz_resposta_id=base["resposta"])
    assert r.status_code == 202, r.text
    job = r.json()
    assert (job["estado"], job["motor"]) == ("pendente", "falso")
    assert job["caracteres_estimados"] == len("Que é Deus?") + len("Inteligência suprema.")

    armazenamento = ArmazenamentoLocal(tmp_path / "audio", "https://audio.exemplo")
    assert worker.processar_um(SessionLocal, armazenamento, motor=MotorFalso())

    cap = client.get(f"/v1/admin/capitulos/{base['cap'].id}", headers=hx).json()
    assert cap["estado"] == "audio_gerado"
    assert cap["faixa"]["url"].startswith("https://audio.exemplo/")
    assert cap["acoes"] == ["aprovar_audio", "reprovar_audio"]
    [j] = client.get(f"/v1/admin/capitulos/{base['cap'].id}/jobs", headers=hx).json()
    assert j["estado"] == "concluido"


def test_revisor_de_texto_nao_gera(client, h, base):
    assert _gerar(client, h[PapelUsuario.REVISOR_TEXTO], base).status_code == 403


def test_administrador_tambem_gera(client, h, base):
    assert _gerar(client, h[PapelUsuario.ADMINISTRADOR], base).status_code == 202


def test_pedir_duas_vezes_nao_cobra_duas_vezes(client, session, h, base):
    hx = h[PapelUsuario.REVISOR_AUDIO]
    assert _gerar(client, hx, base).status_code == 202
    r = _gerar(client, hx, base)
    assert r.status_code == 409
    assert "fila" in r.json()["detail"]
    assert len(session.scalars(select(JobAudio)).all()) == 1


def test_texto_nao_revisado_nao_vai_ao_tts(client, session, h, base):
    base["cap"].estado = EstadoCapitulo.IMPORTADO
    session.commit()
    r = _gerar(client, h[PapelUsuario.REVISOR_AUDIO], base)
    assert r.status_code == 409
    assert session.scalar(select(JobAudio.id)) is None


def test_vozes_de_motores_diferentes(client, session, h, base):
    """Narrador Azure e pergunta Piper só falhariam no worker, depois de ocupar a fila."""
    r = _gerar(client, h[PapelUsuario.REVISOR_AUDIO], base, voz_pergunta_id=base["piper"])
    assert r.status_code == 422
    assert session.scalar(select(JobAudio.id)) is None


def test_voz_de_outro_idioma_e_voz_inexistente(client, h, base):
    hx = h[PapelUsuario.REVISOR_AUDIO]
    assert _gerar(client, hx, base, voz_resposta_id=base["frances"]).status_code == 409
    assert _gerar(client, hx, base, voz_resposta_id=9999).status_code == 422


def test_pedido_fica_na_auditoria_com_quem_pediu(client, session, h, base):
    _gerar(client, h[PapelUsuario.REVISOR_AUDIO], base)
    revisor = session.scalar(select(Usuario).where(Usuario.papel == PapelUsuario.REVISOR_AUDIO))
    [log] = session.scalars(
        select(RegistroAuditoria).where(RegistroAuditoria.acao == "audio.enfileirar")
    ).all()
    assert log.usuario_id == revisor.id
    assert session.scalar(select(JobAudio.solicitado_por_id)) == revisor.id
    assert session.scalar(select(JobAudio.estado)) == EstadoJob.PENDENTE


def test_lista_de_vozes_por_idioma(client, h, base):
    vozes = client.get("/v1/admin/vozes?idioma=fr", headers=h[PapelUsuario.REVISOR_TEXTO]).json()
    assert [v["voz_id"] for v in vozes] == ["f"]


def test_capitulo_inexistente(client, h):
    r = client.post(
        "/v1/admin/capitulos/999/gerar-audio",
        json={"voz_narrador_id": 1},
        headers=h[PapelUsuario.REVISOR_AUDIO],
    )
    assert r.status_code == 404
