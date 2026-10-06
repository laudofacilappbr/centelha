"""API pública do catálogo: leitura, sem autenticação, com cache na Cloudflare.

Só expõe o que foi publicado: edição com publicada_em e direitos aprovados, e capítulo
no estado "publicado".
Nada aqui escreve; endpoints do admin ficam em outro prefixo, com autenticação.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..models import (
    Capitulo,
    ConfigApoio,
    Direitos,
    Edicao,
    EstadoCapitulo,
    FaixaAudio,
    Publico,
    Segmento,
    StatusDireitos,
    TipoSegmento,
)

router = APIRouter(prefix="/v1", tags=["catalogo"])

# Navegador guarda 5 min; Cloudflare guarda 1 h. Publicação nova purga o cache (Fase 1).
CACHE_PUBLICO = "public, max-age=300, s-maxage=3600"


def _cache(response: Response) -> None:
    response.headers["Cache-Control"] = CACHE_PUBLICO


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EdicaoResumo(_Base):
    id: int
    idioma: str
    publico: Publico
    titulo: str
    tradutor: str | None
    publicada_em: datetime


class ObraOut(_Base):
    slug: str
    sigla: str
    autor: str
    titulo_original: str
    ano: int | None
    edicoes: list[EdicaoResumo]


class CapituloResumo(_Base):
    id: int
    ordem: int
    titulo: str
    referencia_canonica: str


class EdicaoOut(EdicaoResumo):
    obra_slug: str
    fonte: str
    capitulos: list[CapituloResumo]


class SegmentoOut(_Base):
    id: int
    ordem: int
    tipo: TipoSegmento
    texto: str
    numero_questao: int | None
    subquestao: str | None


class FaixaOut(_Base):
    url: str
    versao: int
    duracao_ms: int
    marcacoes: list[dict]


class CapituloOut(CapituloResumo):
    edicao_id: int
    segmentos: list[SegmentoOut]
    faixa: FaixaOut | None


class QuestaoOut(_Base):
    edicao_id: int
    numero: int
    referencia: str
    capitulo: CapituloResumo
    segmentos: list[SegmentoOut]


def _edicao_visivel():
    # Direitos conferidos de novo na leitura, não só em publicar_edicao: se os direitos
    # de uma edição já publicada forem revogados ou voltarem a pendente, ela sai do ar
    # na próxima requisição, sem depender de alguém lembrar de despublicar.
    return Edicao.publicada_em.is_not(None) & Edicao.direitos.has(
        Direitos.status == StatusDireitos.APROVADO
    )


def _publicado():
    return (Capitulo.estado == EstadoCapitulo.PUBLICADO) & _edicao_visivel()


def _edicao_publicada(session: Session, edicao_id: int) -> Edicao:
    edicao = session.scalar(select(Edicao).where(Edicao.id == edicao_id, _edicao_visivel()))
    if edicao is None:
        raise HTTPException(404, "edição não encontrada")
    return edicao


@router.get("/obras", response_model=list[ObraOut])
def listar_obras(
    response: Response,
    idioma: str | None = Query(None, max_length=35, examples=["pt-BR"]),
    publico: Publico | None = None,
    session: Session = Depends(get_session),
):
    _cache(response)
    filtro = _edicao_visivel()
    if idioma:
        filtro &= Edicao.idioma == idioma
    if publico:
        filtro &= Edicao.publico == publico
    edicoes = session.scalars(select(Edicao).where(filtro).order_by(Edicao.id)).all()
    por_obra: dict[int, ObraOut] = {}
    for ed in edicoes:
        obra = ed.obra
        if obra.id not in por_obra:
            por_obra[obra.id] = ObraOut(
                slug=obra.slug,
                sigla=obra.sigla,
                autor=obra.autor,
                titulo_original=obra.titulo_original,
                ano=obra.ano,
                edicoes=[],
            )
        por_obra[obra.id].edicoes.append(EdicaoResumo.model_validate(ed))
    return sorted(por_obra.values(), key=lambda o: (o.ano or 0, o.slug))


@router.get("/edicoes/{edicao_id}", response_model=EdicaoOut)
def obter_edicao(edicao_id: int, response: Response, session: Session = Depends(get_session)):
    edicao = _edicao_publicada(session, edicao_id)
    _cache(response)
    capitulos = [c for c in edicao.capitulos if c.estado == EstadoCapitulo.PUBLICADO]
    return EdicaoOut(
        **EdicaoResumo.model_validate(edicao).model_dump(),
        obra_slug=edicao.obra.slug,
        fonte=edicao.fonte,
        capitulos=[CapituloResumo.model_validate(c) for c in capitulos],
    )


@router.get("/capitulos/{capitulo_id}", response_model=CapituloOut)
def obter_capitulo(capitulo_id: int, response: Response, session: Session = Depends(get_session)):
    capitulo = session.scalar(
        select(Capitulo)
        .join(Edicao)
        .where(Capitulo.id == capitulo_id, _publicado())
        .options(selectinload(Capitulo.segmentos))
    )
    if capitulo is None:
        raise HTTPException(404, "capítulo não encontrado")
    _cache(response)
    # Regenerar áudio cria versão nova; o app sempre recebe a mais recente.
    faixa = session.scalar(
        select(FaixaAudio)
        .where(FaixaAudio.capitulo_id == capitulo.id)
        .order_by(FaixaAudio.versao.desc(), FaixaAudio.id.desc())
        .limit(1)
    )
    return CapituloOut(
        **CapituloResumo.model_validate(capitulo).model_dump(),
        edicao_id=capitulo.edicao_id,
        segmentos=[SegmentoOut.model_validate(s) for s in capitulo.segmentos],
        faixa=FaixaOut.model_validate(faixa) if faixa else None,
    )


@router.get("/edicoes/{edicao_id}/questoes/{numero}", response_model=QuestaoOut)
def obter_questao(
    edicao_id: int, numero: int, response: Response, session: Session = Depends(get_session)
):
    """Busca por número de questão: "questão 88" leva ao capítulo e aos segmentos dela."""
    edicao = _edicao_publicada(session, edicao_id)
    segmentos = session.scalars(
        select(Segmento)
        .join(Capitulo)
        .where(
            Capitulo.edicao_id == edicao.id,
            Capitulo.estado == EstadoCapitulo.PUBLICADO,
            Segmento.numero_questao == numero,
        )
        .order_by(Capitulo.ordem, Segmento.ordem)
    ).all()
    if not segmentos:
        raise HTTPException(404, "questão não encontrada")
    _cache(response)
    return QuestaoOut(
        edicao_id=edicao.id,
        numero=numero,
        referencia=f"{edicao.obra.sigla}-{numero}",
        capitulo=CapituloResumo.model_validate(segmentos[0].capitulo),
        segmentos=[SegmentoOut.model_validate(s) for s in segmentos],
    )


class ConfigRemota(BaseModel):
    apoio: bool
    caridade: bool
    anuncios: bool


@router.get("/config", response_model=ConfigRemota)
def config_remota(response: Response, session: Session = Depends(get_session)):
    """Configuração lida pelo app ao abrir. Apoio segue o admin (#40); caridade e
    anúncios continuam desligados. O perfil infantil ignora estas opções no próprio
    app, sempre."""
    _cache(response)
    apoio = session.get(ConfigApoio, 1)
    return ConfigRemota(apoio=bool(apoio and apoio.ligado), caridade=False, anuncios=False)
