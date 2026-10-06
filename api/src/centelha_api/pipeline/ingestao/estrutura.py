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


@dataclass
class SegmentoBruto:
    tipo: TipoSegmento
    texto: str
    numero_questao: int | None = None
    subquestao: str | None = None


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
}  # fmt: skip

_RE_PERGUNTA = re.compile(r"^(?P<n>\d{1,4})\s*[.)–-]\s*(?P<texto>.+)$")
_RE_SUBQUESTAO = re.compile(
    r"^(?:(?P<n>\d{1,4})\s*[.\-–]?\s*)?(?P<letra>[a-z])\)\s*[—–-]?\s*(?P<texto>.+)$"
)
_ABRE_CITACAO = ("“", '"', "«", "—", "–")


def _e_titulo_curto(p: str) -> bool:
    return len(p) <= 90 and not p.endswith((".", "?", "!", ":", ";", ",")) or p.isupper()


def _titulo_composto(rotulo: str, resto: str, proximo: str | None) -> tuple[str, bool]:
    """Junta "CAPÍTULO I" com o nome na linha seguinte. Devolve (título, consumiu_proximo)."""
    if resto:
        return f"{rotulo} — {resto}", False
    if proximo and len(proximo) <= 90 and _e_titulo_curto(proximo):
        if not (_RE_CAPITULO.match(proximo) or _RE_DIVISAO.match(proximo)):
            return f"{rotulo} — {proximo}", True
    return rotulo, False


def estruturar(paragrafos: list[str], perfil: str = "generico") -> list[CapituloBruto]:
    if perfil not in ("generico", "perguntas"):
        raise ValueError(f"perfil desconhecido: {perfil}")
    capitulos: list[CapituloBruto] = []
    divisao: str | None = None
    atual: CapituloBruto | None = None
    ultima_questao: int | None = None
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
        proximo = paragrafos[i + 1] if i + 1 < len(paragrafos) else None

        if m := _RE_DIVISAO.match(p):
            titulo, consumiu = _titulo_composto(m["rotulo"], m["resto"], proximo)
            divisao = titulo
            atual = None
            i += 2 if consumiu else 1
            continue
        if m := _RE_CAPITULO.match(p):
            titulo, consumiu = _titulo_composto(m["rotulo"], m["resto"], proximo)
            atual = novo_capitulo(titulo)
            i += 2 if consumiu else 1
            continue
        if p.lower().rstrip(".").replace("’", "'") in _SECOES_AVULSAS:
            divisao = None
            atual = novo_capitulo(p)
            i += 1
            continue

        if atual is None:
            # Texto antes do primeiro capítulo (folha de rosto, abertura da parte).
            atual = novo_capitulo(divisao or "Abertura")

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
            if m := _RE_PERGUNTA.match(p):
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
        "caracteres": sum(len(s.texto) for s in segmentos),
        "por_tipo": {
            t.value: sum(1 for s in segmentos if s.tipo == t)
            for t in TipoSegmento
            if any(s.tipo == t for s in segmentos)
        },
    }
