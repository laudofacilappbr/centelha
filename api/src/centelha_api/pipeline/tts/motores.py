"""Adaptadores de motor de TTS. Todos devolvem WAV PCM 16 bits mono.

A escolha do motor é decisão humana pela escuta (#1). Até lá, cada adaptador recebe o
mesmo trecho e o script de comparação gera as amostras lado a lado.

Motores com marcadores (`sintetizar_com_marcas`) aceitam um bloco de vários segmentos
num pedido só e devolvem o tempo de cada `<mark>`; os demais recebem um segmento por
pedido. Hoje: Google (v1beta1, timepoints) e o falso. O Azure por REST devolve só o
áudio; os bookmarks dele chegam apenas pelo Speech SDK.

Credenciais vêm de variáveis de ambiente, nunca do código:
  CENTELHA_AZURE_TTS_KEY, CENTELHA_AZURE_TTS_REGION
  CENTELHA_GOOGLE_TTS_KEY
  CENTELHA_PIPER_BIN, CENTELHA_PIPER_MODELOS (pasta com os .onnx)
"""

import base64
import json
import math
import os
import re
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


@dataclass(frozen=True)
class SinteseMarcada:
    wav: bytes
    # Nome do <mark> → ms desde o início do áudio.
    marcas_ms: dict[str, int]


class MotorComMarcas(Motor, Protocol):
    def sintetizar_com_marcas(self, pedido: Pedido) -> SinteseMarcada: ...


def aceita_marcas(motor: Motor) -> bool:
    return callable(getattr(motor, "sintetizar_com_marcas", None))


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

    def _tom(self, caracteres: int, voz_id: str) -> bytes:
        n = max(1, round(TAXA_PADRAO * self.ms_por_caractere * caracteres / 1000))
        freq = 220 + (sum(map(ord, voz_id)) % 220)
        return b"".join(
            struct.pack("<h", int(3000 * math.sin(2 * math.pi * freq * i / TAXA_PADRAO)))
            for i in range(n)
        )

    def sintetizar(self, pedido: Pedido) -> bytes:
        self.pedidos.append(pedido)
        return _wav_pcm(self._tom(len(pedido.texto), pedido.voz_id))

    def sintetizar_com_marcas(self, pedido: Pedido) -> SinteseMarcada:
        """Lê o SSML do bloco: texto vira tom, <break> vira silêncio, <mark> anota o tempo."""
        self.pedidos.append(pedido)
        amostras = bytearray()
        marcas: dict[str, int] = {}
        for marca, pausa, texto in _RE_SSML_FALSO.findall(pedido.ssml):
            if marca:
                marcas[marca] = round(len(amostras) // 2 * 1000 / TAXA_PADRAO)
            elif pausa:
                amostras += bytes(2 * round(TAXA_PADRAO * int(pausa) / 1000))
            elif texto.strip():
                amostras += self._tom(len(texto), pedido.voz_id)
        return SinteseMarcada(_wav_pcm(bytes(amostras)), marcas)


_RE_SSML_FALSO = re.compile(r'<mark name="([^"]+)"/>|<break time="(\d+)ms"/>|<[^>]+>|([^<]+)')


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

    def _chamar(self, pedido: Pedido, versao: str, extra: dict) -> tuple[bytes, dict]:
        chave = _exigir("CENTELHA_GOOGLE_TTS_KEY")
        corpo = {
            "input": {"ssml": f"<speak>{pedido.ssml}</speak>"},
            "voice": {"languageCode": pedido.idioma, "name": pedido.voz_id},
            # LINEAR16 já vem com cabeçalho WAV.
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": TAXA_PADRAO},
            **extra,
        }
        resposta = _post(
            f"https://texttospeech.googleapis.com/{versao}/text:synthesize",
            json.dumps(corpo).encode("utf-8"),
            {"Content-Type": "application/json", "X-Goog-Api-Key": chave},
        )
        try:
            dados = json.loads(resposta)
            return base64.b64decode(dados["audioContent"]), dados
        except (KeyError, ValueError) as e:
            raise ErroTTS("google: resposta sem audioContent") from e

    def sintetizar(self, pedido: Pedido) -> bytes:
        return self._chamar(pedido, "v1", {})[0]

    def sintetizar_com_marcas(self, pedido: Pedido) -> SinteseMarcada:
        # Os timepoints de <mark> só existem na v1beta1.
        wav, dados = self._chamar(pedido, "v1beta1", {"enableTimePointing": ["SSML_MARK"]})
        try:
            # JSON de proto3 omite o valor zero: marca no início do áudio vem sem timeSeconds.
            marcas = {
                t["markName"]: round(float(t.get("timeSeconds", 0)) * 1000)
                for t in dados.get("timepoints", [])
            }
        except (KeyError, TypeError, ValueError) as e:
            raise ErroTTS("google: timepoints inválidos") from e
        return SinteseMarcada(wav, marcas)


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
