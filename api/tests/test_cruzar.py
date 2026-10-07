from centelha_api.pipeline.ingestao.cruzar import (
    como_markdown,
    comparar_textos,
    cruzar,
    main,
    palavras,
)
from centelha_api.pipeline.ingestao.estrutura import estruturar

A = """Livre premier

Chapitre premier — Dieu

Dieu et l’infini.

1. Qu’est-ce que Dieu ?

« Dieu est l’intelligence suprême, cause première de toutes choses. »

― Et l’infini ?

« Ce qui n’a ni commencement ni fin. »

2. Où peut-on trouver la preuve de l’existence de Dieu ?

« Dans un axiome que vous appliquez à vos sciences. »

Kardec commente ici les preuves."""

# Outra transcrição: apóstrofo reto, ligadura, um erro de OCR, um acento a menos, a
# questão 2 sem a resposta e uma questão 3 a mais. O subtítulo "Dieu et l'infini."
# entra noutro lugar da estrutura, o que não é diferença de texto.
B = """Livre premier

Chapitre premier — Dieu

Dieu et l'infini.

1. Qu'est-ce que Dieu ?

« Dieu est l'intelligence suprème, cause prernière de toutes choses. »

― Et l'infini ?

« Ce qui n'a ni commencement ni fin. »

2. Où peut-on trouver la preuve de l'existence de Dieu ?

« Dans un axiome que vous appliquez a vos sciences. »

Kardec commente ici les preuves.

3. Dieu est-il un être distinct ?

« Oui. »"""


def _cruzar():
    return cruzar(
        estruturar(A.split("\n\n"), "perguntas"), estruturar(B.split("\n\n"), "perguntas")
    )


def test_palavras_ignora_tipografia():
    assert palavras("L’œuvre, « l'âme » !") == ["L'oeuvre", "l'âme"]


def test_aponta_palavra_e_acento_no_trecho_certo():
    r = _cruzar()
    assert [(d.onde, d.a, d.b, d.so_acento) for d in r.diferencas] == [
        ("1 · resposta", "suprême", "suprème", True),
        (
            "1 · resposta",
            "l'intelligence suprême cause [première] de toutes choses",
            "[prernière]",
            False,
        ),
        ("2 · resposta", "à", "a", True),
        # A questão 3 só existe em B: entra como texto a mais depois do último trecho de A.
        ("2 · comentario", "ici les preuves [∅]", "[Dieu est-il un être distinct Oui]", False),
    ]
    assert (r.so_em_a, r.so_em_b) == ([], ["3"])


def test_mesma_transcricao_nao_tem_diferenca():
    capitulos = estruturar(A.split("\n\n"), "perguntas")
    r = cruzar(capitulos, capitulos)
    assert r.diferencas == []
    assert r.comparados > 0


def test_comparar_textos_mostra_o_contexto():
    [d] = comparar_textos("un deux trois quatre cinq six", "un deux trois QUATRO cinq six", "x")
    assert (d.a, d.b, d.so_acento) == ("un deux trois [quatre] cinq six", "[QUATRO]", False)


def test_relatorio_e_cli(tmp_path, capsys):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text(A, encoding="utf-8")
    b.write_text(B, encoding="utf-8")
    saida = tmp_path / "cruzamento.md"
    assert main([str(a), str(b), "--perfil", "perguntas", "--saida", str(saida)]) == 0
    texto = saida.read_text(encoding="utf-8")
    assert "Questões só em B: 3" in texto
    assert "| 1 · resposta |" in texto
    assert "com diferença" in capsys.readouterr().out
    assert como_markdown(_cruzar(), "a", "b").startswith("# Cruzamento: a × b")
