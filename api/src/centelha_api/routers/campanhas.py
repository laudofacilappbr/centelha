"""Campanhas de caridade com instituição parceira (#41).

Decisões do dono: uma instituição de referência e rodízio entre outras (1A+B), e o
calendário do ano com as datas da issue e outras que surgirem (2B). O Pix é da
instituição; o projeto não recebe nada e não vê quanto entrou, por isso o resultado é
o que a instituição informa depois do fim. Nunca no perfil infantil: o app ignora
`caridade` nesse perfil.
"""

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..dominio import contas, pix
from ..dominio.permissoes import Permissao
from ..models import Campanha, Instituicao, Usuario
from ..ratelimit import ip_do_cliente
from .admin import exigir
from .catalogo import _cache
from .temas import SLUG

publico = APIRouter(prefix="/v1", tags=["site"])
admin = APIRouter(prefix="/v1/admin", tags=["admin"])
pode_gerir = exigir(Permissao.GERIR_CAMPANHAS)

# Chave do lock de publicação: duas publicações simultâneas não podem ambas concluir
# que não há outra campanha no mesmo período.
_LOCK_PUBLICACAO = 4101


def _https(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    v = v.strip()
    # Só https: o link sai do site e do app com dinheiro do outro lado.
    if not v.startswith("https://") or any(c in v for c in " <>\"'"):
        raise ValueError("o link precisa começar com https://")
    return v


# --- Esquemas ---------------------------------------------------------------


class InstituicaoEntrada(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    cnpj: str = Field(max_length=20)
    descricao: str = Field(min_length=1, max_length=2000)
    chave_pix: str | None = Field(default=None, max_length=100)
    pagina_doacao: str | None = Field(default=None, max_length=500)
    site: str | None = Field(default=None, max_length=500)

    @field_validator("cnpj")
    @classmethod
    def _cnpj(cls, v: str) -> str:
        return pix.cnpj(v)

    @field_validator("chave_pix")
    @classmethod
    def _pix(cls, v: str | None) -> str | None:
        return None if v is None or not v.strip() else pix.chave_pix(v)

    @field_validator("pagina_doacao", "site")
    @classmethod
    def _links(cls, v: str | None) -> str | None:
        return _https(v)


class InstituicaoSaida(InstituicaoEntrada):
    id: int


class CampanhaEntrada(BaseModel):
    slug: str = Field(min_length=2, max_length=80, pattern=SLUG)
    titulo: str = Field(min_length=1, max_length=200)
    # Texto puro, como nos temas: o site escapa tudo.
    texto: str = Field(min_length=1, max_length=5000)
    instituicao_id: int
    inicio: date
    fim: date
    meta_centavos: int | None = Field(default=None, ge=100, le=10**12)
    imagem_url: str | None = Field(default=None, max_length=500)

    @field_validator("imagem_url")
    @classmethod
    def _imagem(cls, v: str | None) -> str | None:
        return _https(v)

    @model_validator(mode="after")
    def _periodo(self):
        if self.fim < self.inicio:
            raise ValueError("fim antes do início")
        return self


class Resultado(BaseModel):
    arrecadado_centavos: int = Field(ge=0, le=10**12)
    resultado: str = Field(min_length=1, max_length=3000)


class CampanhaAdmin(BaseModel):
    id: int
    slug: str
    titulo: str
    texto: str
    instituicao: InstituicaoSaida
    inicio: date
    fim: date
    meta_centavos: int | None
    imagem_url: str | None
    publicado_em: datetime | None
    arrecadado_centavos: int | None
    resultado: str | None


class InstituicaoPublica(BaseModel):
    nome: str
    cnpj: str
    descricao: str
    chave_pix: str | None
    pagina_doacao: str | None
    site: str | None


class CampanhaPublica(BaseModel):
    slug: str
    titulo: str
    texto: str
    instituicao: InstituicaoPublica
    inicio: date
    fim: date
    # Pela data do banco no momento da leitura. O site estático guarda as datas e
    # refaz a conta no navegador, para não mostrar o Pix de uma campanha encerrada.
    situacao: Literal["futura", "ativa", "encerrada"]
    meta_centavos: int | None
    imagem_url: str | None
    arrecadado_centavos: int | None
    resultado: str | None
    publicado_em: datetime
    atualizado_em: datetime


def _admin(c: Campanha) -> CampanhaAdmin:
    return CampanhaAdmin(
        id=c.id, slug=c.slug, titulo=c.titulo, texto=c.texto,
        instituicao=InstituicaoSaida.model_validate(c.instituicao, from_attributes=True),
        inicio=c.inicio, fim=c.fim, meta_centavos=c.meta_centavos, imagem_url=c.imagem_url,
        publicado_em=c.publicado_em, arrecadado_centavos=c.arrecadado_centavos,
        resultado=c.resultado,
    )  # fmt: skip


def _hoje(session: Session) -> date:
    # Relógio do banco, não do processo: o container pode estar minutos à frente.
    return session.scalar(select(func.current_date()))


def _situacao(c: Campanha, hoje: date) -> str:
    if hoje < c.inicio:
        return "futura"
    return "ativa" if hoje <= c.fim else "encerrada"


def _publica(c: Campanha, hoje: date) -> CampanhaPublica:
    return CampanhaPublica(
        slug=c.slug, titulo=c.titulo, texto=c.texto,
        instituicao=InstituicaoPublica.model_validate(c.instituicao, from_attributes=True),
        inicio=c.inicio, fim=c.fim, situacao=_situacao(c, hoje),
        meta_centavos=c.meta_centavos, imagem_url=c.imagem_url,
        arrecadado_centavos=c.arrecadado_centavos, resultado=c.resultado,
        publicado_em=c.publicado_em, atualizado_em=c.atualizado_em,
    )  # fmt: skip


def _instituicao(session: Session, instituicao_id: int) -> Instituicao:
    i = session.get(Instituicao, instituicao_id)
    if i is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "instituição não encontrada")
    return i


def _campanha(session: Session, campanha_id: int) -> Campanha:
    c = session.get(Campanha, campanha_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "campanha não encontrada")
    return c


def _sem_sobreposicao(session: Session, c: Campanha) -> None:
    """Uma campanha ativa por vez: nenhuma outra publicada pode cruzar o período."""
    session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_PUBLICACAO})
    outra = session.scalar(
        select(Campanha.slug).where(
            Campanha.id != c.id,
            Campanha.publicado_em.is_not(None),
            Campanha.inicio <= c.fim,
            Campanha.fim >= c.inicio,
        )
    )
    if outra:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"período cruza com a campanha publicada '{outra}'"
        )


