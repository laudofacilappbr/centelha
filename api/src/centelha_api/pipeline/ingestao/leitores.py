"""Leitores de arquivo: todos devolvem a lista de parágrafos do texto, em ordem.

Só bibliotecas Python (sem pandoc), para rodar no container do worker.
"""

import re
import warnings
from pathlib import Path

_ESPACOS = re.compile(r"[ \t   ]+")
# "pala-\nvra" → "palavra"; quebra simples de linha vira espaço.
_HIFENIZACAO = re.compile(r"(\w)-\n(\w)")
_QUEBRA = re.compile(r"\s*\n\s*")


def limpar(texto: str) -> str:
    texto = _HIFENIZACAO.sub(r"\1\2", texto)
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


_NUMERO_DE_PAGINA = re.compile(r"^\s*[-–]?\s*\d{1,4}\s*[-–]?\s*$")


def ler_pdf(caminho: Path) -> list[str]:
    import pymupdf

    paragrafos: list[str] = []
    with pymupdf.open(str(caminho)) as doc:
        for pagina in doc:
            for bloco in pagina.get_text("blocks", sort=True):
                texto = bloco[4]
                if _NUMERO_DE_PAGINA.match(texto):
                    continue
                texto = limpar(texto)
                if texto:
                    paragrafos.append(texto)
    return paragrafos


LEITORES = {".txt": ler_txt, ".docx": ler_docx, ".epub": ler_epub, ".pdf": ler_pdf}


def ler(caminho: Path) -> list[str]:
    leitor = LEITORES.get(caminho.suffix.lower())
    if leitor is None:
        raise ValueError(f"formato não suportado: {caminho.suffix} (use {', '.join(LEITORES)})")
    return leitor(caminho)
