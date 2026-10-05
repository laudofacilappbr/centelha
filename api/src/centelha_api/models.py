"""Modelo de dados da especificação.

A obra é independente de idioma; tudo que tem idioma fica na edição. Um idioma novo
ou uma adaptação juvenil/infantil é uma nova edição da mesma obra, sem mudar o esquema.
"""

import enum
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _enum(cls: type[enum.Enum]) -> Enum:
    return Enum(cls, name=cls.__name__.lower(), values_callable=lambda e: [m.value for m in e])


class Publico(enum.StrEnum):
    ADULTO = "adulto"
    JUVENIL = "juvenil"
    INFANTIL = "infantil"


class StatusDireitos(enum.StrEnum):
    PENDENTE = "pendente"
    APROVADO = "aprovado"
    RECUSADO = "recusado"


class EstadoCapitulo(enum.StrEnum):
    """Fluxo editorial do admin; reprovação volta um passo."""

    IMPORTADO = "importado"
    TEXTO_REVISADO = "texto_revisado"
    AUDIO_GERADO = "audio_gerado"
    AUDIO_REVISADO = "audio_revisado"
    PUBLICADO = "publicado"


class TipoSegmento(enum.StrEnum):
    TITULO = "titulo"
    PARAGRAFO = "paragrafo"
    PERGUNTA = "pergunta"
    RESPOSTA = "resposta"
    COMENTARIO = "comentario"
    NOTA = "nota"


class PapelVoz(enum.StrEnum):
    NARRADOR = "narrador"
    PERGUNTA = "pergunta"
    RESPOSTA = "resposta"


class Timestamps:
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Obra(Timestamps, Base):
    __tablename__ = "obra"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    autor: Mapped[str] = mapped_column(String(200))
    titulo_original: Mapped[str] = mapped_column(String(300))
    ano: Mapped[int | None]
    idioma_original: Mapped[str] = mapped_column(String(35))
    # Prefixo da referência canônica, ex.: "LE" para O Livro dos Espíritos (LE-150).
    sigla: Mapped[str] = mapped_column(String(10), unique=True)

    edicoes: Mapped[list["Edicao"]] = relationship(back_populates="obra")


class Edicao(Timestamps, Base):
    __tablename__ = "edicao"

    id: Mapped[int] = mapped_column(primary_key=True)
    obra_id: Mapped[int] = mapped_column(ForeignKey("obra.id"))
    idioma: Mapped[str] = mapped_column(String(35))  # BCP 47, ex.: pt-BR
    publico: Mapped[Publico] = mapped_column(_enum(Publico), default=Publico.ADULTO)
    titulo: Mapped[str] = mapped_column(String(300))
    tradutor: Mapped[str | None] = mapped_column(String(200))
    fonte: Mapped[str] = mapped_column(Text)
    # Notas de rodapé: "fim_paragrafo" ou "omitir" (normalização do pipeline).
    notas_rodape: Mapped[str] = mapped_column(String(20), default="fim_paragrafo")
    publicada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    obra: Mapped[Obra] = relationship(back_populates="edicoes")
    direitos: Mapped["Direitos | None"] = relationship(back_populates="edicao")
    capitulos: Mapped[list["Capitulo"]] = relationship(
        back_populates="edicao", order_by="Capitulo.ordem"
    )


class Direitos(Timestamps, Base):
    __tablename__ = "direitos"

    id: Mapped[int] = mapped_column(primary_key=True)
    edicao_id: Mapped[int] = mapped_column(ForeignKey("edicao.id"), unique=True)
    status: Mapped[StatusDireitos] = mapped_column(
        _enum(StatusDireitos), default=StatusDireitos.PENDENTE
    )
    falecimento_tradutor: Mapped[date | None] = mapped_column(Date)
    base_legal: Mapped[str | None] = mapped_column(Text)
    documento_url: Mapped[str | None] = mapped_column(Text)
    aprovado_por: Mapped[str | None] = mapped_column(String(200))
    aprovado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    edicao: Mapped[Edicao] = relationship(back_populates="direitos")


class Capitulo(Timestamps, Base):
    __tablename__ = "capitulo"
    __table_args__ = (UniqueConstraint("edicao_id", "ordem"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    edicao_id: Mapped[int] = mapped_column(ForeignKey("edicao.id"))
    ordem: Mapped[int]
    titulo: Mapped[str] = mapped_column(String(300))
    # Liga o mesmo capítulo entre idiomas, ex.: "ESE-05".
    referencia_canonica: Mapped[str] = mapped_column(String(40))
    estado: Mapped[EstadoCapitulo] = mapped_column(
        _enum(EstadoCapitulo), default=EstadoCapitulo.IMPORTADO
    )

    edicao: Mapped[Edicao] = relationship(back_populates="capitulos")
    segmentos: Mapped[list["Segmento"]] = relationship(
        back_populates="capitulo", order_by="Segmento.ordem"
    )
    faixas: Mapped[list["FaixaAudio"]] = relationship(back_populates="capitulo")


class Segmento(Base):
    __tablename__ = "segmento"
    __table_args__ = (UniqueConstraint("capitulo_id", "ordem"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    capitulo_id: Mapped[int] = mapped_column(ForeignKey("capitulo.id"))
    ordem: Mapped[int]
    tipo: Mapped[TipoSegmento] = mapped_column(_enum(TipoSegmento))
    texto: Mapped[str] = mapped_column(Text)
    numero_questao: Mapped[int | None] = mapped_column(Integer, index=True)
    # Letra da subquestão: 88a → numero_questao=88, subquestao="a" (referência LE-88a).
    subquestao: Mapped[str | None] = mapped_column(String(4))

    capitulo: Mapped[Capitulo] = relationship(back_populates="segmentos")


class Voz(Base):
    __tablename__ = "voz"

    id: Mapped[int] = mapped_column(primary_key=True)
    idioma: Mapped[str] = mapped_column(String(35))
    motor: Mapped[str] = mapped_column(String(40))  # azure, google, elevenlabs, piper
    voz_id: Mapped[str] = mapped_column(String(120))
    papel: Mapped[PapelVoz] = mapped_column(_enum(PapelVoz))
    publico: Mapped[Publico] = mapped_column(_enum(Publico), default=Publico.ADULTO)


class FaixaAudio(Base):
    __tablename__ = "faixa_audio"
    __table_args__ = (UniqueConstraint("capitulo_id", "voz_id", "versao"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    capitulo_id: Mapped[int] = mapped_column(ForeignKey("capitulo.id"))
    voz_id: Mapped[int] = mapped_column(ForeignKey("voz.id"))
    versao: Mapped[int] = mapped_column(default=1)
    url: Mapped[str] = mapped_column(Text)
    duracao_ms: Mapped[int]
    # [{"segmento_id": 1, "inicio_ms": 0, "fim_ms": 4200}, ...] para a leitura acompanhada.
    marcacoes: Mapped[list[dict]] = mapped_column(JSON, default=list)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    capitulo: Mapped[Capitulo] = relationship(back_populates="faixas")


class Pronuncia(Timestamps, Base):
    __tablename__ = "pronuncia"
    __table_args__ = (UniqueConstraint("idioma", "termo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    idioma: Mapped[str] = mapped_column(String(35))
    termo: Mapped[str] = mapped_column(String(120))
    # Grafia para <sub alias> ou fonemas IPA para <phoneme>.
    substituicao: Mapped[str | None] = mapped_column(String(200))
    ipa: Mapped[str | None] = mapped_column(String(200))


class InscricaoListaEspera(Base):
    __tablename__ = "inscricao_lista_espera"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    origem: Mapped[str] = mapped_column(String(40))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
