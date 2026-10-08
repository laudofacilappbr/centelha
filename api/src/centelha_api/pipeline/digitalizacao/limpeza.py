"""Limpeza do texto do OCR, página por página.

Entrada: as páginas do OCR, separadas por \\f (form feed, como o Tesseract escreve).
Saída: parágrafos com a página de origem, para o relatório apontar onde conferir.

- Cabeçalhos e rodapés repetidos saem: a linha que, sem os dígitos, aparece no topo ou
  no pé de muitas páginas (título da obra), e a que está em maiúsculas com o número da
  página na ponta e se repete em 3 ou mais (cabeçalho corrido de cada capítulo).
- Cabeçalho que não se repete também sai quando o número na ponta é o da página: o
  número impresso acompanha a página do PDF com um deslocamento fixo. Pega o cabeçalho
  de capítulo curto e o que o OCR leu torto ("36 CHAPITRE LV.", "PRIÈRES GÉNÉRALES, 387").
- Linha em branco no meio do parágrafo, que o Tesseract põe, não o parte quando a frase
  está aberta e a linha seguinte começa em minúscula.
- Número de página sozinho na linha sai.
- Palavra hifenizada no fim da linha, ou no fim da página, é juntada. O hífen fica
  quando a palavra é composta ("nous-|mêmes"): o livro a escreve com hífen no meio de
  alguma linha, ou é o "-t-il" do francês.
- Ligaduras e espaços estranhos são normalizados; aspas ficam como no exemplar.
- Ruído da margem sai: "|", "|}" e "|n" no começo ou no fim da linha são a borda da
  página vizinha que entrou no escaneado (fac-símile da Library of Congress, #45).
"""

import re
from collections import Counter
from dataclasses import dataclass

from ..ingestao.leitores import compostos, juntar_hifen

_LIGADURAS = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ſ": "s"})
_ESPACOS = re.compile(r"[ \t   ]+")
_NUMERO_PAGINA = re.compile(r"^[\s\-–—.]*\d{1,4}[\s\-–—.]*$")
_ROMANO_PAGINA = re.compile(r"^\s*[ivxlc]{1,7}\s*$", re.IGNORECASE)
# Fim de linha com hífen depois de letra: "pala-" + "vra". Ponto ou vírgula soltos depois
# do hífen são sujeira da margem ("hu-. |" no Évangile), não fim de frase.
_HIFEN_FINAL = re.compile(r"(\w)[-¬][.,]?$")
# As pontas de uma palavra partida no fim da linha: "c'est-" + "à-dire".
_FIM_DE_PALAVRA = re.compile(r"\w+(?:['’-]\w+)*$")
_COMECO_DE_PALAVRA = re.compile(r"\w+(?:['’-]\w+)*")
# Token que começa com barra ou chave, na ponta da linha. Nenhum livro do acervo usa
# "|" nem chaves: é a lombada ou a página ao lado. Palavra antes da barra ("à|m") fica.
_RUIDO_INICIO = re.compile(r"^(?:[|{}\\]+\S?\s+)+")
_RUIDO_FIM = re.compile(r"(?:\s+[|{}\\]+\S{0,2})+$")
# Barra colada na palavra, sem espaço: "|profanation", "spiri-|", "détério-|:", "est}".
# Só "|", "}" e "\": o "{" no começo da palavra costuma ser "1" ou "t" mal lido ("{ous",
# "{er"), e isso é correção, não ruído. Depois do hífen sai também a pontuação solta
# que vem junto ("-|:"), para a hifenização juntar.
_RUIDO_COLADO_INICIO = re.compile(r"^[|}\\]+(?=[^\s|{}\\])")
_RUIDO_COLADO_FIM = re.compile(r"(?<=[-¬])[|{}\\]+\S{0,2}$|(?<=[^\s|{}\\])[|}\\][|{}\\]*$")
# Linha que é só a borda da página vizinha ("|", "| | |", "| :", "‘|"): sai inteira, sem
# virar linha em branco, que partiria o parágrafo.
_SO_RUIDO = re.compile(r"^[\s|{}\\\[\]:;.,'‘’_—–=+*-]*[|{}\\=+*][\s|{}\\\[\]:;.,'‘’_—–=+*-]*$")
# Sinal da margem na frente da linha ("* pour eux", "_ faites", ". preuve", ":germer",
# "-soins"): fica no texto e, depois de linha em branco, abre parágrafo falso. "*", "+",
# "=" e "_" não começam linha de texto; ".", ":", "‘" e "-" só saem antes de minúscula,
# que não começa frase.
_MARGEM_INICIO = re.compile(r"^(?:[*+=_]+\s*(?=\S)|[.:,;‘-]\s*(?=[a-zà-ÿ]))")


