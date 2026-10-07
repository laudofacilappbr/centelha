"""Admin: liberar o download em formato aberto para a conta de quem pediu (#134).

POST   /v1/admin/exportacoes        {email, pedido}  libera para a conta desse e-mail
GET    /v1/admin/exportacoes                         liberações vigentes
DELETE /v1/admin/exportacoes/{id}                    revoga

O pedido chega pelo suporte, por autodeclaração (1A). Procedimento em
docs/suporte/exportacao-acessibilidade.md.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..dominio import conta_leitor, contas, exportacao_aberta
from ..dominio.permissoes import Permissao
from ..models import ContaLeitor, ExportacaoLiberada, Usuario
from ..ratelimit import ip_do_cliente
from .admin import exigir

router = APIRouter(prefix="/v1/admin/exportacoes", tags=["admin"])
pode_liberar = exigir(Permissao.LIBERAR_EXPORTACAO)


class PedidoLiberacao(BaseModel):
    email: EmailStr = Field(max_length=320)
    pedido: str = Field(min_length=1, max_length=40, pattern=r"\S")


class LiberacaoOut(BaseModel):
    id: int
    email: str
    pedido: str
    liberada_em: datetime
    liberada_por: str | None
    capitulos_baixados: int


def _saida(session: Session, e: ExportacaoLiberada) -> LiberacaoOut:
    return LiberacaoOut(
        id=e.id,
        email=e.conta.email,
        pedido=e.pedido,
        liberada_em=e.liberada_em,
        liberada_por=e.liberada_por.email if e.liberada_por else None,
        capitulos_baixados=exportacao_aberta.total_baixado(session, e.id),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def liberar(
    dados: PedidoLiberacao,
    request: Request,
    usuario: Usuario = Depends(pode_liberar),
    session: Session = Depends(get_session),
) -> LiberacaoOut:
    conta = session.scalar(
        select(ContaLeitor).where(ContaLeitor.email == conta_leitor.normalizar(dados.email))
    )
    if conta is None:
        # A liberação é da conta, não do e-mail: a pessoa entra no app primeiro.
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "nenhuma conta com esse e-mail; peça que entre no app"
        )
    try:
        liberacao = exportacao_aberta.liberar(session, conta, dados.pedido, usuario)
    except exportacao_aberta.LiberacaoRecusada as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    # Sem o e-mail no log: a auditoria não é apagada, e a conta pode ser excluída.
    contas.registrar(
        session,
        "exportacao_liberada",
        usuario,
        "conta_leitor",
        conta.id,
        ip_do_cliente(request),
        pedido=liberacao.pedido,
    )
    session.commit()
    session.refresh(liberacao)
    return _saida(session, liberacao)


@router.get("")
def listar(
    _: Usuario = Depends(pode_liberar), session: Session = Depends(get_session)
) -> list[LiberacaoOut]:
    vigentes = session.scalars(
        select(ExportacaoLiberada)
        .where(ExportacaoLiberada.revogada_em.is_(None))
        .order_by(ExportacaoLiberada.id)
    )
    return [_saida(session, e) for e in vigentes]


@router.delete("/{liberacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def revogar(
    liberacao_id: int,
    request: Request,
    usuario: Usuario = Depends(pode_liberar),
    session: Session = Depends(get_session),
):
    liberacao = session.get(ExportacaoLiberada, liberacao_id)
    if liberacao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "liberação não encontrada")
    try:
        exportacao_aberta.revogar(session, liberacao, usuario)
    except exportacao_aberta.LiberacaoRecusada as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    contas.registrar(
        session,
        "exportacao_revogada",
        usuario,
        "conta_leitor",
        liberacao.conta_id,
        ip_do_cliente(request),
        pedido=liberacao.pedido,
    )
    session.commit()
