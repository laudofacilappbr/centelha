"""Cadastro e aprovação de direitos de uma edição.

O sistema não decide se uma obra está em domínio público: isso é parecer jurídico
(#3). Ele só exige que a aprovação venha com a prova registrada e que qualquer
mudança na prova invalide a aprovação anterior.
"""

from datetime import UTC, date, datetime

from ..models import Direitos, Edicao, StatusDireitos, Usuario

CAMPOS_EDITAVEIS = ("falecimento_tradutor", "base_legal", "documento_url")


class DireitosIncompletos(ValueError):
    def __init__(self, pendencias: list[str]) -> None:
        super().__init__("faltam: " + ", ".join(pendencias))
        self.pendencias = pendencias


def pendencias(edicao: Edicao) -> list[str]:
    """O que falta registrar antes de aprovar. Lista vazia = pode aprovar."""
    d = edicao.direitos
    faltam = []
    if d is None or not (d.base_legal or "").strip():
        faltam.append("base_legal")
    if d is None or not (d.documento_url or "").strip():
        faltam.append("documento_url")
    # Tradução tem direito próprio do tradutor (Lei 9.610, art. 7º, XI): sem a data de
    # falecimento não há como conferir o prazo de domínio público (art. 41).
    if edicao.tradutor and (d is None or d.falecimento_tradutor is None):
        faltam.append("falecimento_tradutor")
    return faltam


def obter_ou_criar(edicao: Edicao) -> Direitos:
    if edicao.direitos is None:
        edicao.direitos = Direitos(status=StatusDireitos.PENDENTE)
    return edicao.direitos


def atualizar(
    edicao: Edicao,
    falecimento_tradutor: date | None,
    base_legal: str | None,
    documento_url: str | None,
) -> dict[str, list[object]]:
    """Grava os campos e devolve o que mudou ({campo: [antes, depois]}).

    Mudou qualquer campo de um registro já aprovado ou recusado → volta a pendente.
    A aprovação vale para a prova que o aprovador viu; trocar o documento depois e
    manter "aprovado" seria aprovar algo que ninguém conferiu."""
    d = obter_ou_criar(edicao)
    novos = {
        "falecimento_tradutor": falecimento_tradutor,
        "base_legal": (base_legal or "").strip() or None,
        "documento_url": (documento_url or "").strip() or None,
    }
    mudancas: dict[str, list[object]] = {}
    for campo in CAMPOS_EDITAVEIS:
        antes = getattr(d, campo)
        if antes != novos[campo]:
            mudancas[campo] = [_json(antes), _json(novos[campo])]
            setattr(d, campo, novos[campo])
    if mudancas and d.status != StatusDireitos.PENDENTE:
        mudancas["status"] = [d.status.value, StatusDireitos.PENDENTE.value]
        _voltar_a_pendente(d)
    return mudancas


def aprovar(edicao: Edicao, aprovador: Usuario, agora: datetime | None = None) -> Direitos:
    faltam = pendencias(edicao)
    if faltam:
        raise DireitosIncompletos(faltam)
    d = edicao.direitos
    assert d is not None  # pendencias() já garantiu
    d.status = StatusDireitos.APROVADO
    # E-mail, não nome: é único e não muda quando a pessoa corrige o nome no cadastro.
    # O id do usuário fica no registro de auditoria.
    d.aprovado_por = aprovador.email
    d.aprovado_em = agora or datetime.now(UTC)
    return d


def recusar(edicao: Edicao) -> Direitos:
    d = obter_ou_criar(edicao)
    d.status = StatusDireitos.RECUSADO
    d.aprovado_por = None
    d.aprovado_em = None
    return d


def _voltar_a_pendente(d: Direitos) -> None:
    d.status = StatusDireitos.PENDENTE
    d.aprovado_por = None
    d.aprovado_em = None


def _json(v: object) -> object:
    return v.isoformat() if isinstance(v, date) else v