@dataclass(frozen=True)
class Paragrafo:
    pagina: int
    texto: str


_ROTULOS = {"capítulo", "capitulo", "livro", "parte", "chapitre", "livre", "partie", ""}


def _assinatura(linha: str) -> str:
    """Linha sem dígitos, sem caixa e sem o número romano da ponta: o cabeçalho "O LIVRO
    DOS ESPÍRITOS 123" de toda página tem a mesma assinatura, e "IV INTRODUCTION." e
    "INTRODUCTION. V" (o romano troca de lado na página par e na ímpar) também.

    Só o romano em maiúsculas e na ponta da linha, onde fica o número de página: "il"
    no meio da frase francesa não é número. E "CAPÍTULO IV" fica com o número, senão
    todo título de capítulo no topo da página teria a mesma assinatura e sairia como
    cabeçalho."""
    sem_romano = re.sub(r"^[IVXLC]{1,6}\b|\b[IVXLC]{1,6}[.]?$", " ", linha.strip())
    if _normal(sem_romano) in _ROTULOS:
        sem_romano = linha
    return _normal(sem_romano)


def _normal(linha: str) -> str:
    # Vírgula também sai: o OCR lê o ponto do cabeçalho como vírgula ("CONSOLATEUR, 89").
    return " ".join(re.sub(r"[\d\s.,\-–—]+", " ", linha.lower()).split())


# Número de página na ponta da linha: arábico ou romano em maiúsculas.
_NUMERO_NA_PONTA = re.compile(r"^(\d{1,4}|[IVXLC]{1,6})\b|\b(\d{1,4}|[IVXLC]{1,6})[.]?$")


_ARABICO_NA_PONTA = re.compile(r"^\d{1,4}\b|\b\d{1,4}[.]?$")


def _cabecalho_numerado(linha: str) -> bool:
    """Número de página na ponta e o resto em maiúsculas. Linha de texto com número no
    fim ("la phrase 2.", "Matthieu, ch. V, v. 3") é minúscula e fica.

    Romano só conta como número de página quando o resto não é rótulo: em "IV
    INTRODUCTION." é a página; em "CHAPITRE V", título que abre o capítulo, é o
    número do capítulo."""
    resto = _NUMERO_NA_PONTA.sub("", linha)
    letras = "".join(c for c in resto if c.isalpha())
    if not _NUMERO_NA_PONTA.search(linha) or len(letras) < 3 or not letras.isupper():
        return False
    return bool(_ARABICO_NA_PONTA.search(linha)) or _normal(resto) not in _ROTULOS