def _publicadas():
    return (
        select(Campanha)
        .where(Campanha.publicado_em.is_not(None))
        .options(selectinload(Campanha.instituicao))
        .order_by(Campanha.inicio.desc())
    )


# --- Público ----------------------------------------------------------------


@publico.get("/campanhas")
def listar_publicas(
    response: Response, session: Session = Depends(get_session)
) -> list[CampanhaPublica]:
    """Publicadas, da mais recente à mais antiga, com o resultado das encerradas."""
    _cache(response)
    hoje = _hoje(session)
    return [_publica(c, hoje) for c in session.scalars(_publicadas())]


@publico.get("/campanhas/{slug}")
def ver_publica(
    slug: str, response: Response, session: Session = Depends(get_session)
) -> CampanhaPublica:
    c = session.scalar(_publicadas().where(Campanha.slug == slug))
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "campanha não encontrada")
    _cache(response)
    return _publica(c, _hoje(session))


# --- Admin: instituições ----------------------------------------------------


@admin.get("/instituicoes")
def listar_instituicoes(
    _: Usuario = Depends(pode_gerir), session: Session = Depends(get_session)
) -> list[InstituicaoSaida]:
    return [
        InstituicaoSaida.model_validate(i, from_attributes=True)
        for i in session.scalars(select(Instituicao).order_by(Instituicao.nome))
    ]


