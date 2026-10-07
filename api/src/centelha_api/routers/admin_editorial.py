"""Admin: fluxo editorial (#20). Revisão de texto, escuta e transições de estado."""

from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..dominio import contas, editorial
from ..dominio.permissoes import Permissao
from ..models import (
    Capitulo,
    Edicao,
    EstadoCapitulo,
    FaixaAudio,
    RegistroAuditoria,
    RevisaoIA,
    Segmento,
    TipoSegmento,
    Usuario,
)
from ..pipeline import revisao_doutrinaria
from ..ratelimit import ip_do_cliente
from .admin import exigir, pode_ver_admin

router = APIRouter(prefix="/v1/admin", tags=["admin"])
pode_editar_segmento = exigir(Permissao.EDITAR_SEGMENTO)
pode_anexar_revisao = exigir(Permissao.EDITAR_CONTEUDO)


class EdicaoResumo(BaseModel):
    id: int
    titulo: str
    idioma: str
    publicada: bool
    # Quantos capítulos em cada estado: a fila de trabalho de cada revisor.
    capitulos_por_estado: dict[EstadoCapitulo, int]


class CapituloResumo(BaseModel):
    id: int
    ordem: int
    titulo: str
    referencia_canonica: str
    estado: EstadoCapitulo


class SegmentoSaida(BaseModel):
    id: int
    ordem: int
    tipo: TipoSegmento
    texto: str
    numero_questao: int | None
    subquestao: str | None
    # Texto como saiu da ingestão, quando já foi editado; None se nunca mudou.
    # É o lado esquerdo da revisão lado a lado.
    texto_importado: str | None


class FaixaSaida(BaseModel):
    url: str
    versao: int
    duracao_ms: int
    marcacoes: list[dict]


class RevisaoIAResumo(BaseModel):
    id: int
    criado_em: datetime
    bloqueios: int
    atencoes: int
    ok: int


class RevisaoIASaida(RevisaoIAResumo):
    relatorio: str
    usuario_id: int | None


class RevisaoIAEntrada(BaseModel):
    """O Markdown de `revisao_doutrinaria relatorio` e a contagem que ele imprime."""

    relatorio: str = Field(min_length=1, max_length=500_000)
    bloqueios: int = Field(ge=0)
    atencoes: int = Field(ge=0)
    ok: int = Field(ge=0)


class CapituloDetalhe(CapituloResumo):
    edicao_id: int
    texto_editavel: bool
    # Ações que quem está logado pode tomar agora.
    acoes: list[str]
    segmentos: list[SegmentoSaida]
    faixa: FaixaSaida | None
    # Última revisão doutrinária da IA (#98), só nas adaptações. Informa quem aprova; não
    # trava a aprovação.
    revisao_ia: RevisaoIAResumo | None = None


class EdicaoTexto(BaseModel):
    texto: str = Field(min_length=1, max_length=20000)


class PedidoTransicao(BaseModel):
    acao: str = Field(max_length=40)
    motivo: str | None = Field(default=None, max_length=2000)


class EventoHistorico(BaseModel):
    criado_em: datetime
    usuario_id: int | None
    acao: str
    detalhes: dict


def _capitulo(session: Session, capitulo_id: int, travar: bool = False) -> Capitulo:
    consulta = select(Capitulo).where(Capitulo.id == capitulo_id)
    if travar:
        # Dois revisores aprovando o mesmo capítulo ao mesmo tempo: o segundo espera
        # o primeiro e recebe "estado errado", em vez de as duas transições valerem.
        consulta = consulta.with_for_update()
    capitulo = session.scalar(consulta)
    if capitulo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "capítulo não encontrado")
    return capitulo


def _textos_importados(session: Session, ids: list[int]) -> dict[int, str]:
    """Texto original de cada segmento editado, tirado da primeira edição no log."""
    if not ids:
        return {}
    registros = session.scalars(
        select(RegistroAuditoria)
        .where(
            RegistroAuditoria.acao == "segmento_editado",
            RegistroAuditoria.alvo_tipo == "segmento",
            RegistroAuditoria.alvo_id.in_(ids),
        )
        .order_by(RegistroAuditoria.id)
    )
    originais: dict[int, str] = {}
    for r in registros:
        originais.setdefault(r.alvo_id, r.detalhes["antes"])
    return originais


