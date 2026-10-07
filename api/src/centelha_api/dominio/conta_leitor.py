"""Conta opcional de quem lê (#43, decisão 1A): entrar sem senha, por código no e-mail.

Só o app principal tem conta. O perfil infantil é um app separado (#50, opção A) e não
tem conta, analítica nem link externo (CLAUDE.md).
"""

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import CodigoAcesso, ContaLeitor, DownloadAberto, ExportacaoLiberada, SessaoConta


def _hash(*partes: str) -> str:
    return hashlib.sha256("".join(partes).encode()).hexdigest()


def normalizar(email: str) -> str:
    return email.strip().lower()


def novo_codigo(session: Session, email: str) -> str:
    """Gera o código e invalida os anteriores do mesmo e-mail: só o último vale.

    O relógio é o do banco (func.now()), não o do processo, como no resto da fila."""
    cfg = get_settings()
    email = normalizar(email)
    # Código vencido não serve para nada e guarda um e-mail: sai em um dia (LGPD,
    # necessidade). Aproveita cada pedido, sem tarefa agendada.
    session.execute(
        delete(CodigoAcesso).where(CodigoAcesso.criado_em < func.now() - timedelta(days=1))
    )
    session.execute(
        update(CodigoAcesso)
        .where(CodigoAcesso.email == email, CodigoAcesso.usado_em.is_(None))
        .values(usado_em=func.now())
    )
    codigo = f"{secrets.randbelow(10**6):06d}"
    sal = secrets.token_hex(16)
    session.add(
        CodigoAcesso(
            email=email,
            codigo_hash=_hash(sal, codigo),
            sal=sal,
            expira_em=func.now() + timedelta(minutes=cfg.conta_codigo_minutos),
        )
    )
    return codigo


def confirmar_codigo(session: Session, email: str, codigo: str) -> ContaLeitor | None:
    """Conta do e-mail se o código confere; cria a conta na primeira vez.

    Erro conta tentativa; na quinta, o código morre. A comparação é em tempo constante."""
    cfg = get_settings()
    email = normalizar(email)
    agora = session.scalar(select(func.now()))
    vigente = session.scalar(
        select(CodigoAcesso)
        .where(
            CodigoAcesso.email == email,
            CodigoAcesso.usado_em.is_(None),
            CodigoAcesso.expira_em > agora,
        )
        .order_by(CodigoAcesso.id.desc())
        .with_for_update()
    )
    if vigente is None:
        return None
    if not secrets.compare_digest(vigente.codigo_hash, _hash(vigente.sal, codigo.strip())):
        vigente.tentativas += 1
        if vigente.tentativas >= cfg.conta_codigo_tentativas:
            vigente.usado_em = agora
        session.commit()
        return None
    vigente.usado_em = agora
    conta = session.scalar(select(ContaLeitor).where(ContaLeitor.email == email))
    if conta is None:
        conta = ContaLeitor(email=email)
        session.add(conta)
    conta.ultimo_acesso_em = agora
    session.flush()
    return conta


def criar_sessao(session: Session, conta: ContaLeitor) -> tuple[str, SessaoConta]:
    token = secrets.token_urlsafe(32)
    sessao = SessaoConta(
        conta=conta,
        token_hash=_hash(token),
        expira_em=func.now() + timedelta(days=get_settings().conta_sessao_dias),
    )
    session.add(sessao)
    session.flush()
    return token, sessao


def resolver_sessao(session: Session, token: str) -> SessaoConta | None:
    return session.scalar(
        select(SessaoConta).where(
            SessaoConta.token_hash == _hash(token),
            SessaoConta.revogada_em.is_(None),
            SessaoConta.expira_em > func.now(),
        )
    )


def exportar(session: Session, email: str) -> dict | None:
    conta = session.scalar(select(ContaLeitor).where(ContaLeitor.email == normalizar(email)))
    if conta is None:
        return None
    return {
        "email": conta.email,
        "criada_em": conta.criada_em.isoformat(),
        "ultimo_acesso_em": conta.ultimo_acesso_em.isoformat() if conta.ultimo_acesso_em else None,
        "finalidade": "sincronizar progresso, marcadores e planos de estudo entre aparelhos",
        "base_legal": "execução de serviço pedido pelo titular (LGPD art. 7º, V)",
        "exportacao_aberta": [
            {
                "pedido": e.pedido,
                "liberada_em": e.liberada_em.isoformat(),
                "revogada_em": e.revogada_em.isoformat() if e.revogada_em else None,
                "capitulos_baixados": session.scalar(
                    select(func.count(DownloadAberto.id)).where(DownloadAberto.liberacao_id == e.id)
                ),
            }
            for e in session.scalars(
                select(ExportacaoLiberada)
                .where(ExportacaoLiberada.conta_id == conta.id)
                .order_by(ExportacaoLiberada.id)
            )
        ],
    }


def excluir(session: Session, email: str) -> int:
    """Apaga a conta, as sessões e as liberações de exportação (em cascata) e os códigos
    do e-mail. Devolve quantas
    contas saíram (0 ou 1)."""
    email = normalizar(email)
    session.execute(delete(CodigoAcesso).where(CodigoAcesso.email == email))
    resultado = session.execute(delete(ContaLeitor).where(ContaLeitor.email == email))
    return resultado.rowcount