def _repetidas(paginas: list[list[str]], minimo: float = 0.3) -> tuple[set[str], set[str]]:
    """Assinaturas de cabeçalho ou rodapé: nas 2 primeiras ou 2 últimas linhas.

    Duas regras. A linha que se repete em muitas páginas (o título da obra). E a que
    traz número de página na ponta e se repete em 3 ou mais: o cabeçalho corrido de
    cada capítulo ("JE NE SUIS POINT VENU DÉTRUIRE LA LOI. 3", "8 CHAPITRE I.") só
    aparece nas páginas dele, longe dos 30% do livro. Subtítulo repetido ("Instructions
    des Esprits") não tem número, e linha de texto com número no fim não é maiúscula."""
    if len(paginas) < 3:
        return set(), set()
    contagem: Counter[str] = Counter()
    numeradas: Counter[str] = Counter()
    for linhas in paginas:
        bordas = linhas[:2] + linhas[-2:]
        contagem.update({a for a in map(_assinatura, bordas) if a})
        numeradas.update(
            {a for linha in bordas if _cabecalho_numerado(linha) and (a := _assinatura(linha))}
        )
    muitas = {a for a, n in contagem.items() if n >= max(3, minimo * len(paginas))}
    # A segunda regra só vale para a linha que tem o número: o título "CHAPITRE V" que
    # abre o capítulo tem a mesma assinatura do cabeçalho "62 CHAPITRE V." e fica.
    return muitas, {a for a, n in numeradas.items() if n >= 3}


def _numero_arabico(linha: str) -> int | None:
    m = _ARABICO_NA_PONTA.search(linha)
    return int(m.group().rstrip(".")) if m else None


def _deslocamentos(paginas: list[list[str]]) -> set[int]:
    """Página do PDF menos o número impresso, nos cabeçalhos numerados das bordas.

    Vale o deslocamento que aparece em 3 ou mais páginas: costuma haver mais de um (as
    páginas preliminares e o corpo, uma gravura sem número no meio)."""
    contagem: Counter[int] = Counter()
    for numero, linhas in enumerate(paginas, start=1):
        for linha in linhas[:2] + linhas[-2:]:
            if _cabecalho_numerado(linha) and (n := _numero_arabico(linha)) is not None:
                contagem[numero - n] += 1
    return {d for d, n in contagem.items() if n >= 3}


def _numero_da_pagina(linha: str, numero: int, deslocamentos: set[int]) -> bool:
    """Cabeçalho em maiúsculas cujo número é o desta página (±1: folga para uma página
    sem número que ainda não mudou o deslocamento)."""
    n = _numero_arabico(linha) if _cabecalho_numerado(linha) else None
    return n is not None and any(abs(numero - d - n) <= 1 for d in deslocamentos)


def _sem_ruido(linha: str) -> str:
    linha = _RUIDO_FIM.sub("", _RUIDO_INICIO.sub("", linha))
    linha = _RUIDO_COLADO_FIM.sub("", _RUIDO_COLADO_INICIO.sub("", linha)).strip()
    return _MARGEM_INICIO.sub("", linha)


def _juntar_hifen(anterior: str, inicio: int, seguinte: str, conhecidos: set[str]) -> str:
    """Junta "pala-" + "vra"; o hífen fica quando é da palavra (juntar_hifen)."""
    primeira = anterior[: inicio + 1]
    m = _FIM_DE_PALAVRA.search(primeira)
    s = _COMECO_DE_PALAVRA.match(seguinte)
    if m and s and juntar_hifen(m.group(), s.group(), conhecidos) != m.group() + s.group():
        return f"{primeira}-{seguinte}"
    return primeira + seguinte


