import pytest

from centelha_api.pipeline.normalizacao.numeros_pt_br import (
    cardinal,
    int_para_romano,
    ordinal,
    romano_para_int,
)
from centelha_api.pipeline.normalizacao.pt_br import normalizar


@pytest.mark.parametrize(
    ("n", "esperado"),
    [
        (0, "zero"),
        (14, "catorze"),
        (21, "vinte e um"),
        (100, "cem"),
        (101, "cento e um"),
        (150, "cento e cinquenta"),
        (1000, "mil"),
        (1019, "mil e dezenove"),
        (1100, "mil e cem"),
        (1300, "mil e trezentos"),
        (1857, "mil oitocentos e cinquenta e sete"),
        (1864, "mil oitocentos e sessenta e quatro"),
        (2000, "dois mil"),
        (2026, "dois mil e vinte e seis"),
        (21000, "vinte e um mil"),
        (1_000_000, "um milhão"),
        (2_500_000, "dois milhões e quinhentos mil"),
    ],
)
def test_cardinal(n, esperado):
    assert cardinal(n) == esperado


@pytest.mark.parametrize(
    ("n", "fem", "esperado"),
    [
        (1, False, "primeiro"),
        (2, True, "segunda"),
        (10, False, "décimo"),
        (17, False, "décimo sétimo"),
        (28, True, "vigésima oitava"),
        (100, False, "centésimo"),
    ],
)
def test_ordinal(n, fem, esperado):
    assert ordinal(n, feminino=fem) == esperado


def test_romanos_ida_e_volta():
    for n in range(1, 400):
        assert romano_para_int(int_para_romano(n)) == n
    with pytest.raises(ValueError):
        romano_para_int("IIII")


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Capítulo XVII", "Capítulo dezessete"),
        ("CAPÍTULO V — Bem-aventurados os aflitos", "CAPÍTULO cinco — Bem-aventurados os aflitos"),
        ("ver cap. XXVIII", "ver capítulo vinte e oito"),
        ("Livro II", "Livro segundo"),
        ("Parte Primeira", "Parte Primeira"),
        ("Parte III", "Parte terceira"),
        ("no século XIX", "no século dezenove"),
        ("Questão 88.", "Questão oitenta e oito."),
        ("ver q. 150", "ver questão cento e cinquenta"),
        ("n.º 3", "número três"),
        ("§ 4", "parágrafo quatro"),
        ("S. Luís e S. Agostinho", "São Luís e São Agostinho"),
        ("o Sr. Allan Kardec", "o senhor Allan Kardec"),
        ("em 18 de abril de 1857", "em dezoito de abril de mil oitocentos e cinquenta e sete"),
        ("as 1.019 questões", "as mil e dezenove questões"),
        ("1º de janeiro", "primeiro de janeiro"),
        ("a 2ª edição", "a segunda edição"),
        ("Deus, Espíritos, etc.", "Deus, Espíritos, etcétera"),
        ("(N. do T.)", "(nota do tradutor)"),
    ],
)
def test_normalizar(entrada, esperado):
    assert normalizar(entrada) == esperado


def test_nao_mexe_em_romano_sem_contexto():
    # "I" sozinho é pronome em outras línguas e inicial em nomes; sem contexto, fica.
    assert normalizar("Allan Kardec, cap. I") == "Allan Kardec, capítulo um"
    assert normalizar("Luís XIV e o Eu") == "Luís XIV e o Eu"


def test_preserva_decimais_e_espacos():
    assert normalizar("  Deus  é   amor ") == "Deus é amor"
    assert normalizar("3,5 metros") == "3,5 metros"
