"""Relatório de revisão: o que um humano precisa conferir no exemplar, com a página.

Nada aqui altera o texto. Cada achado aponta a página do exemplar, para o revisor
olhar a imagem e corrigir no arquivo (ou no admin, depois da ingestão).

- Suspeitas de OCR: dígito no meio de palavra ("c0m", "l1vro"), caracteres que não
  existem no português impresso, "rn" e "m" confundidos quando a outra forma aparece
  no próprio texto, palavra muito curta e isolada que costuma ser sujeira.
- Parágrafo que começa com minúscula: provavelmente continua o anterior (quebra de
  página ou de coluna).
- Numeração das questões (perfil "perguntas"): faltando ou repetida.
- Diferenças contra um texto de referência digital. A referência só aponta onde olhar;
  a correção vem do exemplar, nunca da referência (#2).
"""

import difflib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from ..ingestao.estrutura import estruturar, resumo
from .limpeza import Paragrafo
from .ortografia import Troca, a_conferir

_PALAVRA = re.compile(r"[\wÀ-ÿ'’-]+")
_DIGITO_NA_PALAVRA = re.compile(r"\b(?=\w*\d)(?=\w*[a-zà-ÿ])\w{2,}\b", re.IGNORECASE)
# Letras e sinais esperados num livro em português; o resto costuma ser ruído de OCR.
_ESPERADOS = re.compile(
    r"[\wÀ-ÿ\s.,;:!?¡¿'’‘\"“”«»()\[\]\-–—…/§ºª°*&%$+=]",
)
_ORDINAIS = re.compile(r"^\d+[ºªo°]$|^\d+[a-z]$")


@dataclass
class Achado:
    pagina: int
    tipo: str
    trecho: str
    detalhe: str = ""


@dataclass
class Relatorio:
    achados: list[Achado] = field(default_factory=list)
    trocas: list[Troca] = field(default_factory=list)
    conferir_circunflexo: list[str] = field(default_factory=list)
    questoes: dict | None = None


def _contexto(texto: str, inicio: int, fim: int, margem: int = 30) -> str:
    a, b = max(0, inicio - margem), min(len(texto), fim + margem)
    return ("…" if a else "") + texto[a:b].replace("\n", " ") + ("…" if b < len(texto) else "")


def suspeitas(paragrafos: list[Paragrafo]) -> list[Achado]:
    achados: list[Achado] = []
    vocabulario = Counter(w.lower() for p in paragrafos for w in _PALAVRA.findall(p.texto))
    for p in paragrafos:
        t = p.texto
        for m in _DIGITO_NA_PALAVRA.finditer(t):
            if not _ORDINAIS.match(m.group(0)):
                achados.append(
                    Achado(p.pagina, "dígito em palavra", m.group(0), _contexto(t, *m.span()))
                )
        estranhos = sorted({c for c in t if not _ESPERADOS.match(c)})
        if estranhos:
            achados.append(Achado(p.pagina, "caractere estranho", "".join(estranhos), t[:80]))
        for m in _PALAVRA.finditer(t):
            w = m.group(0).lower()
            # "rn" lido no lugar de "m" (ou o contrário) quando a outra forma existe no
            # próprio livro e é bem mais comum.
            for a, b in (("rn", "m"), ("m", "rn")):
                if a in w:
                    outra = w.replace(a, b, 1)
                    if vocabulario[outra] >= 3 * max(1, vocabulario[w]):
                        achados.append(
                            Achado(p.pagina, "rn/m", m.group(0), f"mais comum no livro: {outra}")
                        )
        if t[:1].islower():
            achados.append(Achado(p.pagina, "começa com minúscula", t[:60], "juntar ao anterior?"))
    return achados


def _normal(palavra: str) -> str:
    sem = unicodedata.normalize("NFD", palavra.lower())
    return "".join(c for c in sem if unicodedata.category(c) != "Mn")


