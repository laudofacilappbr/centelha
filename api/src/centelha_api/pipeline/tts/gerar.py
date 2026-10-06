"""Gera a faixa de um capítulo: normaliza, aplica o dicionário, sintetiza cada segmento
com a voz do seu papel e entrega à pós-produção.

Não toca no banco: recebe os segmentos e devolve a faixa montada. A fila de jobs (que
vem depois) lê do banco, chama isto e grava a FaixaAudio.
"""

import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ...models import TipoSegmento
from ..audio import FaixaMontada, TrechoAudio, montar_capitulo
from ..normalizacao import fr, pt_br
from ..pronuncia import EntradaPronuncia, aplicar, aplicar_texto
from .motores import Motor, Pedido

# Pausa depois de cada tipo de segmento. Título respira mais; a resposta vem logo
# depois da pergunta, como num diálogo.
PAUSAS_MS: dict[TipoSegmento, int] = {
    TipoSegmento.TITULO: 1200,
    TipoSegmento.PERGUNTA: 500,
    TipoSegmento.RESPOSTA: 800,
    TipoSegmento.COMENTARIO: 700,
    TipoSegmento.PARAGRAFO: 700,
    TipoSegmento.NOTA: 700,
}

# Por idioma BCP 47; sem o exato, vale o idioma base ("fr-CA" usa o de "fr").
# Não há chave "pt": pt-PT lê números e abreviações de outro jeito e fica sem normalização.
NORMALIZADORES = {"pt-BR": pt_br.normalizar, "fr": fr.normalizar}


def normalizador(idioma: str) -> Callable[[str], str]:
    funcao = NORMALIZADORES.get(idioma) or NORMALIZADORES.get(idioma.split("-")[0])
    if funcao is None:
        raise ValueError(f"sem normalização para {idioma}")
    return funcao


@dataclass(frozen=True)
class SegmentoParaVoz:
    id: int
    tipo: TipoSegmento
    texto: str


@dataclass(frozen=True)
class Vozes:
    """Voz por papel. O Livro dos Espíritos usa vozes distintas para pergunta e resposta;
    sem elas, tudo sai na voz do narrador."""

    narrador: str
    pergunta: str | None = None
    resposta: str | None = None

    def para(self, tipo: TipoSegmento) -> str:
        if tipo == TipoSegmento.PERGUNTA and self.pergunta:
            return self.pergunta
        if tipo == TipoSegmento.RESPOSTA and self.resposta:
            return self.resposta
        return self.narrador


@dataclass(frozen=True)
class ResultadoGeracao:
    faixa: FaixaMontada
    # Caracteres enviados ao motor: base do custo por obra (#24).
    caracteres: int
    segundos_sintese: float


def pedido_para(
    segmento: SegmentoParaVoz,
    vozes: Vozes,
    dicionario: list[EntradaPronuncia],
    idioma: str = "pt-BR",
) -> Pedido:
    texto = normalizador(idioma)(segmento.texto)
    return Pedido(
        ssml=aplicar(texto, dicionario),
        texto=aplicar_texto(texto, dicionario),
        voz_id=vozes.para(segmento.tipo),
        idioma=idioma,
    )


def gerar_capitulo(
    segmentos: list[SegmentoParaVoz],
    motor: Motor,
    vozes: Vozes,
    dicionario: list[EntradaPronuncia],
    destino: Path,
    idioma: str = "pt-BR",
) -> ResultadoGeracao:
    inicio = time.monotonic()
    caracteres = 0
    with tempfile.TemporaryDirectory() as tmp:
        trechos = []
        for s in segmentos:
            pedido = pedido_para(s, vozes, dicionario, idioma)
            caracteres += len(pedido.ssml if motor.aceita_ssml else pedido.texto)
            wav = Path(tmp) / f"{s.id}.wav"
            wav.write_bytes(motor.sintetizar(pedido))
            trechos.append(TrechoAudio(s.id, wav, PAUSAS_MS.get(s.tipo)))
        faixa = montar_capitulo(trechos, destino)
    return ResultadoGeracao(faixa, caracteres, time.monotonic() - inicio)
