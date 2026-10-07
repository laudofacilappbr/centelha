"""Cruza duas transcrições da mesma obra e aponta onde elas discordam (#45).

    centelha-cruzar wikisource.epub gallica.txt --perfil perguntas --saida cruzamento.md

As duas fontes passam pela mesma ingestão (EPUB, PDF, TXT, DOCX). As questões são
casadas por número, subquestão e tipo; o texto fora das questões (introdução,
comentários de capítulo), por capítulo na ordem. A comparação é palavra a palavra:
apóstrofo, aspas, espaços, ligaduras e pontuação não contam; acento e caixa contam,
mas ficam numa lista à parte.

O relatório só aponta onde olhar. Quem decide é a revisão, olhando o fac-símile: nenhuma
das duas fontes é a referência da outra.
"""

import argparse
import difflib
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from ...models import TipoSegmento
from .estrutura import CapituloBruto, estruturar
from .leitores import ler

_PALAVRA = re.compile(r"[^\W_]+(?:['-][^\W_]+)*")
_TIPOGRAFIA = str.maketrans(
    {"’": "'", "‘": "'", "ʼ": "'", "œ": "oe", "Œ": "Oe", "æ": "ae", "Æ": "Ae"}
)


def palavras(texto: str) -> list[str]:
    """Palavras sem pontuação, com apóstrofo e ligadura num formato só."""
    return _PALAVRA.findall(unicodedata.normalize("NFC", texto).translate(_TIPOGRAFIA))


def _dobrada(palavra: str) -> str:
    """Sem acento e sem caixa: o que alinha as duas fontes."""
    sem = unicodedata.normalize("NFD", palavra.casefold())
    return "".join(c for c in sem if unicodedata.category(c) != "Mn")


@dataclass
class Diferenca:
    onde: str
    a: str
    b: str
    so_acento: bool = False


@dataclass
class Cruzamento:
    so_em_a: list[str] = field(default_factory=list)
    so_em_b: list[str] = field(default_factory=list)
    comparados: int = 0
    diferencas: list[Diferenca] = field(default_factory=list)

    @property
    def com_diferenca(self) -> int:
        return len({d.onde for d in self.diferencas})


