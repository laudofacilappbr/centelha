"""Blog: posts escritos no admin e publicados no site (#42).

Regras do blog (site-landing-page.md) que viram código aqui:
- revisão doutrinária humana antes de publicar, feita por outra pessoa que não o autor;
- todo post cita a fonte exata e linka para ela: publicar exige ao menos uma
  referência que aponte para trecho publicado;
- post publicado não muda sem passar de novo pela revisão.
A chamada para o app no fim de cada post fica no template do site.
"""

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import Field, HttpUrl, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..dominio import contas, temas
from ..dominio.permissoes import Permissao
from ..dominio.seo import CamposSeo
from ..models import EstadoPost, LinhaEditorial, Post, PostReferencia, Usuario
from ..ratelimit import ip_do_cliente
from .admin import exigir, pode_ver_admin
from .catalogo import _cache
from .temas import SLUG, Item

publico = APIRouter(prefix="/v1", tags=["site"])
admin = APIRouter(prefix="/v1/admin/posts", tags=["admin"])
pode_editar = exigir(Permissao.EDITAR_CONTEUDO)
# Revisão doutrinária: quem aprova texto (revisor de texto ou administrador).
pode_revisar = exigir(Permissao.APROVAR_TEXTO)


class PostEntrada(CamposSeo):
    slug: str = Field(min_length=2, max_length=100, pattern=SLUG)
    titulo: str = Field(min_length=1, max_length=200)
    resumo: str = Field(min_length=1, max_length=300)
    texto: str = Field(min_length=1, max_length=50_000)
    linha: LinhaEditorial
    capa_url: HttpUrl | None = None
    idioma: str = Field(default="pt-BR", max_length=35)
    referencias: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("capa_url")
    @classmethod
    def _so_https(cls, v: HttpUrl | None) -> HttpUrl | None:
        if v is not None and v.scheme != "https":
            raise ValueError("capa precisa de link https")
        return v


class PostResumo(CamposSeo):
    slug: str
    titulo: str
    resumo: str
    linha: LinhaEditorial
    capa_url: str | None
    publicado_em: datetime
    atualizado_em: datetime


class PostPublico(PostResumo):
    texto: str
    idioma: str
    fontes: list[Item]


class PostAdmin(CamposSeo):
    id: int
    slug: str
    titulo: str
    resumo: str
    texto: str
    linha: LinhaEditorial
    capa_url: str | None
    idioma: str
    estado: EstadoPost
    autor_id: int
    revisado_por_id: int | None
    publicado_em: datetime | None
    referencias: list[str]
    nao_resolvidas: list[str]


def _admin(session: Session, p: Post) -> PostAdmin:
    refs = [r.referencia for r in p.referencias]
    ok = temas.resolver(session, refs, p.idioma)
    return PostAdmin(
        id=p.id, slug=p.slug, titulo=p.titulo, resumo=p.resumo, texto=p.texto, linha=p.linha,
        capa_url=p.capa_url, idioma=p.idioma, estado=p.estado, autor_id=p.autor_id,
        revisado_por_id=p.revisado_por_id, publicado_em=p.publicado_em, referencias=refs,
        nao_resolvidas=[r for r in refs if r not in ok],
        seo_titulo=p.seo_titulo, seo_descricao=p.seo_descricao,
    )  # fmt: skip


def _resumo(p: Post) -> PostResumo:
    return PostResumo(
        slug=p.slug, titulo=p.titulo, resumo=p.resumo, linha=p.linha, capa_url=p.capa_url,
        publicado_em=p.publicado_em, atualizado_em=p.atualizado_em,
        seo_titulo=p.seo_titulo, seo_descricao=p.seo_descricao,
    )  # fmt: skip


def _post(session: Session, post_id: int) -> Post:
    p = session.get(Post, post_id, with_for_update=True)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "post não encontrado")
    return p


def _referencias(dados: PostEntrada) -> list[str]:
    try:
        return list(dict.fromkeys(temas.validar(r) for r in dados.referencias))
    except temas.ReferenciaInvalida as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e


def _aplicar(session: Session, p: Post, dados: PostEntrada, refs: list[str]) -> None:
    p.slug, p.titulo, p.resumo = dados.slug, dados.titulo, dados.resumo.strip()
    p.texto, p.linha, p.idioma = dados.texto.strip(), dados.linha, dados.idioma
    p.capa_url = str(dados.capa_url) if dados.capa_url else None
    p.seo_titulo, p.seo_descricao = dados.seo_titulo, dados.seo_descricao
    # Apaga antes de inserir: no mesmo flush o SQLAlchemy insere primeiro, e uma
    # referência mantida bateria no UNIQUE (post_id, referencia).
    p.referencias.clear()
    session.flush()
    p.referencias = [PostReferencia(referencia=r, ordem=i) for i, r in enumerate(refs)]


# --- Público ----------------------------------------------------------------


def _publicados():
    return (
        select(Post)
        .where(Post.estado == EstadoPost.PUBLICADO)
        .options(selectinload(Post.referencias))
        .order_by(Post.publicado_em.desc())
    )


