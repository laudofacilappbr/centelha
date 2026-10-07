import pytest

from centelha_api.models import TipoSegmento
from centelha_api.pipeline.normalizacao.fr import normalizar
from centelha_api.pipeline.normalizacao.numeros_fr import cardinal, ordinal
from centelha_api.pipeline.pronuncia import SEED_FR, SEED_PT_BR, seed
from centelha_api.pipeline.tts.gerar import SegmentoParaVoz, Vozes, normalizador, pedido_para


@pytest.mark.parametrize(
    ("n", "esperado"),
    [
        (0, "zéro"),
        (16, "seize"),
        (17, "dix-sept"),
        (21, "vingt et un"),
        (22, "vingt-deux"),
        (70, "soixante-dix"),
        (71, "soixante et onze"),
        (77, "soixante-dix-sept"),
        (80, "quatre-vingts"),
        (81, "quatre-vingt-un"),
        (88, "quatre-vingt-huit"),
        (91, "quatre-vingt-onze"),
        (99, "quatre-vingt-dix-neuf"),
        (100, "cent"),
        (101, "cent un"),
        (200, "deux cents"),
        (250, "deux cent cinquante"),
        (1000, "mille"),
        (1019, "mille dix-neuf"),
        (1857, "mille huit cent cinquante-sept"),
        (80_000, "quatre-vingt mille"),
        (200_000, "deux cent mille"),
        (1_000_000, "un million"),
        (200_000_000, "deux cents millions"),
    ],
)
def test_cardinal(n, esperado):
    assert cardinal(n) == esperado


@pytest.mark.parametrize(
    ("n", "fem", "esperado"),
    [
        (1, False, "premier"),
        (1, True, "première"),
        (2, False, "deuxième"),
        (3, False, "troisième"),
        (4, False, "quatrième"),
        (5, False, "cinquième"),
        (9, False, "neuvième"),
        (11, False, "onzième"),
        (19, False, "dix-neuvième"),
        (21, False, "vingt et unième"),
        (80, False, "quatre-vingtième"),
        (200, False, "deux centième"),
        (1000, False, "millième"),
    ],
)
def test_ordinal(n, fem, esperado):
    assert ordinal(n, feminino=fem) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Chapitre XVII", "Chapitre dix-sept"),
        ("CHAPITRE I — Dieu", "CHAPITRE premier — Dieu"),
        ("voir chap. XXVIII", "voir chapitre vingt-huit"),
        ("Livre II", "Livre deux"),
        ("Partie I", "Partie première"),
        ("au XIXe siècle", "au dix-neuvième siècle"),
        ("le Ve siècle", "le cinquième siècle"),
        ("Napoléon Ier", "Napoléon premier"),
        ("Question 88.", "Question quatre-vingt-huit."),
        ("voir q. 150", "voir question cent cinquante"),
        ("n° 3", "numéro trois"),
        ("§ 4", "paragraphe quatre"),
        ("M. Allan Kardec", "Monsieur Allan Kardec"),
        ("Mme Dupont et Mlle Martin", "Madame Dupont et Mademoiselle Martin"),
        ("St Louis et Ste Thérèse", "Saint Louis et Sainte Thérèse"),
        ("le 18 avril 1857", "le dix-huit avril mille huit cent cinquante-sept"),
        ("les 1\u00a0019 questions", "les mille dix-neuf questions"),
        ("les 1.019 questions", "les mille dix-neuf questions"),
        ("en 1857, puis", "en mille huit cent cinquante-sept, puis"),
        ("le 1er janvier", "le premier janvier"),
        ("la 1re édition", "la première édition"),
        ("la 2e édition", "la deuxième édition"),
        ("Dieu, Esprits, etc.", "Dieu, Esprits, et cetera"),
        ("c.-à-d. l'âme", "c'est-à-dire l'âme"),
        ("(N. du T.)", "(note du traducteur)"),
    ],
)
def test_normalizar(entrada, esperado):
    assert normalizar(entrada) == esperado


