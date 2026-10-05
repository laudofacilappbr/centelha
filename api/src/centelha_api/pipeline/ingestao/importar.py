from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...models import Capitulo, Edicao, EstadoCapitulo, Segmento
from .estrutura import CapituloBruto


class ImportacaoRecusada(Exception):
    pass


def importar(
    session: Session, edicao: Edicao, capitulos: list[CapituloBruto], substituir: bool = False
) -> list[Capitulo]:
    """Grava capítulos e segmentos no estado "importado".

    Substituir só é permitido enquanto nenhum capítulo passou da revisão de texto:
    depois disso há trabalho humano e áudio que não podem ser apagados por reimportação.
    """
    existentes = session.scalars(select(Capitulo).where(Capitulo.edicao_id == edicao.id)).all()
    if existentes:
        if not substituir:
            raise ImportacaoRecusada(
                f"edição {edicao.id} já tem {len(existentes)} capítulos; use substituir"
            )
        avancados = [c.ordem for c in existentes if c.estado != EstadoCapitulo.IMPORTADO]
        if avancados:
            raise ImportacaoRecusada(f"capítulos já revisados, não substituo: {avancados}")
        ids = [c.id for c in existentes]
        session.execute(delete(Segmento).where(Segmento.capitulo_id.in_(ids)))
        session.execute(delete(Capitulo).where(Capitulo.id.in_(ids)))
        session.flush()

    sigla = edicao.obra.sigla
    criados = []
    for ordem, bruto in enumerate(capitulos, start=1):
        capitulo = Capitulo(
            edicao_id=edicao.id,
            ordem=ordem,
            titulo=bruto.titulo[:300],
            referencia_canonica=f"{sigla}-C{ordem:03d}",
            estado=EstadoCapitulo.IMPORTADO,
        )
        capitulo.segmentos = [
            Segmento(
                ordem=n,
                tipo=s.tipo,
                texto=s.texto,
                numero_questao=s.numero_questao,
                subquestao=s.subquestao,
            )
            for n, s in enumerate(bruto.segmentos, start=1)
        ]
        session.add(capitulo)
        criados.append(capitulo)
    session.flush()
    return criados
