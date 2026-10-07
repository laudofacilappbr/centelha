"""Leitores de arquivo: todos devolvem a lista de parágrafos do texto, em ordem.

Só bibliotecas Python (sem pandoc), para rodar no container do worker.
"""

import re
import warnings
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_ESPACOS = re.compile(r"[ \t   ]+")
# "pala-\nvra" → "palavra"; quebra simples de linha vira espaço.
_HIFENIZACAO = re.compile(r"(\w)-[ \t]*\n\s*(\w+)")
# Exceção: pronome depois de verbo com acento ("avaliá-\nla", "dê-\nse") é hífen de
# verdade. Sem acento não dá para saber ("fra-\nse" é "frase", "pode-\nse" é "pode-se"):
# fica sem hífen e a revisão corrige.
_ENCLITICO = re.compile(r"(?:l[oa]s?|se|lhes?|me|te|nos|vos)")
_VOGAL_ACENTUADA = "áéíóúâêô"


def _desfazer_hifenizacao(m: re.Match) -> str:
    antes, depois = m[1], m[2]
    if antes in _VOGAL_ACENTUADA and _ENCLITICO.fullmatch(depois):
        return f"{antes}-{depois}"
    return antes + depois


_QUEBRA = re.compile(r"\s*\n\s*")
# PDF da FEB usa \x03 como espaço antes da referência bíblica e hífen discricionário (U+00AD)
# na quebra de linha e, solto, no começo de linha.
_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HIFEN_DISCRICIONARIO_NA_QUEBRA = re.compile(r"\u00ad[ \t]*\n")


def limpar(texto: str) -> str:
    texto = _CONTROLE.sub(" ", texto)
    texto = _HIFEN_DISCRICIONARIO_NA_QUEBRA.sub("-\n", texto).replace("\u00ad", "")
    texto = _HIFENIZACAO.sub(_desfazer_hifenizacao, texto)
    texto = _QUEBRA.sub(" ", texto)
    return _ESPACOS.sub(" ", texto).strip()


def ler_txt(caminho: Path) -> list[str]:
    bruto = caminho.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    return [p for p in (limpar(b) for b in re.split(r"\n\s*\n", bruto)) if p]


def ler_docx(caminho: Path) -> list[str]:
    import docx

    documento = docx.Document(str(caminho))
    return [p for p in (limpar(par.text) for par in documento.paragraphs) if p]


def ler_epub(caminho: Path) -> list[str]:
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        livro = epub.read_epub(str(caminho), options={"ignore_ncx": True})
    if _e_wikisource(livro):
        return _ler_wikisource(livro)
    paragrafos: list[str] = []
    for id_item, _ in livro.spine:
        item = livro.get_item_with_id(id_item)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        sopa = BeautifulSoup(item.get_content(), "html.parser")
        for no in sopa.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote"]):
            # blockquote com <p> dentro já entra pelos <p>.
            if no.name == "blockquote" and no.find("p"):
                continue
            texto = limpar(no.get_text(" "))
            if texto:
                paragrafos.append(texto)
    return paragrafos


# --- EPUB do Wikisource (WS Export, #45) -------------------------------------------
#
# https://ws-export.wmcloud.org/?lang=fr&page=Le_Livre_des_Esprits&format=epub-3
# Um arquivo por subpágina do Wikisource. Fora do texto da obra: folha de rosto da
# exportação ("Exporté de Wikisource le..."), créditos, página principal e sumário.

_WS_FORA = ("title.xhtml", "about.xhtml", "nav.xhtml")
_WS_SUMARIO = re.compile(r"table[ _]des[ _]mati|sum[áa]rio|[íi]ndice", re.IGNORECASE)
# Subpáginas com o próprio título no corpo (h2/h3): "LIVRE PREMIER", "CHAPITRE PREMIER".
_WS_TITULO_NO_CORPO = re.compile(r"^(?:livre|chapitre|livro|cap[íi]tulo|partie|parte)b", re.I)


def _e_wikisource(livro) -> bool:
    return any(
        "wikisource" in str(valor).lower()
        for campo in ("contributor", "source", "identifier")
        for valor, _ in livro.get_metadata("DC", campo)
    )