def test_palavras_curtas_nao_viram_romano():
    # "Le", "De", "Ce", "Me" são romano + "e" na forma, mas são palavras.
    frase = "Le monde. De l'âme. Ce qui est. Me voici. Louis XIV"
    assert normalizar(frase) == frase


def test_espaco_comum_nao_junta_numeros():
    assert normalizar("questions 12 345") == "questions douze trois cent quarante-cinq"
    assert normalizar("3,5 mètres") == "3,5 mètres"


def test_normalizador_por_idioma():
    assert normalizador("fr")("2e") == "deuxième"
    assert normalizador("fr-FR")("2e") == "deuxième"
    assert normalizador("pt-BR")("2ª") == "segunda"
    with pytest.raises(ValueError):
        normalizador("pt-PT")
    with pytest.raises(ValueError):
        normalizador("es")


def test_seed_por_idioma():
    assert seed("fr-FR") is SEED_FR
    assert seed("pt-BR") is SEED_PT_BR
    assert seed("de") == []


def test_pedido_em_frances():
    segmento = SegmentoParaVoz(
        1, TipoSegmento.PERGUNTA, "88. Que pensait Hahnemann au XIXe siècle ?"
    )
    p = pedido_para(segmento, Vozes("fr-FR-HenriNeural"), SEED_FR, "fr-FR")
    assert p.idioma == "fr-FR"
    assert p.texto == "quatre-vingt-huit. Que pensait Ânemane au dix-neuvième siècle ?"
    assert '<sub alias="Ânemane">Hahnemann</sub>' in p.ssml


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (
            "(Saint Matthieu, ch. v, v. 17, 18.)",
            "(Saint Matthieu, chapitre cinq, versets dix-sept, dix-huit.)",
        ),
        (
            "(Saint Jean, ch.xiv, v.15, 16.)",
            "(Saint Jean, chapitre quatorze, versets quinze, seize.)",
        ),
        ("(Saint Luc, ch. vi, v. 7,8.)", "(Saint Luc, chapitre six, versets sept, huit.)"),
        ("(Ch. x, v. 3-5.)", "(chapitre dix, versets trois à cinq.)"),
        ("(Ch. iv, v. 2.)", "(chapitre quatre, verset deux.)"),
        ("(Ch. xii, nos 40,41.)", "(chapitre douze, numéros quarante, quarante et un.)"),
        ("(Ch. xii, n°s 4 et 5.)", "(chapitre douze, numéros quatre et cinq.)"),
        ("(Voy. Introduction, paragr. iv.)", "(Voyez Introduction, paragraphe quatre.)"),
    ],
)
def test_citacoes_de_kardec(entrada, esperado):
    """No Évangile de 1866, 279 citações ficavam com "ch." e "v." literais, e "7,8" seria
    decimal ("sept virgule huit") para a voz."""
    assert normalizar(entrada) == esperado


def test_romano_que_abre_o_paragrafo_e_numero_de_secao():
    assert normalizar("IV. L'âme impure, en cet état.") == "Quatre. L'âme impure, en cet état."
    assert normalizar("XVII. La vertu ne peut pas s'enseigner.").startswith("Dix-sept. La vertu")
    # Romano inválido (erro de OCR) e romano no meio da frase ficam.
    assert normalizar("IL. Tant que nous aurons") == "IL. Tant que nous aurons"
    assert normalizar("le roi Louis XIV. Puis") == "le roi Louis XIV. Puis"


def test_nos_sem_lista_e_possessivo_e_decimal_fora_de_citacao_fica():
    assert normalizar("nos 12 apôtres") == "nos douze apôtres"
    assert normalizar("3,5 mètres") == "3,5 mètres"


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("(Ciel et Enfer, ch. 11.)", "(Ciel et Enfer, chapitre onze.)"),
        ("(Saint Matthieu, v. de 13 à 17.)", "(Saint Matthieu, versets de treize à dix-sept.)"),
        ("(Voy. Introduction; art. Publicains.)", "(Voyez Introduction; article Publicains.)"),
        ("C'est un art. Il faut", "C'est un art. Il faut"),
    ],
)
def test_remissoes(entrada, esperado):
    assert normalizar(entrada) == esperado
