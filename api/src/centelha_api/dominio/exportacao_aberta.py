"""Download em formato aberto pela conta do app, por acessibilidade (#134, 1A e 2D).

A pessoa entra no app com a conta opcional e pede pelo suporte, autodeclarando a
necessidade (sem comprovante: seria dado de saúde, sensível na LGPD). O suporte libera
para aquela conta; só nela o app mostra "Baixar em formato aberto". Cada capítulo baixado
fica registrado, com limite diário, e a liberação pode ser revogada.
"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ContaLeitor, DownloadAberto, ExportacaoLiberada, FaixaAudio, Usuario


class LiberacaoRecusada(Exception):
    pass


def vigente(session: Session, conta_id: int) -> ExportacaoLiberada | None:
    return session.scalar(
        select(ExportacaoLiberada).where(
            ExportacaoLiberada.conta_id == conta_id, ExportacaoLiberada.revogada_em.is_(None)
        )
    )


def liberar(
    session: Session, conta: ContaLeitor, pedido: str, usuario: Usuario
) -> ExportacaoLiberada:
    # Trava a conta: dois cliques em "liberar" esperam um pelo outro em vez de esbarrar
    # no índice único.
    session.scalar(select(ContaLeitor.id).where(ContaLeitor.id == conta.id).with_for_update())
    if vigente(session, conta.id) is not None:
        raise LiberacaoRecusada("a conta já tem liberação vigente")
    liberacao = ExportacaoLiberada(conta=conta, pedido=pedido.strip(), liberada_por=usuario)
    session.add(liberacao)
    session.flush()
    return liberacao


def revogar(session: Session, liberacao: ExportacaoLiberada, usuario: Usuario) -> None:
    if liberacao.revogada_em is not None:
        raise LiberacaoRecusada("liberação já revogada")
    liberacao.revogada_em = func.now()
    liberacao.revogada_por_id = usuario.id


def baixados_em_24h(session: Session, liberacao: ExportacaoLiberada) -> int:
    return session.scalar(
        select(func.count(DownloadAberto.id)).where(
            DownloadAberto.liberacao_id == liberacao.id,
            DownloadAberto.criado_em > func.now() - timedelta(days=1),
        )
    )


def registrar_download(session: Session, liberacao: ExportacaoLiberada, faixa: FaixaAudio) -> bool:
    """Registra o download; False se o limite de 24 h já foi atingido."""
    # Trava a liberação: pedidos simultâneos contam um depois do outro.
    session.scalar(
        select(ExportacaoLiberada.id).where(ExportacaoLiberada.id == liberacao.id).with_for_update()
    )
    if baixados_em_24h(session, liberacao) >= get_settings().exportacao_downloads_por_dia:
        return False
    session.add(DownloadAberto(liberacao_id=liberacao.id, faixa_id=faixa.id))
    return True


def total_baixado(session: Session, liberacao_id: int) -> int:
    return session.scalar(
        select(func.count(DownloadAberto.id)).where(DownloadAberto.liberacao_id == liberacao_id)
    )
