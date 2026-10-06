"""Admin: cadastro de direitos da edição (#22).

Ler é aberto a qualquer papel do admin (o revisor precisa saber por que a edição não
publica); editar e aprovar ficam com o administrador.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy.orm import Session

from ..db import get_session
from ..dominio import contas, direitos
from ..dominio.permissoes import Permissao
from ..models import Edicao, StatusDireitos, Usuario
from ..ratelimit import ip_do_cliente
from .admin import exigir, pode_ver_admin

router = APIRouter(prefix="/v1/admin/edicoes/{edicao_id}/direitos", tags=["admin"])
pode_editar_direitos = exigir(Permissao.EDITAR_DIREITOS)
pode_aprovar_direitos = exigir(Permissao.APROVAR_DIREITOS)


class DireitosEntrada(BaseModel):
    falecimento_tradutor: date | None = None
    base_legal: str | None = Field(default=None, max_length=5000)
    # Link para o documento (parecer, certidão, página da edição-fonte). Upload próprio
    # entra quando houver storage (#19); até lá, só https.
    documento_url: HttpUrl | None = Field(default=None)

    @field_validator("documento_url")
    @classmethod
    def _so_https(cls, v: HttpUrl | None) -> HttpUrl | None:
        if v is not None and v.scheme != "https":
            raise ValueError("o documento precisa de link https")
        return v


class Recusa(BaseModel):
    motivo: str = Field(min_length=1, max_length=2000)


class DireitosSaida(BaseModel):
    edicao_id: int
    status: StatusDireitos
    falecimento_tradutor: date | None
    base_legal: str | None
    documento_url: str | None
    aprovado_por: str | None
    aprovado_em: datetime | None
    # O que falta para aprovar; o admin mostra isso em vez de um botão que dá erro.
    pendencias: list[str]
    publicada: bool

    @classmethod
    def de(cls, edicao: Edicao) -> "DireitosSaida":
        d = edicao.direitos
        return cls(
            edicao_id=edicao.id,
            status=d.status if d else StatusDireitos.PENDENTE,
            falecimento_tradutor=d.falecimento_tradutor if d else None,
            base_legal=d.base_legal if d else None,
            documento_url=d.documento_url if d else None,
            aprovado_por=d.aprovado_por if d else None,
            aprovado_em=d.aprovado_em if d else None,
            pendencias=direitos.pendencias(edicao),
            publicada=edicao.publicada_em is not None,
        )


def _edicao(session: Session, edicao_id: int) -> Edicao:
    edicao = session.get(Edicao, edicao_id)
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "edição não encontrada")
    return edicao


@router.get("")
def ver(
    edicao_id: int,
    _: Usuario = Depends(pode_ver_admin),
    session: Session = Depends(get_session),
) -> DireitosSaida:
    return DireitosSaida.de(_edicao(session, edicao_id))


@router.put("")
def atualizar(
    edicao_id: int,
    dados: DireitosEntrada,
    request: Request,
    autor: Usuario = Depends(pode_editar_direitos),
    session: Session = Depends(get_session),
) -> DireitosSaida:
    edicao = _edicao(session, edicao_id)
    mudancas = direitos.atualizar(
        edicao,
        dados.falecimento_tradutor,
        dados.base_legal,
        str(dados.documento_url) if dados.documento_url else None,
    )
    if mudancas:
        contas.registrar(
            session,
            "direitos_alterados",
            autor,
            "edicao",
            edicao.id,
            ip_do_cliente(request),
            **mudancas,
        )
    session.commit()
    return DireitosSaida.de(edicao)


@router.post("/aprovar")
def aprovar(
    edicao_id: int,
    request: Request,
    autor: Usuario = Depends(pode_aprovar_direitos),
    session: Session = Depends(get_session),
) -> DireitosSaida:
    edicao = _edicao(session, edicao_id)
    try:
        direitos.aprovar(edicao, autor)
    except direitos.DireitosIncompletos as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, {"erro": str(e), "pendencias": e.pendencias}
        ) from e
    d = edicao.direitos
    # A prova aprovada vai junto no log: se alguém mudar os campos depois, o registro
    # mostra o que estava na tela no momento da aprovação.
    contas.registrar(
        session,
        "direitos_aprovados",
        autor,
        "edicao",
        edicao.id,
        ip_do_cliente(request),
        base_legal=d.base_legal,
        documento_url=d.documento_url,
        falecimento_tradutor=(
            d.falecimento_tradutor.isoformat() if d.falecimento_tradutor else None
        ),
    )
    session.commit()
    return DireitosSaida.de(edicao)


@router.post("/recusar")
def recusar(
    edicao_id: int,
    dados: Recusa,
    request: Request,
    autor: Usuario = Depends(pode_aprovar_direitos),
    session: Session = Depends(get_session),
) -> DireitosSaida:
    edicao = _edicao(session, edicao_id)
    direitos.recusar(edicao)
    # Recusar uma edição já publicada tira do ar pelo filtro do catálogo; o log diz que
    # isso aconteceu, para ninguém procurar "por que o livro sumiu do app".
    contas.registrar(
        session,
        "direitos_recusados",
        autor,
        "edicao",
        edicao.id,
        ip_do_cliente(request),
        motivo=dados.motivo,
        estava_publicada=edicao.publicada_em is not None,
    )
    session.commit()
    return DireitosSaida.de(edicao)
