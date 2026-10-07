from pathlib import Path

import pytest

from centelha_api.pipeline.digitalizacao import cli, ocr
from centelha_api.pipeline.digitalizacao.limpeza import Paragrafo, como_texto, limpar_paginas
from centelha_api.pipeline.digitalizacao.ortografia import a_conferir, atualizar
from centelha_api.pipeline.digitalizacao.revisao import como_markdown, diferencas, revisar


@pytest.mark.parametrize(
    ("antes", "depois"),
    [
        ("Êle disse sôbre a côr dêste govêrno.", "Ele disse sobre a cor deste governo."),
        (
            "Se fôsse assim, aquêle têrmo seria um êrro.",
            "Se fosse assim, aquele termo seria um erro.",
        ),
        ("sòmente e fàcilmente", "somente e facilmente"),
        (
            "Vai à casa e às aulas; àquele homem, àquilo.",
            "Vai à casa e às aulas; àquele homem, àquilo.",
        ),
        ("freqüente, agüentar, tranqüilo", "frequente, aguentar, tranquilo"),
        ("Freqüentemente, o Sr. Müller", "Frequentemente, o Sr. Müller"),
        (
            "a idéia, as platéias, heróico, jóia, Européia",
            "a ideia, as plateias, heroico, joia, Europeia",
        ),
        ("os papéis, os heróis, anéis, dói", "os papéis, os heróis, anéis, dói"),
        ("crêem, lêem, vêem; o vôo e o enjôo", "creem, leem, veem; o voo e o enjoo"),
        (
            "Você pôde pôr três coisas; êles têm e vêm.",
            "Você pôde pôr três coisas; eles têm e vêm.",
        ),
        ("ÊLE", "ELE"),
    ],
)
def test_atualizar_grafia(antes, depois):
    assert atualizar(antes)[0] == depois


def test_trocas_registram_regra():
    _, trocas = atualizar("Êle teve a idéia.")
    assert [(t.antes, t.depois) for t in trocas] == [("Êle", "Ele"), ("idéia", "ideia")]
    assert trocas[0].regra.startswith("acento diferencial")


def test_circunflexo_fora_das_listas_vai_para_conferir():
    assert a_conferir("A côrte viu o fenômeno; você e três ciências; pôde.") == ["côrte"]


PAGINAS = "\f".join(
    [
        "O LIVRO DOS ESPÍRITOS\n\nCAPÍTULO I\n\nDE DEUS\n\n1. Que é Deus?\n\n"
        "“Deus é a inteligência su-\nprema, causa primária de todas as\n\n7",
        "O LIVRO DOS ESPÍRITOS 8\n\ncoisas.”\n\n2. Que se deve entender por in-\nfinito?\n\n8",
        "O LIVRO DOS ESPÍRITOS\n\n“O que não tem começo nem fim.”\n\n3. Pergunta três?\n\n9",
        "O LIVRO DOS ESPÍRITOS 10\n\n“Resposta três.”\n\nComentário de Kardec.\n\n10",
    ]
)


def test_limpeza_tira_cabecalho_numero_e_junta_hifen_e_pagina():
    paragrafos = limpar_paginas(PAGINAS)
    textos = [p.texto for p in paragrafos]
    assert "O LIVRO DOS ESPÍRITOS" not in " ".join(textos)
    assert textos[:5] == [
        "CAPÍTULO I",
        "DE DEUS",
        "1. Que é Deus?",
        "“Deus é a inteligência suprema, causa primária de todas as coisas.”",
        "2. Que se deve entender por infinito?",
    ]
    # O parágrafo que atravessa a página guarda a página onde começa.
    assert paragrafos[3].pagina == 1
    assert paragrafos[4].pagina == 2
    assert not any(t.strip().isdigit() for t in textos)
    assert como_texto(paragrafos).count("\n\n") == len(paragrafos) - 1


def test_limpeza_de_ligaduras_e_espacos():
    [p] = limpar_paginas("A ﬁlosoﬁa   do  Espírito.")
    assert p.texto == "A filosofia do Espírito."


