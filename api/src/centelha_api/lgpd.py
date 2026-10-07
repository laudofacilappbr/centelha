"""Atendimento a pedidos do titular (LGPD art. 18) sobre os dados que o Centelha coleta.

Dados pessoais: o e-mail da lista de espera e a conta opcional de quem lê (#43). A conta
também se exporta e se exclui pelo próprio app. Ferramenta de administrador,
não endpoint público: pedido chega por privacidade@ e a identidade é confirmada por
resposta ao próprio e-mail antes de rodar o comando.

    centelha-lgpd exportar pessoa@exemplo.com   # acesso e portabilidade (JSON)
    centelha-lgpd excluir pessoa@exemplo.com    # eliminação / revogação do consentimento
"""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .dominio import conta_leitor
from .models import InscricaoListaEspera


def exportar(session: Session, email: str) -> dict:
    email = email.strip().lower()
    inscricoes = session.scalars(
        select(InscricaoListaEspera).where(InscricaoListaEspera.email == email)
    ).all()
    return {
        "titular": email,
        "gerado_em": datetime.now(UTC).isoformat(),
        "lista_de_espera": [
            {
                "email": i.email,
                "origem": i.origem,
                "inscrito_em": i.criado_em.isoformat(),
                "finalidade": "avisar sobre o lançamento do app Centelha",
                "base_legal": "consentimento (LGPD art. 7º, I)",
            }
            for i in inscricoes
        ],
        "conta": conta_leitor.exportar(session, email),
    }


def excluir(session: Session, email: str) -> int:
    email = email.strip().lower()
    resultado = session.execute(
        delete(InscricaoListaEspera).where(InscricaoListaEspera.email == email)
    )
    contas = conta_leitor.excluir(session, email)
    session.commit()
    return resultado.rowcount + contas


def _registro(email: str) -> str:
    # Prova de atendimento sem guardar o dado eliminado: só o hash.
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="centelha-lgpd", description=__doc__)
    parser.add_argument("acao", choices=["exportar", "excluir"])
    parser.add_argument("email")
    args = parser.parse_args(argv)

    from .db import SessionLocal

    with SessionLocal() as session:
        if args.acao == "exportar":
            print(json.dumps(exportar(session, args.email), ensure_ascii=False, indent=2))
        else:
            n = excluir(session, args.email)
            print(
                f"{datetime.now(UTC).isoformat()} excluir titular={_registro(args.email)} "
                f"registros={n}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
