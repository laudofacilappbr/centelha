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
