import base64
import json
import wave
from io import BytesIO

import pytest

from centelha_api.models import TipoSegmento
from centelha_api.pipeline.pronuncia import SEED_PT_BR, EntradaPronuncia, aplicar_texto
from centelha_api.pipeline.tts import comparar, motores
from centelha_api.pipeline.tts.gerar import SegmentoParaVoz, Vozes, gerar_capitulo, pedido_para
from centelha_api.pipeline.tts.motores import (
    ErroTTS,
    MotorAzure,
    MotorFalso,
    MotorGoogle,
    MotorPiper,
    Pedido,
    SinteseMarcada,
)

SEGMENTOS = [
    SegmentoParaVoz(1, TipoSegmento.TITULO, "Capítulo XVII"),
    SegmentoParaVoz(2, TipoSegmento.PERGUNTA, "Que diz Kardec na q. 150?"),
    SegmentoParaVoz(3, TipoSegmento.RESPOSTA, "Resposta curta & direta."),
]

# Prosa corrida (O Evangelho): tudo na voz do narrador, sem termos do dicionário.
PROSA = [
    SegmentoParaVoz(1, TipoSegmento.TITULO, "Sede perfeitos"),
    SegmentoParaVoz(2, TipoSegmento.PARAGRAFO, "Amai os vossos inimigos."),
    SegmentoParaVoz(3, TipoSegmento.PARAGRAFO, "Fazei o bem aos que vos odeiam."),
]


def test_aplicar_texto_usa_substituicao_e_ignora_ipa():
    entradas = [*SEED_PT_BR, EntradaPronuncia("Erasto", ipa="eˈɾastu")]
    assert aplicar_texto("Allan Kardec e Erasto", entradas) == "Alan Kardéc e Erasto"


def test_pedido_normaliza_aplica_dicionario_e_escolhe_voz():
    vozes = Vozes("narrador", pergunta="voz-p", resposta="voz-r")
    p = pedido_para(SEGMENTOS[1], vozes, SEED_PT_BR)
    assert p.voz_id == "voz-p"
    assert p.texto == "Que diz Kardéc na questão cento e cinquenta?"
    assert '<sub alias="Kardéc">Kardec</sub>' in p.ssml
    assert pedido_para(SEGMENTOS[2], vozes, SEED_PT_BR).ssml == "Resposta curta &amp; direta."
    assert pedido_para(SEGMENTOS[0], vozes, SEED_PT_BR).voz_id == "narrador"


def test_sem_vozes_de_dialogo_tudo_no_narrador():
    assert Vozes("n").para(TipoSegmento.PERGUNTA) == "n"


def test_gerar_capitulo_ponta_a_ponta(tmp_path):
    motor = MotorFalso()
    r = gerar_capitulo(SEGMENTOS, motor, Vozes("n", "p", "r"), SEED_PT_BR, tmp_path / "c.m4a")
    assert r.faixa.arquivo.exists()
    assert [m["segmento_id"] for m in r.faixa.marcacoes] == [1, 2, 3]
    # Pausa depois do título (1200 ms) maior que depois da pergunta (500 ms).
    m = r.faixa.marcacoes
    assert m[1]["inicio_ms"] - m[0]["fim_ms"] == 1200
    assert m[2]["inicio_ms"] - m[1]["fim_ms"] == 500
    assert [p.voz_id for p in motor.pedidos] == ["n", "p", "r"]
    assert r.caracteres == sum(len(p.ssml) for p in motor.pedidos)
    assert r.modo == "segmento"


def test_bloco_junta_a_prosa_num_pedido_com_os_mesmos_tempos(tmp_path):
    por_segmento = gerar_capitulo(PROSA, MotorFalso(), Vozes("n"), SEED_PT_BR, tmp_path / "s.m4a")
    motor = MotorFalso()
    em_bloco = gerar_capitulo(
        PROSA, motor, Vozes("n"), SEED_PT_BR, tmp_path / "b.m4a", modo="bloco"
    )
    assert em_bloco.modo == "bloco"
    assert em_bloco.pedidos == 1
    [pedido] = motor.pedidos
    assert pedido.ssml.startswith('<mark name="i1"/>Sede perfeitos<mark name="f1"/>')
    # A pausa de cada tipo vai dentro do bloco: 1200 ms após o título, 700 após parágrafo.
    assert '<mark name="f1"/><break time="1200ms"/><mark name="i2"/>' in pedido.ssml
    assert '<mark name="f2"/><break time="700ms"/><mark name="i3"/>' in pedido.ssml
    assert pedido.ssml.endswith('<mark name="f3"/>')
    # O motor falso fala o mesmo tempo nos dois modos: as marcações têm de coincidir.
    assert em_bloco.faixa.marcacoes == por_segmento.faixa.marcacoes
    assert em_bloco.faixa.duracao_ms == por_segmento.faixa.duracao_ms


