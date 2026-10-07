"""Modelo de dados da especificação.

A obra é independente de idioma; tudo que tem idioma fica na edição. Um idioma novo
ou uma adaptação juvenil/infantil é uma nova edição da mesma obra, sem mudar o esquema.
"""

import enum
from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
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
    # Só edições juvenis e infantis (#49): adaptação passa por revisão doutrinária e de
    # linguagem antes de virar áudio. Edição adulta pula este estado.
    DOUTRINA_REVISADA = "doutrina_revisada"
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
    __table_args__ = (
        UniqueConstraint("idioma", "publico", "slug", name="edicao_idioma_publico_slug_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    obra_id: Mapped[int] = mapped_column(ForeignKey("obra.id"))
    idioma: Mapped[str] = mapped_column(String(35))  # BCP 47, ex.: pt-BR
    publico: Mapped[Publico] = mapped_column(_enum(Publico), default=Publico.ADULTO)
    titulo: Mapped[str] = mapped_column(String(300))
    # URL da edição nos outros idiomas do site (#48, decisão 2A): /fr/oeuvres/<slug>.
    # Preenchido na publicação a partir do título e fixo depois, para a URL não mudar.
    # O português continua no slug da obra.
    slug: Mapped[str | None] = mapped_column(String(120))
    # SEO opcional (#42): vazio, o site usa o modelo da página. Título curto porque o
    # site acrescenta " | Centelhar"; descrição no tamanho que a busca mostra.
    seo_titulo: Mapped[str | None] = mapped_column(String(60))
    seo_descricao: Mapped[str | None] = mapped_column(String(160))
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
    # SEO opcional (#42): vazio, o site usa o modelo da página. Título curto porque o
    # site acrescenta " | Centelhar"; descrição no tamanho que a busca mostra.
    seo_titulo: Mapped[str | None] = mapped_column(String(60))
    seo_descricao: Mapped[str | None] = mapped_column(String(160))
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
    # "m4a" aberto ou "cent1" cifrado (ADR 0004). A chave da faixa fica embrulhada pela
    # chave-mestra e nunca sai na API pública: só o app atestado a recebe.
    formato: Mapped[str] = mapped_column(String(10), default="m4a", server_default="m4a")
    chave_cifrada: Mapped[bytes | None] = mapped_column(LargeBinary)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    capitulo: Mapped[Capitulo] = relationship(back_populates="faixas")


class RevisaoIA(Base):
    """Relatório da primeira revisão doutrinária feita por IA num capítulo adaptado (#98).
    Só informa quem aprova no admin: não muda o estado nem trava a aprovação."""

    __tablename__ = "revisao_ia"

    id: Mapped[int] = mapped_column(primary_key=True)
    capitulo_id: Mapped[int] = mapped_column(ForeignKey("capitulo.id"), index=True)
    relatorio: Mapped[str] = mapped_column(Text)
    bloqueios: Mapped[int]
    atencoes: Mapped[int]
    ok: Mapped[int]
    # Nulo quando veio do comando no servidor, sem usuário do admin.
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Pronuncia(Timestamps, Base):
    __tablename__ = "pronuncia"
    __table_args__ = (UniqueConstraint("idioma", "termo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    idioma: Mapped[str] = mapped_column(String(35))
    termo: Mapped[str] = mapped_column(String(120))
    # Grafia para <sub alias> ou fonemas IPA para <phoneme>.
    substituicao: Mapped[str | None] = mapped_column(String(200))
    ipa: Mapped[str | None] = mapped_column(String(200))


class PapelUsuario(enum.StrEnum):
    """Papéis do admin (especificação, seção Admin). As permissões de cada um
    ficam em dominio/permissoes.py, não no banco: mudar quem pode o quê é
    mudança de código revisada, não um clique no painel."""

    ADMINISTRADOR = "administrador"
    REVISOR_TEXTO = "revisor_texto"
    REVISOR_AUDIO = "revisor_audio"


class Usuario(Timestamps, Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Sempre minúsculo; a unicidade depende disso.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    nome: Mapped[str] = mapped_column(String(200))
    senha_hash: Mapped[str] = mapped_column(String(200))
    papel: Mapped[PapelUsuario] = mapped_column(_enum(PapelUsuario))
    # Desativar em vez de apagar: o log de auditoria continua apontando para alguém.
    ativo: Mapped[bool] = mapped_column(default=True, server_default="true")


class SessaoAdmin(Base):
    __tablename__ = "sessao_admin"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    # SHA-256 do token. O token em si só existe na resposta do login: um vazamento
    # do banco não entrega sessões válidas.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    usuario: Mapped[Usuario] = relationship()


class RegistroAuditoria(Base):
    """Quem fez o quê, append-only. Nenhum código atualiza ou apaga linhas daqui."""

    __tablename__ = "registro_auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nulo só quando não há usuário identificado (ex.: login com e-mail desconhecido).
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    acao: Mapped[str] = mapped_column(String(60), index=True)
    alvo_tipo: Mapped[str | None] = mapped_column(String(40))
    alvo_id: Mapped[int | None]
    detalhes: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    usuario: Mapped[Usuario | None] = relationship()


class InscricaoListaEspera(Base):
    __tablename__ = "inscricao_lista_espera"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    origem: Mapped[str] = mapped_column(String(40))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EstadoJob(enum.StrEnum):
    PENDENTE = "pendente"
    EXECUTANDO = "executando"
    CONCLUIDO = "concluido"
    FALHOU = "falhou"


class JobAudio(Base):
    """Geração do áudio de um capítulo, na fila do próprio PostgreSQL.

    O worker pega com SELECT ... FOR UPDATE SKIP LOCKED; com vários workers, cada job
    sai para um só. Worker que morre no meio deixa o job em "executando" com lease
    vencido, e outro worker o retoma.
    """

    __tablename__ = "job_audio"
    __table_args__ = (
        # Um job ativo por capítulo: pedir duas vezes não gera (nem cobra) duas vezes.
        Index(
            "uq_job_audio_ativo_por_capitulo",
            "capitulo_id",
            unique=True,
            postgresql_where="estado IN ('pendente', 'executando')",
        ),
        Index("ix_job_audio_fila", "estado", "disponivel_em"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    capitulo_id: Mapped[int] = mapped_column(ForeignKey("capitulo.id"), index=True)
    motor: Mapped[str] = mapped_column(String(40))
    voz_narrador_id: Mapped[int] = mapped_column(ForeignKey("voz.id"))
    voz_pergunta_id: Mapped[int | None] = mapped_column(ForeignKey("voz.id"))
    voz_resposta_id: Mapped[int | None] = mapped_column(ForeignKey("voz.id"))
    estado: Mapped[EstadoJob] = mapped_column(_enum(EstadoJob), default=EstadoJob.PENDENTE)
    tentativas: Mapped[int] = mapped_column(default=0)
    max_tentativas: Mapped[int] = mapped_column(default=3)
    disponivel_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    lease_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erro: Mapped[str | None] = mapped_column(Text)
    caracteres: Mapped[int | None]
    faixa_id: Mapped[int | None] = mapped_column(ForeignKey("faixa_audio.id"))
    solicitado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    iniciado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    capitulo: Mapped[Capitulo] = relationship()


class TipoLancamento(enum.StrEnum):
    CUSTO = "custo"
    ARRECADACAO = "arrecadacao"


class MesTransparencia(Base):
    """Um mês da prestação de contas pública (#36).

    Só aparece no site depois de publicado: um mês com metade dos lançamentos daria
    um custo menor que o real, e é exatamente a conta que a página existe para mostrar.
    """

    __tablename__ = "mes_transparencia"
    # Primeiro dia do mês; o dia não significa nada além disso.
    __table_args__ = (CheckConstraint("extract(day from mes) = 1", name="mes_no_dia_1"),)

    mes: Mapped[date] = mapped_column(Date, primary_key=True)
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publicado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))

    lancamentos: Mapped[list["LancamentoTransparencia"]] = relationship(
        back_populates="mes_ref", order_by="LancamentoTransparencia.id"
    )


class LancamentoTransparencia(Timestamps, Base):
    __tablename__ = "lancamento_transparencia"
    __table_args__ = (CheckConstraint("valor_centavos >= 0", name="valor_nao_negativo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mes: Mapped[date] = mapped_column(ForeignKey("mes_transparencia.mes"), index=True)
    tipo: Mapped[TipoLancamento] = mapped_column(_enum(TipoLancamento))
    item: Mapped[str] = mapped_column(String(120))
    # Centavos inteiros: float some e soma errado (0,1 + 0,2), e a página é de conta.
    valor_centavos: Mapped[int] = mapped_column(BigInteger)
    nota: Mapped[str | None] = mapped_column(String(300))

    mes_ref: Mapped[MesTransparencia] = relationship(back_populates="lancamentos")


class Tema(Timestamps, Base):
    """Página de tema do site (#42): texto curto da equipe ligando questões e capítulos.

    "O que o espiritismo diz sobre reencarnação" responde a uma busca real; o texto de
    Kardec está em centenas de sites, a curadoria que liga os trechos não.
    """

    __tablename__ = "tema"

    id: Mapped[int] = mapped_column(primary_key=True)
    # URL permanente: /temas/<slug>. Não muda depois de publicado.
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    titulo: Mapped[str] = mapped_column(String(200))
    resumo: Mapped[str] = mapped_column(Text)
    idioma: Mapped[str] = mapped_column(String(35), default="pt-BR")
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    referencias: Mapped[list["TemaReferencia"]] = relationship(
        back_populates="tema", order_by="TemaReferencia.ordem", cascade="all, delete-orphan"
    )


class TemaReferencia(Base):
    __tablename__ = "tema_referencia"
    __table_args__ = (UniqueConstraint("tema_id", "referencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tema_id: Mapped[int] = mapped_column(ForeignKey("tema.id", ondelete="CASCADE"), index=True)
    # Referência canônica, não id: "LE-88" (questão) ou "LE-C001" (capítulo). Ids de
    # capítulo mudam quando a edição é reimportada; a referência não.
    referencia: Mapped[str] = mapped_column(String(40), index=True)
    ordem: Mapped[int]

    tema: Mapped[Tema] = relationship(back_populates="referencias")


class LinhaEditorial(enum.StrEnum):
    """Linhas do blog (site-landing-page.md, "Linhas editoriais")."""

    KARDEC_RESPONDE = "kardec_responde"
    ESTUDO_GUIADO = "estudo_guiado"
    VIDA_PRATICA = "vida_pratica"
    PAIS_E_EVANGELIZADORES = "pais_e_evangelizadores"
    BASTIDORES = "bastidores"
    CAMPANHAS = "campanhas"
    NOVIDADES = "novidades"


class EstadoPost(enum.StrEnum):
    RASCUNHO = "rascunho"
    # Revisão doutrinária humana feita por outra pessoa; só daqui se publica.
    REVISADO = "revisado"
    PUBLICADO = "publicado"


class Post(Timestamps, Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(primary_key=True)
    # URL permanente: /blog/<slug>. Não muda depois de publicado.
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    titulo: Mapped[str] = mapped_column(String(200))
    # Uma ou duas frases: lista do blog e <meta description>.
    resumo: Mapped[str] = mapped_column(String(300))
    # SEO opcional (#42): vazio, o site usa o modelo da página. Título curto porque o
    # site acrescenta " | Centelhar"; descrição no tamanho que a busca mostra.
    seo_titulo: Mapped[str | None] = mapped_column(String(60))
    seo_descricao: Mapped[str | None] = mapped_column(String(160))
    # Markdown restrito (parágrafos, subtítulos, listas, ênfase e links); o site
    # escapa o HTML antes de interpretar.
    texto: Mapped[str] = mapped_column(Text)
    linha: Mapped[LinhaEditorial] = mapped_column(_enum(LinhaEditorial))
    capa_url: Mapped[str | None] = mapped_column(Text)
    idioma: Mapped[str] = mapped_column(String(35), default="pt-BR")
    estado: Mapped[EstadoPost] = mapped_column(_enum(EstadoPost), default=EstadoPost.RASCUNHO)
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    revisado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    revisado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    referencias: Mapped[list["PostReferencia"]] = relationship(
        back_populates="post", order_by="PostReferencia.ordem", cascade="all, delete-orphan"
    )


class PostReferencia(Base):
    """Fonte citada pelo post, como nos temas: referência canônica ("LE-88")."""

    __tablename__ = "post_referencia"
    __table_args__ = (UniqueConstraint("post_id", "referencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id", ondelete="CASCADE"), index=True)
    referencia: Mapped[str] = mapped_column(String(40))
    ordem: Mapped[int]

    post: Mapped[Post] = relationship(back_populates="referencias")


class ConfigApoio(Timestamps, Base):
    """Apoio ao projeto (#40): uma linha só, editada pelo administrador.

    Nasce desligado. Ligar depende de quem recebe o dinheiro estar resolvido (#4),
    e a página pública diz o nome de quem recebe: dinheiro que fica com o projeto
    não pode parecer caridade (especificação, Monetização).
    """

    __tablename__ = "config_apoio"
    # Uma linha: duas configurações "ativas" seriam duas verdades sobre o mesmo botão.
    __table_args__ = (CheckConstraint("id = 1", name="linha_unica"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    ligado: Mapped[bool] = mapped_column(default=False)
    recebedor: Mapped[str | None] = mapped_column(String(200))
    mensagem: Mapped[str | None] = mapped_column(String(500))
    valores_centavos: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    # Meios. Compra no app é o padrão nas lojas; Pix e link externo valem no site e,
    # onde a loja permitir, no app (decisão C em #40).
    compra_no_app: Mapped[bool] = mapped_column(default=False)
    chave_pix: Mapped[str | None] = mapped_column(String(77))
    link_externo: Mapped[str | None] = mapped_column(Text)
    atualizado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))


class Termo(Timestamps, Base):
    """Verbete do glossário do site (#42): "o que é perispírito".

    Definição curta da equipe, sempre fundamentada em trechos publicados de Kardec:
    o glossário não ensina doutrina por conta própria, aponta onde Kardec ensina.
    """

    __tablename__ = "termo"
    __table_args__ = (UniqueConstraint("idioma", "termo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # URL permanente: /glossario/<slug>. Não muda depois de publicado.
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    termo: Mapped[str] = mapped_column(String(80))
    definicao: Mapped[str] = mapped_column(Text)
    idioma: Mapped[str] = mapped_column(String(35), default="pt-BR")
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    referencias: Mapped[list["TermoReferencia"]] = relationship(
        back_populates="termo", order_by="TermoReferencia.ordem", cascade="all, delete-orphan"
    )


class TermoReferencia(Base):
    """Trecho que fundamenta a definição, como nos temas: referência canônica ("LE-88")."""

    __tablename__ = "termo_referencia"
    __table_args__ = (UniqueConstraint("termo_id", "referencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    termo_id: Mapped[int] = mapped_column(ForeignKey("termo.id", ondelete="CASCADE"), index=True)
    referencia: Mapped[str] = mapped_column(String(40), index=True)
    ordem: Mapped[int]

    termo: Mapped[Termo] = relationship(back_populates="referencias")


class Instituicao(Timestamps, Base):
    """Instituição parceira das campanhas de caridade (#41).

    O Pix é dela: o dinheiro cai na conta da instituição e o projeto não toca nele.
    Por isso a página mostra nome e CNPJ, para quem doa conferir a quem está doando.
    """

    __tablename__ = "instituicao"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    # Só dígitos, com dígito verificador conferido na entrada.
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)
    descricao: Mapped[str] = mapped_column(Text)
    chave_pix: Mapped[str | None] = mapped_column(String(77))
    # Página de doação da própria instituição: no iOS o app abre esta página em vez de
    # mostrar o Pix (regra da Apple para quem não é entidade aprovada por ela).
    pagina_doacao: Mapped[str | None] = mapped_column(Text)
    site: Mapped[str | None] = mapped_column(Text)


class Campanha(Timestamps, Base):
    """Campanha com início e fim, ligada a uma instituição (#41).

    Uma ativa por vez: duas campanhas ao mesmo tempo dividem a atenção e viram pedido
    permanente, que é o que o calendário existe para evitar.
    """

    __tablename__ = "campanha"
    __table_args__ = (CheckConstraint("fim >= inicio", name="fim_depois_do_inicio"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # URL permanente: /campanhas/<slug>. Não muda depois de publicada.
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    titulo: Mapped[str] = mapped_column(String(200))
    texto: Mapped[str] = mapped_column(Text)
    instituicao_id: Mapped[int] = mapped_column(ForeignKey("instituicao.id"))
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date] = mapped_column(Date)
    meta_centavos: Mapped[int | None] = mapped_column(BigInteger)
    imagem_url: Mapped[str | None] = mapped_column(Text)
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Resultado informado pela instituição depois do fim. O projeto não vê o Pix, então
    # não há "progresso ao vivo": só o número que a instituição prestou contas.
    arrecadado_centavos: Mapped[int | None] = mapped_column(BigInteger)
    resultado: Mapped[str | None] = mapped_column(Text)

    instituicao: Mapped[Instituicao] = relationship()


class DesafioAtestacao(Base):
    """Valor de uso único que o app inclui no atestado (ADR 0004). Impede reaproveitar
    um atestado capturado: cada registro de aparelho consome um desafio novo."""

    __tablename__ = "desafio_atestacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    valor: Mapped[str] = mapped_column(String(64), unique=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Dispositivo(Base):
    """Instalação do app que provou ser legítima. Não identifica a pessoa: guarda só a
    plataforma e o identificador do atestado, e o token fica como hash."""

    __tablename__ = "dispositivo"

    id: Mapped[int] = mapped_column(primary_key=True)
    plataforma: Mapped[str] = mapped_column(String(10))
    # SHA-256 do token entregue ao app; o token em si não é guardado.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # keyId do App Attest ou equivalente; serve para revogar e investigar abuso.
    identificador: Mapped[str | None] = mapped_column(String(200))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultimo_uso_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EntregaChave(Base):
    """Cada chave de faixa entregue a um aparelho: base do limite diário contra raspagem."""

    __tablename__ = "entrega_chave"
    __table_args__ = (Index("ix_entrega_chave_dispositivo_criado", "dispositivo_id", "criado_em"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dispositivo_id: Mapped[int] = mapped_column(ForeignKey("dispositivo.id"))
    faixa_id: Mapped[int] = mapped_column(ForeignKey("faixa_audio.id"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
