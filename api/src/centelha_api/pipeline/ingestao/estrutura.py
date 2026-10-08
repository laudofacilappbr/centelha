"""Transforma parágrafos em capítulos e segmentos.

Reconhece os títulos em português e em francês.

Perfis:
- "generico": parágrafos narrados em sequência (O Evangelho, A Gênese...).
- "perguntas": O Livro dos Espíritos e O Livro dos Médiuns — pergunta numerada,
  resposta dos Espíritos (entre aspas) e comentário de Kardec, com subquestões (88a).

O resultado é revisado lado a lado com a fonte no admin; heurística errada aqui vira
correção manual lá, nunca texto publicado sem revisão.
"""

import re
from dataclasses import dataclass, field

from ...models import TipoSegmento
from .leitores import Nota, Subtitulo


@dataclass
class SegmentoBruto:
    tipo: TipoSegmento
    texto: str
    numero_questao: int | None = None
    subquestao: str | None = None
    # Número deduzido pela posição, não lido no texto ("impresso 647", "sem número").
    numero_inferido: str | None = None


@dataclass
class CapituloBruto:
    titulo: str
    segmentos: list[SegmentoBruto] = field(default_factory=list)


# Português e francês (originais de Kardec: "LIVRE PREMIER", "CHAPITRE PREMIER",
# "PREMIÈRE PARTIE").
_ORDINAIS = (
    r"primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|quint[oa]|sext[oa]|sétim[oa]|oitav[oa]"
    r"|non[oa]|décim[oa]|únic[oa]"
    r"|premier|première|second|seconde|deuxième|troisième|quatrième|cinquième|sixième"
    r"|septième|huitième|neuvième|dixième|unique"
)
_ROMANO_OU_ORDINAL = rf"(?:[IVXLCDM]+|{_ORDINAIS}|\d+)"
_FIM_ROTULO = r"\b\.?\s*(?:[—–:.-]\s*)?(?P<resto>.*)$"
_RE_CAPITULO = re.compile(
    rf"^(?P<rotulo>(?:cap[íi]tulo|chapitre)\s+{_ROMANO_OU_ORDINAL}){_FIM_ROTULO}",
    re.IGNORECASE,
)
_RE_DIVISAO = re.compile(
    rf"^(?P<rotulo>(?:livro|parte|livre|partie)\s+{_ROMANO_OU_ORDINAL}"
    rf"|(?:{_ORDINAIS})\s+(?:parte|partie)){_FIM_ROTULO}",
    re.IGNORECASE,
)
_SECOES_AVULSAS = {
    "introdução", "prolegômenos", "conclusão", "prefácio", "preâmbulo", "nota", "advertência",
    "introdução ao estudo da doutrina espírita",
    "introduction", "prolégomènes", "conclusion", "préface", "préambule", "avant-propos",
    "avertissement", "introduction à l'étude de la doctrine spirite",
    "avis sur cette nouvelle édition",
}  # fmt: skip
# Abre capítulo só antes do primeiro capítulo numerado; depois é seção dentro dele (o
# "Preâmbulo" do cap. XXVIII de O Evangelho).
_SO_ANTES_DOS_CAPITULOS = {"preâmbulo", "préambule"}
# Título espaçado da FEB: "I N T R O D U Ç Ã O".
_LETRAS_ESPACADAS = re.compile(r"^(?:\w ){3,}\w$")

# "(?!\d)": "2.000 léguas", na Introdução, é milhar, não a questão 2.
_RE_PERGUNTA = re.compile(r"^(?P<n>\d{1,4})\s*[.)–-](?!\d)\s*(?P<texto>.+)$")
# Sumário do capítulo na FEB: "1. Deus e o infinito. - 2. Provas da existência de Deus."
# No começo do livro, sem questão anterior, ele tomaria o lugar da questão 1.
_RE_SUMARIO = re.compile(r"^1\s*\.\s.*\s[-–]\s*2\s*\.\s")
# Pergunta sem número, aberta por hífen: a 1011 no PDF da FEB ("- Assim, pelo dogma...?").
_RE_SEM_NUMERO = re.compile(r"^[-–]\s*(?P<texto>.+\?)$")
# Até onde procurar a próxima questão numerada ao deduzir um número que falta.
_ALCANCE_PROXIMA = 40
_RE_SUBQUESTAO = re.compile(
    r"^(?:(?P<n>\d{1,4})\s*[.\-–]?\s*)?(?P<letra>[a-z])\)\s*[—–-]?\s*(?P<texto>.+)$"
)
_ABRE_CITACAO = ("“", '"', "«", "—", "–")
# Original francês de 1860: a pergunta que continua a anterior abre com "―" (U+2015), sem
# letra; a FEB numerou essas perguntas com a), b)... Aqui ganham letra na ordem.
_RE_SEGUIMENTO = re.compile(r"^―\s*(?P<texto>.+)$")


