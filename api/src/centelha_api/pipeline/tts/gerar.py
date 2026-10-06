"""Gera a faixa de um capítulo: normaliza, aplica o dicionário, sintetiza com a voz do
papel de cada segmento e entrega à pós-produção.

Dois modos de pedido ao motor:
- "segmento": um pedido por segmento. A entonação recomeça a cada parágrafo.
- "bloco": segmentos consecutivos da mesma voz vão juntos num pedido, com a pausa entre
  eles como <break> e um <mark> no início e no fim de cada um. A entonação flui entre
  parágrafos e o tempo de cada segmento sai dos marcadores. Só para motores com
  marcadores; nos demais, cai para "segmento".

O modo padrão é escolha do dono pela escuta, junto com o motor (#1, #77).

Não toca no banco: recebe os segmentos e devolve a faixa montada. A fila de jobs lê do
banco, chama isto e grava a FaixaAudio.
"""

import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ...models import TipoSegmento
from ..audio import PAUSA_PADRAO_MS, FaixaMontada, MarcaSegmento, TrechoAudio, montar_capitulo
from ..normalizacao import fr, pt_br
from ..pronuncia import EntradaPronuncia, aplicar, aplicar_texto
from .motores import ErroTTS, Motor, Pedido, aceita_marcas

Modo = Literal["segmento", "bloco"]
MODOS: tuple[Modo, ...] = ("segmento", "bloco")

# Teto do SSML de um bloco, em bytes UTF-8. O Google recusa entrada acima de 5000 bytes
# (contando o <speak>); a folga cobre o envelope.
LIMITE_BLOCO_BYTES = 4500

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
    # Modo de fato usado: "bloco" pedido a motor sem marcadores sai "segmento".
    modo: Modo = "segmento"
    pedidos: int = 0


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


@dataclass(frozen=True)
class _Item:
    segmento: SegmentoParaVoz
    pedido: Pedido

    @property
    def pausa_ms(self) -> int:
        return PAUSAS_MS.get(self.segmento.tipo, PAUSA_PADRAO_MS)


def _ssml_bloco(itens: list[_Item]) -> str:
    partes = []
    for i, item in enumerate(itens):
        sid = item.segmento.id
        partes.append(f'<mark name="i{sid}"/>{item.pedido.ssml}<mark name="f{sid}"/>')
        if i < len(itens) - 1:
            partes.append(f'<break time="{item.pausa_ms}ms"/>')
    return "".join(partes)


def agrupar_blocos(itens: list[_Item], limite_bytes: int = LIMITE_BLOCO_BYTES) -> list[list[_Item]]:
    """Segmentos consecutivos da mesma voz, até o limite. Segmento que sozinho passa do
    limite vai num bloco só dele, como no modo por segmento."""
    blocos: list[list[_Item]] = []
    for item in itens:
        atual = blocos[-1] if blocos else None
        if (
            atual
            and atual[-1].pedido.voz_id == item.pedido.voz_id
            and len(_ssml_bloco([*atual, item]).encode("utf-8")) <= limite_bytes
        ):
            atual.append(item)
        else:
            blocos.append([item])
    return blocos


def _marcas_do_bloco(bloco: list[_Item], marcas_ms: dict[str, int]) -> tuple[MarcaSegmento, ...]:
    """Converte os <mark> devolvidos pelo motor no tempo de cada segmento, recusando
    marca ausente ou fora de ordem: tempo errado quebra a leitura acompanhada."""
    resultado = []
    anterior = 0
    for item in bloco:
        sid = item.segmento.id
        try:
            inicio, fim = marcas_ms[f"i{sid}"], marcas_ms[f"f{sid}"]
        except KeyError as e:
            raise ErroTTS(f"motor não devolveu a marca {e.args[0]} do segmento {sid}") from e
        if not anterior <= inicio <= fim:
            raise ErroTTS(f"marcas fora de ordem no segmento {sid}: {inicio}–{fim} ms")
        resultado.append(MarcaSegmento(sid, inicio, fim))
        anterior = fim
    return tuple(resultado)


def gerar_capitulo(
    segmentos: list[SegmentoParaVoz],
    motor: Motor,
    vozes: Vozes,
    dicionario: list[EntradaPronuncia],
    destino: Path,
    idioma: str = "pt-BR",
    modo: Modo = "segmento",
    limite_bloco_bytes: int = LIMITE_BLOCO_BYTES,
) -> ResultadoGeracao:
    if modo not in MODOS:
        raise ValueError(f"modo desconhecido: {modo} (use {', '.join(MODOS)})")
    if modo == "bloco" and not aceita_marcas(motor):
        modo = "segmento"
    inicio = time.monotonic()
    itens = [_Item(s, pedido_para(s, vozes, dicionario, idioma)) for s in segmentos]
    caracteres = 0
    trechos = []
    with tempfile.TemporaryDirectory() as tmp:
        if modo == "bloco":
            for bloco in agrupar_blocos(itens, limite_bloco_bytes):
                pedido = Pedido(
                    ssml=_ssml_bloco(bloco),
                    texto="\n\n".join(i.pedido.texto for i in bloco),
                    voz_id=bloco[0].pedido.voz_id,
                    idioma=idioma,
                )
                caracteres += len(pedido.ssml)
                sintese = motor.sintetizar_com_marcas(pedido)  # type: ignore[attr-defined]
                wav = Path(tmp) / f"b{bloco[0].segmento.id}.wav"
                wav.write_bytes(sintese.wav)
                trechos.append(
                    TrechoAudio(
                        bloco[0].segmento.id,
                        wav,
                        bloco[-1].pausa_ms,
                        _marcas_do_bloco(bloco, sintese.marcas_ms),
                    )
                )
        else:
            for item in itens:
                pedido = item.pedido
                caracteres += len(pedido.ssml if motor.aceita_ssml else pedido.texto)
                wav = Path(tmp) / f"{item.segmento.id}.wav"
                wav.write_bytes(motor.sintetizar(pedido))
                trechos.append(TrechoAudio(item.segmento.id, wav, item.pausa_ms))
        faixa = montar_capitulo(trechos, destino)
    return ResultadoGeracao(faixa, caracteres, time.monotonic() - inicio, modo, len(trechos))