def diferencas(paragrafos: list[Paragrafo], referencia: str, limite: int = 500) -> list[Achado]:
    """Palavra a palavra, sem acento e sem caixa (a referência costuma ter outra grafia).

    O que sobra é diferença de palavra: erro de OCR, ou revisão que a referência fez e
    o exemplar não tem — por isso só aponta, nunca corrige."""
    palavras: list[tuple[str, int]] = [
        (w, p.pagina) for p in paragrafos for w in _PALAVRA.findall(p.texto)
    ]
    ref = _PALAVRA.findall(referencia)
    a = [_normal(w) for w, _ in palavras]
    b = [_normal(w) for w in ref]
    achados: list[Achado] = []
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        pagina = palavras[min(i1, len(palavras) - 1)][1] if palavras else 0
        ocr_trecho = " ".join(w for w, _ in palavras[i1:i2]) or "∅"
        ref_trecho = " ".join(ref[j1:j2]) or "∅"
        achados.append(Achado(pagina, f"diferença ({op})", ocr_trecho, f"referência: {ref_trecho}"))
        if len(achados) >= limite:
            break
    return achados


def revisar(
    paragrafos: list[Paragrafo],
    trocas: list[Troca] | None = None,
    referencia: str | None = None,
    perfil: str | None = None,
) -> Relatorio:
    texto = "\n".join(p.texto for p in paragrafos)
    rel = Relatorio(
        achados=suspeitas(paragrafos),
        trocas=trocas or [],
        conferir_circunflexo=a_conferir(texto),
    )
    if referencia:
        rel.achados += diferencas(paragrafos, referencia)
    if perfil:
        rel.questoes = resumo(estruturar([p.texto for p in paragrafos], perfil))
        numeros = [
            int(m.group(1)) for p in paragrafos if (m := re.match(r"^(\d{1,4})\s*[.)–-]", p.texto))
        ]
        rel.questoes["questoes_repetidas"] = sorted(n for n, c in Counter(numeros).items() if c > 1)
    rel.achados.sort(key=lambda a: (a.pagina, a.tipo))
    return rel


def como_markdown(rel: Relatorio, titulo: str) -> str:
    linhas = [f"# Revisão: {titulo}", ""]
    if rel.questoes:
        q = rel.questoes
        linhas += [
            "## Questões",
            "",
            f"- Total: {q['questoes']} (de {q['primeira_questao']} a {q['ultima_questao']})",
            f"- Faltando: {', '.join(map(str, q['questoes_faltando'])) or 'nenhuma'}",
            f"- Repetidas: {', '.join(map(str, q['questoes_repetidas'])) or 'nenhuma'}",
            "",
        ]
    linhas += [f"## Achados ({len(rel.achados)})", ""]
    if rel.achados:
        linhas += ["| Página | Tipo | Trecho | Detalhe |", "| --- | --- | --- | --- |"]
        for a in rel.achados:
            cel = [str(a.pagina), a.tipo, a.trecho, a.detalhe]
            linhas.append("| " + " | ".join(c.replace("|", "\\|") for c in cel) + " |")
    else:
        linhas.append("Nenhum.")
    contagem = Counter((t.antes, t.depois, t.regra) for t in rel.trocas)
    linhas += ["", f"## Atualização ortográfica ({len(rel.trocas)} trocas)", ""]
    if contagem:
        linhas += ["| Antes | Depois | Regra | Vezes |", "| --- | --- | --- | --- |"]
        for (antes, depois, regra), n in contagem.most_common():
            linhas.append(f"| {antes} | {depois} | {regra} | {n} |")
    else:
        linhas.append("Nenhuma.")
    linhas += ["", "## Circunflexo a conferir", ""]
    linhas.append(
        ", ".join(rel.conferir_circunflexo)
        + "\n\nPalavras com ê/ô fora das listas: podem estar certas hoje ou ser um diferencial"
        " de 1943 que a lista não tem. Corrija no texto e acrescente a palavra à lista certa"
        " em `ortografia.py`."
        if rel.conferir_circunflexo
        else "Nenhuma."
    )
    return "\n".join(linhas) + "\n"