def _titulos_do_sumario(livro) -> dict[str, str]:
    """Arquivo → título da subpágina, pelo nav.xhtml."""
    from bs4 import BeautifulSoup

    titulos: dict[str, str] = {}
    for item in livro.get_items():
        if item.get_name().endswith("nav.xhtml"):
            sopa = BeautifulSoup(item.get_content(), "html.parser")
            for a in sopa.find_all("a", href=True):
                titulos[a["href"].split("#")[0].rsplit("/", 1)[-1]] = limpar(a.get_text(" "))
    return titulos


def _ler_wikisource(livro) -> list[str]:
    import ebooklib
    from bs4 import BeautifulSoup

    titulos = _titulos_do_sumario(livro)
    paragrafos: list[str] = []
    primeiro = True
    for id_item, _ in livro.spine:
        item = livro.get_item_with_id(id_item)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        nome = item.get_name().rsplit("/", 1)[-1]
        if nome in _WS_FORA:
            continue
        if primeiro:
            # A página principal da obra: folha de rosto e sumário geral.
            primeiro = False
            continue
        titulo = titulos.get(nome, "")
        if _WS_SUMARIO.search(titulo) or _WS_SUMARIO.search(nome):
            continue
        sopa = BeautifulSoup(item.get_content(), "html.parser")
        # Notas de rodapé: o texto sai da lista do fim e entra logo depois do parágrafo
        # que a chama; a chamada ("[1]") sai do texto.
        notas: dict[str, str] = {}
        for li in sopa.select("ol.references li[id]"):
            for volta in li.select(".mw-cite-backlink"):
                volta.decompose()
            notas[li["id"]] = limpar(li.get_text(" "))
        for ol in sopa.select("ol.references"):
            ol.decompose()
        # Título da subpágina que no corpo vem em <div> centralizada (Avis, Introduction).
        if titulo and not _WS_TITULO_NO_CORPO.match(titulo):
            paragrafos.append(titulo)
        for no in sopa.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote"]):
            if no.name == "blockquote" and no.find("p"):
                continue
            chamadas = []
            for sup in no.select("sup.reference"):
                if (a := sup.find("a", href=True)) and a["href"].lstrip("#") in notas:
                    chamadas.append(a["href"].lstrip("#"))
                sup.decompose()
            # Sem separador: itálico no meio da frase não pode virar "médiums , ainsi".
            for br in no.find_all("br"):
                br.replace_with("\n")
            texto = limpar(no.get_text(""))
            if texto:
                # h4/h5 dentro do capítulo: subtítulo de seção ("Paradis, enfer et
                # purgatoire."), que fecha a resposta anterior.
                paragrafos.append(Subtitulo(texto) if no.name in ("h4", "h5", "h6") else texto)
            paragrafos.extend(Nota(notas[c]) for c in chamadas if notas.get(c))
    return paragrafos


_NUMERO_DE_PAGINA = re.compile(r"^\s*[-–]?\s*\d{1,4}\s*[-–]?\s*$")


# Faixas do topo e do pé da página onde moram cabeçalho corrido e número de página. O
# cabeçalho do LE da FEB oscila entre 8,8% e 10,6% da altura; o título de capítulo mais
# alto (ESE) começa em 13,9%.
_TOPO, _PE = 0.13, 0.92
# Cabeçalho corrido é o mesmo texto (sem os números, com as maiúsculas) na margem de mais
# de uma página. O título real aparece uma vez só e, no ESE, em versalete ("capítulo vi"),
# o que o separa do cabeçalho "Capítulo VI".
_REPETICOES_DE_CABECALHO = 2
_SEPARADOR_DE_NOTAS = re.compile(r"^_{3,}$")
_INICIO_DE_NOTA = re.compile(
    r"^\s*(?:\(\d{1,3}\)|\d{1,3}|\*{1,3})(?:\s+|(?=[A-ZÀ-Ú“\"]))(?P<texto>.+)$"
)
# Nota da editora (FEB: "N.E. de 1947", "N. da E.", "Nota Especial") tem direito próprio e
# não entra no texto. As de Kardec e as do tradutor (N.T., Guillon Ribeiro) ficam. Procura
# em toda a nota, não só no começo: se duas notas grudarem por erro de leitura, perde-se a
# de Kardec (volta na revisão) em vez de vazar texto da editora.
_NOTA_DA_EDITORA = re.compile(
    r"\bN\.\s?E\.|\bN\.\s?da\s?E\.|Nota da Editora|da Editora \(FEB\)|Nota Especial",
    re.IGNORECASE,
)
_CHAMADA_ENTRE_PARENTESES = re.compile(r"\(\d{1,3}\)")
# Fecha parágrafo. Dois-pontos e ponto e vírgula não fecham: "opinião:" no pé da página
# continua em "é um Proteu" na seguinte, e a minúscula é o que decide.
_FIM_DE_FRASE = tuple('.!?”"»)…—')
_FONTES_DE_ORNAMENTO = ("ornament", "dingbat")


