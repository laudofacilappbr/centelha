"""Pós-produção: junta o áudio dos segmentos de um capítulo numa faixa.

Entrada: um WAV por segmento, saído do motor de TTS. Saída: AAC (.m4a) com loudness
padronizado (−16 LUFS, mobile) e as marcações de tempo de cada segmento para a leitura
acompanhada. As marcações saem da contagem de amostras, não de estimativa: o destaque
no app só fica certo se o tempo for exato.
"""

import os
import re
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

PAUSA_PADRAO_MS = 600


@dataclass(frozen=True)
class MarcaSegmento:
    """Onde um segmento começa e termina dentro do áudio de um bloco, em ms relativos."""

    segmento_id: int
    inicio_ms: int
    fim_ms: int


@dataclass(frozen=True)
class TrechoAudio:
    segmento_id: int
    wav: Path
    # Pausa depois deste trecho; None usa a padrão. Título pede pausa maior que parágrafo.
    pausa_depois_ms: int | None = None
    # Trecho sintetizado em bloco (vários segmentos num pedido): o tempo de cada um,
    # vindo dos marcadores do motor. None = o trecho inteiro é um segmento só.
    marcas: tuple[MarcaSegmento, ...] | None = None


@dataclass(frozen=True)
class FaixaMontada:
    arquivo: Path
    duracao_ms: int
    marcacoes: list[dict]


class ErroPosProducao(Exception):
    pass


def ffmpeg_exe() -> str:
    """CENTELHA_FFMPEG > ffmpeg do sistema (container do worker) > binário do imageio (dev)."""
    if exe := os.environ.get("CENTELHA_FFMPEG"):
        return exe
    if exe := shutil.which("ffmpeg"):
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as e:
        raise ErroPosProducao("ffmpeg não encontrado; instale ou defina CENTELHA_FFMPEG") from e


def _ms(frames: int, taxa: int) -> int:
    return round(frames * 1000 / taxa)


def juntar_wav(trechos: list[TrechoAudio], destino: Path, pausa_ms: int = PAUSA_PADRAO_MS):
    """Concatena os WAVs com silêncio entre eles. Devolve (duração_ms, marcações)."""
    if not trechos:
        raise ErroPosProducao("capítulo sem trechos de áudio")
    formato = None
    marcacoes: list[dict] = []
    total = 0
    with wave.open(str(destino), "wb") as saida:
        for i, trecho in enumerate(trechos):
            with wave.open(str(trecho.wav), "rb") as entrada:
                params = (entrada.getnchannels(), entrada.getsampwidth(), entrada.getframerate())
                if formato is None:
                    formato = params
                    saida.setnchannels(params[0])
                    saida.setsampwidth(params[1])
                    saida.setframerate(params[2])
                elif params != formato:
                    raise ErroPosProducao(
                        f"segmento {trecho.segmento_id}: formato {params} difere de {formato}"
                    )
                n = entrada.getnframes()
                saida.writeframes(entrada.readframes(n))
            canais, largura, taxa = formato
            inicio, fim = _ms(total, taxa), _ms(total + n, taxa)
            for m in trecho.marcas or (MarcaSegmento(trecho.segmento_id, 0, fim - inicio),):
                marcacoes.append(
                    {
                        "segmento_id": m.segmento_id,
                        "inicio_ms": min(inicio + m.inicio_ms, fim),
                        "fim_ms": min(inicio + m.fim_ms, fim),
                    }
                )
            total += n
            if i < len(trechos) - 1:
                pausa = trecho.pausa_depois_ms if trecho.pausa_depois_ms is not None else pausa_ms
                silencio = round(taxa * pausa / 1000)
                saida.writeframes(b"\x00" * silencio * canais * largura)
                total += silencio
    return _ms(total, formato[2]), marcacoes


_RE_DURACAO = re.compile(r"Duration: (\d+):(\d+):(\d+\.\d+)")


def duracao_ms(arquivo: Path) -> int:
    """Duração lida pelo ffmpeg (sem depender de ffprobe)."""
    r = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(arquivo)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    m = _RE_DURACAO.search(r.stderr)
    if not m:
        raise ErroPosProducao(f"não consegui ler a duração de {arquivo}")
    h, mi, s = m.groups()
    return round((int(h) * 3600 + int(mi) * 60 + float(s)) * 1000)


def montar_capitulo(
    trechos: list[TrechoAudio],
    destino: Path,
    pausa_ms: int = PAUSA_PADRAO_MS,
    alvo_lufs: float = -16.0,
    bitrate: str = "64k",
) -> FaixaMontada:
    with tempfile.TemporaryDirectory() as tmp:
        bruto = Path(tmp) / "capitulo.wav"
        duracao, marcacoes = juntar_wav(trechos, bruto, pausa_ms)
        with wave.open(str(bruto), "rb") as w:
            taxa = w.getframerate()
        comando = [
            ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(bruto),
            "-af", f"loudnorm=I={alvo_lufs}:TP=-1.5:LRA=11",
            # loudnorm trabalha em 192 kHz; volta à taxa do TTS.
            "-ar", str(taxa),
            "-c:a", "aac", "-b:a", bitrate,
            "-movflags", "+faststart",
            str(destino),
        ]  # fmt: skip
        r = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            raise ErroPosProducao(f"ffmpeg falhou: {r.stderr.strip()[-500:]}")
    return FaixaMontada(arquivo=destino, duracao_ms=duracao, marcacoes=marcacoes)
