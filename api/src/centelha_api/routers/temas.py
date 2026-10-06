"""Temas: admin escreve e liga trechos; site e app leem os publicados (#42)."""

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..dominio import contas, temas
from ..dominio.permissoes import Permissao
from ..models import Tema, TemaReferencia, Usuario
from ..ratelimit import ip_do_cliente
from .admin import exigir
from .catalogo import _cache

publico = APIRouter(prefix="/v1", tags=["site"])
admin = APIRouter(prefix="/v1/admin/temas", tags=["admin"])
pode_editar = exigir(Permissao.EDITAR_CONTEUDO)

SLUG = r"^[a-z0-9]+(-[a-z0-9]+)*$"


class TemaEntrada(BaseModel):
    slug: str = Field(min_length=2, max_length=80, pattern=SLUG)
    titulo: str = Field(min_length=1, max_length=200)
    # Texto puro, parágrafos separados por linha em branco. Sem HTML nem Markdown: o
    # site escapa tudo, e não há como um tema injetar marcação na página.
    resumo: str = Field(min_length=1, max_length=5000)
    idioma: str = Field(default="pt-BR", max_length=35)
    referencias: list[str] = Field(default_factory=list, max_length=200)


class Item(BaseModel):
    referencia: str
    tipo: str
    obra_slug: str
    edicao_id: int
    capitulo_id: int
    capitulo_ordem: int
    titulo: str
    numero_questao: int | None


class TemaPublico(BaseModel):
    slug: str
    titulo: str
    resumo: str
    idioma: str
    publicado_em: datetime
    atualizado_em: datetime
    itens: list[Item]


class TemaAdmin(BaseModel):
    id: int
    slug: str
    titulo: str
    resumo: str
    idioma: str
    publicado_em: datetime | None
    referencias: list[str]
    # Referências que hoje não apontam para nada publicado (erro de digitação, ou
    # trecho ainda não publicado): não aparecem no site até resolverem.
    nao_resolvidas: list[str]


def _admin(session: Session, t: Tema) -> TemaAdmin:
    refs = [r.referencia for r in t.referencias]
    ok = temas.resolver(session, refs, t.idioma)
    return TemaAdmin(
        id=t.id, slug=t.slug, titulo=t.titulo, resumo=t.resumo, idioma=t.idioma,
        publicado_em=t.publicado_em, referencias=refs,
        nao_resolvidas=[r for r in refs if r not in ok],
    )  # fmt: skip


def _publico(session: Session, t: Tema) -> TemaPublico:
    refs = [r.referencia for r in t.referencias]
    ok = temas.resolver(session, refs, t.idioma)
    return TemaPublico(
        slug=t.slug, titulo=t.titulo, resumo=t.resumo, idioma=t.idioma,
        publicado_em=t.publicado_em, atualizado_em=t.atualizado_em,
        itens=[Item(**asdict(ok[r])) for r in refs if r in ok],
    )  # fmt: skip


def _referencias(dados: TemaEntrada) -> list[str]:
    try:
        refs = [temas.validar(r) for r in dados.referencias]
    except temas.ReferenciaInvalida as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    # Mantém a ordem dada e tira repetidas.
    return list(dict.fromkeys(refs))


def _tema(session: Session, tema_id: int) -> Tema:
    t = session.get(Tema, tema_id)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tema não encontrado")
    return t


# --- Público ----------------------------------------------------------------


def _publicados():
    return (
        select(Tema)
        .where(Tema.publicado_em.is_not(None))
        .options(selectinload(Tema.referencias))
        .order_by(Tema.titulo)
    )


@publico.get("/temas")
def listar_publicos(
    response: Response, idioma: str = "pt-BR", session: Session = Depends(get_session)
) -> list[TemaPublico]:
    """Com os itens: o site inverte a lista para mostrar "temas relacionados" em cada
    questão sem uma chamada por página."""
    _cache(response)
    consulta = _publicados().where(Tema.idioma == idioma)
    return [_publico(session, t) for t in session.scalars(consulta)]


