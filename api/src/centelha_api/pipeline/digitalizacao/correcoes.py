"""Correções da revisão humana, num arquivo versionado, aplicadas depois da limpeza.

Corrigir direto no texto.txt perde a revisão a cada OCR ou limpeza refeitos. Aqui cada
correção diz a página do exemplar, o que o OCR leu e o que está impresso, e é aplicada
de novo a cada "processar":

    # comentário
    p. 422: CHAPITRE XXVIIT => CHAPITRE XXVIII
    p. 12: juntar: suite du paragraphe
    p. 72: apagar: 96 CHAPITRE III.

A página é a do **começo do parágrafo**, a mesma que o revisao.md mostra: um parágrafo
que vira a página fica inteiro na página onde começa.

- "trecho lido => trecho certo": o trecho tem de aparecer **uma vez só** nos parágrafos
  daquela página. Se não aparece (a limpeza mudou, ou já foi corrigido) ou aparece mais
  de uma vez, é erro: correção que passa calada é revisão perdida sem ninguém ver.
- "juntar: começo do parágrafo": o parágrafo da página que começa assim continua o
  anterior (virada de página ou linha em branco que o OCR pôs no meio).
- "apagar: começo do parágrafo": o parágrafo não é texto do livro (cabeçalho com o
  número mal lido, que a limpeza não reconheceu, ou sujeira da margem). Costuma vir com
  um "juntar:" do parágrafo seguinte, que estava partido por ele.

Ordem: trocas, depois apagar, depois juntar. O arquivo é escrito olhando o texto já
corrigido, e a junção tem de cair no parágrafo de antes do que foi apagado.

Só erro de leitura: o arquivo não troca redação (regra da skill de digitalização).
"""

import re
from dataclasses import dataclass

from .limpeza import Paragrafo

_LINHA = re.compile(r"^p\.\s*(\d+)\s*:\s*(.+)$")
_JUNTAR = "juntar:"
_APAGAR = "apagar:"
_ORDEM = {"trocar": 0, "apagar": 1, "juntar": 2}
_SETA = "=>"


class ErroCorrecao(ValueError):
    """Uma ou mais correções não puderam ser aplicadas; a mensagem lista cada uma."""


@dataclass(frozen=True)
class Correcao:
    linha: int
    pagina: int
    lido: str
    certo: str | None  # só nas trocas
    acao: str = "trocar"  # trocar, apagar ou juntar

    def __str__(self) -> str:
        acao = (
            f"{self.lido} => {self.certo}" if self.acao == "trocar" else f"{self.acao}: {self.lido}"
        )
        return f"linha {self.linha} (p. {self.pagina}: {acao})"


def ler(texto: str) -> list[Correcao]:
    correcoes, erros = [], []
    for n, bruta in enumerate(texto.splitlines(), 1):
        linha = bruta.strip()
        if not linha or linha.startswith("#"):
            continue
        m = _LINHA.match(linha)
        if not m:
            erros.append(
                f"linha {n}: esperado 'p. <página>: <lido> => <certo>', 'juntar:' ou 'apagar:'"
            )
            continue
        pagina, resto = int(m.group(1)), m.group(2)
        if resto.startswith((_JUNTAR, _APAGAR)):
            acao = resto[: resto.index(":")]
            inicio = resto[len(acao) + 1 :].strip()
            if not inicio:
                erros.append(f"linha {n}: '{acao}:' sem o começo do parágrafo")
                continue
            correcoes.append(Correcao(n, pagina, inicio, None, acao))
        elif resto.count(_SETA) == 1:
            lido, certo = (s.strip() for s in resto.split(_SETA))
            if not lido or lido == certo:
                erros.append(f"linha {n}: trecho lido vazio ou igual ao certo")
                continue
            correcoes.append(Correcao(n, pagina, lido, certo))
        else:
            erros.append(f"linha {n}: use '=>' uma vez, entre o lido e o certo")
    if erros:
        raise ErroCorrecao("\n".join(erros))
    return correcoes


def aplicar(paragrafos: list[Paragrafo], correcoes: list[Correcao]) -> list[Paragrafo]:
    """Devolve os parágrafos corrigidos, ou ErroCorrecao com todas as que falharam."""
    textos = [p.texto for p in paragrafos]
    paginas = [p.pagina for p in paragrafos]
    erros = []
    for c in sorted(correcoes, key=lambda c: _ORDEM[c.acao]):
        da_pagina = [i for i, pg in enumerate(paginas) if pg == c.pagina and textos[i] is not None]
        if c.acao == "trocar":
            onde = [i for i in da_pagina if c.lido in textos[i]]
            vezes = sum(textos[i].count(c.lido) for i in onde)
            if vezes != 1:
                erros.append(f"{c}: o trecho aparece {vezes} vez(es) na página, esperado 1")
                continue
            textos[onde[0]] = textos[onde[0]].replace(c.lido, c.certo)
        else:
            onde = [i for i in da_pagina if textos[i].startswith(c.lido)]
            if len(onde) != 1:
                erros.append(f"{c}: {len(onde)} parágrafo(s) começam assim na página, esperado 1")
                continue
            i = onde[0]
            if c.acao == "apagar":
                textos[i] = None
                continue
            antes = [j for j in range(i) if textos[j] is not None]
            if not antes:
                erros.append(f"{c}: não há parágrafo antes para juntar")
                continue
            anterior = antes[-1]
            textos[anterior] = f"{textos[anterior]} {textos[i]}"
            textos[i] = None
    if erros:
        raise ErroCorrecao("\n".join(erros))
    return [Paragrafo(pg, t) for pg, t in zip(paginas, textos, strict=True) if t is not None]
