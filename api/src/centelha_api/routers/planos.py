"""Planos de estudo (#43, decisão 2A): roteiros fixos, com o texto escrito pela IA.

Os roteiros moram em conteudo/planos.json, versionados no repositório. Assim o dono os
revisa na PR antes de irem ao ar, e uma mudança de roteiro tem histórico. Não há
tabela nem admin: são três planos, e editar o JSON numa PR é o fluxo de revisão.

Cada leitura aponta para a obra por referência canônica, e não pelo id de uma edição:
- questões do LE ({"sigla": "LE", "de": 1, "ate": 16}), numeração igual em todas as
  traduções;
- capítulo ({"sigla": "ESE", "capitulo": "ESE-C003"}).
O app resolve a referência na edição que a pessoa lê.
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field, model_validator

router = APIRouter(prefix="/v1/planos", tags=["planos"])

_ARQUIVO = Path(__file__).resolve().parent.parent / "conteudo" / "planos.json"
# O conteúdo só muda com deploy: o cache pode ser longo.
_CACHE = "public, max-age=3600, s-maxage=86400"
_ULTIMA_QUESTAO_LE = 1019
_REFERENCIA = re.compile(r"^(?P<sigla>[A-Z]{2,5})-C\d{3}$")


class Leitura(BaseModel):
    sigla: Literal["LE", "ESE"]
    capitulo: str | None = None
    de: int | None = Field(default=None, ge=1, le=_ULTIMA_QUESTAO_LE)
    ate: int | None = Field(default=None, ge=1, le=_ULTIMA_QUESTAO_LE)

    @model_validator(mode="after")
    def _uma_forma(self) -> "Leitura":
        if self.capitulo is not None:
            m = _REFERENCIA.match(self.capitulo)
            if self.de is not None or self.ate is not None:
                raise ValueError("leitura é capítulo ou faixa de questões, não os dois")
            if not m or m["sigla"] != self.sigla:
                raise ValueError(f"referência de capítulo inválida: {self.capitulo}")
        else:
            if self.sigla != "LE" or self.de is None or self.ate is None:
                raise ValueError("faixa de questões só existe no LE, com de e ate")
            if self.de > self.ate:
                raise ValueError(f"faixa invertida: {self.de} a {self.ate}")
        return self


class Dia(BaseModel):
    dia: int
    titulo: str
    leituras: list[Leitura] = Field(min_length=1)


class PlanoResumo(BaseModel):
    slug: str
    titulo: str
    descricao: str
    dias: int


class Plano(BaseModel):
    slug: str
    titulo: str
    descricao: str
    dias: list[Dia]

    @model_validator(mode="after")
    def _dias_em_ordem(self) -> "Plano":
        if [d.dia for d in self.dias] != list(range(1, len(self.dias) + 1)):
            raise ValueError(f"plano {self.slug}: dias fora de ordem ou faltando")
        return self


class ArquivoPlanos(BaseModel):
    versao: int
    idioma: str
    autoria: str
    planos: list[Plano]


@cache
def carregar() -> ArquivoPlanos:
    """Lê e valida o arquivo. Erro aqui derruba a subida da api e os testes: roteiro
    quebrado não chega ao app."""
    return ArquivoPlanos.model_validate(json.loads(_ARQUIVO.read_text(encoding="utf-8")))


@router.get("", response_model=list[PlanoResumo])
def listar(response: Response) -> list[PlanoResumo]:
    response.headers["Cache-Control"] = _CACHE
    return [
        PlanoResumo(slug=p.slug, titulo=p.titulo, descricao=p.descricao, dias=len(p.dias))
        for p in carregar().planos
    ]


@router.get("/{slug}", response_model=Plano)
def detalhe(slug: str, response: Response) -> Plano:
    for p in carregar().planos:
        if p.slug == slug:
            response.headers["Cache-Control"] = _CACHE
            return p
    raise HTTPException(404, "plano não encontrado")