def _detalhe(session: Session, capitulo: Capitulo, usuario: Usuario) -> CapituloDetalhe:
    segmentos = session.scalars(
        select(Segmento).where(Segmento.capitulo_id == capitulo.id).order_by(Segmento.ordem)
    ).all()
    originais = _textos_importados(session, [s.id for s in segmentos])
    faixa = session.scalar(
        select(FaixaAudio)
        .where(FaixaAudio.capitulo_id == capitulo.id)
        .order_by(FaixaAudio.versao.desc(), FaixaAudio.id.desc())
        .limit(1)
    )
    return CapituloDetalhe(
        id=capitulo.id,
        ordem=capitulo.ordem,
        titulo=capitulo.titulo,
        referencia_canonica=capitulo.referencia_canonica,
        estado=capitulo.estado,
        edicao_id=capitulo.edicao_id,
        texto_editavel=editorial.texto_editavel(capitulo),
        acoes=editorial.acoes_possiveis(capitulo, usuario.papel),
        segmentos=[
            SegmentoSaida(
                id=s.id,
                ordem=s.ordem,
                tipo=s.tipo,
                texto=s.texto,
                numero_questao=s.numero_questao,
                subquestao=s.subquestao,
                texto_importado=originais.get(s.id) if originais.get(s.id) != s.texto else None,
            )
            for s in segmentos
        ],
        faixa=FaixaSaida.model_validate(faixa, from_attributes=True) if faixa else None,
        revisao_ia=_ultima_revisao_ia(session, capitulo.id),
    )


def _revisoes_ia(capitulo_id: int):
    return (
        select(RevisaoIA)
        .where(RevisaoIA.capitulo_id == capitulo_id)
        .order_by(RevisaoIA.criado_em.desc(), RevisaoIA.id.desc())
    )


def _ultima_revisao_ia(session: Session, capitulo_id: int) -> RevisaoIAResumo | None:
    r = session.scalar(_revisoes_ia(capitulo_id).limit(1))
    return RevisaoIAResumo.model_validate(r, from_attributes=True) if r else None


def _contagem(e: Edicao) -> dict[EstadoCapitulo, int]:
    # Todos os estados, mesmo com zero: o admin monta colunas fixas.
    n = Counter(c.estado for c in e.capitulos)
    return {estado: n.get(estado, 0) for estado in EstadoCapitulo}


@router.get("/edicoes")
def listar_edicoes(
    _: Usuario = Depends(pode_ver_admin), session: Session = Depends(get_session)
) -> list[EdicaoResumo]:
    edicoes = session.scalars(
        select(Edicao).options(selectinload(Edicao.capitulos)).order_by(Edicao.id)
    ).all()
    return [
        EdicaoResumo(
            id=e.id,
            titulo=e.titulo,
            idioma=e.idioma,
            publicada=e.publicada_em is not None,
            capitulos_por_estado=_contagem(e),
        )
        for e in edicoes
    ]


@router.get("/edicoes/{edicao_id}/capitulos")
def listar_capitulos(
    edicao_id: int,
    estado: EstadoCapitulo | None = None,
    _: Usuario = Depends(pode_ver_admin),
    session: Session = Depends(get_session),
) -> list[CapituloResumo]:
    if session.get(Edicao, edicao_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "edição não encontrada")
    consulta = select(Capitulo).where(Capitulo.edicao_id == edicao_id).order_by(Capitulo.ordem)
    if estado:
        consulta = consulta.where(Capitulo.estado == estado)
    return [
        CapituloResumo.model_validate(c, from_attributes=True) for c in session.scalars(consulta)
    ]


@router.get("/capitulos/{capitulo_id}")
def ver_capitulo(
    capitulo_id: int,
    usuario: Usuario = Depends(pode_ver_admin),
    session: Session = Depends(get_session),
) -> CapituloDetalhe:
    return _detalhe(session, _capitulo(session, capitulo_id), usuario)


@router.post("/capitulos/{capitulo_id}/transicoes")
def transicionar(
    capitulo_id: int,
    pedido: PedidoTransicao,
    request: Request,
    usuario: Usuario = Depends(pode_ver_admin),
    session: Session = Depends(get_session),
) -> CapituloDetalhe:
    capitulo = _capitulo(session, capitulo_id, travar=True)
    antes = capitulo.estado
    try:
        editorial.aplicar(capitulo, pedido.acao, usuario.papel, pedido.motivo)
    except editorial.SemPermissao as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sem permissão") from e
    except editorial.TransicaoInvalida as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    detalhes: dict[str, object] = {"de": antes.value, "para": capitulo.estado.value}
    if pedido.motivo:
        detalhes["motivo"] = pedido.motivo.strip()
    contas.registrar(
        session,
        f"capitulo_{pedido.acao}",
        usuario,
        "capitulo",
        capitulo.id,
        ip_do_cliente(request),
        **detalhes,
    )
    session.commit()
    return _detalhe(session, capitulo, usuario)