def _e_titulo_curto(p: str) -> bool:
    return len(p) <= 90 and not p.endswith((".", "?", "!", ":", ";", ",")) or p.isupper()


def _e_subtitulo(ligacao: str, nome: str) -> bool:
    return (
        not isinstance(ligacao, Nota)
        and len(ligacao) <= 30
        and ligacao[:1].islower()
        and len(nome) <= 40
        and nome.isupper()
    )


def _titulo_composto(rotulo: str, resto: str, proximo: str | None) -> tuple[str, bool]:
    """Junta "CAPÍTULO I" com o nome na linha seguinte. Devolve (título, consumiu_proximo)."""
    if rotulo.islower():
        # Versalete do PDF vem em minúsculas: "capítulo xiv" → "Capítulo XIV".
        palavra, _, numero = rotulo.partition(" ")
        numero = numero.upper() if re.fullmatch(r"[ivxlcdm]+", numero) else numero
        rotulo = f"{palavra.capitalize()} {numero}"
    if resto:
        return f"{rotulo} — {resto}", False
    if proximo and len(proximo) <= 90 and _e_titulo_curto(proximo):
        if not (_RE_CAPITULO.match(proximo) or _RE_DIVISAO.match(proximo)):
            return f"{rotulo} — {proximo}", True
    return rotulo, False


def _proxima_numerada(paragrafos: list[str], inicio: int, acima_de: int) -> int | None:
    for p in paragrafos[inicio : inicio + _ALCANCE_PROXIMA]:
        if (m := _RE_PERGUNTA.match(p)) and int(m["n"]) > acima_de:
            return int(m["n"])
    return None


def _numero_que_falta(
    paragrafos: list[str], i: int, ultima_questao: int | None
) -> tuple[str, str] | None:
    """Pergunta com número trocado na impressão ("647." entre a 673 e a 675) ou sem
    número ("- Assim...?" entre a 1010 e a 1012). Só quando falta exatamente um número e
    ela está no lugar dele; devolve o texto e o motivo, que vai para o resumo."""
    p = paragrafos[i]
    if ultima_questao is None or not p.rstrip().endswith("?"):
        return None
    if m := _RE_PERGUNTA.match(p):
        if int(m["n"]) > ultima_questao:
            return None
        texto, motivo = m["texto"], f"impresso {m['n']}"
    elif m := _RE_SEM_NUMERO.match(p):
        texto, motivo = m["texto"], "sem número"
    else:
        return None
    if _proxima_numerada(paragrafos, i + 1, ultima_questao) != ultima_questao + 2:
        return None
    return texto, motivo