@publico.get("/temas/{slug}")
def ver_publico(
    slug: str, response: Response, session: Session = Depends(get_session)
) -> TemaPublico:
    t = session.scalar(_publicados().where(Tema.slug == slug))
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tema não encontrado")
    _cache(response)
    return _publico(session, t)


# --- Admin ------------------------------------------------------------------


@admin.get("")
def listar(
    _: Usuario = Depends(pode_editar), session: Session = Depends(get_session)
) -> list[TemaAdmin]:
    ts = session.scalars(select(Tema).options(selectinload(Tema.referencias)).order_by(Tema.titulo))
    return [_admin(session, t) for t in ts]


@admin.post("", status_code=status.HTTP_201_CREATED)
def criar(
    dados: TemaEntrada,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> TemaAdmin:
    if session.scalar(select(Tema.id).where(Tema.slug == dados.slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"slug '{dados.slug}' já existe")
    refs = _referencias(dados)
    t = Tema(slug=dados.slug, titulo=dados.titulo, resumo=dados.resumo.strip(), idioma=dados.idioma)
    t.referencias = [TemaReferencia(referencia=r, ordem=i) for i, r in enumerate(refs)]
    session.add(t)
    session.flush()
    contas.registrar(
        session, "tema_criado", autor, "tema", t.id, ip_do_cliente(request), slug=t.slug
    )
    session.commit()
    return _admin(session, t)


@admin.put("/{tema_id}")
def alterar(
    tema_id: int,
    dados: TemaEntrada,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> TemaAdmin:
    t = _tema(session, tema_id)
    # Slug é a URL. Trocar depois de publicado quebra links e o que o Google já indexou.
    if dados.slug != t.slug and t.publicado_em is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "tema publicado não troca de slug")
    if dados.slug != t.slug and session.scalar(select(Tema.id).where(Tema.slug == dados.slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"slug '{dados.slug}' já existe")
    refs = _referencias(dados)
    antes = {"titulo": t.titulo, "referencias": [r.referencia for r in t.referencias]}
    t.slug, t.titulo, t.resumo, t.idioma = (
        dados.slug,
        dados.titulo,
        dados.resumo.strip(),
        dados.idioma,
    )
    # Apaga antes de inserir: no mesmo flush o SQLAlchemy insere primeiro, e uma
    # referência mantida bateria no UNIQUE (tema_id, referencia).
    t.referencias.clear()
    session.flush()
    t.referencias = [TemaReferencia(referencia=r, ordem=i) for i, r in enumerate(refs)]
    contas.registrar(
        session, "tema_alterado", autor, "tema", t.id, ip_do_cliente(request),
        antes=antes, depois={"titulo": t.titulo, "referencias": refs},
    )  # fmt: skip
    session.commit()
    session.refresh(t)
    return _admin(session, t)


@admin.post("/{tema_id}/publicar")
def publicar(
    tema_id: int,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> TemaAdmin:
    t = _tema(session, tema_id)
    vista = _admin(session, t)
    # Tema sem nenhum trecho publicado é só um texto solto; a página existe para ligar
    # a busca aos trechos.
    if len(vista.referencias) == len(vista.nao_resolvidas):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "nenhuma referência aponta para trecho publicado"
        )
    t.publicado_em = t.publicado_em or func.now()
    contas.registrar(
        session, "tema_publicado", autor, "tema", t.id, ip_do_cliente(request), slug=t.slug
    )
    session.commit()
    session.refresh(t)
    return _admin(session, t)


@admin.post("/{tema_id}/despublicar")
def despublicar(
    tema_id: int,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> TemaAdmin:
    t = _tema(session, tema_id)
    t.publicado_em = None
    contas.registrar(
        session, "tema_despublicado", autor, "tema", t.id, ip_do_cliente(request), slug=t.slug
    )
    session.commit()
    session.refresh(t)
    return _admin(session, t)