def test_bloco_separa_vozes_e_respeita_o_limite(tmp_path):
    motor = MotorFalso()
    r = gerar_capitulo(
        SEGMENTOS, motor, Vozes("n", "p", "r"), SEED_PT_BR, tmp_path / "a.m4a", modo="bloco"
    )
    assert [p.voz_id for p in motor.pedidos] == ["n", "p", "r"]
    assert [m["segmento_id"] for m in r.faixa.marcacoes] == [1, 2, 3]

    motor = MotorFalso()
    r = gerar_capitulo(
        PROSA, motor, Vozes("n"), SEED_PT_BR, tmp_path / "b.m4a", "pt-BR", "bloco", 80
    )
    assert len(motor.pedidos) == 3
    assert all(len(p.ssml.encode()) <= 80 for p in motor.pedidos)


class _SoSegmento:
    """Motor sem marcadores, como o Piper e o Azure por REST."""

    nome = "so-segmento"
    aceita_ssml = True

    def __init__(self):
        self.interno = MotorFalso()

    def sintetizar(self, pedido):
        return self.interno.sintetizar(pedido)


def test_bloco_em_motor_sem_marcadores_cai_para_segmento(tmp_path):
    motor = _SoSegmento()
    r = gerar_capitulo(PROSA, motor, Vozes("n"), SEED_PT_BR, tmp_path / "a.m4a", modo="bloco")
    assert r.modo == "segmento"
    assert len(motor.interno.pedidos) == 3


class _PerdeMarca(MotorFalso):
    def sintetizar_com_marcas(self, pedido):
        s = super().sintetizar_com_marcas(pedido)
        return SinteseMarcada(s.wav, {k: v for k, v in s.marcas_ms.items() if k != "f2"})


def test_marca_ausente_falha_em_vez_de_gravar_tempo_errado(tmp_path):
    with pytest.raises(ErroTTS, match="f2"):
        gerar_capitulo(PROSA, _PerdeMarca(), Vozes("n"), SEED_PT_BR, tmp_path / "a", modo="bloco")


def test_modo_desconhecido(tmp_path):
    with pytest.raises(ValueError, match="modo"):
        gerar_capitulo(PROSA, MotorFalso(), Vozes("n"), SEED_PT_BR, tmp_path / "a", modo="x")


class _Resposta:
    padrao = b""

    def __init__(self, corpo: bytes):
        self.corpo = corpo

    def read(self):
        return self.corpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def requisicoes(monkeypatch):
    feitas = []

    def falso_urlopen(req, timeout):
        feitas.append(req)
        return _Resposta(_Resposta.padrao)

    monkeypatch.setattr(motores.urllib.request, "urlopen", falso_urlopen)
    return feitas


def _wav():
    buf = BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * 10)
    return buf.getvalue()


PEDIDO = Pedido(ssml='<sub alias="Kardéc">Kardec</sub>', texto="Kardéc", voz_id="pt-BR-X")


def test_azure_monta_ssml_com_voz(monkeypatch, requisicoes):
    _Resposta.padrao = _wav()
    monkeypatch.setenv("CENTELHA_AZURE_TTS_KEY", "k")
    monkeypatch.setenv("CENTELHA_AZURE_TTS_REGION", "brazilsouth")
    assert MotorAzure().sintetizar(PEDIDO) == _wav()
    [req] = requisicoes
    assert req.full_url.startswith("https://brazilsouth.tts.speech.microsoft.com/")
    assert req.get_header("Ocp-apim-subscription-key") == "k"
    corpo = req.data.decode()
    assert '<voice name="pt-BR-X">' in corpo
    assert 'xml:lang="pt-BR"' in corpo


def test_google_decodifica_audio(monkeypatch, requisicoes):
    _Resposta.padrao = json.dumps({"audioContent": base64.b64encode(_wav()).decode()}).encode()
    monkeypatch.setenv("CENTELHA_GOOGLE_TTS_KEY", "g")
    assert MotorGoogle().sintetizar(PEDIDO) == _wav()
    corpo = json.loads(requisicoes[0].data)
    assert corpo["voice"] == {"languageCode": "pt-BR", "name": "pt-BR-X"}
    assert corpo["input"]["ssml"].startswith("<speak>")
    # Chave vai no cabeçalho, nunca na URL (não cai em log de proxy).
    assert "g" not in requisicoes[0].full_url.split("/")[-1]
    assert "/v1/" in requisicoes[0].full_url


