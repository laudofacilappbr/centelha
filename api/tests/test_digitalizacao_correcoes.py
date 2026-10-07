"""Correções da revisão em arquivo versionado (#45).

O que importa: refazer o OCR ou a limpeza não pode perder a revisão em silêncio. Por
isso cada correção que não se aplica mais é erro, e o texto.txt não é gravado."""

import pytest

from centelha_api.pipeline.digitalizacao import cli
from centelha_api.pipeline.digitalizacao.correcoes import ErroCorrecao, aplicar, ler
from centelha_api.pipeline.digitalizacao.limpeza import Paragrafo
from centelha_api.pipeline.digitalizacao.revisao import diferencas

PARAGRAFOS = [
    Paragrafo(339, "Fin du chapitre."),
    Paragrafo(340, "CHAPITRE XXVIIT"),
    Paragrafo(340, "Les Esprits ont toujours dit : La forme n'est rien, la"),
    Paragrafo(341, "pensée est tout. Priez chacun selon vos convictions."),
]


def test_troca_e_juncao_na_pagina_indicada():
    correcoes = ler(
        """
        # Évangile 1866
        p. 340: CHAPITRE XXVIIT => CHAPITRE XXVIII
        p. 341: juntar: pensée est tout
        """
    )
    assert aplicar(PARAGRAFOS, correcoes) == [
        Paragrafo(339, "Fin du chapitre."),
        Paragrafo(340, "CHAPITRE XXVIII"),
        Paragrafo(
            340,
            "Les Esprits ont toujours dit : La forme n'est rien, la pensée est tout. "
            "Priez chacun selon vos convictions.",
        ),
    ]


def test_juncao_usa_o_texto_ja_corrigido():
    """Quem revisa escreve o 'juntar:' olhando o texto corrigido, não o OCR cru."""
    paragrafos = [Paragrafo(1, "Il dit"), Paragrafo(2, "qne tout passe.")]
    correcoes = ler("p. 2: juntar: que tout\np. 2: qne => que")
    assert aplicar(paragrafos, correcoes) == [Paragrafo(1, "Il dit que tout passe.")]


@pytest.mark.parametrize(
    ("linha", "motivo"),
    [
        ("p. 341: CHAPITRE XXVIIT => CHAPITRE XXVIII", "aparece 0 vez(es)"),  # página errada
        ("p. 340: es => is", "aparece 2 vez(es)"),  # ambíguo ("Les", "est"): pede trecho maior
        ("p. 341: juntar: Les Esprits ont", "0 parágrafo(s)"),  # está na 340
        ("p. 339: juntar: Fin du", "não há parágrafo antes"),
    ],
)
def test_correcao_que_nao_se_aplica_e_erro(linha, motivo):
    with pytest.raises(ErroCorrecao, match=motivo.replace("(", r"\(").replace(")", r"\)")):
        aplicar(PARAGRAFOS, ler(linha))


def test_todas_as_falhas_aparecem_juntas():
    with pytest.raises(ErroCorrecao) as e:
        aplicar(PARAGRAFOS, ler("p. 1: x => y\np. 2: z => w"))
    assert "linha 1" in str(e.value) and "linha 2" in str(e.value)


@pytest.mark.parametrize(
    "linha",
    ["340: a => b", "p. 340: a => b => c", "p. 340: sem seta", "p. 340: a => a", "p. 3: juntar:"],
)
def test_linha_mal_escrita_e_recusada(linha):
    with pytest.raises(ErroCorrecao, match="linha 1"):
        ler(linha)


def test_cli_aplica_correcoes_e_nao_grava_quando_alguma_falha(tmp_path, capsys):
    paginas = tmp_path / "ese.paginas.txt"
    paginas.write_text(
        "CHAPITRE XXVIIT\n\nPriez chacun selon vos convictions.\n\fAutre page.\n",
        encoding="utf-8",
    )
    certas = tmp_path / "certas.txt"
    certas.write_text("p. 1: XXVIIT => XXVIII\n", encoding="utf-8")
    saida = tmp_path / "saida"
    args = ["processar", str(paginas), "--saida", str(saida), "--idioma", "fra", "--correcoes"]
    assert cli.main([*args, str(certas)]) == 0
    texto = (saida / "texto.txt").read_text(encoding="utf-8")
    assert "CHAPITRE XXVIII\n" in texto and "XXVIIT" not in texto

    velhas = tmp_path / "velhas.txt"
    velhas.write_text("p. 2: XXVIIT => XXVIII\n", encoding="utf-8")
    nova = tmp_path / "nova"
    assert cli.main([*args[:3], str(nova), *args[4:], str(velhas)]) == 1
    assert not (nova / "texto.txt").exists()
    assert "linha 1 (p. 2: XXVIIT => XXVIII)" in capsys.readouterr().err


def test_diferencas_ignoram_apostrofo_e_hifenizacao_da_referencia():
    """No Évangile, 204 das 500 diferenças eram só ’ contra ' (#45)."""
    paragrafos = [Paragrafo(8, "L’enfer et les maximes morales d’après l’Évangile.")]
    ref = "L'enfer et les maximes mo- rales d'après l'Évangile."
    assert diferencas(paragrafos, ref) == []


def test_diferencas_ignoram_cabecalho_corrido_da_referencia_mas_nao_titulo_unico():
    """O texto do archive.org não separa páginas: o cabeçalho corrido fica no meio."""
    paragrafos = [Paragrafo(80, "CHAPITRE V"), Paragrafo(80, "Heureux ceux qu’ils consolent, car")]
    ref = (
        "CHAPITRE V\n"
        "BIENHEUREUX  LES  AFFLIGÉS.  77\nHeureux ceux\nBIENHEUREUX LES AFFLIGÉS. 79\n"
        "qu 'ils consolent\nBIENHEUREUX   LES  AFFLIGÉS.  81\ncar"
    )
    assert diferencas(paragrafos, ref) == []


def test_apagar_cabecalho_e_juntar_a_continuacao_ao_paragrafo_de_antes():
    """Cabeçalho com número mal lido ("96 CHAPITRE III.") ficava entre os dois pedaços
    do parágrafo. Juntar sem apagar uniria o texto ao cabeçalho."""
    paragrafos = [
        Paragrafo(72, "Au fond de l'intelligence gît, latente,"),
        Paragrafo(72, "96 CHAPITRE III."),
        Paragrafo(72, "la vague intuition d'un Être suprême."),
    ]
    correcoes = ler(
        "p. 72: juntar: la vague intuition\np. 72: apagar: 36 CHAPITRE\np. 72: 96 CHAP => 36 CHAP"
    )
    assert aplicar(paragrafos, correcoes) == [
        Paragrafo(
            72, "Au fond de l'intelligence gît, latente, la vague intuition d'un Être suprême."
        )
    ]


def test_apagar_que_nao_acha_o_paragrafo_e_erro():
    with pytest.raises(ErroCorrecao, match="0 parágrafo"):
        aplicar(PARAGRAFOS, ler("p. 340: apagar: 96 CHAPITRE"))
    with pytest.raises(ErroCorrecao, match="linha 1"):
        ler("p. 3: apagar:")


def test_juntar_palavra_partida_na_virada_tira_o_hifen():
    paragrafos = [Paragrafo(28, "le parti-"), Paragrafo(28, "culier, et ils adoptèrent")]
    assert aplicar(paragrafos, ler("p. 28: juntar: culier")) == [
        Paragrafo(28, "le particulier, et ils adoptèrent")
    ]