def test_paragrafos_sem_linha_em_branco_separados_por_recuo_e_tamanho():
    # Como o Tesseract devolve um livro com recuo: linhas seguidas, sem linha em branco.
    pagina = "\n".join(
        [
            "CAPÍTULO I",
            "DO PRIMEIRO TEMA",
            "1. Que é o primeiro assunto deste livro, e como se chega",
            "a ele?",
            "“É a ideia sobre a qual tudo se apoia; ele explica as causas",
            "e os efeitos, como se viu no ano de",
            "1857. Depois disso, ninguém mais duvidou do que foi dito ali",
            "pelos que estudaram.”",
            "Comentário do autor sobre a questão, longo o bastante para",
            "ocupar duas linhas inteiras da página.",
            "2. Segunda pergunta?",
        ]
    )
    textos = [p.texto for p in limpar_paginas(pagina)]
    assert textos == [
        "CAPÍTULO I",
        "DO PRIMEIRO TEMA",
        "1. Que é o primeiro assunto deste livro, e como se chega a ele?",
        "“É a ideia sobre a qual tudo se apoia; ele explica as causas e os efeitos, como se"
        " viu no ano de 1857. Depois disso, ninguém mais duvidou do que foi dito ali pelos"
        " que estudaram.”",
        "Comentário do autor sobre a questão, longo o bastante para ocupar duas linhas"
        " inteiras da página.",
        "2. Segunda pergunta?",
    ]


def test_revisao_aponta_trema_lido_como_ii():
    rel = revisar([Paragrafo(9, "de modo fregiiente e tranqiiilo, no século XII.")])
    achados = [(a.trecho, a.detalhe) for a in rel.achados if a.tipo == "trema lido como ii"]
    assert ("fregiiente", "talvez freguente (confira g/q na imagem)") in achados
    assert all("XII" not in t for t, _ in achados)


def test_revisao_aponta_palavra_rara_parecida_com_frequente_mas_nao_flexao():
    frase = "O homem estuda de modo frequente e os espíritos estudam o espírito. "
    paragrafos = [Paragrafo(1, frase * 5), Paragrafo(6, "Um caso fregiente e estudar.")]
    achados = [
        (a.pagina, a.trecho, a.detalhe)
        for a in revisar(paragrafos).achados
        if a.tipo == "parecida com palavra frequente"
    ]
    assert achados == [(6, "fregiente", "talvez frequente")]


def test_sometne_com_circunflexo_vai_para_conferir():
    assert a_conferir("sômente o fenômeno") == ["sômente"]


def test_revisao_aponta_suspeitas_com_pagina():
    paragrafos = [
        Paragrafo(3, "O homem c0m a alma; o homem e o homem e o homem."),
        Paragrafo(4, "continua aqui o hornem de antes €."),
        Paragrafo(5, "O 2º capítulo e a questão 88a."),
    ]
    rel = revisar(paragrafos)
    tipos = {(a.pagina, a.tipo, a.trecho) for a in rel.achados}
    assert (3, "dígito em palavra", "c0m") in tipos
    assert (4, "caractere estranho", "€") in tipos
    assert (4, "começa com minúscula", "continua aqui o hornem de antes €.") in tipos
    assert any(a.tipo == "rn/m" and a.trecho == "hornem" for a in rel.achados)
    # Ordinais e subquestões não são sujeira.
    assert not any(a.pagina == 5 for a in rel.achados)


def test_revisao_de_questoes_faltando_e_repetidas():
    paragrafos = [
        Paragrafo(1, t)
        for t in ["1. Pergunta?", "“Resposta.”", "2. Pergunta?", "“R.”", "2. De novo?", "“R.”"]
        + ["4. Pergunta?", "“R.”"]
    ]
    rel = revisar(paragrafos, perfil="perguntas")
    assert rel.questoes["questoes_faltando"] == [3]
    assert rel.questoes["questoes_repetidas"] == [2]
    md = como_markdown(rel, "teste")
    assert "Faltando: 3" in md and "Repetidas: 2" in md


def test_diferencas_contra_referencia_ignoram_acento_e_caixa():
    paragrafos = [Paragrafo(2, "Deus é a inteligencia suprema, causa prirnária de tudo.")]
    ref = "Deus é a Inteligência suprema, causa primária de todas as coisas."
    achados = diferencas(paragrafos, ref)
    trechos = [(a.trecho, a.detalhe) for a in achados]
    assert ("prirnária", "referência: primária") in trechos
    assert ("tudo", "referência: todas as coisas") in trechos
    assert all(a.pagina == 2 for a in achados)