@admin.post("/instituicoes", status_code=status.HTTP_201_CREATED)
def criar_instituicao(
    dados: InstituicaoEntrada,
    request: Request,
    autor: Usuario = Depends(pode_gerir),
    session: Session = Depends(get_session),
) -> InstituicaoSaida:
    if session.scalar(select(Instituicao.id).where(Instituicao.cnpj == dados.cnpj)):
        raise HTTPException(status.HTTP_409_CONFLICT, "CNPJ já cadastrado")
    i = Instituicao(**dados.model_dump())
    session.add(i)
    session.flush()
    contas.registrar(
        session, "instituicao_criada", autor, "instituicao", i.id, ip_do_cliente(request),
        **dados.model_dump(),
    )  # fmt: skip
    session.commit()
    return InstituicaoSaida.model_validate(i, from_attributes=True)


@admin.put("/instituicoes/{instituicao_id}")
def alterar_instituicao(
    instituicao_id: int,
    dados: InstituicaoEntrada,
    request: Request,
    autor: Usuario = Depends(pode_gerir),
    session: Session = Depends(get_session),
) -> InstituicaoSaida:
    i = _instituicao(session, instituicao_id)
    if dados.cnpj != i.cnpj:
        # Outro CNPJ é outra instituição: quem doou numa campanha publicada conferiu
        # aquele CNPJ. Cadastre a nova e troque a campanha.
        com_campanha = session.scalar(
            select(Campanha.id).where(
                Campanha.instituicao_id == i.id, Campanha.publicado_em.is_not(None)
            )
        )
        if com_campanha:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "instituição com campanha publicada não troca de CNPJ"
            )
        if session.scalar(select(Instituicao.id).where(Instituicao.cnpj == dados.cnpj)):
            raise HTTPException(status.HTTP_409_CONFLICT, "CNPJ já cadastrado")
    antes = InstituicaoEntrada.model_validate(i, from_attributes=True).model_dump()
    for k, v in dados.model_dump().items():
        setattr(i, k, v)
    contas.registrar(
        session, "instituicao_alterada", autor, "instituicao", i.id, ip_do_cliente(request),
        antes=antes, depois=dados.model_dump(),
    )  # fmt: skip
    session.commit()
    return InstituicaoSaida.model_validate(i, from_attributes=True)


# --- Admin: campanhas -------------------------------------------------------


@admin.get("/campanhas")
def listar_campanhas(
    _: Usuario = Depends(pode_gerir), session: Session = Depends(get_session)
) -> list[CampanhaAdmin]:
    cs = session.scalars(
        select(Campanha)
        .options(selectinload(Campanha.instituicao))
        .order_by(Campanha.inicio.desc())
    )
    return [_admin(c) for c in cs]


