"""Adaptadores de motor de TTS. Todos devolvem WAV PCM 16 bits mono.

A escolha do motor é decisão humana pela escuta (#1). Até lá, cada adaptador recebe o
mesmo trecho e o script de comparação gera as amostras lado a lado.

Credenciais vêm de variáveis de ambiente, nunca do código:
  CENTELHA_AZURE_TTS_KEY, CENTELHA_AZURE_TTS_REGION
  CENTELHA_GOOGLE_TTS_KEY
  CENTELHA_PIPER_BIN, CENTELHA_PIPER_MODELOS (pasta com os .onnx)
"""

import base64
import json
import math
import os
import struct
import subprocess
import urllib.request
import wave
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Protocol
from xml.sax.saxutils import quoteattr

TAXA_PADRAO = 24000


class ErroTTS(Exception):
    pass


@dataclass(frozen=True)
class Pedido:
    """Um trecho para sintetizar.

    ssml: fragmento já escapado, com <sub>/<phoneme> do dicionário (sem <speak>).
    texto: o mesmo trecho em texto puro, com as substituições do dicionário aplicadas,
           para motores sem SSML (Piper).
    """

    ssml: str
    texto: str
    voz_id: str
    idioma: str = "pt-BR"


class Motor(Protocol):
    nome: str
    aceita_ssml: bool

    def sintetizar(self, pedido: Pedido) -> bytes: ...


def _wav_pcm(amostras: bytes, taxa: int = TAXA_PADRAO) -> bytes:
    saida = BytesIO()
    with wave.open(saida, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(amostras)
    return saida.getvalue()


def _post(url: str, corpo: bytes, cabecalhos: dict[str, str], timeout: float = 60) -> bytes:
    req = urllib.request.Request(url, data=corpo, headers=cabecalhos, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        detalhe = e.read()[:300].decode("utf-8", "replace")
        raise ErroTTS(f"{url}: HTTP {e.code} {detalhe}") from e
    except urllib.error.URLError as e:
        raise ErroTTS(f"{url}: {e.reason}") from e


def _exigir(var: str) -> str:
    valor = os.environ.get(var)
    if not valor:
        raise ErroTTS(f"defina {var}")
    return valor


@dataclass
class MotorFalso:
    """Para desenvolvimento e testes: tom curto proporcional ao tamanho do texto.

    Permite rodar o pipeline inteiro sem custo e sem rede. Guarda os pedidos recebidos.
    """

    nome: str = "falso"
    aceita_ssml: bool = True
    ms_por_caractere: int = 20
    pedidos: list[Pedido] = field(default_factory=list)

    def sintetizar(self, pedido: Pedido) -> bytes:
        self.pedidos.append(pedido)
        n = max(1, round(TAXA_PADRAO * self.ms_por_caractere * len(pedido.texto) / 1000))
        freq = 220 + (sum(map(ord, pedido.voz_id)) % 220)
        amostras = b"".join(
            struct.pack("<h", int(3000 * math.sin(2 * math.pi * freq * i / TAXA_PADRAO)))
            for i in range(n)
        )
        return _wav_pcm(amostras)


@dataclass
class MotorAzure:
    nome: str = "azure"
    aceita_ssml: bool = True

    def sintetizar(self, pedido: Pedido) -> bytes:
        regiao = _exigir("CENTELHA_AZURE_TTS_REGION")
        ssml = (
            f'<speak version="1.0" xml:lang={quoteattr(pedido.idioma)}>'
            f"<voice name={quoteattr(pedido.voz_id)}>{pedido.ssml}</voice></speak>"
        )
        return _post(
            f"https://{regiao}.tts.speech.microsoft.com/cognitiveservices/v1",
            ssml.encode("utf-8"),
            {
                "Ocp-Apim-Subscription-Key": _exigir("CENTELHA_AZURE_TTS_KEY"),
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                "User-Agent": "centelha-pipeline",
            },
        )


@dataclass
class MotorGoogle:
    nome: str = "google"
    aceita_ssml: bool = True

    def sintetizar(self, pedido: Pedido) -> bytes:
        chave = _exigir("CENTELHA_GOOGLE_TTS_KEY")
        corpo = {
            "input": {"ssml": f"<speak>{pedido.ssml}</speak>"},
            "voice": {"languageCode": pedido.idioma, "name": pedido.voz_id},
            # LINEAR16 já vem com cabeçalho WAV.
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": TAXA_PADRAO},
        }
        resposta = _post(
            "https://texttospeech.googleapis.com/v1/text:synthesize",
            json.dumps(corpo).encode("utf-8"),
            {"Content-Type": "application/json", "X-Goog-Api-Key": chave},
        )
        try:
            return base64.b64decode(json.loads(resposta)["audioContent"])
        except (KeyError, ValueError) as e:
            raise ErroTTS("google: resposta sem audioContent") from e


@dataclass
class MotorPiper:
    """Piper local (open source). Sem SSML: recebe o texto com as substituições aplicadas."""

    nome: str = "piper"
    aceita_ssml: bool = False

    def sintetizar(self, pedido: Pedido) -> bytes:
        binario = os.environ.get("CENTELHA_PIPER_BIN", "piper")
        modelo = Path(_exigir("CENTELHA_PIPER_MODELOS")) / f"{pedido.voz_id}.onnx"
        if not modelo.exists():
            raise ErroTTS(f"piper: modelo não encontrado: {modelo}")
        r = subprocess.run(
            [binario, "--model", str(modelo), "--output_file", "-"],
            input=pedido.texto.encode("utf-8"),
            capture_output=True,
            timeout=300,
        )
        if r.returncode != 0:
            raise ErroTTS(f"piper falhou: {r.stderr[-300:].decode('utf-8', 'replace')}")
        return r.stdout


MOTORES: dict[str, type] = {
    "falso": MotorFalso,
    "azure": MotorAzure,
    "google": MotorGoogle,
    "piper": MotorPiper,
}


def motor(nome: str) -> Motor:
    try:
        return MOTORES[nome]()
    except KeyError as e:
        raise ErroTTS(f"motor desconhecido: {nome} (use {', '.join(MOTORES)})") from e
