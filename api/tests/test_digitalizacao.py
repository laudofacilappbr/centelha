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
    # O "2." repetido está onde falta a 3: vira a 3, e o relatório aponta as duas coisas.
    assert rel.questoes["questoes_faltando"] == []
    assert rel.questoes["questoes_inferidas"] == {3: "impresso 2"}
    assert rel.questoes["questoes_repetidas"] == [2]
    md = como_markdown(rel, "teste")
    assert "Repetidas: 2" in md and "conferir no exemplar: 3 (impresso 2)" in md

    sem_vizinha = [Paragrafo(1, t) for t in ["1. P?", "“R.”", "4. P?", "“R.”"]]
    assert revisar(sem_vizinha, perfil="perguntas").questoes["questoes_faltando"] == [2, 3]


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


def test_parecida_ignora_palavra_que_o_outro_texto_tambem_tem():
    """No Évangile, 1.597 achados de "parecida" caíram para 302 com o OCR do
    archive.org como referência: palavra que os dois OCRs leram igual é palavra boa."""
    frequente = " ".join(["vertus"] * 6)
    paragrafos = [
        Paragrafo(1, f"{frequente} les versets du livre."),
        Paragrafo(2, f"{frequente} une vcrtus mal lue."),
    ]
    sem = {a.trecho for a in revisar(paragrafos, idioma="fra").achados}
    assert {"versets", "vcrtus"} <= sem
    com = {
        a.trecho
        for a in revisar(paragrafos, referencia="Les versets.", idioma="fra").achados
        if a.tipo == "parecida com palavra frequente"
    }
    assert com == {"vcrtus"}


def test_parecida_nao_aponta_diferenca_so_de_acento():
    """Maiúscula sem acento era a norma da época ("l'Evangile" × "l'évangile")."""
    paragrafos = [Paragrafo(1, " ".join(["évangile"] * 6) + " L'Evangile du Christ.")]
    achados = [a.trecho for a in revisar(paragrafos, idioma="fra").achados]
    assert "Evangile" not in " ".join(achados)


def test_cabecalho_com_romano_dos_dois_lados_sai_mas_titulo_de_capitulo_fica():
    """Introdução do Évangile: "IV INTRODUCTION." na página par, "INTRODUCTION. V" na
    ímpar. O romano não pode tirar o título "CAPÍTULO V" que abre um capítulo."""
    paginas = []
    for n, cab in enumerate(["IV INTRODUCTION.", "INTRODUCTION. V", "VI INTRODUCTION."], 4):
        paginas.append(f"{cab}\n\nTexte de la page {n}, qui continue la phrase de la page\n")
    # Quatro capítulos abrindo no topo da página: sem o romano, "capítulo" se repetiria
    # em todas e sairia como cabeçalho.
    corpo = {
        "I": "Que é Deus?",
        "II": "Do elemento material.",
        "III": "Da criação.",
        "IV": "Do princípio vital.",
    }
    for romano, texto in corpo.items():
        paginas.append(f"CAPÍTULO {romano}\n\n{texto}\n")
    lidos = [p.texto for p in limpar_paginas("\f".join(paginas))]
    assert not any("INTRODUCTION" in t for t in lidos)
    assert all(t in lidos for t in corpo.values())
    assert [t for t in lidos if t.startswith("CAPÍTULO")] == [
        "CAPÍTULO I",
        "CAPÍTULO II",
        "CAPÍTULO III",
        "CAPÍTULO IV",
    ]


def test_linha_em_branco_no_meio_do_paragrafo_nao_o_parte():
    """O Tesseract põe linha em branco dentro do parágrafo; minúscula depois de frase
    aberta é continuação. Depois de ponto final, é parágrafo novo."""
    pagina = "Là aussi est la cause de sa\n\npropagation si rapide.\n\nNouveau paragraphe ici.\n"
    assert [p.texto for p in limpar_paginas(pagina)] == [
        "Là aussi est la cause de sa propagation si rapide.",
        "Nouveau paragraphe ici.",
    ]