def limpar_paginas(texto_ocr: str) -> list[Paragrafo]:
    paginas = [
        [
            _sem_ruido(_ESPACOS.sub(" ", linha.translate(_LIGADURAS)).strip())
            for linha in p.split("\n")
            if not _SO_RUIDO.match(linha)
        ]
        for p in texto_ocr.replace("\r\n", "\n").split("\f")
    ]
    nao_vazias = [[linha for linha in p if linha] for p in paginas]
    repetidas, numeradas = _repetidas(nao_vazias)
    deslocamentos = _deslocamentos(nao_vazias)
    conhecidos = compostos([linha for p in nao_vazias for linha in p])

    paragrafos: list[Paragrafo] = []
    atual: list[str] = []
    pagina_atual = 1
    tipico = 60  # caracteres por linha; recalculado a cada página
    em_branco = False

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

        def cabecalho(linha: str, numero: int = numero) -> bool:
            return bool(
                _NUMERO_PAGINA.match(linha)
                or _ROMANO_PAGINA.match(linha)
                or _assinatura(linha) in repetidas
                or (_assinatura(linha) in numeradas and _cabecalho_numerado(linha))
                or _numero_da_pagina(linha, numero, deslocamentos)
            )

        for borda in (0, -1):
            for _ in range(3):
                if not uteis:
                    break
                linha = uteis[borda]
                # Sujeira de 1 ou 2 caracteres na ponta ("—", "|", "Us") esconde o
                # cabeçalho logo depois. Sai só junto com ele: sozinha, pode ser texto.
                dentro = [x for x in (uteis[1:] if borda == 0 else uteis[-2::-1]) if len(x) > 2][:1]
                if cabecalho(linha) or (len(linha) <= 2 and dentro and cabecalho(dentro[0])):
                    uteis.pop(borda)
                    while uteis and not uteis[borda]:
                        uteis.pop(borda)
        tamanhos = sorted(len(linha) for linha in uteis if len(linha) > 20)
        if tamanhos:
            tipico = tamanhos[len(tamanhos) // 2]
        for linha in uteis:
            if not linha:
                em_branco = True
                continue
            if em_branco:
                em_branco = False
                # O Tesseract põe linha em branco no meio do parágrafo (635 vezes no
                # Évangile de 1866). Minúscula depois de frase ainda aberta continua.
                continua = atual and linha[:1].islower() and not _FIM_DE_FRASE.search(atual[-1])
                if not continua:
                    fechar()
            hifen = _HIFEN_FINAL.search(atual[-1]) if atual else None
            if hifen and linha[:1].islower():
                atual[-1] = _juntar_hifen(
                    atual[-1], hifen.start(), linha.split(" ", 1)[0], conhecidos
                )
                resto = linha.split(" ", 1)[1:] if " " in linha else []
                if resto:
                    atual.append(resto[0])
                continue
            if atual and _inicia_paragrafo(atual[-1], linha, tipico):
                fechar()
            if not atual:
                pagina_atual = numero
            atual.append(linha)
        # Parágrafo que chega ao fim da página não fecha aqui: a primeira linha da
        # próxima decide (minúscula continua, questão ou linha curta antes abre outro).
    fechar()
    return paragrafos


_ABRE_PARAGRAFO = re.compile(
    r"^(\d{1,4}\s*[.)–-]\s|[a-z]\)\s|[“«\"—–]|(cap[íi]tulo|livro|parte|chapitre|livre|partie)\b)",
    re.IGNORECASE,
)
# A citação que fecha o versículo termina em ".)": "(Saint Matthieu, ch. xi, v. 15.)".
_FIM_DE_FRASE = re.compile(r"[.!?:»”\"]\)?$")


def _inicia_paragrafo(anterior: str, linha: str, tipico: int) -> bool:
    """O OCR nem sempre separa parágrafos com linha em branco: o livro usa recuo.

    Abre parágrafo novo quando a linha é questão numerada, subquestão, abre aspas ou
    travessão, é título (caixa alta ou "Capítulo"), ou quando a anterior termina frase
    e é bem mais curta que a linha típica da página (última linha de parágrafo)."""
    if linha[:1].islower():
        return False
    if _ABRE_PARAGRAFO.match(linha) and _FIM_DE_FRASE.search(anterior):
        return True
    # "…no ano de / 1857. Depois…" não abre parágrafo: a questão numerada só conta
    # depois de frase terminada, como acima.
    if linha.isupper() or anterior.isupper():
        return True
    return bool(_FIM_DE_FRASE.search(anterior)) and len(anterior) < 0.8 * tipico


def como_texto(paragrafos: list[Paragrafo]) -> str:
    """Formato que a ingestão lê (parágrafos separados por linha em branco)."""
    return "\n\n".join(p.texto for p in paragrafos) + "\n"