@publico.get("/posts")
def listar_publicos(
    response: Response, idioma: str = "pt-BR", session: Session = Depends(get_session)
) -> list[PostResumo]:
    _cache(response)
    return [_resumo(p) for p in session.scalars(_publicados().where(Post.idioma == idioma))]


@publico.get("/posts/{slug}")
def ver_publico(
    slug: str, response: Response, session: Session = Depends(get_session)
) -> PostPublico:
    p = session.scalar(_publicados().where(Post.slug == slug))
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "post não encontrado")
    _cache(response)
    refs = [r.referencia for r in p.referencias]
    ok = temas.resolver(session, refs, p.idioma)
    return PostPublico(
        **_resumo(p).model_dump(), texto=p.texto, idioma=p.idioma,
        fontes=[Item(**asdict(ok[r])) for r in refs if r in ok],
    )  # fmt: skip


# --- Admin ------------------------------------------------------------------


@admin.get("")
def listar(
    _: Usuario = Depends(pode_ver_admin), session: Session = Depends(get_session)
) -> list[PostAdmin]:
    ps = session.scalars(
        select(Post).options(selectinload(Post.referencias)).order_by(Post.id.desc())
    )
    return [_admin(session, p) for p in ps]


@admin.post("", status_code=status.HTTP_201_CREATED)
def criar(
    dados: PostEntrada,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> PostAdmin:
    if session.scalar(select(Post.id).where(Post.slug == dados.slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"slug '{dados.slug}' já existe")
    refs = _referencias(dados)
    p = Post(autor_id=autor.id, estado=EstadoPost.RASCUNHO, referencias=[])
    session.add(p)
    _aplicar(session, p, dados, refs)
    session.flush()
    contas.registrar(
        session, "post_criado", autor, "post", p.id, ip_do_cliente(request), slug=p.slug
    )
    session.commit()
    return _admin(session, p)


@admin.put("/{post_id}")
def alterar(
    post_id: int,
    dados: PostEntrada,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> PostAdmin:
    p = _post(session, post_id)
    if p.estado == EstadoPost.PUBLICADO:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "post publicado: despublique, edite e passe de novo pela revisão",
        )
    if dados.slug != p.slug and session.scalar(select(Post.id).where(Post.slug == dados.slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"slug '{dados.slug}' já existe")
    refs = _referencias(dados)
    _aplicar(session, p, dados, refs)
    # A revisão vale para o texto que o revisor leu; mudou o texto, revisa de novo.
    voltou = p.estado == EstadoPost.REVISADO
    p.estado, p.revisado_por_id, p.revisado_em = EstadoPost.RASCUNHO, None, None
    contas.registrar(
        session, "post_alterado", autor, "post", p.id, ip_do_cliente(request),
        slug=p.slug, revisao_desfeita=voltou,
    )  # fmt: skip
    session.commit()
    session.refresh(p)
    return _admin(session, p)


@admin.post("/{post_id}/revisar")
def revisar(
    post_id: int,
    request: Request,
    revisor: Usuario = Depends(pode_revisar),
    session: Session = Depends(get_session),
) -> PostAdmin:
    p = _post(session, post_id)
    if p.estado != EstadoPost.RASCUNHO:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"post em '{p.estado.value}', não em rascunho"
        )
    # Revisão é um segundo par de olhos; o autor aprovando o próprio texto não é revisão.
    if revisor.id == p.autor_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "quem escreveu não revisa o próprio post")
    p.estado, p.revisado_por_id, p.revisado_em = EstadoPost.REVISADO, revisor.id, func.now()
    contas.registrar(
        session, "post_revisado", revisor, "post", p.id, ip_do_cliente(request), slug=p.slug
    )
    session.commit()
    session.refresh(p)
    return _admin(session, p)


@admin.post("/{post_id}/publicar")
def publicar(
    post_id: int,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> PostAdmin:
    p = _post(session, post_id)
    if p.estado != EstadoPost.REVISADO:
        raise HTTPException(status.HTTP_409_CONFLICT, "só post revisado é publicado")
    vista = _admin(session, p)
    if len(vista.referencias) == len(vista.nao_resolvidas):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "o post precisa citar ao menos um trecho publicado"
        )
    p.estado, p.publicado_em = EstadoPost.PUBLICADO, func.now()
    contas.registrar(
        session, "post_publicado", autor, "post", p.id, ip_do_cliente(request), slug=p.slug
    )
    session.commit()
    session.refresh(p)
    return _admin(session, p)


@admin.post("/{post_id}/despublicar")
def despublicar(
    post_id: int,
    request: Request,
    autor: Usuario = Depends(pode_editar),
    session: Session = Depends(get_session),
) -> PostAdmin:
    p = _post(session, post_id)
    if p.estado != EstadoPost.PUBLICADO:
        raise HTTPException(status.HTTP_409_CONFLICT, "post não está publicado")
    # Volta a rascunho: para sair de novo, passa outra vez pela revisão.
    p.estado, p.publicado_em, p.revisado_por_id, p.revisado_em = (
        EstadoPost.RASCUNHO,
        None,
        None,
        None,
    )
    contas.registrar(
        session, "post_despublicado", autor, "post", p.id, ip_do_cliente(request), slug=p.slug
    )
    session.commit()
    session.refresh(p)
    return _admin(session, p)