@admin.post("/campanhas", status_code=status.HTTP_201_CREATED)
def criar_campanha(
    dados: CampanhaEntrada,
    request: Request,
    autor: Usuario = Depends(pode_gerir),
    session: Session = Depends(get_session),
) -> CampanhaAdmin:
    _instituicao(session, dados.instituicao_id)
    if session.scalar(select(Campanha.id).where(Campanha.slug == dados.slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"slug '{dados.slug}' já existe")
    c = Campanha(**dados.model_dump())
    session.add(c)
    session.flush()
    contas.registrar(
        session, "campanha_criada", autor, "campanha", c.id, ip_do_cliente(request),
        **dados.model_dump(mode="json"),
    )  # fmt: skip
    session.commit()
    session.refresh(c)
    return _admin(c)


@admin.put("/campanhas/{campanha_id}")
def alterar_campanha(
    campanha_id: int,
    dados: CampanhaEntrada,
    request: Request,
    autor: Usuario = Depends(pode_gerir),
    session: Session = Depends(get_session),
) -> CampanhaAdmin:
    c = _campanha(session, campanha_id)
    publicada = c.publicado_em is not None
    # Slug é a URL; instituição é para quem o dinheiro vai. Depois de publicada, nenhum
    # dos dois muda: quem compartilhou o link ou doou conferiu aquela instituição.
    if publicada and dados.slug != c.slug:
        raise HTTPException(status.HTTP_409_CONFLICT, "campanha publicada não troca de slug")
    if publicada and dados.instituicao_id != c.instituicao_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "campanha publicada não troca de instituição")
    _instituicao(session, dados.instituicao_id)
    if dados.slug != c.slug and session.scalar(
        select(Campanha.id).where(Campanha.slug == dados.slug)
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, f"slug '{dados.slug}' já existe")
    antes = CampanhaEntrada.model_validate(c, from_attributes=True).model_dump(mode="json")
    for k, v in dados.model_dump().items():
        setattr(c, k, v)
    if publicada:
        _sem_sobreposicao(session, c)
    contas.registrar(
        session, "campanha_alterada", autor, "campanha", c.id, ip_do_cliente(request),
        antes=antes, depois=dados.model_dump(mode="json"),
    )  # fmt: skip
    session.commit()
    session.refresh(c)
    return _admin(c)


@admin.post("/campanhas/{campanha_id}/publicar")
def publicar_campanha(
    campanha_id: int,
    request: Request,
    autor: Usuario = Depends(pode_gerir),
    session: Session = Depends(get_session),
) -> CampanhaAdmin:
    c = _campanha(session, campanha_id)
    if not (c.instituicao.chave_pix or c.instituicao.pagina_doacao):
        # Campanha sem Pix nem página de doação seria um pedido sem como atender.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "a instituição não tem chave Pix nem página de doação"
        )
    if c.fim < _hoje(session):
        raise HTTPException(status.HTTP_409_CONFLICT, "campanha já terminou")
    _sem_sobreposicao(session, c)
    c.publicado_em = c.publicado_em or func.now()
    contas.registrar(
        session, "campanha_publicada", autor, "campanha", c.id, ip_do_cliente(request),
        slug=c.slug,
    )  # fmt: skip
    session.commit()
    session.refresh(c)
    return _admin(c)


@admin.post("/campanhas/{campanha_id}/despublicar")
def despublicar_campanha(
    campanha_id: int,
    request: Request,
    autor: Usuario = Depends(pode_gerir),
    session: Session = Depends(get_session),
) -> CampanhaAdmin:
    c = _campanha(session, campanha_id)
    c.publicado_em = None
    contas.registrar(
        session, "campanha_despublicada", autor, "campanha", c.id, ip_do_cliente(request),
        slug=c.slug,
    )  # fmt: skip
    session.commit()
    session.refresh(c)
    return _admin(c)


@admin.put("/campanhas/{campanha_id}/resultado")
def informar_resultado(
    campanha_id: int,
    dados: Resultado,
    request: Request,
    autor: Usuario = Depends(pode_gerir),
    session: Session = Depends(get_session),
) -> CampanhaAdmin:
    c = _campanha(session, campanha_id)
    # Resultado parcial publicado como final engana quem doou e quem lê a transparência.
    if c.fim >= _hoje(session):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "o resultado só entra depois do fim da campanha"
        )
    antes = {"arrecadado_centavos": c.arrecadado_centavos, "resultado": c.resultado}
    c.arrecadado_centavos = dados.arrecadado_centavos
    c.resultado = dados.resultado.strip()
    contas.registrar(
        session, "campanha_resultado", autor, "campanha", c.id, ip_do_cliente(request),
        antes=antes, depois=dados.model_dump(),
    )  # fmt: skip
    session.commit()
    session.refresh(c)
    return _admin(c)
