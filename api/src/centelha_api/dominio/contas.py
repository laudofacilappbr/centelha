"""Senhas, sessões e auditoria do admin."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import RegistroAuditoria, SessaoAdmin, Usuario

# Argon2id com os parâmetros padrão da biblioteca (RFC 9106, perfil de baixa memória).
# Sem alternativa de fallback: se argon2-cffi faltar, o import falha e a API não sobe.
_hasher = PasswordHasher()

SENHA_MIN = 12
# Teto contra requisição com senha de megabytes forçando hash caro.
SENHA_MAX = 128

# Hash de uma senha qualquer, calculado uma vez. O login com e-mail desconhecido
# verifica contra ele para gastar o mesmo tempo do e-mail conhecido; sem isso a
# latência revela quem tem conta.
_HASH_FICTICIO = _hasher.hash(secrets.token_urlsafe(16))


class SenhaInvalida(ValueError):
    pass


def validar_senha(senha: str) -> None:
    # Só comprimento (NIST SP 800-63B): regras de composição levam a "Senha@2026".
    if len(senha) < SENHA_MIN:
        raise SenhaInvalida(f"a senha precisa de pelo menos {SENHA_MIN} caracteres")
    if len(senha) > SENHA_MAX:
        raise SenhaInvalida(f"a senha pode ter no máximo {SENHA_MAX} caracteres")


def gerar_hash(senha: str) -> str:
    validar_senha(senha)
    return _hasher.hash(senha)


def autenticar(session: Session, email: str, senha: str) -> Usuario | None:
    """Usuário ativo com essa senha, ou None. Não distingue o motivo da recusa."""
    usuario = session.scalar(select(Usuario).where(Usuario.email == email.strip().lower()))
    hash_ = usuario.senha_hash if usuario else _HASH_FICTICIO
    try:
        _hasher.verify(hash_, senha)
    except (VerificationError, InvalidHashError):
        return None
    if usuario is None or not usuario.ativo:
        return None
    if _hasher.check_needs_rehash(usuario.senha_hash):
        usuario.senha_hash = _hasher.hash(senha)
    return usuario


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def criar_sessao(
    session: Session, usuario: Usuario, duracao: timedelta, agora: datetime | None = None
) -> tuple[str, SessaoAdmin]:
    agora = agora or datetime.now(UTC)
    # 256 bits aleatórios: SHA-256 sem sal basta, não há o que adivinhar por dicionário.
    token = secrets.token_urlsafe(32)
    sessao = SessaoAdmin(
        usuario=usuario, token_hash=_hash_token(token), criado_em=agora, expira_em=agora + duracao
    )
    session.add(sessao)
    return token, sessao


def resolver_sessao(
    session: Session, token: str, agora: datetime | None = None
) -> SessaoAdmin | None:
    """Sessão válida para o token: não revogada, não expirada, de usuário ativo."""
    agora = agora or datetime.now(UTC)
    sessao = session.scalar(select(SessaoAdmin).where(SessaoAdmin.token_hash == _hash_token(token)))
    if sessao is None or sessao.revogada_em is not None or sessao.expira_em <= agora:
        return None
    # Ativo é conferido a cada requisição: desativar alguém derruba a sessão na hora,
    # mesmo que a revogação em lote ainda não tenha rodado.
    if not sessao.usuario.ativo:
        return None
    return sessao


def revogar_sessoes(
    session: Session, usuario_id: int, exceto_id: int | None = None, agora: datetime | None = None
) -> None:
    cond = [SessaoAdmin.usuario_id == usuario_id, SessaoAdmin.revogada_em.is_(None)]
    if exceto_id is not None:
        cond.append(SessaoAdmin.id != exceto_id)
    session.execute(update(SessaoAdmin).where(*cond).values(revogada_em=agora or datetime.now(UTC)))


def registrar(
    session: Session,
    acao: str,
    usuario: Usuario | None,
    alvo_tipo: str | None = None,
    alvo_id: int | None = None,
    ip: str | None = None,
    **detalhes: object,
) -> RegistroAuditoria:
    """Acrescenta ao log. Não faz commit: o registro entra na mesma transação da ação,
    para não existir ação sem registro nem registro de ação desfeita."""
    registro = RegistroAuditoria(
        usuario_id=usuario.id if usuario else None,
        acao=acao,
        alvo_tipo=alvo_tipo,
        alvo_id=alvo_id,
        ip=ip,
        detalhes=dict(detalhes),
    )
    session.add(registro)
    return registro
