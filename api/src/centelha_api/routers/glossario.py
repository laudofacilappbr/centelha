"""Glossário: admin define termos e aponta os trechos de Kardec; site lê os publicados (#42).

Mesma regra dos temas: referências canônicas ("LE-134"), resolvidas só para trecho
publicado com direitos aprovados (`dominio.temas.resolver`), e publicar exige ao menos
uma resolvida. Uma definição sem fonte seria a equipe ensinando doutrina por conta
própria, que é o que o glossário não pode fazer.
"""

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..dominio import contas, temas
from ..models import Termo, TermoReferencia, Usuario
from ..ratelimit import ip_do_cliente
from .catalogo import _cache
from .temas import SLUG, Item, pode_editar

publico = APIRouter(prefix="/v1", tags=["site"])
admin = APIRouter(prefix="/v1/admin/glossario", tags=["admin"])


class TermoEntrada(BaseModel):
    slug: str = Field(min_length=2, max_length=80, pattern=SLUG)
    termo: str = Field(min_length=1, max_length=80)
    # Texto puro, como nos temas: o site escapa tudo. Curta de propósito: verbete que
    # vira artigo deveria ser tema ou post.
    definicao: str = Field(min_length=1, max_length=1500)
    idioma: str = Field(default="pt-BR", max_length=35)
    referencias: list[str] = Field(default_factory=list, max_length=50)


class TermoPublico(BaseModel):
    slug: str
    termo: str
    definicao: str
    idioma: str
    publicado_em: datetime
    atualizado_em: datetime
    itens: list[Item]


class TermoAdmin(BaseModel):
    id: int
    slug: str
    termo: str
    definicao: str
    idioma: str
    publicado_em: datetime | None
    referencias: list[str]
    nao_resolvidas: list[str]


def _admin(session: Session, t: Termo) -> TermoAdmin:
    refs = [r.referencia for r in t.referencias]
    ok = temas.resolver(session, refs, t.idioma)
    return TermoAdmin(
        id=t.id, slug=t.slug, termo=t.termo, definicao=t.definicao, idioma=t.idioma,
        publicado_em=t.publicado_em, referencias=refs,
        nao_resolvidas=[r for r in refs if r not in ok],
    )  # fmt: skip


def _publico(session: Session, t: Termo) -> TermoPublico:
    refs = [r.referencia for r in t.referencias]
    ok = temas.resolver(session, refs, t.idioma)
    return TermoPublico(
        slug=t.slug, termo=t.termo, definicao=t.definicao, idioma=t.idioma,
        publicado_em=t.publicado_em, atualizado_em=t.atualizado_em,
        itens=[Item(**asdict(ok[r])) for r in refs if r in ok],
    )  # fmt: skip


def _referencias(dados: TermoEntrada) -> list[str]:
    try:
        refs = [temas.validar(r) for r in dados.referencias]
    except temas.ReferenciaInvalida as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    return list(dict.fromkeys(refs))


def _termo(session: Session, termo_id: int) -> Termo:
    t = session.get(Termo, termo_id)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "termo não encontrado")
    return t


def _conflito(session: Session, dados: TermoEntrada, termo_id: int | None) -> None:
    outros = select(Termo.id).where(Termo.id != termo_id) if termo_id else select(Termo.id)
    if session.scalar(outros.where(Termo.slug == dados.slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"slug '{dados.slug}' já existe")
    # "Perispírito" e "perispírito" seriam duas páginas disputando a mesma busca.
    mesmo = outros.where(
        Termo.idioma == dados.idioma, func.lower(Termo.termo) == dados.termo.strip().lower()
    )
    if session.scalar(mesmo):
        raise HTTPException(status.HTTP_409_CONFLICT, f"termo '{dados.termo}' já existe")


# --- Público ----------------------------------------------------------------


def _publicados():
    return (
        select(Termo)
        .where(Termo.publicado_em.is_not(None))
        .options(selectinload(Termo.referencias))
        .order_by(func.lower(Termo.termo))
    )


@publico.get("/glossario")
def listar_publicos(
    response: Response, idioma: str = "pt-BR", session: Session = Depends(get_session)
) -> list[TermoPublico]:
    """Em ordem alfabética e com os itens: o site monta o índice e os "termos desta
    questão" com uma chamada só."""
    _cache(response)
    consulta = _publicados().where(Termo.idioma == idioma)
    return [_publico(session, t) for t in session.scalars(consulta)]


@publico.get("/glossario/{slug}")
def ver_publico(
    slug: str, response: Response, session: Session = Depends(get_session)
) -> TermoPublico:
    t = session.scalar(_publicados().where(Termo.slug == slug))
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "termo não encontrado")
    _cache(response)
    return _publico(session, t)


