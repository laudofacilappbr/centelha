"""Números por extenso em francês (grafia tradicional, hífen só abaixo de cem).

Romanos são os mesmos do pt-BR: use numeros_pt_br.romano_para_int.
"""

_UNIDADES = [
    "zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
    "onze", "douze", "treize", "quatorze", "quinze", "seize", "dix-sept", "dix-huit",
    "dix-neuf",
]  # fmt: skip
_DEZENAS = ["", "", "vingt", "trente", "quarante", "cinquante", "soixante"]


def _ate_cem(n: int, final: bool = True) -> str:
    if n < 20:
        return _UNIDADES[n]
    d, u = divmod(n, 10)
    if d in (7, 9):
        # 70–79 e 90–99 contam a partir de dez: soixante-dix, quatre-vingt-onze.
        base = "soixante" if d == 7 else "quatre-vingt"
        if n == 71:
            return "soixante et onze"
        return f"{base}-{_UNIDADES[10 + u]}"
    if d == 8:
        # "quatre-vingts" só no fim do número: "quatre-vingt mille", "quatre-vingt-un".
        return f"quatre-vingt-{_UNIDADES[u]}" if u else "quatre-vingt" + ("s" if final else "")
    if u == 0:
        return _DEZENAS[d]
    if u == 1:
        return f"{_DEZENAS[d]} et un"
    return f"{_DEZENAS[d]}-{_UNIDADES[u]}"


def _ate_mil(n: int, final: bool = True) -> str:
    c, resto = divmod(n, 100)
    if c == 0:
        return _ate_cem(resto, final)
    centena = "cent" if c == 1 else f"{_UNIDADES[c]} cent"
    if resto:
        return f"{centena} {_ate_cem(resto, final)}"
    # "deux cents", mas "deux cent mille": o "s" cai antes de "mille".
    return centena + ("s" if c > 1 and final else "")


def cardinal(n: int) -> str:
    if n < 0:
        return "moins " + cardinal(-n)
    if n < 1000:
        return _ate_mil(n)
    if n < 1_000_000:
        milhares, resto = divmod(n, 1000)
        maior = "mille" if milhares == 1 else f"{_ate_mil(milhares, final=False)} mille"
        return f"{maior} {_ate_mil(resto)}" if resto else maior
    if n < 1_000_000_000:
        milhoes, resto = divmod(n, 1_000_000)
        # "million" é substantivo: "deux cents millions" mantém o "s".
        maior = f"{cardinal(milhoes)} million" + ("s" if milhoes > 1 else "")
        return f"{maior} {cardinal(resto)}" if resto else maior
    raise ValueError(f"número grande demais: {n}")


def ordinal(n: int, feminino: bool = False) -> str:
    if n < 1:
        raise ValueError(f"ordinal fora do intervalo: {n}")
    if n == 1:
        return "première" if feminino else "premier"
    texto = cardinal(n)
    # Só a última palavra recebe o sufixo: "vingt et unième", "deux centième".
    corte = max(texto.rfind(" "), texto.rfind("-")) + 1
    cabeca, ultima = texto[:corte], texto[corte:]
    if ultima == "cinq":
        ultima = "cinqu"
    elif ultima == "neuf":
        ultima = "neuv"
    elif ultima.endswith(("e", "s")) and ultima not in ("six", "trois"):
        ultima = ultima[:-1]
    return f"{cabeca}{ultima}ième"
