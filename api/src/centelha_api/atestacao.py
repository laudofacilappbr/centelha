"""Verificação do atestado que prova que o pedido vem do app legítimo (ADR 0004, #73).

O app pede um desafio de uso único, gera o atestado na plataforma com esse desafio
dentro e o envia junto. Cada plataforma tem o seu verificador:

- ios: App Attest. Falta configurar (Team ID e bundle id do app).
- android: Play Integrity. Falta configurar (projeto e conta de serviço no Google Cloud).
- falso: só desenvolvimento e testes, com CENTELHA_ATESTACAO_FALSA; nunca em produção.

Plataforma sem verificador configurado responde "indisponível" em vez de aceitar: sem
verificação, a chave não sai.
"""

from dataclasses import dataclass
from typing import Protocol

from .config import Settings


class AtestacaoRecusada(Exception):
    """Atestado inválido: o pedido não prova que vem do app legítimo."""


class AtestacaoIndisponivel(Exception):
    """A plataforma ainda não tem verificador configurado neste servidor."""


@dataclass(frozen=True)
class ResultadoAtestacao:
    # Identificador estável do atestado (keyId no App Attest), para revogar.
    identificador: str


class Verificador(Protocol):
    def verificar(self, atestado: str, desafio: str) -> ResultadoAtestacao: ...


class VerificadorFalso:
    """Aceita só "falso:<desafio>": exercita o fluxo inteiro sem aparelho real."""

    def verificar(self, atestado: str, desafio: str) -> ResultadoAtestacao:
        if atestado != f"falso:{desafio}":
            raise AtestacaoRecusada("atestado falso não confere com o desafio")
        return ResultadoAtestacao(identificador="falso")


PLATAFORMAS = ("ios", "android", "falso")


def verificador(plataforma: str, settings: Settings) -> Verificador:
    if plataforma == "falso":
        if settings.atestacao_falsa and settings.ambiente != "producao":
            return VerificadorFalso()
        raise AtestacaoRecusada("plataforma desconhecida")
    if plataforma in ("ios", "android"):
        raise AtestacaoIndisponivel(f"verificação de {plataforma} ainda não configurada")
    raise AtestacaoRecusada("plataforma desconhecida")
