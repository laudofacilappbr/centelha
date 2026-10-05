import json
from pathlib import Path

import pytest

from centelha_api.models import Capitulo, Edicao, EstadoCapitulo, Obra, Segmento, TipoSegmento
from centelha_api.pipeline.ingestao import leitores
from centelha_api.pipeline.ingestao.cli import main as cli
from centelha_api.pipeline.ingestao.estrutura import estruturar, resumo
from centelha_api.pipeline.ingestao.importar import ImportacaoRecusada, importar

# Texto sintético no formato de O Livro dos Espíritos (não é citação da obra).
LE_EXEMPLO = """\
INTRODUÇÃO

Texto de abertura da introdução, com um parágrafo cor-
rido que quebra a linha no meio.

LIVRO PRIMEIRO

CAPÍTULO I

DO PRIMEIRO TEMA

1. Primeira pergunta de exemplo?

“Primeira resposta de exemplo.”

2. Segunda pergunta de exemplo?

“Segunda resposta, primeiro parágrafo.

“Segunda resposta, segundo parágrafo.”

Comentário do autor sobre a segunda questão.

a) Subquestão ligada à segunda?

“Resposta da subquestão.”

CAPÍTULO II — DO SEGUNDO TEMA

4. Quarta pergunta, a terceira falta de propósito?

“Quarta resposta.”
"""


@pytest.fixture
def paragrafos_le(tmp_path):
    arquivo = tmp_path / "le.txt"
    arquivo.write_text(LE_EXEMPLO, encoding="utf-8")
    return leitores.ler(arquivo)


def test_leitor_txt_junta_linhas_e_hifenizacao(paragrafos_le):
    assert paragrafos_le[1] == (
        "Texto de abertura da introdução, com um parágrafo corrido que quebra a linha no meio."
    )


def test_estrutura_perfil_perguntas(paragrafos_le):
    caps = estruturar(paragrafos_le, "perguntas")
    assert [c.titulo for c in caps] == [
        "INTRODUÇÃO",
        "LIVRO PRIMEIRO — CAPÍTULO I — DO PRIMEIRO TEMA",
        "LIVRO PRIMEIRO — CAPÍTULO II — DO SEGUNDO TEMA",
    ]
    tipos = [(s.tipo.value, s.numero_questao, s.subquestao) for s in caps[1].segmentos]
    assert tipos == [
        ("titulo", None, None),
        ("pergunta", 1, None),
        ("resposta", 1, None),
        ("pergunta", 2, None),
        ("resposta", 2, None),
        ("resposta", 2, None),
        ("comentario", 2, None),
        ("pergunta", 2, "a"),
        ("resposta", 2, "a"),
    ]
    assert caps[1].segmentos[1].texto == "Primeira pergunta de exemplo?"


def test_resumo_aponta_questao_faltando(paragrafos_le):
    r = resumo(estruturar(paragrafos_le, "perguntas"))
    assert r["capitulos"] == 3
    assert (r["primeira_questao"], r["ultima_questao"]) == (1, 4)
    assert r["questoes_faltando"] == [3]
    assert r["caracteres"] > 0


def test_perfil_generico_nao_inventa_perguntas(paragrafos_le):
    caps = estruturar(paragrafos_le, "generico")
    tipos = {s.tipo for c in caps for s in c.segmentos}
    assert tipos == {TipoSegmento.TITULO, TipoSegmento.PARAGRAFO}


def test_texto_antes_do_primeiro_capitulo_vira_abertura():
    caps = estruturar(["Folha de rosto.", "Capítulo 1", "Texto."], "generico")
    assert [c.titulo for c in caps] == ["Abertura", "Capítulo 1"]


def _paragrafos_exemplo():
    return ["CAPÍTULO I", "O TÍTULO", "1. Uma pergunta?", "“Uma resposta.”"]


def test_leitor_docx(tmp_path):
    import docx

    doc = docx.Document()
    for p in _paragrafos_exemplo():
        doc.add_paragraph(p)
    doc.add_paragraph("   ")
    caminho = tmp_path / "x.docx"
    doc.save(caminho)
    assert leitores.ler(caminho) == _paragrafos_exemplo()