# --- Admin ------------------------------------------------------------------


@admin.get("")
def listar(
    _: Usuario = Depends(pode_editar), session: Session = Depends(get_session)
) -> list[TermoAdmin]:
    ts = session.scalars(
        select(Termo).options(selectinload(Termo.referencias)).order_by(func.lower(Termo.termo))
    )
    return [_admin(session, t) for t in ts]


@admin.post("", status_code=status.HTTP_201_CREATED)
def criar(
    dados: TermoEntrada,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> TermoAdmin:
    _conflito(session, dados, None)
    refs = _referencias(dados)
    t = Termo(
        slug=dados.slug, termo=dados.termo.strip(), definicao=dados.definicao.strip(),
        idioma=dados.idioma,
    )  # fmt: skip
    t.referencias = [TermoReferencia(referencia=r, ordem=i) for i, r in enumerate(refs)]
    session.add(t)
    session.flush()
    contas.registrar(
        session, "termo_criado", autor, "termo", t.id, ip_do_cliente(request), slug=t.slug
    )
    session.commit()
    return _admin(session, t)


@admin.put("/{termo_id}")
def alterar(
    termo_id: int,
    dados: TermoEntrada,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> TermoAdmin:
    t = _termo(session, termo_id)
    # Slug é a URL: trocar depois de publicado quebra links e o que o Google indexou.
    if dados.slug != t.slug and t.publicado_em is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "termo publicado não troca de slug")
    _conflito(session, dados, t.id)
    refs = _referencias(dados)
    antes = {
        "termo": t.termo,
        "definicao": t.definicao,
        "referencias": [r.referencia for r in t.referencias],
    }
    t.slug, t.termo, t.definicao, t.idioma = (
        dados.slug, dados.termo.strip(), dados.definicao.strip(), dados.idioma,
    )  # fmt: skip
    # Apaga antes de inserir: no mesmo flush o SQLAlchemy insere primeiro, e uma
    # referência mantida bateria no UNIQUE (termo_id, referencia).
    t.referencias.clear()
    session.flush()
    t.referencias = [TermoReferencia(referencia=r, ordem=i) for i, r in enumerate(refs)]
    contas.registrar(
        session, "termo_alterado", autor, "termo", t.id, ip_do_cliente(request),
        antes=antes, depois={"termo": t.termo, "definicao": t.definicao, "referencias": refs},
    )  # fmt: skip
    session.commit()
    session.refresh(t)
    return _admin(session, t)


@admin.post("/{termo_id}/publicar")
def publicar(
    termo_id: int,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> TermoAdmin:
    t = _termo(session, termo_id)
    vista = _admin(session, t)
    if len(vista.referencias) == len(vista.nao_resolvidas):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "nenhuma referência aponta para trecho publicado"
        )
    t.publicado_em = t.publicado_em or func.now()
    contas.registrar(
        session, "termo_publicado", autor, "termo", t.id, ip_do_cliente(request), slug=t.slug
    )
    session.commit()
    session.refresh(t)
    return _admin(session, t)


@admin.post("/{termo_id}/despublicar")
def despublicar(
    termo_id: int,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> TermoAdmin:
    t = _termo(session, termo_id)
    t.publicado_em = None
    contas.registrar(
        session, "termo_despublicado", autor, "termo", t.id, ip_do_cliente(request), slug=t.slug
    )
    session.commit()
    session.refresh(t)
    return _admin(session, t)
