"""Campos de SEO opcionais de edição, capítulo e post (#42).

Vazio vira None, e o site cai no modelo da página ("Questão 88 — O Livro dos
Espíritos"). O texto é puro: o site escapa tudo, em <title> e <meta>.
"""

from pydantic import BaseModel, Field, field_validator


class CamposSeo(BaseModel):
    # 60 porque o site acrescenta " | Centelhar"; 160 é o que a busca costuma mostrar.
    seo_titulo: str | None = Field(default=None, max_length=60)
    seo_descricao: str | None = Field(default=None, max_length=160)

    @field_validator("seo_titulo", "seo_descricao", mode="before")
    @classmethod
    def _vazio_e_none(cls, v):
        if isinstance(v, str):
            # Quebra de linha num <title> vira espaço no Google; melhor não guardar.
            v = " ".join(v.split())
            return v or None
        return v