def _diff(pa: list[str], onde_a: list[str], pb: list[str], margem: int = 3) -> list[Diferenca]:
    """Diferenças entre as palavras de A e de B; cada uma leva o rótulo do trecho de A
    onde cai (ou do anterior, quando é palavra que só B tem)."""
    da, db = [_dobrada(p) for p in pa], [_dobrada(p) for p in pb]

    def onde(i: int) -> str:
        return onde_a[min(i, len(onde_a) - 1)] if onde_a else "texto"

    achados: list[Diferenca] = []
    sm = difflib.SequenceMatcher(None, da, db, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            # Iguais sem acento e caixa: sobra ver se diferem com eles.
            k = 0
            while k < i2 - i1:
                if pa[i1 + k] == pb[j1 + k]:
                    k += 1
                    continue
                fim = k
                while fim < i2 - i1 and pa[i1 + fim] != pb[j1 + fim]:
                    fim += 1
                achados.append(
                    Diferenca(
                        onde(i1 + k),
                        " ".join(pa[i1 + k : i1 + fim]),
                        " ".join(pb[j1 + k : j1 + fim]),
                        so_acento=True,
                    )
                )
                k = fim
            continue
        # Contexto: as palavras iguais em volta, para achar o trecho no fac-símile.
        antes = " ".join(pa[max(0, i1 - margem) : i1])
        depois = " ".join(pa[i2 : i2 + margem])
        trecho_a = " ".join(pa[i1:i2]) or "∅"
        trecho_b = " ".join(pb[j1:j2]) or "∅"
        achados.append(
            Diferenca(
                onde(i1 if i2 > i1 else max(i1 - 1, 0)),
                f"{antes} [{trecho_a}] {depois}".strip(),
                f"[{trecho_b}]",
            )
        )
    return achados


def comparar_textos(a: str, b: str, onde: str, margem: int = 3) -> list[Diferenca]:
    pa = palavras(a)
    return _diff(pa, [onde] * len(pa), palavras(b), margem)


def _rotulo(s, n_cap: int, titulo: str) -> str:
    if s.numero_questao is None:
        return f"cap. {n_cap} ({titulo[:60]})"
    return f"{s.numero_questao}{s.subquestao or ''} · {s.tipo.value}"


def _palavras_rotuladas(
    capitulos: list[CapituloBruto], primeiro: int
) -> tuple[list[str], list[str]]:
    """Todas as palavras dos capítulos, menos os títulos (cada fonte escreve o seu), com o
    rótulo do trecho de cada uma."""
    ps: list[str] = []
    rotulos: list[str] = []
    for n, c in enumerate(capitulos, start=primeiro):
        for s in c.segmentos:
            if s.tipo == TipoSegmento.TITULO:
                continue
            w = palavras(s.texto)
            ps += w
            rotulos += [_rotulo(s, n, c.titulo)] * len(w)
    return ps, rotulos


def _numeros(capitulos: list[CapituloBruto]) -> set[str]:
    return {
        f"{s.numero_questao}{s.subquestao or ''}"
        for c in capitulos
        for s in c.segmentos
        if s.numero_questao is not None
    }


def cruzar(a: list[CapituloBruto], b: list[CapituloBruto]) -> Cruzamento:
    """Alinha o texto corrido, não segmento com segmento: as duas fontes podem estruturar
    diferente (um subtítulo que numa é parágrafo e na outra comentário), e isso não é
    diferença de texto. Com o mesmo número de capítulos, alinha capítulo a capítulo;
    senão, o livro inteiro de uma vez."""
    r = Cruzamento()
    na, nb = _numeros(a), _numeros(b)
    ordem = lambda x: (int(re.match(r"\d+", x)[0]), x)  # noqa: E731
    r.so_em_a, r.so_em_b = sorted(na - nb, key=ordem), sorted(nb - na, key=ordem)
    pares = (
        list(zip(([c] for c in a), ([c] for c in b), strict=True)) if len(a) == len(b) else [(a, b)]
    )
    if len(a) != len(b):
        r.diferencas.append(Diferenca("estrutura", f"{len(a)} capítulos", f"{len(b)} capítulos"))
    inicio = 1
    for ca, cb in pares:
        pa, rotulos = _palavras_rotuladas(ca, inicio)
        pb, _ = _palavras_rotuladas(cb, inicio)
        r.comparados += len(set(rotulos))
        r.diferencas += _diff(pa, rotulos, pb)
        inicio += len(ca)
    return r


def _tabela(linhas: list[Diferenca], limite: int) -> list[str]:
    if not linhas:
        return ["Nenhuma.", ""]
    saida = ["| Onde | A | B |", "| --- | --- | --- |"]
    for d in linhas[:limite]:
        cel = [d.onde, d.a, d.b]
        saida.append("| " + " | ".join(c.replace("|", "\\|") for c in cel) + " |")
    if len(linhas) > limite:
        saida.append(f"\n… e mais {len(linhas) - limite}.")
    return [*saida, ""]


def como_markdown(r: Cruzamento, nome_a: str, nome_b: str, limite: int = 2000) -> str:
    palavra = [d for d in r.diferencas if not d.so_acento]
    acento = [d for d in r.diferencas if d.so_acento]
    return "\n".join(
        [
            f"# Cruzamento: {nome_a} × {nome_b}",
            "",
            "Aponta onde as fontes discordam; a decisão é da revisão, no fac-símile.",
            "",
            f"- **A:** {nome_a}",
            f"- **B:** {nome_b}",
            f"- Questões só em A: {', '.join(r.so_em_a) or 'nenhuma'}",
            f"- Questões só em B: {', '.join(r.so_em_b) or 'nenhuma'}",
            f"- Trechos comparados: {r.comparados}; com diferença: {r.com_diferenca}",
            "",
            f"## Palavras diferentes ({len(palavra)})",
            "",
            *_tabela(palavra, limite),
            f"## Só acento ou caixa ({len(acento)})",
            "",
            *_tabela(acento, limite),
        ]
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="centelha-cruzar", description=__doc__.splitlines()[0])
    p.add_argument("a", type=Path)
    p.add_argument("b", type=Path)
    p.add_argument("--perfil", choices=["generico", "perguntas"], default="generico")
    p.add_argument("--saida", type=Path, help="relatório em Markdown (padrão: tela)")
    args = p.parse_args(argv)
    try:
        a = estruturar(ler(args.a), args.perfil)
        b = estruturar(ler(args.b), args.perfil)
    except (OSError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1
    r = cruzar(a, b)
    texto = como_markdown(r, args.a.name, args.b.name)
    if args.saida:
        args.saida.write_text(texto, encoding="utf-8")
        palavra = sum(1 for d in r.diferencas if not d.so_acento)
        print(
            f"{r.comparados} trechos comparados, {r.com_diferenca} com diferença "
            f"({palavra} de palavra); relatório em {args.saida}"
        )
    else:
        sys.stdout.write(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