def test_ocr_sem_tesseract_explica(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr.shutil, "which", lambda _: None)
    (tmp_path / "p1.png").write_bytes(b"x")
    with pytest.raises(ocr.ErroOCR, match="container de digitalização"):
        ocr.ocr(tmp_path)


def test_ocr_de_pdf_renderiza_cada_pagina(monkeypatch, tmp_path):
    import pymupdf

    pdf = tmp_path / "exemplar.pdf"
    doc = pymupdf.open()
    for n in range(3):
        doc.new_page().insert_text((72, 72), f"pagina {n}")
    doc.save(str(pdf))
    vistas: list[Path] = []

    def falso(imagem: Path, idioma: str) -> str:
        vistas.append(imagem)
        assert imagem.read_bytes().startswith(b"\x89PNG")
        return f"texto {len(vistas)}"

    monkeypatch.setattr(ocr, "_tesseract", falso)
    assert ocr.ocr(pdf, dpi=50) == "texto 1\ftexto 2\ftexto 3"
    assert len(vistas) == 3


def test_cli_processar_grava_texto_e_revisao(tmp_path, capsys):
    paginas = tmp_path / "le.paginas.txt"
    paginas.write_text(
        PAGINAS.replace("Que é Deus?", "Que é Deus? Êle é a idéia"), encoding="utf-8"
    )
    saida = tmp_path / "le"
    assert (
        cli.main(["processar", str(paginas), "--saida", str(saida), "--perfil", "perguntas"]) == 0
    )
    texto = (saida / "texto.txt").read_text(encoding="utf-8")
    assert "Ele é a ideia" in texto
    revisao = (saida / "revisao.md").read_text(encoding="utf-8")
    assert "# Revisão: le.paginas" in revisao
    assert "| Êle | Ele | acento diferencial (1971) | 1 |" in revisao
    assert "Total: 3 (de 1 a 3)" in revisao


def test_cli_em_frances_nao_atualiza_grafia_nem_procura_trema(tmp_path, monkeypatch):
    """Originais de Kardec (#45): "Êle" e "ii" são regras do português de 1943. Em
    francês, "même" e "fête" ficam como estão, e o OCR usa o modelo fra."""
    pedidos: list[str] = []

    def falso(imagem: Path, idioma: str) -> str:
        pedidos.append(idioma)
        return "Il en est de même pour la fête; ii n'y a rien.\n\nSecond paragraphe."

    monkeypatch.setattr(ocr, "_tesseract", falso)
    pasta = tmp_path / "paginas"
    pasta.mkdir()
    (pasta / "001.png").write_bytes(b"\x89PNG")
    saida = tmp_path / "ese-fr"
    assert cli.main(["tudo", str(pasta), "--saida", str(saida), "--idioma", "fra"]) == 0
    assert pedidos == ["fra"]
    assert "Il en est de même pour la fête" in (saida / "texto.txt").read_text(encoding="utf-8")
    revisao = (saida / "revisao.md").read_text(encoding="utf-8")
    assert "trema lido como ii" not in revisao


def test_idioma_fora_da_imagem_e_recusado(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(["ocr", str(tmp_path), "-o", str(tmp_path / "x.txt"), "--idioma", "deu"])


def test_limpeza_tira_ruido_da_margem_sem_perder_palavra():
    """O fac-símile da Library of Congress pega a borda da página vizinha: o Tesseract
    a lê como "|", "|}" ou "|n" na ponta da linha. Nenhum livro do acervo usa "|"."""
    pagina = (
        "Jésus indique la compensation |\n"
        "| qui attend ceux qui souffrent, et la |}\n"
        "résignation qui fait bénir la souffrance |n\n"
        "comme le prélude de la guérison, à|m la fin.\n"
    )
    [p] = limpar_paginas(pagina)
    assert p.texto == (
        "Jésus indique la compensation qui attend ceux qui souffrent, et la "
        "résignation qui fait bénir la souffrance comme le prélude de la guérison, "
        "à|m la fin."
    )
