"""OCR do exemplar escaneado com o Tesseract (modelo "por").

PDF: cada página é renderizada a 300 dpi pelo PyMuPDF (já dependência da ingestão) e
vai para o Tesseract. Pasta de imagens: uma página por imagem, em ordem de nome.
Saída: as páginas separadas por \\f, como o Tesseract faz, para a limpeza saber onde
cada página começa.

O Tesseract roda no container de digitalização (api/Dockerfile, --target
digitalizacao); fora dele, precisa estar instalado com o pacote de português.
"""

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


class ErroOCR(Exception):
    pass


def _tesseract(imagem: Path, idioma: str) -> str:
    binario = shutil.which("tesseract")
    if binario is None:
        raise ErroOCR("tesseract não encontrado; use o container de digitalização")
    # --psm 3: segmentação automática da página (colunas, cabeçalho, corpo).
    r = subprocess.run(
        [binario, str(imagem), "-", "-l", idioma, "--psm", "3"],
        capture_output=True,
        timeout=300,
    )
    if r.returncode != 0:
        erro = r.stderr[-300:].decode(errors="replace")
        raise ErroOCR(f"tesseract falhou em {imagem.name}: {erro}")
    return r.stdout.decode("utf-8").rstrip("\f")


def ocr(
    origem: Path,
    idioma: str = "por",
    dpi: int = 300,
    progresso: Callable[[int, int], None] | None = None,
) -> str:
    if origem.is_dir():
        imagens = sorted(p for p in origem.iterdir() if p.suffix.lower() in EXTENSOES_IMAGEM)
        if not imagens:
            raise ErroOCR(f"nenhuma imagem em {origem}")
        paginas = []
        for i, img in enumerate(imagens, 1):
            paginas.append(_tesseract(img, idioma))
            if progresso:
                progresso(i, len(imagens))
        return "\f".join(paginas)

    if origem.suffix.lower() != ".pdf":
        raise ErroOCR(f"use um PDF ou uma pasta de imagens: {origem}")
    import pymupdf

    paginas = []
    with pymupdf.open(str(origem)) as doc, tempfile.TemporaryDirectory() as tmp:
        for i, pagina in enumerate(doc, 1):
            png = Path(tmp) / f"p{i:04d}.png"
            pagina.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY).save(str(png))
            paginas.append(_tesseract(png, idioma))
            png.unlink()
            if progresso:
                progresso(i, len(doc))
    return "\f".join(paginas)
