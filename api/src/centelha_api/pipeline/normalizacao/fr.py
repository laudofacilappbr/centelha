"""Normalização de texto em francês antes da síntese de voz (originais de Kardec).

Mesma ordem do pt-BR: romanos com contexto, abreviações, ordinais, números soltos.
Diferenças que pesam: em francês "Chapitre II" se lê "chapitre deux" (só o I vira
"premier"), e o ordinal vem marcado no próprio número ("XIXe siècle", "1er", "2e").
"""

import re

from .numeros_fr import cardinal, ordinal
from .numeros_pt_br import romano_para_int

_ROMANO = r"(?P<romano>[IVXLCDM]+)\b"

# Palavra que antecede o romano -> gênero, para o caso do 1 ("Partie première").
_CONTEXTOS_ROMANOS: dict[str, bool] = {
    "livre": False,
    "chapitre": False,
    "chap.": False,
    "tome": False,
    "volume": False,
    "article": False,
    "partie": True,
    "section": True,
}

_RE_ROMANO_CONTEXTO = re.compile(
    r"\b(?P<palavra>" + "|".join(re.escape(p) for p in _CONTEXTOS_ROMANOS) + r")\s+" + _ROMANO,
    re.IGNORECASE,
)
# "XIXe siècle", "Ier", "IIe": romano com marca de ordinal. Uma letra só exige contexto,
# senão "Le", "De" e "Ce" no começo da frase viram ordinais.
_RE_ROMANO_ORDINAL = re.compile(
    r"\b(?P<romano>[IVXLCDM]{2,}|I(?=er|re|ère)|[IVXLCDM](?=(?:e|ème)\s+siècle))"
    r"(?P<g>er|re|ère|e|ème)\b"
)

_ABREVIACOES: list[tuple[str, str]] = [
    (r"\bchap\.(?=\s)", "chapitre"),
    (r"\bq\.(?=\s*\d)", "question"),
    (r"\b[Nn][°o]\.?(?=\s*\d)", "numéro"),
    (r"§§\s*", "paragraphes "),
    (r"§\s*", "paragraphe "),
    (r"\bMM\.(?=\s+[A-ZÀ-Ý])", "Messieurs"),
    (r"\bM\.(?=\s+[A-ZÀ-Ý])", "Monsieur"),
    (r"\bMmes\b\.?", "Mesdames"),
    (r"\bMme\b\.?", "Madame"),
    (r"\bMlles\b\.?", "Mesdemoiselles"),
    (r"\bMlle\b\.?", "Mademoiselle"),
    (r"\bMgr\b\.?", "Monseigneur"),
    (r"\bDr\b\.?(?=\s+[A-ZÀ-Ý])", "docteur"),
    (r"\bSte(?=[\s-][A-ZÀ-Ý])", "Sainte"),
    (r"\bSt(?=[\s-][A-ZÀ-Ý])", "Saint"),
    (r"\bc\.-à-d\.", "c'est-à-dire"),
    (r"\betc\.", "et cetera"),
    (r"\bp\.\s?ex\.", "par exemple"),
    (r"\bp\.(?=\s*\d)", "page"),
    (r"\bvol\.(?=\s*\d)", "volume"),
    (r"\bN\.\s?du\s?T\.", "note du traducteur"),
]
_RE_ABREVIACOES = [(re.compile(p), s) for p, s in _ABREVIACOES]

_RE_ORDINAL = re.compile(r"\b(?P<n>\d{1,4})(?P<g>er|re|ère|e|ème|è)\b")
# Milhar com ponto, espaço fino ou não separável ("1 019"); espaço comum não, para não
# juntar dois números vizinhos.
_SEP_MILHAR = "[.\u00a0\u202f]"
_RE_NUMERO = re.compile(
    rf"(?<![\d.,])(?P<n>\d{{1,3}}(?:{_SEP_MILHAR}\d{{3}})+|\d+)(?!\d|,\d|{_SEP_MILHAR}\d)"
)
_RE_ESPACOS = re.compile(r"[ \t]+")


def _romano_com_contexto(m: re.Match[str]) -> str:
    palavra = m.group("palavra")
    try:
        n = romano_para_int(m.group("romano"))
    except (KeyError, ValueError):
        return m.group(0)
    feminino = _CONTEXTOS_ROMANOS[palavra.lower()]
    if palavra.lower() == "chap.":
        palavra = "chapitre"
    lido = ordinal(n, feminino) if n == 1 else cardinal(n)
    return f"{palavra} {lido}"


def _romano_ordinal(m: re.Match[str]) -> str:
    try:
        n = romano_para_int(m.group("romano"))
    except (KeyError, ValueError):
        return m.group(0)
    return ordinal(n, feminino=m.group("g") in ("re", "ère"))


def _ordinal(m: re.Match[str]) -> str:
    return ordinal(int(m.group("n")), feminino=m.group("g") in ("re", "ère"))


def _numero(m: re.Match[str]) -> str:
    return cardinal(int(re.sub(_SEP_MILHAR, "", m.group("n"))))


def normalizar(texto: str) -> str:
    texto = _RE_ROMANO_CONTEXTO.sub(_romano_com_contexto, texto)
    texto = _RE_ROMANO_ORDINAL.sub(_romano_ordinal, texto)
    for padrao, substituto in _RE_ABREVIACOES:
        texto = padrao.sub(substituto, texto)
    texto = _RE_ORDINAL.sub(_ordinal, texto)
    texto = _RE_NUMERO.sub(_numero, texto)
    return _RE_ESPACOS.sub(" ", texto).strip()
