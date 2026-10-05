"""Normalização de texto pt-BR antes da síntese de voz.

Cada idioma tem seu módulo, porque números e abreviações mudam de regra.
A ordem importa: romanos com contexto, abreviações, ordinais, depois números soltos.
"""

import re

from .numeros_pt_br import cardinal, ordinal, romano_para_int

_ROMANO = r"(?P<romano>[IVXLCDM]+)\b"

# Palavra que antecede o romano -> como ler: ordinal masculino, ordinal feminino ou cardinal.
# Nas obras de Kardec: "Livro Primeiro", "Parte Segunda", "Capítulo XVII", "século XIX".
_CONTEXTOS_ROMANOS: dict[str, str] = {
    "livro": "ord_m",
    "parte": "ord_f",
    "tomo": "ord_m",
    "capítulo": "card",
    "cap.": "card",
    "item": "card",
    "seção": "card",
    "século": "card",
    "volume": "card",
}

_RE_ROMANO_CONTEXTO = re.compile(
    r"\b(?P<palavra>" + "|".join(re.escape(p) for p in _CONTEXTOS_ROMANOS) + r")\s+" + _ROMANO,
    re.IGNORECASE,
)

# Abreviações comuns nas traduções do século XIX e no aparato editorial.
_ABREVIACOES: list[tuple[str, str]] = [
    (r"\bcap\.(?=\s)", "capítulo"),
    (r"\bcaps\.(?=\s)", "capítulos"),
    (r"\bq\.(?=\s*\d)", "questão"),
    (r"\bn\.?\s?[ºo°]\.?(?=\s*\d)", "número"),
    (r"§§\s*", "parágrafos "),
    (r"§\s*", "parágrafo "),
    (r"\bS\.(?=\s+[A-ZÁÉÍÓÚ])", "São"),
    (r"\bSr\.", "senhor"),
    (r"\bSra\.", "senhora"),
    (r"\bSrs\.", "senhores"),
    (r"\bDr\.", "doutor"),
    (r"\bV\.\s?Ex\.ª", "Vossa Excelência"),
    (r"\betc\.", "etcétera"),
    (r"\bp\.\s?ex\.", "por exemplo"),
    (r"\bpág\.(?=\s*\d)", "página"),
    (r"\bvol\.(?=\s*\d)", "volume"),
    (r"\bN\.\s?do\s?T\.", "nota do tradutor"),
    (r"\bN\.\s?da\s?E\.", "nota da editora"),
]
_RE_ABREVIACOES = [(re.compile(p), s) for p, s in _ABREVIACOES]

_RE_ORDINAL = re.compile(r"\b(?P<n>\d{1,3})\s?(?P<g>[ºª°])")
# Números com ponto de milhar ("1.019") ou simples.
_RE_NUMERO = re.compile(r"(?<![\d.,])(?P<n>\d{1,3}(?:\.\d{3})+|\d+)(?![\d,]|\.\d)")
_RE_ESPACOS = re.compile(r"[ \t]+")


def _romano_com_contexto(m: re.Match[str]) -> str:
    palavra = m.group("palavra")
    try:
        n = romano_para_int(m.group("romano"))
    except (KeyError, ValueError):
        return m.group(0)
    modo = _CONTEXTOS_ROMANOS[palavra.lower()]
    if palavra.lower() == "cap.":
        palavra = "capítulo"
    if modo == "ord_m":
        lido = ordinal(n)
    elif modo == "ord_f":
        lido = ordinal(n, feminino=True)
    else:
        lido = cardinal(n)
    return f"{palavra} {lido}"


def _ordinal(m: re.Match[str]) -> str:
    return ordinal(int(m.group("n")), feminino=m.group("g") == "ª")


def _numero(m: re.Match[str]) -> str:
    return cardinal(int(m.group("n").replace(".", "")))


def normalizar(texto: str) -> str:
    texto = _RE_ROMANO_CONTEXTO.sub(_romano_com_contexto, texto)
    for padrao, substituto in _RE_ABREVIACOES:
        texto = padrao.sub(substituto, texto)
    texto = _RE_ORDINAL.sub(_ordinal, texto)
    texto = _RE_NUMERO.sub(_numero, texto)
    return _RE_ESPACOS.sub(" ", texto).strip()
