"""Vídeo curto vertical (Shorts) a partir de um trecho já narrado (#44).

Etapa de montagem do plano de redes sociais (docs-iniciais/MDs/plano-redes-sociais.md):
o trecho vem do áudio do capítulo, cortado pelas marcações de tempo da pipeline; a
legenda segue as mesmas marcações; na tela, a referência da obra e a chamada para o
app. Escolher o trecho, o roteiro e as imagens é curadoria humana e fica fora daqui.

Legenda em ASS queimada no vídeo (libass), e também em SRT à parte para subir como
legenda da plataforma (acessibilidade e busca).
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .audio import ErroPosProducao, ffmpeg_exe

LARGURA, ALTURA = 1080, 1920
# Cores da marca (site/src/styles/tokens.css): azul-noite, texto creme, dourado.
FUNDO = "0x000F3B"
FONTE = "Comfortaa"
# Shorts aceitam mais, mas o plano pede 30–60 s; acima disso o corte é escolha errada.
DURACAO_MAX_S = 60.0
# Folga depois da última palavra: cortar no fim exato da marcação engole a cauda da voz.
CAUDA_MS = 400
# Caracteres por bloco de legenda: cabe em ~3 linhas a 1080 px sem cobrir a tela.
BLOCO_MAX = 90


class ErroVideo(Exception):
    pass


@dataclass(frozen=True)
class TrechoLegenda:
    texto: str
    inicio_ms: int
    fim_ms: int


@dataclass(frozen=True)
class Legenda:
    texto: str
    inicio_ms: int  # relativo ao início do vídeo
    fim_ms: int


def _blocos(texto: str, maximo: int = BLOCO_MAX) -> list[str]:
    """Quebra em blocos de até `maximo` caracteres, só entre palavras."""
    blocos, atual = [], ""
    for palavra in texto.split():
        candidato = f"{atual} {palavra}".strip()
        if atual and len(candidato) > maximo:
            blocos.append(atual)
            atual = palavra
        else:
            atual = candidato
    if atual:
        blocos.append(atual)
    return blocos


def legendas(trechos: list[TrechoLegenda]) -> list[Legenda]:
    """Uma legenda por bloco, no tempo do segmento, dividido pelos caracteres.

    A pipeline marca o tempo por segmento, não por palavra; repartir pelo tamanho do
    texto é a aproximação que mantém a legenda perto da voz sem alinhamento forçado.
    """
    if not trechos:
        return []
    origem = trechos[0].inicio_ms
    saida = []
    for t in trechos:
        blocos = _blocos(t.texto)
        total = sum(len(b) for b in blocos) or 1
        inicio = t.inicio_ms
        for i, b in enumerate(blocos):
            fim = (
                t.fim_ms
                if i == len(blocos) - 1
                else inicio + round((t.fim_ms - t.inicio_ms) * len(b) / total)
            )
            saida.append(Legenda(b, inicio - origem, fim - origem))
            inicio = fim
    return saida


def _tempo_ass(ms: int) -> str:
    cs = round(ms / 10)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _tempo_srt(ms: int) -> str:
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _escapar_ass(texto: str) -> str:
    # Chaves abrem tag de estilo no ASS; texto de Kardec não pode virar comando.
    return texto.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def documento_ass(
    legs: list[Legenda], referencia: str, chamada: str | None, duracao_ms: int
) -> str:
    """Legenda, referência no topo e chamada embaixo, nas cores da marca (ASS: &HBBGGRR)."""
    linhas = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {LARGURA}",
        f"PlayResY: {ALTURA}",
        "WrapStyle: 0",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, "
        "Alignment, MarginL, MarginR, MarginV, BorderStyle, Outline, Shadow",
        # Texto creme (#FBF5E6) com contorno azul-noite: legível sobre qualquer fundo.
        f"Style: Legenda,{FONTE},64,&H00E6F5FB,&H003B0F00,&H00000000,1,5,90,90,0,1,4,0",
        # Referência em dourado (#FFD84D), no topo.
        f"Style: Referencia,{FONTE},44,&H004DD8FF,&H003B0F00,&H00000000,1,8,90,90,170,1,3,0",
        # Chamada acima da faixa de baixo, que no Shorts fica sob o título e os botões.
        f"Style: Chamada,{FONTE},46,&H00E6F5FB,&H003B0F00,&H00000000,1,2,90,90,480,1,3,0",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Text",
    ]
    fim = _tempo_ass(duracao_ms)
    linhas.append(f"Dialogue: 0,{_tempo_ass(0)},{fim},Referencia,{_escapar_ass(referencia)}")
    if chamada:
        linhas.append(f"Dialogue: 0,{_tempo_ass(0)},{fim},Chamada,{_escapar_ass(chamada)}")
    for leg in legs:
        linhas.append(
            f"Dialogue: 1,{_tempo_ass(leg.inicio_ms)},{_tempo_ass(leg.fim_ms)},Legenda,"
            f"{_escapar_ass(leg.texto)}"
        )
    return "\n".join(linhas) + "\n"


def documento_srt(legs: list[Legenda]) -> str:
    return "\n".join(
        f"{i}\n{_tempo_srt(leg.inicio_ms)} --> {_tempo_srt(leg.fim_ms)}\n{leg.texto}\n"
        for i, leg in enumerate(legs, start=1)
    )


def montar_video(
    audio_capitulo: Path,
    trechos: list[TrechoLegenda],
    referencia: str,
    chamada: str | None,
    destino: Path,
    fundo: Path | None = None,
    duracao_max_s: float = DURACAO_MAX_S,
) -> Path:
    """Gera destino.mp4 e destino.srt. Devolve o caminho do vídeo."""
    if not trechos:
        raise ErroVideo("nenhum segmento no trecho")
    inicio = trechos[0].inicio_ms
    fim = trechos[-1].fim_ms + CAUDA_MS
    duracao = fim - inicio
    if duracao / 1000 > duracao_max_s:
        raise ErroVideo(f"trecho de {duracao / 1000:.1f} s passa de {duracao_max_s:.0f} s")
    legs = legendas(trechos)

    destino = destino.with_suffix(".mp4")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.with_suffix(".srt").write_text(documento_srt(legs), encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp:
        # O filtro ass recebe caminho relativo ao cwd: caminho absoluto no Windows ("C:")
        # colide com o ":" que separa opções do filtro.
        Path(tmp, "legenda.ass").write_text(
            documento_ass(legs, referencia, chamada, duracao), encoding="utf-8"
        )
        filtro = "ass=legenda.ass"
        if fontes := os.environ.get("CENTELHA_VIDEO_FONTES"):
            filtro += f":fontsdir={fontes}"
        if fundo:
            entrada_video = ["-loop", "1", "-i", str(fundo.resolve())]
            # Preenche 9:16 cortando o excesso, sem distorcer a imagem.
            filtro = (
                f"scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,"
                f"crop={LARGURA}:{ALTURA},{filtro}"
            )
        else:
            entrada_video = ["-f", "lavfi", "-i", f"color=c={FUNDO}:s={LARGURA}x{ALTURA}:r=30"]
        comando = [
            ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            *entrada_video,
            "-ss", f"{inicio / 1000:.3f}", "-to", f"{fim / 1000:.3f}",
            "-i", str(audio_capitulo.resolve()),
            "-map", "0:v", "-map", "1:a",
            "-vf", filtro,
            "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-t", f"{duracao / 1000:.3f}",
            "-movflags", "+faststart",
            str(destino.resolve()),
        ]  # fmt: skip
        r = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8", cwd=tmp)
        if r.returncode != 0:
            raise ErroPosProducao(f"ffmpeg falhou: {r.stderr.strip()[-500:]}")
    return destino
