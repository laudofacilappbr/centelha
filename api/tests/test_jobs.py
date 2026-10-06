from datetime import timedelta

import pytest
from sqlalchemy import func, select

from centelha_api.config import get_settings
from centelha_api.db import SessionLocal
from centelha_api.models import (
    Capitulo,
    Edicao,
    EstadoCapitulo,
    EstadoJob,
    FaixaAudio,
    JobAudio,
    Obra,
    PapelVoz,
    Pronuncia,
    RegistroAuditoria,
    Segmento,
    TipoSegmento,
    Voz,
)
from centelha_api.pipeline import jobs, worker
from centelha_api.pipeline.armazenamento import ArmazenamentoLocal
from centelha_api.pipeline.tts.motores import MotorFalso


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
        ordem=1,
        titulo="Capítulo I",
        referencia_canonica="LE-C001",
        estado=EstadoCapitulo.TEXTO_REVISADO,
    )
    cap.segmentos = [
        Segmento(ordem=1, tipo=TipoSegmento.TITULO, texto="Capítulo I"),
        Segmento(ordem=2, tipo=TipoSegmento.PERGUNTA, texto="Que diz Kardec?", numero_questao=1),
        Segmento(ordem=3, tipo=TipoSegmento.RESPOSTA, texto="Resposta.", numero_questao=1),
    ]
    ed.capitulos = [cap]
    narrador = Voz(idioma="pt-BR", motor="falso", voz_id="n", papel=PapelVoz.NARRADOR)
    resposta = Voz(idioma="pt-BR", motor="falso", voz_id="r", papel=PapelVoz.RESPOSTA)
    frances = Voz(idioma="fr", motor="falso", voz_id="f", papel=PapelVoz.NARRADOR)
    session.add_all([ed, narrador, resposta, frances])
    session.add(Pronuncia(idioma="pt-BR", termo="Kardec", substituicao="Kardéc"))
    session.commit()
    return {"cap": cap, "narrador": narrador, "resposta": resposta, "frances": frances}


@pytest.fixture
def armazenamento(tmp_path):
    return ArmazenamentoLocal(tmp_path / "audio", "https://audio.exemplo")


def _enfileirar(session, base, **kw):
    job = jobs.enfileirar(session, base["cap"], "falso", base["narrador"], **kw)
    session.commit()
    return job


def test_recusa_texto_nao_revisado(session, base):
    base["cap"].estado = EstadoCapitulo.IMPORTADO
    with pytest.raises(jobs.JobRecusado, match="texto revisado"):
        jobs.enfileirar(session, base["cap"], "falso", base["narrador"])


def test_recusa_voz_de_outro_idioma_e_motor_desconhecido(session, base):
    with pytest.raises(jobs.JobRecusado, match="fr"):
        jobs.enfileirar(session, base["cap"], "falso", base["frances"])
    with pytest.raises(Exception, match="desconhecido"):
        jobs.enfileirar(session, base["cap"], "eleven", base["narrador"])


def test_um_job_ativo_por_capitulo(session, base):
    _enfileirar(session, base)
    with pytest.raises(jobs.JobRecusado, match="já tem"):
        jobs.enfileirar(session, base["cap"], "falso", base["narrador"])


def test_ciclo_completo_gera_faixa_e_avanca_capitulo(session, base, armazenamento):
    job = _enfileirar(session, base, resposta=base["resposta"])
    motor = MotorFalso()
    assert worker.processar_um(SessionLocal, armazenamento, motor) is True

    session.expire_all()
    job = session.get(JobAudio, job.id)
    assert job.estado == EstadoJob.CONCLUIDO
    assert job.caracteres > 0
    faixa = session.get(FaixaAudio, job.faixa_id)
    assert faixa.versao == 1
    assert faixa.url == "https://audio.exemplo/le/pt-BR/e1/le-c001-v1.m4a".replace(
        "e1", f"e{base['cap'].edicao_id}"
    )
    assert [m["segmento_id"] for m in faixa.marcacoes] == [s.id for s in base["cap"].segmentos]
    assert (armazenamento.raiz / faixa.url.split("audio.exemplo/")[1]).exists()
    assert session.get(Capitulo, base["cap"].id).estado == EstadoCapitulo.AUDIO_GERADO
    # Dicionário do banco foi aplicado e a resposta saiu na voz própria.
    assert '<sub alias="Kardéc">Kardec</sub>' in motor.pedidos[1].ssml
    assert [p.voz_id for p in motor.pedidos] == ["n", "n", "r"]
    acoes = session.scalars(select(RegistroAuditoria.acao)).all()
    assert acoes == ["audio.enfileirar", "audio.gerado"]

    # Regenerar cria a versão 2, sem apagar a 1.
    _enfileirar(session, base)
    worker.processar_um(SessionLocal, armazenamento, MotorFalso())
    assert sorted(session.scalars(select(FaixaAudio.versao)).all()) == [1, 2]


