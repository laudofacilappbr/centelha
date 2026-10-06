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
)

SEGMENTOS = [
    SegmentoParaVoz(1, TipoSegmento.TITULO, "Capítulo XVII"),
    SegmentoParaVoz(2, TipoSegmento.PERGUNTA, "Que diz Kardec na q. 150?"),
    SegmentoParaVoz(3, TipoSegmento.RESPOSTA, "Resposta curta & direta."),
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


def test_sem_credencial_explica(monkeypatch):
    monkeypatch.delenv("CENTELHA_AZURE_TTS_KEY", raising=False)
    monkeypatch.delenv("CENTELHA_AZURE_TTS_REGION", raising=False)
    with pytest.raises(ErroTTS, match="CENTELHA_AZURE_TTS_REGION"):
        MotorAzure().sintetizar(PEDIDO)


def test_piper_sem_modelo(monkeypatch, tmp_path):
    monkeypatch.setenv("CENTELHA_PIPER_MODELOS", str(tmp_path))
    with pytest.raises(ErroTTS, match="modelo não encontrado"):
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