class Nota(str):
    """Nota de rodapé. É `str` para quem só quer o texto; `estruturar` a vira segmento "nota"."""


class Subtitulo(str):
    """Subtítulo de seção dentro do capítulo, quando o arquivo o marca (h4 do Wikisource).
    `estruturar` o vira parágrafo e encerra a resposta em curso."""


@dataclass
class _Linha:
    bloco: int
    y0: float
    y1: float
    tamanho: float
    texto: str


def _linhas_da_pagina(pagina) -> list[_Linha]:
    linhas = []
    for nb, bloco in enumerate(pagina.get_text("dict", sort=True)["blocks"]):
        if bloco["type"] != 0:
            continue
        for linha in bloco["lines"]:
            # Span só de espaço fica (é o espaço entre "1." e "Não"), mas não conta tamanho.
            spans = [
                s
                for s in linha["spans"]
                if not any(f in s["font"].lower() for f in _FONTES_DE_ORNAMENTO)
            ]
            com_texto = [s for s in spans if s["text"].strip()]
            if not com_texto:
                continue
            maior = max(s["size"] for s in com_texto)
            # Chamada de nota em sobrescrito ("soberano.4"): número em corpo bem menor que
            # o da linha. Sem tirar, o narrador leria "soberano quatro". O primeiro span fica:
            # no rodapé, ele é o número que abre a nota e separa uma nota da outra.
            texto = "".join(
                s["text"]
                for s in spans
                if s is com_texto[0]
                or not (s["size"] < maior * 0.75 and s["text"].strip().isdigit())
            )
            if not texto.strip():
                continue
            y0, y1 = linha["bbox"][1], linha["bbox"][3]
            if linhas and linhas[-1].bloco == nb and abs(linhas[-1].y0 - y0) < 1:
                # Mesma altura, mesmo bloco: é a mesma linha partida em colunas, como o
                # "(1)" recuado do texto da nota no LE.
                linhas[-1].texto += " " + texto
                continue
            linhas.append(_Linha(nb, y0, y1, round(maior, 1), texto))
    return linhas


def _assinatura(texto: str) -> str:
    return re.sub(r"[\d\s]+", " ", texto).strip()


def _corpo(linhas: list[_Linha]) -> float:
    """Tamanho de letra do texto corrido: o mais frequente, pesado pelo número de caracteres."""
    contagem: Counter[float] = Counter()
    for linha in linhas:
        contagem[linha.tamanho] += len(linha.texto)
    return contagem.most_common(1)[0][0] if contagem else 0.0