def test_cabecalho_de_capitulo_com_numero_sai_e_subtitulo_repetido_fica():
    """O cabeçalho corrido de um capítulo só aparece nas páginas dele, longe dos 30% do
    livro; tem o número da página na ponta e está em maiúsculas. Subtítulo repetido no
    topo da página não tem número; linha de texto com número no fim é minúscula."""
    paginas = []
    for n in range(2, 12, 2):
        paginas.append(f"{n} CHAPITRE I.\n\nTexte pair {n}, qui finit avec la phrase {n}.\n")
        paginas.append(
            f"JE NE SUIS POINT VENU DÉTRUIRE LA LOI. {n + 1}\n\n"
            "Instructions des Esprits\n\nAutre paragraphe.\n"
        )
    paginas += [f"Page {n} sans en-tête, avec du texte long qui continue.\n" for n in range(40)]
    lidos = [p.texto for p in limpar_paginas("\f".join(paginas))]
    assert not any("CHAPITRE" in t or "DÉTRUIRE" in t for t in lidos)
    texto = " ".join(lidos)
    assert "la phrase 2." in texto
    assert texto.count("Instructions des Esprits") == 5


def test_titulo_que_abre_o_capitulo_fica_mesmo_com_o_cabecalho_igual():
    """Regressão da #131: "62 CHAPITRE V." (cabeçalho corrido) e "CHAPITRE V" (título no
    topo da página que abre o capítulo) têm a mesma assinatura. Só o numerado sai."""
    paginas = ["CHAPITRE V\n\nBIENHEUREUX LES AFFLIGÉS.\n\nTexte d'ouverture.\n"]
    for n in range(62, 70, 2):
        paginas.append(f"{n} CHAPITRE V.\n\nTexte de la page {n}.\n")
    paginas += [f"Page {n} sans en-tête, avec du texte long.\n" for n in range(40)]
    lidos = [p.texto for p in limpar_paginas("\f".join(paginas))]
    assert lidos[:2] == ["CHAPITRE V", "BIENHEUREUX LES AFFLIGÉS."]
    assert not any(t.endswith("CHAPITRE V.") for t in lidos)


def _livro_com_deslocamento(paginas_extras: dict[int, str], primeira: int = 47) -> str:
    """Páginas do PDF a partir da 1, com o número impresso = página do PDF - 46 (como no
    Évangile: PDF 135, página 89) e cabeçalho corrido numerado, mais páginas extras."""
    paginas = []
    for pdf in range(1, 70):
        if pdf in paginas_extras:
            paginas.append(paginas_extras[pdf])
        elif pdf >= primeira:
            n = pdf - 46
            paginas.append(f"{n} CHAPITRE I.\n\nTexte de la page {n}, avec une phrase finie.\n")
        else:
            paginas.append(f"Page préliminaire {pdf}, sans en-tête, avec du texte.\n")
    return "\f".join(paginas)


def test_cabecalho_que_nao_se_repete_sai_quando_o_numero_e_o_da_pagina():
    """No Évangile, o cabeçalho do capítulo curto aparece 2 vezes, e o OCR leu o ponto
    como vírgula ("LE CHRIST CONSOLATEUR, 89"): a repetição não pega. O número na ponta
    ser o da página (PDF menos o deslocamento) pega. Título com número que não é o da
    página fica."""
    livro = _livro_com_deslocamento(
        {
            60: "LE CHRIST CONSOLATEUR, 14\n\nLe Christ promet un autre consolateur.\n",
            61: "LE CHRIST CONSOLATEUR. 15\n\nC'est l'Esprit de Vérité.\n",
            62: "LES 40 MARTYRS\n\nTitre avec un nombre qui n'est pas la page.\n",
            63: "ANNÉE 1860\n\nTitre en haut, nombre loin de la page 17.\n",
        }
    )
    lidos = [p.texto for p in limpar_paginas(livro)]
    texto = " ".join(lidos)
    assert "CONSOLATEUR" not in texto
    assert "Le Christ promet un autre consolateur." in texto
    assert "LES 40 MARTYRS" in texto and "ANNÉE 1860" in texto


def test_sujeira_curta_sai_junto_com_o_cabecalho_mas_sozinha_fica():
    """ "|" e "Us" acima do cabeçalho (p. 129 e 211 do Évangile) o escondiam da borda."""
    livro = _livro_com_deslocamento(
        {
            60: "|\n|\nAIMEZ VOS ENNEMIS. 14\n\nAimez vos ennemis, dit Jésus.\n",
            61: "Us\n\nAh\n\nLa ligne courte du haut reste quand rien ne la suit.\n",
        }
    )
    texto = " ".join(p.texto for p in limpar_paginas(livro))
    assert "AIMEZ" not in texto and "|" not in texto
    assert "Aimez vos ennemis, dit Jésus." in texto
    assert " Us " in f" {texto} " and " Ah " in f" {texto} "