def test_leitor_epub(tmp_path):
    from ebooklib import epub

    livro = epub.EpubBook()
    livro.set_identifier("teste")
    livro.set_title("Teste")
    livro.set_language("pt-BR")
    cap = epub.EpubHtml(title="c1", file_name="c1.xhtml", lang="pt-BR")
    cap.content = (
        "<html><body><h1>CAPÍTULO I</h1><h2>O TÍTULO</h2>"
        "<p>1. Uma pergunta?</p><blockquote><p>“Uma resposta.”</p></blockquote>"
        "</body></html>"
    )
    livro.add_item(cap)
    livro.add_item(epub.EpubNcx())
    livro.add_item(epub.EpubNav())
    livro.spine = [cap]
    caminho = tmp_path / "x.epub"
    epub.write_epub(str(caminho), livro)
    assert leitores.ler(caminho) == _paragrafos_exemplo()


def test_leitor_pdf_ignora_numero_de_pagina(tmp_path):
    import pymupdf

    doc = pymupdf.open()
    pagina = doc.new_page()
    y = 72
    for p in [*_paragrafos_exemplo(), "12"]:
        pagina.insert_text((72, y), p, fontname="helv")
        y += 40
    caminho = tmp_path / "x.pdf"
    doc.save(caminho)
    # Fonte base do PDF não tem aspas curvas; o leitor só não pode perder o texto.
    lidos = leitores.ler(caminho)
    assert lidos[:3] == _paragrafos_exemplo()[:3]
    assert "12" not in lidos
    assert len(lidos) == 4


def test_formato_nao_suportado(tmp_path):
    with pytest.raises(ValueError, match="formato"):
        leitores.ler(tmp_path / "x.odt")


def _edicao(session):
    obra = Obra(
        slug="o-livro-dos-espiritos",
        autor="Allan Kardec",
        titulo_original="Le Livre des Esprits",
        idioma_original="fr",
        sigla="LE",
    )
    edicao = Edicao(obra=obra, idioma="pt-BR", titulo="O Livro dos Espíritos", fonte="teste")
    session.add(edicao)
    session.commit()
    return edicao


def test_importar_grava_capitulos_e_segmentos(session, paragrafos_le):
    edicao = _edicao(session)
    importar(session, edicao, estruturar(paragrafos_le, "perguntas"))
    session.commit()
    caps = session.query(Capitulo).order_by(Capitulo.ordem).all()
    assert [c.referencia_canonica for c in caps] == ["LE-C001", "LE-C002", "LE-C003"]
    assert {c.estado for c in caps} == {EstadoCapitulo.IMPORTADO}
    sub = session.query(Segmento).filter_by(subquestao="a", tipo=TipoSegmento.PERGUNTA).one()
    assert sub.numero_questao == 2


def test_reimportar_exige_substituir_e_protege_revisados(session, paragrafos_le):
    edicao = _edicao(session)
    caps = estruturar(paragrafos_le, "perguntas")
    importar(session, edicao, caps)
    session.commit()
    with pytest.raises(ImportacaoRecusada, match="substituir"):
        importar(session, edicao, caps)
    importar(session, edicao, caps[:1], substituir=True)
    session.commit()
    assert session.query(Capitulo).count() == 1

    session.query(Capitulo).one().estado = EstadoCapitulo.TEXTO_REVISADO
    session.commit()
    with pytest.raises(ImportacaoRecusada, match="revisados"):
        importar(session, edicao, caps, substituir=True)


def test_cli_resumo_e_json(tmp_path, capsys):
    fonte = tmp_path / "le.txt"
    fonte.write_text(LE_EXEMPLO, encoding="utf-8")
    saida = tmp_path / "estrutura.json"
    assert cli([str(fonte), "--perfil", "perguntas", "--json", str(saida)]) == 0
    assert json.loads(capsys.readouterr().out)["questoes_faltando"] == [3]
    assert json.loads(Path(saida).read_text(encoding="utf-8"))[1]["segmentos"][1]["tipo"] == (
        "pergunta"
    )
