"""SEO de edição e capítulo no admin (#42); o do post vai junto com o post.

Fica na edição, não na obra: a obra não tem idioma, e o título que responde a uma
busca ("O Livro dos Espíritos em áudio") é de uma língua só. Assim /es e /fr (#48)
ganham o próprio texto sem outra migração.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..dominio import contas
from ..dominio.permissoes import Permissao
from ..dominio.seo import CamposSeo
from ..models import Capitulo, Edicao, Usuario
from ..ratelimit import ip_do_cliente
from .admin import exigir

router = APIRouter(prefix="/v1/admin", tags=["admin"])
pode_editar = exigir(Permissao.EDITAR_CONTEUDO)


def _aplicar(session, request, autor, alvo, tipo: str, dados: CamposSeo) -> CamposSeo:
    antes = CamposSeo.model_validate(alvo, from_attributes=True).model_dump()
    alvo.seo_titulo, alvo.seo_descricao = dados.seo_titulo, dados.seo_descricao
    contas.registrar(
        session, "seo_alterado", autor, tipo, alvo.id, ip_do_cliente(request),
        antes=antes, depois=dados.model_dump(),
    )  # fmt: skip
    session.commit()
    return CamposSeo.model_validate(alvo, from_attributes=True)


@router.put("/edicoes/{edicao_id}/seo")
def seo_edicao(
    edicao_id: int,
    dados: CamposSeo,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> CamposSeo:
    edicao = session.get(Edicao, edicao_id)
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "edição não encontrada")
    return _aplicar(session, request, autor, edicao, "edicao", dados)


@router.put("/capitulos/{capitulo_id}/seo")
def seo_capitulo(
    capitulo_id: int,
    dados: CamposSeo,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> CamposSeo:
    capitulo = session.get(Capitulo, capitulo_id)
    if capitulo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "capítulo não encontrado")
    return _aplicar(session, request, autor, capitulo, "capitulo", dados)