def estruturar(paragrafos: list[str], perfil: str = "generico") -> list[CapituloBruto]:
    if perfil not in ("generico", "perguntas"):
        raise ValueError(f"perfil desconhecido: {perfil}")
    capitulos: list[CapituloBruto] = []
    divisao: str | None = None
    atual: CapituloBruto | None = None
    ultima_questao: int | None = None
    viu_capitulo = False
    # Estado do perfil "perguntas": o que o próximo parágrafo provavelmente é.
    esperando_resposta = False
    dentro_da_resposta = False

    def novo_capitulo(titulo: str) -> CapituloBruto:
        nonlocal esperando_resposta, dentro_da_resposta
        esperando_resposta = dentro_da_resposta = False
        completo = f"{divisao} — {titulo}" if divisao else titulo
        cap = CapituloBruto(titulo=completo)
        cap.segmentos.append(SegmentoBruto(TipoSegmento.TITULO, titulo))
        capitulos.append(cap)
        return cap

    i = 0
    while i < len(paragrafos):
        p = paragrafos[i]
        if _LETRAS_ESPACADAS.match(p) and not isinstance(p, Nota):
            p = p.replace(" ", "")
        proximo = paragrafos[i + 1] if i + 1 < len(paragrafos) else None

        if isinstance(p, Nota):
            # Nota de rodapé não é título nem pergunta, e não interrompe a resposta em curso.
            if atual is None:
                atual = novo_capitulo(divisao or "Abertura")
            ultimo = atual.segmentos[-1]
            atual.segmentos.append(
                SegmentoBruto(TipoSegmento.NOTA, p, ultimo.numero_questao, ultimo.subquestao)
            )
            i += 1
            continue
        if m := _RE_DIVISAO.match(p):
            titulo, consumiu = _titulo_composto(m["rotulo"], m["resto"], proximo)
            divisao = titulo
            atual = None
            i += 2 if consumiu else 1
            continue
        if m := _RE_CAPITULO.match(p):
            titulo, consumiu = _titulo_composto(m["rotulo"], m["resto"], proximo)
            atual = novo_capitulo(titulo)
            viu_capitulo = True
            i += 2 if consumiu else 1
            continue
        chave = p.lower().rstrip(".").replace("’", "'")
        if chave in _SECOES_AVULSAS and not (viu_capitulo and chave in _SO_ANTES_DOS_CAPITULOS):
            divisao = None
            i += 1
            # Subtítulo partido em linhas: "INTRODUÇÃO" / "ao estudo da" / "DOUTRINA ESPÍRITA".
            if i + 1 < len(paragrafos) and _e_subtitulo(paragrafos[i], paragrafos[i + 1]):
                p = f"{p} {paragrafos[i]} {paragrafos[i + 1]}"
                i += 2
            atual = novo_capitulo(p)
            continue

        if atual is None:
            # Texto antes do primeiro capítulo (folha de rosto, abertura da parte).
            atual = novo_capitulo(divisao or "Abertura")

        if isinstance(p, Subtitulo):
            atual.segmentos.append(SegmentoBruto(TipoSegmento.PARAGRAFO, p))
            esperando_resposta = dentro_da_resposta = False
            i += 1
            continue

        if perfil == "perguntas":
            if m := _RE_SUBQUESTAO.match(p):
                if m["n"]:
                    ultima_questao = int(m["n"])
                atual.segmentos.append(
                    SegmentoBruto(TipoSegmento.PERGUNTA, m["texto"], ultima_questao, m["letra"])
                )
                esperando_resposta, dentro_da_resposta = True, False
                i += 1
                continue
            if (m := _RE_SEGUIMENTO.match(p)) and ultima_questao is not None:
                letras = [
                    s.subquestao
                    for s in atual.segmentos
                    if s.numero_questao == ultima_questao and s.subquestao
                ]
                letra = chr(ord(max(letras)) + 1) if letras else "a"
                atual.segmentos.append(
                    SegmentoBruto(TipoSegmento.PERGUNTA, m["texto"], ultima_questao, letra)
                )
                esperando_resposta, dentro_da_resposta = True, False
                i += 1
                continue
            if deduzida := _numero_que_falta(paragrafos, i, ultima_questao):
                texto, motivo = deduzida
                ultima_questao += 1
                atual.segmentos.append(
                    SegmentoBruto(
                        TipoSegmento.PERGUNTA, texto, ultima_questao, numero_inferido=motivo
                    )
                )
                esperando_resposta, dentro_da_resposta = True, False
                i += 1
                continue
            # A numeração das questões só cresce: "1. D'où vient..." dentro de um
            # comentário de Kardec é lista, não a questão 1 de novo.
            if (
                (m := _RE_PERGUNTA.match(p))
                and (ultima_questao is None or int(m["n"]) > ultima_questao)
                and not _RE_SUMARIO.match(p)
            ):
                ultima_questao = int(m["n"])
                atual.segmentos.append(
                    SegmentoBruto(TipoSegmento.PERGUNTA, m["texto"], ultima_questao)
                )
                esperando_resposta, dentro_da_resposta = True, False
                i += 1
                continue
            ultimo = atual.segmentos[-1]
            if esperando_resposta or (dentro_da_resposta and p.startswith(_ABRE_CITACAO)):
                atual.segmentos.append(
                    SegmentoBruto(
                        TipoSegmento.RESPOSTA, p, ultimo.numero_questao, ultimo.subquestao
                    )
                )
                esperando_resposta, dentro_da_resposta = False, True
                i += 1
                continue
            if dentro_da_resposta:
                atual.segmentos.append(
                    SegmentoBruto(
                        TipoSegmento.COMENTARIO, p, ultimo.numero_questao, ultimo.subquestao
                    )
                )
                i += 1
                continue

        atual.segmentos.append(SegmentoBruto(TipoSegmento.PARAGRAFO, p))
        i += 1

    return [c for c in capitulos if len(c.segmentos) > 1 or c is capitulos[-1]]


def resumo(capitulos: list[CapituloBruto]) -> dict:
    segmentos = [s for c in capitulos for s in c.segmentos]
    questoes = {s.numero_questao for s in segmentos if s.numero_questao is not None}
    # Buraco na numeração é o sinal mais barato de parágrafo mal classificado.
    faltando = sorted(set(range(min(questoes), max(questoes) + 1)) - questoes) if questoes else []
    return {
        "capitulos": len(capitulos),
        "segmentos": len(segmentos),
        "questoes": len(questoes),
        "primeira_questao": min(questoes, default=None),
        "ultima_questao": max(questoes, default=None),
        "questoes_faltando": faltando,
        # Conferir no fac-símile: o número foi deduzido pela posição.
        "questoes_inferidas": {
            s.numero_questao: s.numero_inferido for s in segmentos if s.numero_inferido
        },
        "caracteres": sum(len(s.texto) for s in segmentos),
        "por_tipo": {
            t.value: sum(1 for s in segmentos if s.tipo == t)
            for t in TipoSegmento
            if any(s.tipo == t for s in segmentos)
        },
    }