def ler_pdf(caminho: Path, paginas: tuple[int, int] | None = None) -> list[str]:
    """Parágrafos do texto corrido, sem cabeçalho, número de página e notas da editora.

    `paginas` (primeira, última; contando do 1, como o visualizador de PDF) recorta a obra.
    Folha de rosto, sumário, nota da editora e índice ficam de fora pela faixa, não por
    heurística: a faixa é auditável e fica registrada junto da edição.
    """
    import pymupdf

    with pymupdf.open(str(caminho)) as doc:
        primeira, ultima = paginas or (1, len(doc))
        if not 1 <= primeira <= ultima <= len(doc):
            raise ValueError(f"faixa de páginas {primeira}-{ultima} fora de 1-{len(doc)}")
        por_pagina = [
            (doc[n].rect.height, _linhas_da_pagina(doc[n])) for n in range(primeira - 1, ultima)
        ]

    corpo = _corpo([linha for _, linhas in por_pagina for linha in linhas])
    na_margem: Counter[str] = Counter()
    for altura, linhas in por_pagina:
        na_margem.update(
            {_assinatura(lin.texto) for lin in linhas if not _TOPO * altura < lin.y0 < _PE * altura}
        )
    # Altura em que o cabeçalho corrido costuma estar. Pega o de capítulo curto, que aparece
    # numa página só e escapa da contagem de repetições ("DA LEI DE SOCIEDADE", 3 páginas).
    alturas: Counter[int] = Counter()
    for altura, linhas in por_pagina:
        alturas.update(
            round(lin.y0)
            for lin in linhas
            if lin.y0 < _TOPO * altura
            and not _NUMERO_DE_PAGINA.match(lin.texto)
            and na_margem[_assinatura(lin.texto)] >= _REPETICOES_DE_CABECALHO
        )
    alturas_de_cabecalho = {y for y, n in alturas.items() if n >= 3}

    paragrafos: list[str] = []
    # Nota: (posição em `paragrafos` depois da qual entra, linhas). Só vira texto no fim,
    # porque nota longa continua no rodapé da página seguinte, sem número.
    notas: list[tuple[int, list[str]]] = []
    aberto_no_corpo: float | None = None

    for altura, linhas in por_pagina:
        corrido: list[_Linha] = []
        rodape: list[_Linha] = []
        linhas_no_bloco = Counter(linha.bloco for linha in linhas)
        # Bloco inteiro no topo: o do cabeçalho. Texto corrido que começa no topo (ESE)
        # desce página abaixo no mesmo bloco.
        blocos_no_topo = {
            b
            for b in linhas_no_bloco
            if all(lin.y0 < _TOPO * altura for lin in linhas if lin.bloco == b)
        }
        for linha in linhas:
            na_faixa_da_margem = not _TOPO * altura < linha.y0 < _PE * altura
            cabecalho = na_margem[_assinatura(linha.texto)] >= _REPETICOES_DE_CABECALHO
            na_altura_de_cabecalho = linha.bloco in blocos_no_topo and any(
                abs(linha.y0 - y) <= 1 for y in alturas_de_cabecalho
            )
            if na_faixa_da_margem and (
                _NUMERO_DE_PAGINA.match(linha.texto) or cabecalho or na_altura_de_cabecalho
            ):
                continue
            if cabecalho and linhas_no_bloco[linha.bloco] > 1:
                # O PDF da UEL às vezes embute o cabeçalho corrido no meio de um parágrafo
                # ("no silên- DA LEI DE SOCIEDADE cio"). Título de verdade vem em bloco próprio.
                continue
            if (
                rodape
                or _SEPARADOR_DE_NOTAS.match(linha.texto.strip())
                # Corpo bem menor na metade de baixo: começou o rodapé. Citação em corpo 10
                # sobre texto 12 (0,83) não cai aqui; nota em corpo 8 (0,67) cai.
                or (linha.y0 > altura / 2 and linha.tamanho <= corpo * 0.75)
            ):
                rodape.append(linha)
            else:
                corrido.append(linha)

        # Blocos do PyMuPDF são parágrafos, com dois acertos: título em duas linhas de corpo
        # grande vem em dois blocos e é juntado; subtítulo que veio no mesmo bloco do texto
        # ("Uma realeza terrestre" + "8. Quem melhor...") é separado.
        blocos: list[list[_Linha]] = []
        anterior: _Linha | None = None
        for linha in corrido:
            e_titulo = linha.tamanho > corpo * 1.1
            titulo_continuado = (
                anterior is not None
                and linha.tamanho == anterior.tamanho
                and e_titulo
                and linha.y0 - anterior.y1 < linha.tamanho
            )
            mesmo_bloco = (
                anterior is not None
                and anterior.bloco == linha.bloco
                and (anterior.tamanho > corpo * 1.1) == e_titulo
            )
            if mesmo_bloco or titulo_continuado:
                blocos[-1].append(linha)
            else:
                blocos.append([linha])
            anterior = linha

        # Chamada "(1)" só sai do texto se o rodapé desta página tem a nota "(1)": "(85)"
        # no meio do LE é remissão à questão 85 e tem de ser lida.
        chamadas = {
            m[0] for lin in rodape if (m := _CHAMADA_ENTRE_PARENTESES.match(lin.texto.strip()))
        }
        for bloco in blocos:
            texto = limpar("\n".join(linha.texto for linha in bloco))
            for chamada in chamadas:
                texto = re.sub(rf"\s?{re.escape(chamada)}(?=[\s.,;:!?”\"]|$)", "", texto)
            if not texto:
                continue
            if aberto_no_corpo == bloco[0].tamanho and texto[:1].islower():
                # Parágrafo partido (virada de página, ou o PyMuPDF dividiu o bloco, como no
                # sumário centralizado do ESE): o anterior ficou sem ponto final, este começa
                # em minúscula, e o corpo de letra é o mesmo. O "capítulo xxviii" em
                # versalete (11) depois de texto (12) não é continuação.
                paragrafos[-1] = limpar(f"{paragrafos[-1]}\n{texto}")
            else:
                paragrafos.append(texto)
            # Corpo de letra do parágrafo se ele ficou aberto; senão, nada a continuar.
            aberto_no_corpo = None if paragrafos[-1].endswith(_FIM_DE_FRASE) else bloco[-1].tamanho

        for linha in rodape:
            if _SEPARADOR_DE_NOTAS.match(linha.texto.strip()):
                continue
            if m := _INICIO_DE_NOTA.match(linha.texto):
                notas.append((len(paragrafos), [m["texto"]]))
            elif notas:
                notas[-1][1].append(linha.texto)
            else:
                notas.append((len(paragrafos), [linha.texto]))

    # De trás para a frente, para as posições anteriores continuarem valendo.
    for posicao, linhas_da_nota in reversed(notas):
        texto = limpar("\n".join(linhas_da_nota))
        if texto and not _NOTA_DA_EDITORA.search(texto):
            paragrafos.insert(posicao, Nota(texto))
    return paragrafos