def test_modo_bloco_vem_da_configuracao(session, base, armazenamento, monkeypatch):
    monkeypatch.setattr(get_settings(), "tts_modo", "bloco")
    job = _enfileirar(session, base, resposta=base["resposta"])
    motor = MotorFalso()
    assert worker.processar_um(SessionLocal, armazenamento, motor) is True

    session.expire_all()
    faixa = session.get(FaixaAudio, session.get(JobAudio, job.id).faixa_id)
    # Os dois segmentos do narrador num pedido; a resposta, em outra voz, noutro.
    assert [p.voz_id for p in motor.pedidos] == ["n", "r"]
    assert [m["segmento_id"] for m in faixa.marcacoes] == [s.id for s in base["cap"].segmentos]


def test_fila_vazia(session):
    assert worker.processar_um(SessionLocal, None, MotorFalso()) is False


class _MotorQuebrado(MotorFalso):
    def sintetizar(self, pedido):
        raise RuntimeError("provedor fora do ar")


def test_falha_volta_a_fila_com_espera_e_desiste_no_limite(session, base, armazenamento):
    job = _enfileirar(session, base)
    worker.processar_um(SessionLocal, armazenamento, _MotorQuebrado())
    session.expire_all()
    job = session.get(JobAudio, job.id)
    assert job.estado == EstadoJob.PENDENTE
    assert "provedor fora do ar" in job.erro
    assert job.disponivel_em > job.iniciado_em
    # Ainda em espera: o worker não pega.
    assert worker.processar_um(SessionLocal, armazenamento, _MotorQuebrado()) is False

    for _ in range(2):
        job.disponivel_em = job.disponivel_em - timedelta(hours=1)
        session.commit()
        worker.processar_um(SessionLocal, armazenamento, _MotorQuebrado())
        session.expire_all()
        job = session.get(JobAudio, job.id)
    assert job.estado == EstadoJob.FALHOU
    assert job.tentativas == 3
    assert session.get(Capitulo, base["cap"].id).estado == EstadoCapitulo.TEXTO_REVISADO


def test_lease_vencido_e_retomado(session, base):
    job = _enfileirar(session, base)
    with SessionLocal() as s:
        assert jobs.pegar(s).id == job.id
    # Worker "morreu" com o job em executando; antes do lease vencer, ninguém pega.
    with SessionLocal() as s:
        assert jobs.pegar(s) is None
    with SessionLocal() as s:
        depois = s.scalar(select(func.now())) + timedelta(hours=1)
    with SessionLocal() as s:
        retomado = jobs.pegar(s, agora=depois)
        assert retomado.id == job.id
        assert retomado.tentativas == 2


def test_skip_locked_nao_entrega_o_mesmo_job_a_dois_workers(session, base):
    job = _enfileirar(session, base)
    with SessionLocal() as a:
        # Worker A segura a linha sem ter feito commit ainda.
        a.scalar(select(JobAudio).where(JobAudio.id == job.id).with_for_update())
        with SessionLocal() as b:
            assert jobs.pegar(b) is None
        a.rollback()


def test_armazenamento_recusa_chave_fora_da_pasta(tmp_path, armazenamento):
    origem = tmp_path / "x.m4a"
    origem.write_bytes(b"x")
    for chave in ("../fora.m4a", "/abs.m4a", "a/../../b.m4a"):
        with pytest.raises(ValueError):
            armazenamento.salvar(origem, chave)
    assert armazenamento.salvar(origem, "le/x.m4a") == "https://audio.exemplo/le/x.m4a"


def test_cli_seed_enfileirar_e_status(session, base, capsys):
    from centelha_api.pipeline import fila_cli

    assert fila_cli.main(["pronuncias-seed"]) == 0
    assert "já existiam" in capsys.readouterr().out
    ed = base["cap"].edicao_id
    args = ["enfileirar", "--edicao", str(ed), "--motor", "falso"]
    assert fila_cli.main([*args, "--narrador", str(base["narrador"].id)]) == 0
    assert "1 capítulos na fila" in capsys.readouterr().out
    fila_cli.main(["status", "--edicao", str(ed)])
    assert "pendente" in capsys.readouterr().out
    assert fila_cli.main([*args, "--narrador", "99999"]) == 1