def test_hifen_com_sujeira_da_margem_depois_ainda_junta():
    """ "recevez les hu-. |" + "miliations": o ponto solto não é fim de frase."""
    pagina = "fustigez votre orgueil ; recevez les hu-. |\nmiliations sans murmurer.\n"
    assert [p.texto for p in limpar_paginas(pagina)] == [
        "fustigez votre orgueil ; recevez les humiliations sans murmurer."
    ]


def test_hifen_de_palavra_composta_fica_ao_juntar():
    """Évangile de 1866 (#45): "nous-|mêmes" virava "nousmêmes". O hífen fica quando o
    livro escreve a palavra com hífen no meio de alguma linha, ou no "-t-il"; a quebra
    comum continua juntando sem ele."""
    pagina = (
        "Aimez-vous les uns les autres, et vous-mêmes ; c'est-à-dire, sans\n"
        "orgueil. Connaissez-vous vous-\n"
        "mêmes, c'est-\n"
        "à-dire votre âme ; a-\n"
        "t-il dit autre chose ? Il parle de la souf-\n"
        "france, et de lui-\n"
        "même.\n"
    )
    assert [p.texto for p in limpar_paginas(pagina)] == [
        "Aimez-vous les uns les autres, et vous-mêmes ; c'est-à-dire, sans orgueil. "
        "Connaissez-vous vous-mêmes, c'est-à-dire votre âme ; a-t-il dit autre chose ? "
        "Il parle de la souffrance, et de luimême."
    ]


def test_barra_colada_na_palavra_sai_e_o_hifen_junta():
    """Fac-símile da Library of Congress (#45): a borda da página vizinha entra colada
    na palavra, sem espaço. O "{" no começo da palavra fica: é "1" ou "t" mal lido."""
    pagina = (
        "une religion entièrement spiri-|\n"
        "tuelle ; il leur fallait\n"
        "|profanation, et la forme est}\n"
        "toujours belle, mais dé- |\n"
        "tério-|:\n"
        "rations et {ous les jours.\n"
    )
    assert [p.texto for p in limpar_paginas(pagina)] == [
        "une religion entièrement spirituelle ; il leur fallait profanation, et la forme "
        "est toujours belle, mais détériorations et {ous les jours."
    ]


def test_linha_so_de_barra_sai_sem_partir_paragrafo():
    """Fac-símile da Library of Congress (#45): a borda da página vizinha vira linha
    sozinha ("|", "| | |", "| :"). Ficando, entrava no parágrafo e travava o hífen
    ("s'éta- | blir"); virando linha em branco, partiria o parágrafo. Sai inteira."""
    pagina = (
        "les préjugés qu'elles froissent, ne peuvent s'éta-\n"
        "|\n"
        "blir que peu à peu ; il a dù leur\n"
        "| | |\n"
        "attribuer une origine divine.\n"
        "| :\n"
        "\n"
        "Nouveau paragraphe.\n"
    )
    assert [p.texto for p in limpar_paginas(pagina)] == [
        "les préjugés qu'elles froissent, ne peuvent s'établir que peu à peu ; il a dù leur "
        "attribuer une origine divine.",
        "Nouveau paragraphe.",
    ]


def test_sinal_da_margem_na_frente_da_linha_sai():
    """Fac-símile da Library of Congress (#45): sinal da margem na frente da linha
    ("* pour", ". preuve", "-soins", "_ En") ficava no texto e, depois de linha em
    branco, abria parágrafo falso. Ponto e hífen só saem antes de minúscula."""
    pagina = (
        "La religion était\n"
        "\n"
        "* pour eux plutôt un moyen. Ainsi l'expiation sert d'é-\n"
        ". preuve; sacrifiez aux be-\n"
        "-soins du jour.\n"
        "=\n"
        "_ En effet, c'est vrai.\n"
        "- Non, dit-il.\n"
    )
    assert [p.texto for p in limpar_paginas(pagina)] == [
        "La religion était pour eux plutôt un moyen. Ainsi l'expiation sert d'épreuve; "
        "sacrifiez aux besoins du jour.",
        "En effet, c'est vrai. - Non, dit-il.",
    ]


def test_citacao_que_termina_em_ponto_e_parentese_fecha_frase():
    """No Évangile, o versículo citado fecha com ".)": a questão numerada seguinte abre
    parágrafo, em vez de entrar no anterior (19 casos no livro, #45)."""
    pagina = (
        "Que celui-là entende qui a des oreilles. (Saint Matthieu, ch. xi, v. 15.)\n"
        "14. Si le principe de la réincarnation exprimé dans saint Jean pouvait.\n"
    )
    assert [p.texto[:3] for p in limpar_paginas(pagina)] == ["Que", "14."]
