"""EPUB exportado do Wikisource (WS Export), no formato de Le Livre des Esprits (#45)."""

from ebooklib import epub

from centelha_api.models import TipoSegmento
from centelha_api.pipeline.ingestao.estrutura import estruturar, resumo
from centelha_api.pipeline.ingestao.leitores import Nota, Subtitulo, ler

_AVIS = """<div style="text-align:center">AVIS</div><div>SUR CETTE NOUVELLE ÉDITION</div>
<p>Dans la première édition de cet ouvrage, nous avons annoncé une partie.</p>"""

_LIVRE = """<h2 class="tmp"> LIVRE PREMIER<div> </div>LES CAUSES PREMIÈRES</h2>"""

_CHAPITRE = """<h3 class="tmp"> CHAPITRE PREMIER<div> </div>DIEU</h3>
<div style="text-align:center"><span>1. Dieu et l’infini. ― 2. Preuves.</span></div>
<h4 class="tmp"> Dieu et l’infini.</h4>
<p>1. Qu’est-ce que Dieu<span> </span>?</p>
<p>«<span> </span>Dieu est l’intelligence suprême, cause première de toutes
choses<sup class="mw-ref reference"><a href="#cite_note-1-n91">[1]</a></sup>.<span> </span>»</p>
<p>2. Que doit-on entendre par l’<i>infini</i>, sans fin<span> </span>?</p>
<p>«<span> </span>Ce qui n’a ni commencement ni fin.<span> </span>»</p>
<p>― Pourrait-on dire que Dieu c’est l’infini<span> </span>?</p>
<p>«<span> </span>Définition incomplète.<span> </span>»</p>
<p>― Et l’espace<span> </span>?</p>
<p>«<span> </span>Autre chose.<span> </span>»</p>
<p>Kardec résume ainsi les questions qui restent :</p>
<p>1. D’où vient l’aptitude des enfants<span> </span>?</p>
<h4 class="tmp"> Preuves de l’existence de Dieu.</h4>
<p>3. Où peut-on trouver la preuve de l’existence de Dieu<span> </span>?</p>
<p>«<span> </span>Dans un axiome.<span> </span>»</p>
<hr/>
<ol class="mw-references references"><li id="cite_note-1-n91">
<span class="mw-cite-backlink"><a href="#cite_ref-1">↑</a></span>
<span class="reference-text">Le texte placé entre guillemets est la réponse des Esprits.</span>
</li></ol>"""


def _epub_wikisource(tmp_path):
    livro = epub.EpubBook()
    livro.set_identifier("https://fr.wikisource.org/wiki/Le_Livre_des_Esprits")
    livro.set_title("Le Livre des Esprits")
    livro.set_language("fr")
    livro.add_metadata("DC", "contributor", "Wikisource")
    paginas = []
    for nome, titulo, corpo in [
        ("title.xhtml", "Le Livre des Esprits", "<p>Exporté de Wikisource le 7 octobre 2026</p>"),
        ("c0_Le_Livre_des_Esprits.xhtml", "Le Livre des Esprits", "<p>Table générale</p>"),
        ("c1_Avis.xhtml", "Avis sur cette nouvelle édition", _AVIS),
        ("c4_Livre_premier.xhtml", "Livre premier", _LIVRE),
        ("c5_Livre_premier_Chapitre_I.xhtml", "Chapitre I", _CHAPITRE),
        ("c38_Table_des_matieres.xhtml", "Table des matières", "<p>Chapitre I. — Dieu 1</p>"),
        ("about.xhtml", "À propos", "<p>Cette édition électronique provient de Wikisource</p>"),
    ]:
        pagina = epub.EpubHtml(title=titulo, file_name=nome, lang="fr")
        pagina.content = f"<html><body>{corpo}</body></html>"
        livro.add_item(pagina)
        paginas.append(pagina)
    livro.toc = paginas
    livro.spine = paginas
    livro.add_item(epub.EpubNcx())
    livro.add_item(epub.EpubNav())
    caminho = tmp_path / "lde.epub"
    epub.write_epub(str(caminho), livro)
    return caminho


def test_leitor_tira_o_que_nao_e_da_obra_e_marca_notas_e_subtitulos(tmp_path):
    paragrafos = ler(_epub_wikisource(tmp_path))
    texto = "\n".join(paragrafos)
    assert "Exporté de Wikisource" not in texto
    assert "Table générale" not in texto
    assert "Chapitre I. — Dieu 1" not in texto
    assert "édition électronique" not in texto
    assert paragrafos[0] == "Avis sur cette nouvelle édition"
    # Chamada de nota fora do texto; a nota logo depois do parágrafo que a chama.
    i = next(n for n, p in enumerate(paragrafos) if p.startswith("« Dieu est"))
    assert "[1]" not in paragrafos[i]
    assert paragrafos[i].endswith("toutes choses. »")
    assert isinstance(paragrafos[i + 1], Nota)
    assert paragrafos[i + 1] == "Le texte placé entre guillemets est la réponse des Esprits."
    # Itálico no meio da frase não abre espaço antes da vírgula.
    assert "l’infini, sans fin ?" in texto
    assert isinstance(paragrafos[paragrafos.index("Dieu et l’infini.")], Subtitulo)


def test_estrutura_do_original_frances(tmp_path):
    capitulos = estruturar(ler(_epub_wikisource(tmp_path)), "perguntas")
    assert [c.titulo for c in capitulos] == [
        "Avis sur cette nouvelle édition",
        "LIVRE PREMIER — LES CAUSES PREMIÈRES — CHAPITRE PREMIER — DIEU",
    ]
    segs = capitulos[1].segmentos
    perguntas = [(s.numero_questao, s.subquestao) for s in segs if s.tipo == TipoSegmento.PERGUNTA]
    # "―" é a pergunta que continua a anterior; ganha letra na ordem, como na FEB.
    assert perguntas == [(1, None), (2, None), (2, "a"), (2, "b"), (3, None)]
    # A lista numerada dentro do comentário não reinicia a numeração.
    lista = next(s for s in segs if s.texto.startswith("1. D’où vient"))
    assert lista.tipo == TipoSegmento.COMENTARIO
    # Subtítulo de seção encerra a resposta: não vira comentário da questão anterior.
    sub = next(s for s in segs if s.texto == "Preuves de l’existence de Dieu.")
    assert sub.tipo == TipoSegmento.PARAGRAFO
    nota = next(s for s in segs if s.tipo == TipoSegmento.NOTA)
    assert nota.numero_questao == 1
    assert resumo(capitulos)["questoes"] == 3
