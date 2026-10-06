"""Resolve as referências de um tema para o conteúdo publicado (#42).

O público só vê referência que aponta para capítulo publicado de edição visível
(publicada e com direitos aprovados): um tema não pode ser porta dos fundos para
texto que o catálogo esconde. O admin vê também as que não resolvem, para corrigir.
"""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    Capitulo,
    Direitos,
    Edicao,
    EstadoCapitulo,
    Obra,
    Publico,
    Segmento,
    StatusDireitos,
)

# "LE-88", "LE-88a" (questão) ou "LE-C001" (capítulo).
PADRAO = re.compile(r"^([A-Z]{1,10})-(?:(\d+)([a-z]?)|(C\d{3}))$")


class ReferenciaInvalida(ValueError):
    pass


@dataclass
class Resolvida:
    referencia: str
    tipo: str  # "questao" | "capitulo"
    obra_slug: str
    edicao_id: int
    capitulo_id: int
    capitulo_ordem: int
    titulo: str
    numero_questao: int | None


def validar(referencia: str) -> str:
    ref = referencia.strip()
    if not PADRAO.match(ref):
        raise ReferenciaInvalida(
            f"referência inválida: {referencia!r} (ex.: LE-88, LE-88a, ESE-C005)"
        )
    return ref


def _visivel():
    return (
        (Capitulo.estado == EstadoCapitulo.PUBLICADO)
        & Edicao.publicada_em.is_not(None)
        & Edicao.direitos.has(Direitos.status == StatusDireitos.APROVADO)
    )


def resolver(session: Session, referencias: list[str], idioma: str) -> dict[str, Resolvida]:
    """Referências que apontam para conteúdo publicado no idioma; as outras ficam de fora."""
    saida: dict[str, Resolvida] = {}
    for ref in referencias:
        m = PADRAO.match(ref)
        if not m:
            continue
        sigla, numero, sub, cap_ref = m.groups()
        base = (
            select(Capitulo, Obra.slug)
            .join(Edicao, Edicao.id == Capitulo.edicao_id)
            .join(Obra, Obra.id == Edicao.obra_id)
            .where(Obra.sigla == sigla, Edicao.idioma == idioma, _visivel())
            # Com edição adulta e juvenil no mesmo idioma, o tema aponta para a adulta.
            .order_by((Edicao.publico != Publico.ADULTO), Edicao.id)
        )
        if cap_ref:
            linha = session.execute(
                base.where(Capitulo.referencia_canonica == ref).limit(1)
            ).first()
            if linha:
                cap, slug = linha
                saida[ref] = Resolvida(
                    ref, "capitulo", slug, cap.edicao_id, cap.id, cap.ordem, cap.titulo, None
                )
            continue
        linha = session.execute(
            base.join(Segmento, Segmento.capitulo_id == Capitulo.id)
            .where(
                Segmento.numero_questao == int(numero),
                Segmento.subquestao.is_(None) if not sub else Segmento.subquestao == sub,
            )
            .add_columns(Segmento.texto)
            .order_by(Segmento.ordem)
            .limit(1)
        ).first()
        if linha:
            cap, slug, texto = linha
            titulo = texto if len(texto) <= 160 else texto[:157].rsplit(" ", 1)[0] + "…"
            saida[ref] = Resolvida(
                ref, "questao", slug, cap.edicao_id, cap.id, cap.ordem, titulo, int(numero)
            )
    return saida
