"""Limpeza do texto do OCR, página por página.

Entrada: as páginas do OCR, separadas por \\f (form feed, como o Tesseract escreve).
Saída: parágrafos com a página de origem, para o relatório apontar onde conferir.

- Cabeçalhos e rodapés repetidos (título da obra, nome do capítulo) saem quando a
  mesma linha, sem os dígitos, aparece no topo ou no pé de muitas páginas.
- Número de página sozinho na linha sai.
- Palavra hifenizada no fim da linha, ou no fim da página, é juntada.
- Ligaduras e espaços estranhos são normalizados; aspas ficam como no exemplar.
"""

import re
from collections import Counter
from dataclasses import dataclass

_LIGADURAS = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ſ": "s"})
_ESPACOS = re.compile(r"[ \t   ]+")
_NUMERO_PAGINA = re.compile(r"^[\s\-–—.]*\d{1,4}[\s\-–—.]*$")
_ROMANO_PAGINA = re.compile(r"^\s*[ivxlc]{1,7}\s*$", re.IGNORECASE)
# Fim de linha com hífen depois de letra minúscula: "pala-" + "vra".
_HIFEN_FINAL = re.compile(r"(\w)[-¬]$")


@dataclass(frozen=True)
class Paragrafo:
    pagina: int
    texto: str


def _assinatura(linha: str) -> str:
    """Linha sem dígitos e sem caixa: o cabeçalho "O LIVRO DOS ESPÍRITOS 123" de toda
    página tem a mesma assinatura."""
    return re.sub(r"[\d\s.\-–—]+", " ", linha.lower()).strip()


def _repetidas(paginas: list[list[str]], minimo: float = 0.3) -> set[str]:
    """Assinaturas que aparecem nas 2 primeiras ou 2 últimas linhas de muitas páginas."""
    if len(paginas) < 4:
        return set()
    contagem: Counter[str] = Counter()
    for linhas in paginas:
        bordas = {_assinatura(linha) for linha in linhas[:2] + linhas[-2:]}
        contagem.update(a for a in bordas if a)
    return {a for a, n in contagem.items() if n >= max(3, minimo * len(paginas))}


def limpar_paginas(texto_ocr: str) -> list[Paragrafo]:
    paginas = [
        [_ESPACOS.sub(" ", linha.translate(_LIGADURAS)).strip() for linha in p.split("\n")]
        for p in texto_ocr.replace("\r\n", "\n").split("\f")
    ]
    repetidas = _repetidas([[linha for linha in p if linha] for p in paginas])

    paragrafos: list[Paragrafo] = []
    atual: list[str] = []
    pagina_atual = 1

    def fechar() -> None:
        if atual:
            paragrafos.append(Paragrafo(pagina_atual, " ".join(atual)))
            atual.clear()

    for numero, linhas in enumerate(paginas, start=1):
        # Remove bordas repetidas e números de página; o resto mantém a ordem.
        uteis = list(linhas)
        while uteis and not uteis[0]:
            uteis.pop(0)
        while uteis and not uteis[-1]:
            uteis.pop()
        for borda in (0, -1):
            for _ in range(2):
                if not uteis:
                    break
                linha = uteis[borda]
                if (
                    _NUMERO_PAGINA.match(linha)
                    or _ROMANO_PAGINA.match(linha)
                    or _assinatura(linha) in repetidas
                ):
                    uteis.pop(borda)
                    while uteis and not uteis[borda]:
                        uteis.pop(borda)
        for linha in uteis:
            if not linha:
                fechar()
                continue
            if not atual:
                pagina_atual = numero
            if atual and _HIFEN_FINAL.search(atual[-1]) and linha[:1].islower():
                atual[-1] = atual[-1][:-1] + linha.split(" ", 1)[0]
                resto = linha.split(" ", 1)[1:] if " " in linha else []
                if resto:
                    atual.append(resto[0])
                continue
            atual.append(linha)
        # Parágrafo que continua na página seguinte: só fecha se a última linha termina
        # frase; senão a próxima página o completa.
        if atual and re.search(r"[.!?:»”\"]$", atual[-1]):
            fechar()
    fechar()
    return paragrafos


def como_texto(paragrafos: list[Paragrafo]) -> str:
    """Formato que a ingestão lê (parágrafos separados por linha em branco)."""
    return "\n\n".join(p.texto for p in paragrafos) + "\n"
