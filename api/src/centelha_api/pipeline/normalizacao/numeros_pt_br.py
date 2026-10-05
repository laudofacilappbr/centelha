"""Números por extenso em português do Brasil."""

_UNIDADES = [
    "zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
    "dez", "onze", "doze", "treze", "catorze", "quinze", "dezesseis", "dezessete",
    "dezoito", "dezenove",
]  # fmt: skip
_DEZENAS = [
    "", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta",
    "noventa",
]  # fmt: skip
_CENTENAS = [
    "", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos",
    "setecentos", "oitocentos", "novecentos",
]  # fmt: skip

_ORD_UNIDADES = [
    "", "primeiro", "segundo", "terceiro", "quarto", "quinto", "sexto", "sétimo", "oitavo",
    "nono",
]  # fmt: skip
_ORD_DEZENAS = [
    "", "décimo", "vigésimo", "trigésimo", "quadragésimo", "quinquagésimo", "sexagésimo",
    "septuagésimo", "octogésimo", "nonagésimo",
]  # fmt: skip
_ORD_CENTENAS = [
    "", "centésimo", "ducentésimo", "trecentésimo", "quadringentésimo", "quingentésimo",
    "sexcentésimo", "septingentésimo", "octingentésimo", "nongentésimo",
]  # fmt: skip


def _ate_mil(n: int) -> str:
    if n < 20:
        return _UNIDADES[n]
    if n < 100:
        d, u = divmod(n, 10)
        return _DEZENAS[d] + (f" e {_UNIDADES[u]}" if u else "")
    if n == 100:
        return "cem"
    c, resto = divmod(n, 100)
    return _CENTENAS[c] + (f" e {_ate_mil(resto)}" if resto else "")


def _junta(maior: str, resto: int) -> str:
    # "mil e dezenove", "mil e trezentos", mas "mil oitocentos e cinquenta e sete".
    if resto == 0:
        return maior
    sep = " e " if resto < 100 or resto % 100 == 0 else " "
    return maior + sep + cardinal(resto)


def cardinal(n: int) -> str:
    if n < 0:
        return "menos " + cardinal(-n)
    if n < 1000:
        return _ate_mil(n)
    if n < 1_000_000:
        milhares, resto = divmod(n, 1000)
        maior = "mil" if milhares == 1 else f"{_ate_mil(milhares)} mil"
        return _junta(maior, resto)
    if n < 1_000_000_000:
        milhoes, resto = divmod(n, 1_000_000)
        maior = "um milhão" if milhoes == 1 else f"{cardinal(milhoes)} milhões"
        return _junta(maior, resto)
    raise ValueError(f"número grande demais: {n}")


def ordinal(n: int, feminino: bool = False) -> str:
    if not 1 <= n < 1000:
        raise ValueError(f"ordinal fora do intervalo: {n}")
    c, resto = divmod(n, 100)
    d, u = divmod(resto, 10)
    partes = [p for p in (_ORD_CENTENAS[c], _ORD_DEZENAS[d], _ORD_UNIDADES[u]) if p]
    texto = " ".join(partes)
    if feminino:
        texto = " ".join(p[:-1] + "a" for p in partes)
    return texto


_ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def romano_para_int(romano: str) -> int:
    total = 0
    anterior = 0
    for letra in reversed(romano.upper()):
        valor = _ROMANOS[letra]
        if valor < anterior:
            total -= valor
        else:
            total += valor
            anterior = valor
    if int_para_romano(total) != romano.upper():
        raise ValueError(f"romano inválido: {romano}")
    return total


def int_para_romano(n: int) -> str:
    tabela = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
        (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]  # fmt: skip
    saida = []
    for valor, simbolo in tabela:
        q, n = divmod(n, valor)
        saida.append(simbolo * q)
    return "".join(saida)
