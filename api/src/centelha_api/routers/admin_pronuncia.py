"""Admin: dicionário de pronúncia e regeneração dos capítulos afetados (#23)."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..dominio import contas, dicionario
from ..dominio.permissoes import Permissao
from ..models import EstadoCapitulo, Pronuncia, Usuario
from ..ratelimit import ip_do_cliente
from .admin import exigir, pode_ver_admin

router = APIRouter(prefix="/v1/admin/pronuncias", tags=["admin"])
pode_editar_dicionario = exigir(Permissao.EDITAR_DICIONARIO)
pode_gerar_audio = exigir(Permissao.GERAR_AUDIO)


class Grafia(BaseModel):
    substituicao: str | None = Field(default=None, max_length=200)
    ipa: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _alguma(self) -> "Grafia":
        self.substituicao = (self.substituicao or "").strip() or None
        self.ipa = (self.ipa or "").strip() or None
        # Entrada sem grafia nem IPA não muda nada na síntese e ainda parece corrigida.
        if not self.substituicao and not self.ipa:
            raise ValueError("informe substituicao ou ipa")
        return self


class NovaPronuncia(Grafia):
    idioma: str = Field(min_length=2, max_length=35)
    termo: str = Field(min_length=1, max_length=120)
    # Capítulo em que o erro foi ouvido; vai para a auditoria como origem.
    capitulo_id: int | None = None


class AfetadoSaida(BaseModel):
    capitulo_id: int
    edicao_id: int
    titulo: str
    estado: EstadoCapitulo
    ocorrencias: int


class PronunciaSaida(BaseModel):
    id: int
    idioma: str
    termo: str
    substituicao: str | None
    ipa: str | None


class PronunciaComAfetados(PronunciaSaida):
    # Capítulos com áudio que ficaram desatualizados por esta mudança.
    capitulos_afetados: list[AfetadoSaida]


class Regeneracao(BaseModel):
    enfileirados: list[int]
    pulados: dict[int, str]


def _pronuncia(session: Session, pronuncia_id: int) -> Pronuncia:
    p = session.get(Pronuncia, pronuncia_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entrada não encontrada")
    return p


def _com_afetados(session: Session, p: Pronuncia, afetados=None) -> PronunciaComAfetados:
    if afetados is None:
        afetados = dicionario.capitulos_afetados(session, p.idioma, p.termo)
    return PronunciaComAfetados(
        **PronunciaSaida.model_validate(p, from_attributes=True).model_dump(),
        capitulos_afetados=[AfetadoSaida(**asdict(a)) for a in afetados],
    )


@router.get("")
def listar(
    idioma: str | None = None,
    _: Usuario = Depends(pode_ver_admin),
    session: Session = Depends(get_session),
) -> list[PronunciaSaida]:
    consulta = select(Pronuncia).order_by(Pronuncia.idioma, Pronuncia.termo)
    if idioma:
        consulta = consulta.where(Pronuncia.idioma == idioma)
    return [
        PronunciaSaida.model_validate(p, from_attributes=True) for p in session.scalars(consulta)
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(
    dados: NovaPronuncia,
    request: Request,
    autor: Usuario = Depends(pode_editar_dicionario),
    session: Session = Depends(get_session),
) -> PronunciaComAfetados:
    termo = dados.termo.strip()
    existe = session.scalar(
        select(Pronuncia.id).where(Pronuncia.idioma == dados.idioma, Pronuncia.termo == termo)
    )
    if existe:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"'{termo}' já está no dicionário (id {existe})"
        )
    p = Pronuncia(idioma=dados.idioma, termo=termo, substituicao=dados.substituicao, ipa=dados.ipa)
    session.add(p)
    session.flush()
    contas.registrar(
        session,
        "pronuncia_criada",
        autor,
        "pronuncia",
        p.id,
        ip_do_cliente(request),
        termo=termo,
        substituicao=p.substituicao,
        ipa=p.ipa,
        capitulo_origem=dados.capitulo_id,
    )
    session.commit()
    return _com_afetados(session, p)


@router.get("/{pronuncia_id}")
def ver(
    pronuncia_id: int,
    _: Usuario = Depends(pode_ver_admin),
    session: Session = Depends(get_session),
) -> PronunciaComAfetados:
    return _com_afetados(session, _pronuncia(session, pronuncia_id))


@router.patch("/{pronuncia_id}")
def alterar(
    pronuncia_id: int,
    dados: Grafia,
    request: Request,
    autor: Usuario = Depends(pode_editar_dicionario),
    session: Session = Depends(get_session),
) -> PronunciaComAfetados:
    # Termo e idioma não mudam: trocar o termo é outra entrada (apague e crie), e os
    # capítulos afetados pelo termo antigo seriam esquecidos.
    p = _pronuncia(session, pronuncia_id)
    antes = {"substituicao": p.substituicao, "ipa": p.ipa}
    p.substituicao, p.ipa = dados.substituicao, dados.ipa
    depois = {"substituicao": p.substituicao, "ipa": p.ipa}
    if antes != depois:
        contas.registrar(
            session,
            "pronuncia_alterada",
            autor,
            "pronuncia",
            p.id,
            ip_do_cliente(request),
            termo=p.termo,
            antes=antes,
            depois=depois,
        )
    session.commit()
    return _com_afetados(session, p)


@router.delete("/{pronuncia_id}")
def apagar(
    pronuncia_id: int,
    request: Request,
    autor: Usuario = Depends(pode_editar_dicionario),
    session: Session = Depends(get_session),
) -> PronunciaComAfetados:
    p = _pronuncia(session, pronuncia_id)
    # Afetados calculados antes de apagar, com o dicionário que ainda tem a entrada:
    # são os capítulos cujo áudio usa a grafia que deixa de existir.
    afetados = dicionario.capitulos_afetados(session, p.idioma, p.termo)
    saida = _com_afetados(session, p, afetados)
    contas.registrar(
        session,
        "pronuncia_apagada",
        autor,
        "pronuncia",
        p.id,
        ip_do_cliente(request),
        termo=p.termo,
        substituicao=p.substituicao,
        ipa=p.ipa,
    )
    session.delete(p)
    session.commit()
    return saida


@router.post("/{pronuncia_id}/regenerar")
def regenerar(
    pronuncia_id: int,
    autor: Usuario = Depends(pode_gerar_audio),
    session: Session = Depends(get_session),
) -> Regeneracao:
    """Enfileira de novo os capítulos afetados, com as vozes da última geração de cada um.
    Publicados ficam de fora (despublicar é decisão de quem publica)."""
    p = _pronuncia(session, pronuncia_id)
    afetados = dicionario.capitulos_afetados(session, p.idioma, p.termo)
    r = dicionario.regenerar(session, afetados, autor)
    return Regeneracao(enfileirados=r.enfileirados, pulados=r.pulados)