LEITORES = {".txt": ler_txt, ".docx": ler_docx, ".epub": ler_epub, ".pdf": ler_pdf}


def cortar_em(paragrafos: list[str], inicio: str) -> list[str]:
    """Descarta do primeiro parágrafo que começa com `inicio` em diante.

    Para o que a faixa de páginas não separa: a "Nota Especial" da FEB na mesma página
    da conclusão do LE. Texto não encontrado é erro, para um erro de digitação não deixar
    passar tudo.
    """
    for n, p in enumerate(paragrafos):
        if p.startswith(inicio):
            return paragrafos[:n]
    raise ValueError(f"nenhum parágrafo começa com {inicio!r}")


def comecar_em(paragrafos: list[str], inicio: str) -> list[str]:
    """Descarta o que vem antes do primeiro parágrafo que começa com `inicio`.

    O par de `cortar_em` para a frente do livro: folha de rosto e lista de obras antes da
    PRÉFACE do Évangile (decisão do dono na #45). Texto não encontrado é erro, pelo mesmo
    motivo.
    """
    for n, p in enumerate(paragrafos):
        if p.startswith(inicio):
            return paragrafos[n:]
    raise ValueError(f"nenhum parágrafo começa com {inicio!r}")


def ler(caminho: Path, paginas: tuple[int, int] | None = None) -> list[str]:
    leitor = LEITORES.get(caminho.suffix.lower())
    if leitor is None:
        raise ValueError(f"formato não suportado: {caminho.suffix} (use {', '.join(LEITORES)})")
    if paginas is None:
        return leitor(caminho)
    if leitor is not ler_pdf:
        raise ValueError("faixa de páginas só vale para PDF")
    return ler_pdf(caminho, paginas)