@router.patch("/segmentos/{segmento_id}")
def editar_segmento(
    segmento_id: int,
    dados: EdicaoTexto,
    request: Request,
    usuario: Usuario = Depends(pode_editar_segmento),
    session: Session = Depends(get_session),
) -> SegmentoSaida:
    segmento = session.get(Segmento, segmento_id)
    if segmento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "segmento não encontrado")
    # Trava o capítulo: sem isso, uma aprovação de texto simultânea passaria com a
    # edição entrando logo depois, num capítulo já marcado como revisado.
    capitulo = _capitulo(session, segmento.capitulo_id, travar=True)
    if not editorial.texto_editavel(capitulo):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"capítulo em '{capitulo.estado.value}'; reabra o texto para editar",
        )
    novo = dados.texto.strip()
    if novo != segmento.texto:
        contas.registrar(
            session,
            "segmento_editado",
            usuario,
            "segmento",
            segmento.id,
            ip_do_cliente(request),
            antes=segmento.texto,
            depois=novo,
            capitulo_id=capitulo.id,
        )
        segmento.texto = novo
    session.commit()
    original = _textos_importados(session, [segmento.id]).get(segmento.id)
    return SegmentoSaida(
        id=segmento.id,
        ordem=segmento.ordem,
        tipo=segmento.tipo,
        texto=segmento.texto,
        numero_questao=segmento.numero_questao,
        subquestao=segmento.subquestao,
        texto_importado=original if original != segmento.texto else None,
    )


@router.get("/capitulos/{capitulo_id}/historico")
def historico(
    capitulo_id: int,
    _: Usuario = Depends(pode_ver_admin),
    session: Session = Depends(get_session),
) -> list[EventoHistorico]:
    """Transições do capítulo e edições dos seus segmentos, em ordem."""
    _capitulo(session, capitulo_id)
    ids_segmentos = select(Segmento.id).where(Segmento.capitulo_id == capitulo_id)
    registros = session.scalars(
        select(RegistroAuditoria)
        .where(
            (
                (RegistroAuditoria.alvo_tipo == "capitulo")
                & (RegistroAuditoria.alvo_id == capitulo_id)
            )
            | (
                (RegistroAuditoria.alvo_tipo == "segmento")
                & RegistroAuditoria.alvo_id.in_(ids_segmentos)
            )
        )
        .order_by(RegistroAuditoria.id)
    )
    return [EventoHistorico.model_validate(r, from_attributes=True) for r in registros]


@router.post("/capitulos/{capitulo_id}/revisoes-ia", status_code=status.HTTP_201_CREATED)
def anexar_revisao_ia(
    capitulo_id: int,
    dados: RevisaoIAEntrada,
    request: Request,
    usuario: Usuario = Depends(pode_anexar_revisao),
    session: Session = Depends(get_session),
) -> RevisaoIASaida:
    """Anexa o relatório da revisão por IA (#98) a um capítulo adaptado."""
    capitulo = _capitulo(session, capitulo_id)
    contagem = {"bloqueio": dados.bloqueios, "atencao": dados.atencoes, "ok": dados.ok}
    try:
        revisao = revisao_doutrinaria.anexar(
            session, capitulo, dados.relatorio, contagem, usuario, ip_do_cliente(request)
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    session.commit()
    return RevisaoIASaida.model_validate(revisao, from_attributes=True)


@router.get("/capitulos/{capitulo_id}/revisoes-ia")
def listar_revisoes_ia(
    capitulo_id: int,
    _: Usuario = Depends(pode_ver_admin),
    session: Session = Depends(get_session),
) -> list[RevisaoIASaida]:
    """Da mais recente à mais antiga, com o relatório inteiro."""
    _capitulo(session, capitulo_id)
    return [
        RevisaoIASaida.model_validate(r, from_attributes=True)
        for r in session.scalars(_revisoes_ia(capitulo_id))
    ]
