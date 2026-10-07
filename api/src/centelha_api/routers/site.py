"""Marca do conteúdo do site (#42): o site-construtor regera o site quando ela muda.

A marca cobre tudo o que o build do site lê da API, publicado ou não: rascunho editado
também a muda, e o construtor só espera ela parar de mudar antes de regerar. Não diz
nada além de "mudou": é um hash, sem datas nem contagens.
"""

import hashlib

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Base

router = APIRouter(prefix="/v1/site", tags=["site"])

# Tabelas que o build do site lê, direta ou indiretamente (src/lib/*.ts do site).
TABELAS = (
    "obra",
    "edicao",
    "direitos",
    "capitulo",
    "segmento",
    "voz",
    "faixa_audio",
    "tema",
    "tema_referencia",
    "post",
    "post_referencia",
    "termo",
    "termo_referencia",
    "mes_transparencia",
    "lancamento_transparencia",
    "config_apoio",
    "instituicao",
    "campanha",
)


def _consulta(nome: str) -> str:
    # Hash das linhas, na ordem da chave: pega inclusão, exclusão e qualquer alteração,
    # inclusive feita fora do ORM (o atualizado_em só muda pelo ORM).
    chave = ", ".join(c.name for c in Base.metadata.tables[nome].primary_key.columns)
    return f"select md5(coalesce(string_agg(t::text, '|' order by {chave}), '')) from {nome} t"


# Uma consulta só; os nomes vêm da lista acima e do modelo, nunca da requisição.
_SQL = text(
    "select "
    + ", ".join(f"({_consulta(n)})" for n in TABELAS)
    # A situação das campanhas e o "hoje" das páginas mudam com a data do banco.
    + ", current_date::text"
)


@router.get("/marca")
def marca(response: Response, session: Session = Depends(get_session)) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    partes = session.execute(_SQL).one()
    return {"marca": hashlib.sha256("\n".join(partes).encode()).hexdigest()}