def test_google_devolve_o_tempo_das_marcas(monkeypatch, requisicoes):
    _Resposta.padrao = json.dumps(
        {
            "audioContent": base64.b64encode(_wav()).decode(),
            # Marca no início vem sem timeSeconds (proto3 omite o zero).
            "timepoints": [{"markName": "i1"}, {"markName": "f1", "timeSeconds": 1.2345}],
        }
    ).encode()
    monkeypatch.setenv("CENTELHA_GOOGLE_TTS_KEY", "g")
    s = MotorGoogle().sintetizar_com_marcas(PEDIDO)
    assert s == SinteseMarcada(_wav(), {"i1": 0, "f1": 1234})
    [req] = requisicoes
    assert "/v1beta1/text:synthesize" in req.full_url
    assert json.loads(req.data)["enableTimePointing"] == ["SSML_MARK"]


def test_sem_credencial_explica(monkeypatch):
    monkeypatch.delenv("CENTELHA_AZURE_TTS_KEY", raising=False)
    monkeypatch.delenv("CENTELHA_AZURE_TTS_REGION", raising=False)
    with pytest.raises(ErroTTS, match="CENTELHA_AZURE_TTS_REGION"):
        MotorAzure().sintetizar(PEDIDO)


def test_piper_sem_url(monkeypatch):
    monkeypatch.delenv("CENTELHA_PIPER_URL", raising=False)
    with pytest.raises(ErroTTS, match="CENTELHA_PIPER_URL"):
        MotorPiper().sintetizar(PEDIDO)


def test_piper_pede_texto_puro_e_voz_ao_servico(monkeypatch, requisicoes):
    monkeypatch.setenv("CENTELHA_PIPER_URL", "http://piper:5000/")
    monkeypatch.setattr(_Resposta, "padrao", _wav())
    wav = MotorPiper().sintetizar(PEDIDO)
    req = requisicoes[0]
    assert req.full_url == "http://piper:5000/synthesize"
    corpo = json.loads(req.data)
    # Texto puro (sem SSML), com a substituição do dicionário já aplicada.
    assert corpo == {"text": PEDIDO.texto, "voice": PEDIDO.voz_id}
    assert wav.startswith(b"RIFF")


def test_piper_resposta_que_nao_e_wav(monkeypatch, requisicoes):
    monkeypatch.setenv("CENTELHA_PIPER_URL", "http://piper:5000")
    monkeypatch.setattr(_Resposta, "padrao", b"<!doctype html>")
    with pytest.raises(ErroTTS, match="não é WAV"):
        MotorPiper().sintetizar(PEDIDO)


def test_motor_desconhecido():
    with pytest.raises(ErroTTS, match="desconhecido"):
        motores.motor("eleven")


def test_comparar_gera_amostras_e_pula_motor_sem_credencial(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("CENTELHA_GOOGLE_TTS_KEY", raising=False)
    fonte = tmp_path / "trecho.txt"
    fonte.write_text("1. Pergunta de teste?\n\n“Resposta de teste.”\n", encoding="utf-8")
    saida = tmp_path / "amostras"
    codigo = comparar.main(
        [
            str(fonte),
            "--saida",
            str(saida),
            "--perfil",
            "perguntas",
            "--motor",
            "falso:a",
            "--motor",
            "google:pt-BR-Neural2-B",
        ]
    )
    assert codigo == 0
    resumo = json.loads((saida / "resumo.json").read_text(encoding="utf-8"))
    assert (saida / resumo["falso:a"]["arquivo"]).exists()
    assert "CENTELHA_GOOGLE_TTS_KEY" in resumo["google:pt-BR-Neural2-B"]["erro"]


def test_comparar_ambos_gera_segmento_e_bloco(tmp_path):
    fonte = tmp_path / "trecho.txt"
    fonte.write_text("Primeiro parágrafo.\n\nSegundo parágrafo.\n", encoding="utf-8")
    saida = tmp_path / "amostras"
    argv = [str(fonte), "--saida", str(saida), "--modo", "ambos"]
    assert comparar.main([*argv, "--motor", "falso:a", "--motor", "piper:x"]) == 0
    resumo = json.loads((saida / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["falso:a:segmento"]["modo"] == "segmento"
    assert resumo["falso:a:bloco"]["modo"] == "bloco"
    assert resumo["falso:a:bloco"]["pedidos"] < resumo["falso:a:segmento"]["pedidos"]
    assert (saida / "falso-a-segmento.m4a").exists()
    assert (saida / "falso-a-bloco.m4a").exists()
    assert "sem modo bloco" in resumo["piper:x:bloco"]["erro"]
