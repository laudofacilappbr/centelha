import math
import struct
import subprocess
import wave

import pytest

from centelha_api.pipeline.audio import (
    ErroPosProducao,
    MarcaSegmento,
    TrechoAudio,
    duracao_ms,
    ffmpeg_exe,
    juntar_wav,
    montar_capitulo,
)

TAXA = 24000


def _tom(caminho, segundos, taxa=TAXA, freq=440.0, amplitude=0.1, canais=1):
    n = int(taxa * segundos)
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(canais)
        w.setsampwidth(2)
        w.setframerate(taxa)
        quadros = b"".join(
            struct.pack("<h", int(amplitude * 32767 * math.sin(2 * math.pi * freq * i / taxa)))
            * canais
            for i in range(n)
        )
        w.writeframes(quadros)
    return caminho


def test_marcacoes_exatas_com_pausas(tmp_path):
    trechos = [
        TrechoAudio(10, _tom(tmp_path / "a.wav", 1.0), pausa_depois_ms=1000),
        TrechoAudio(11, _tom(tmp_path / "b.wav", 0.5)),
        TrechoAudio(12, _tom(tmp_path / "c.wav", 0.25)),
    ]
    duracao, marcacoes = juntar_wav(trechos, tmp_path / "x.wav", pausa_ms=600)
    assert marcacoes == [
        {"segmento_id": 10, "inicio_ms": 0, "fim_ms": 1000},
        {"segmento_id": 11, "inicio_ms": 2000, "fim_ms": 2500},
        {"segmento_id": 12, "inicio_ms": 3100, "fim_ms": 3350},
    ]
    # Sem pausa depois do último trecho.
    assert duracao == 3350


def test_trecho_em_bloco_usa_as_marcas_de_cada_segmento(tmp_path):
    trechos = [
        TrechoAudio(1, _tom(tmp_path / "a.wav", 0.5), pausa_depois_ms=1000),
        TrechoAudio(
            2,
            _tom(tmp_path / "b.wav", 2.0),
            marcas=(MarcaSegmento(2, 100, 900), MarcaSegmento(3, 1200, 2500)),
        ),
    ]
    duracao, marcacoes = juntar_wav(trechos, tmp_path / "x.wav")
    assert marcacoes == [
        {"segmento_id": 1, "inicio_ms": 0, "fim_ms": 500},
        # O bloco começa em 1500 ms; as marcas são relativas a ele.
        {"segmento_id": 2, "inicio_ms": 1600, "fim_ms": 2400},
        # Marca além do fim do áudio do bloco fica presa ao fim dele.
        {"segmento_id": 3, "inicio_ms": 2700, "fim_ms": 3500},
    ]
    assert duracao == 3500


def test_formatos_diferentes_sao_recusados(tmp_path):
    trechos = [
        TrechoAudio(1, _tom(tmp_path / "a.wav", 0.1)),
        TrechoAudio(2, _tom(tmp_path / "b.wav", 0.1, taxa=16000)),
    ]
    with pytest.raises(ErroPosProducao, match="segmento 2"):
        juntar_wav(trechos, tmp_path / "x.wav")


def test_capitulo_vazio(tmp_path):
    with pytest.raises(ErroPosProducao, match="sem trechos"):
        juntar_wav([], tmp_path / "x.wav")


def _lufs_integrado(arquivo):
    r = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(arquivo), "-af", "ebur128", "-f", "null", "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    resumo = r.stderr.split("Summary:")[-1]
    return float(resumo.split("I:")[1].split("LUFS")[0])


def test_montar_capitulo_gera_aac_normalizado(tmp_path):
    trechos = [
        TrechoAudio(1, _tom(tmp_path / "a.wav", 2.0, amplitude=0.02)),
        TrechoAudio(2, _tom(tmp_path / "b.wav", 2.0, amplitude=0.02, freq=330)),
    ]
    faixa = montar_capitulo(trechos, tmp_path / "cap.m4a")
    assert faixa.arquivo.exists()
    assert faixa.duracao_ms == 4600
    # AAC acrescenta poucos ms de priming; o que importa é a escala bater.
    assert abs(duracao_ms(faixa.arquivo) - faixa.duracao_ms) < 100
    # Tom baixo (≈ −37 LUFS) sobe para perto do alvo.
    assert _lufs_integrado(faixa.arquivo) == pytest.approx(-16.0, abs=1.5)
