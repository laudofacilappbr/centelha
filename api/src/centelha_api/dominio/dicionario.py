"""Dicionário de pronúncia no admin: quais capítulos uma entrada afeta e regenerá-los.

Fluxo da especificação: erro de pronúncia apontado na escuta vira entrada no
dicionário, e o trecho é regenerado. A regeneração é por capítulo: a pipeline
sintetiza o capítulo inteiro (não guarda áudio por segmento).
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Capitulo, Edicao, EstadoCapitulo, EstadoJob, JobAudio, Pronuncia, Segmento, Voz
from ..pipeline import jobs
from ..pipeline.pronuncia import EntradaPronuncia, termos_usados

E = EstadoCapitulo
# Estados em que já existe áudio feito com o dicionário antigo.
COM_AUDIO = (E.AUDIO_GERADO, E.AUDIO_REVISADO, E.PUBLICADO)


@dataclass
class Afetado:
    capitulo_id: int
    edicao_id: int
    titulo: str
    estado: EstadoCapitulo
    # Segmentos em que a síntese usaria a entrada.
    ocorrencias: int


def _entradas(session: Session, idioma: str) -> list[EntradaPronuncia]:
    return [
        EntradaPronuncia(p.termo, p.substituicao, p.ipa)
        for p in session.scalars(select(Pronuncia).where(Pronuncia.idioma == idioma))
    ]


def capitulos_afetados(
    session: Session, idioma: str, termo: str, entradas: list[EntradaPronuncia] | None = None
) -> list[Afetado]:
    """Capítulos com áudio cujo texto a síntese leria com esta entrada.

    `entradas` é o dicionário a considerar; por padrão, o do banco. Ao apagar uma
    entrada, passe o dicionário de antes, com ela, para achar quem a usava."""
    entradas = _entradas(session, idioma) if entradas is None else entradas
    if not any(e.termo == termo for e in entradas):
        entradas = [*entradas, EntradaPronuncia(termo)]
    # LIKE só pré-filtra (rápido, com falso positivo: "Kardec" dentro de "Allan
    # Kardec"); quem decide é termos_usados, a mesma regra da síntese.
    linhas = session.execute(
        select(Capitulo, Segmento.texto)
        .join(Segmento, Segmento.capitulo_id == Capitulo.id)
        .join(Edicao, Edicao.id == Capitulo.edicao_id)
        .where(
            Edicao.idioma == idioma,
            Capitulo.estado.in_(COM_AUDIO),
            Segmento.texto.contains(termo, autoescape=True),
        )
        .order_by(Capitulo.edicao_id, Capitulo.ordem)
    ).all()
    por_capitulo: dict[int, Afetado] = {}
    for capitulo, texto in linhas:
        if termo not in termos_usados(texto, entradas):
            continue
        a = por_capitulo.setdefault(
            capitulo.id,
            Afetado(capitulo.id, capitulo.edicao_id, capitulo.titulo, capitulo.estado, 0),
        )
        a.ocorrencias += 1
    return list(por_capitulo.values())


@dataclass
class ResultadoRegeneracao:
    enfileirados: list[int]
    # capitulo_id → motivo
    pulados: dict[int, str]


def regenerar(session: Session, afetados: list[Afetado], usuario) -> ResultadoRegeneracao:
    """Enfileira de novo cada capítulo afetado, com as vozes da última geração.

    Faz commit por capítulo: enfileirar() desfaz a transação inteira quando acha job
    duplicado, e um capítulo recusado não pode desfazer os já enfileirados."""
    res = ResultadoRegeneracao([], {})
    for a in afetados:
        capitulo = session.get(Capitulo, a.capitulo_id)
        if capitulo.estado == E.PUBLICADO:
            # Não despublica sozinho: tirar do ar é decisão de quem publica.
            res.pulados[a.capitulo_id] = "publicado: despublique antes de regenerar"
            continue
        ativo = session.scalar(
            select(JobAudio.id).where(
                JobAudio.capitulo_id == capitulo.id,
                JobAudio.estado.in_([EstadoJob.PENDENTE, EstadoJob.EXECUTANDO]),
            )
        )
        if ativo:
            res.pulados[a.capitulo_id] = "já tem geração na fila"
            continue
        ultimo = session.scalar(
            select(JobAudio)
            .where(JobAudio.capitulo_id == capitulo.id, JobAudio.estado == EstadoJob.CONCLUIDO)
            .order_by(JobAudio.id.desc())
            .limit(1)
        )
        if ultimo is None:
            res.pulados[a.capitulo_id] = "sem geração anterior para repetir as vozes"
            continue

        def voz(i: int | None) -> Voz | None:
            return session.get(Voz, i) if i else None

        try:
            jobs.enfileirar(
                session,
                capitulo,
                ultimo.motor,
                voz(ultimo.voz_narrador_id),
                voz(ultimo.voz_pergunta_id),
                voz(ultimo.voz_resposta_id),
                usuario,
            )
        except jobs.JobRecusado as e:
            res.pulados[a.capitulo_id] = str(e)
            continue
        session.commit()
        res.enfileirados.append(a.capitulo_id)
    return res
