"""Apoio ao projeto (#40): configuração no admin, leitura pública para o site e o app.

Opção C decidida pelo dono: compra no app como padrão nas lojas, Pix e link externo
onde for permitido. O apoio nasce desligado; ligar exige dizer quem recebe e ter ao
menos um meio. Apoiar não libera conteúdo, e o perfil infantil nunca mostra nada disto
(o app ignora a configuração nesse perfil).
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..db import get_session
from ..dominio import contas
from ..dominio.permissoes import Permissao
from ..models import ConfigApoio, Usuario
from ..ratelimit import ip_do_cliente
from .admin import exigir
from .catalogo import _cache

publico = APIRouter(prefix="/v1", tags=["site"])
admin = APIRouter(prefix="/v1/admin/apoio", tags=["admin"])
pode_gerir = exigir(Permissao.GERIR_APOIO)

# Formatos de chave Pix do Banco Central, já sem espaços.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TELEFONE = re.compile(r"^\+55\d{10,11}$")
_ALEATORIA = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_CNPJ = re.compile(r"^\d{14}$")


def _chave_pix(valor: str) -> str:
    chave = re.sub(r"\s", "", valor)
    so_digitos = re.sub(r"[.\-/]", "", chave)
    if re.fullmatch(r"\d{11}", so_digitos):
        # CPF na página pública expõe o documento de quem recebe (hoje pessoa física,
        # #4). Chave aleatória, e-mail ou telefone recebem o mesmo Pix sem isso.
        raise ValueError("chave CPF não é aceita: use chave aleatória, e-mail ou telefone")
    if _CNPJ.fullmatch(so_digitos):
        return so_digitos
    if _ALEATORIA.fullmatch(chave.lower()):
        return chave.lower()
    if _TELEFONE.fullmatch(chave) or (len(chave) <= 77 and _EMAIL.fullmatch(chave)):
        return chave
    raise ValueError("chave Pix inválida: use chave aleatória, e-mail, telefone (+55…) ou CNPJ")


class Apoio(BaseModel):
    ligado: bool = False
    recebedor: str | None = Field(default=None, min_length=2, max_length=200)
    mensagem: str | None = Field(default=None, max_length=500)
    # R$ 1 a R$ 1.000; no máximo seis botões.
    valores_centavos: list[int] = Field(default_factory=list, max_length=6)
    compra_no_app: bool = False
    chave_pix: str | None = Field(default=None, max_length=100)
    link_externo: str | None = Field(default=None, max_length=500)

    @field_validator("valores_centavos")
    @classmethod
    def _valores(cls, v: list[int]) -> list[int]:
        if any(x < 100 or x > 100_000 for x in v):
            raise ValueError("cada valor entre 100 e 100000 centavos")
        return sorted(set(v))

    @field_validator("chave_pix")
    @classmethod
    def _pix(cls, v: str | None) -> str | None:
        return None if v is None or not v.strip() else _chave_pix(v)

    @field_validator("link_externo")
    @classmethod
    def _link(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        # Só https: o link sai do site e do app com dinheiro do outro lado.
        if not re.fullmatch(r"https://[^\s<>\"']+", v.strip()):
            raise ValueError("link externo precisa começar com https://")
        return v.strip()


class ApoioPublico(BaseModel):
    """Desligado, só `ligado: false`: nada de meio ou recebedor parado no ar."""

    ligado: bool
    recebedor: str | None = None
    mensagem: str | None = None
    valores_centavos: list[int] = []
    compra_no_app: bool = False
    chave_pix: str | None = None
    link_externo: str | None = None


def carregar(session: Session) -> ConfigApoio:
    return session.get(ConfigApoio, 1) or ConfigApoio(
        id=1, ligado=False, valores_centavos=[], compra_no_app=False
    )


def _dados(cfg: ConfigApoio) -> Apoio:
    return Apoio.model_validate(cfg, from_attributes=True)


@publico.get("/apoio")
def apoio_publico(response: Response, session: Session = Depends(get_session)) -> ApoioPublico:
    _cache(response)
    cfg = carregar(session)
    if not cfg.ligado:
        return ApoioPublico(ligado=False)
    return ApoioPublico(**_dados(cfg).model_dump())


@admin.get("")
def ver(_: Usuario = Depends(pode_gerir), session: Session = Depends(get_session)) -> Apoio:
    return _dados(carregar(session))


@admin.put("")
def alterar(
    dados: Apoio,
    request: Request,
    autor: Usuario = Depends(pode_gerir),
    session: Session = Depends(get_session),
) -> Apoio:
    if dados.ligado:
        faltando = []
        if not dados.recebedor:
            # A página diz para quem vai o dinheiro; sem isso o apoio parece caridade.
            faltando.append("quem recebe")
        if not (dados.compra_no_app or dados.chave_pix or dados.link_externo):
            faltando.append("um meio (compra no app, Pix ou link)")
        if not dados.valores_centavos:
            faltando.append("ao menos um valor sugerido")
        if faltando:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "para ligar, falta: " + ", ".join(faltando)
            )
    cfg = session.get(ConfigApoio, 1, with_for_update=True)
    if cfg is None:
        cfg = ConfigApoio(id=1)
        session.add(cfg)
        antes = None
    else:
        antes = _dados(cfg).model_dump(mode="json")
    for k, v in dados.model_dump().items():
        setattr(cfg, k, v)
    cfg.atualizado_por_id = autor.id
    contas.registrar(
        session,
        "apoio_alterado",
        autor,
        "config_apoio",
        1,
        ip_do_cliente(request),
        antes=antes,
        depois=dados.model_dump(mode="json"),
    )
    session.commit()
    return _dados(cfg)
