"""Cria administrador pela linha de comando.

É o único caminho para a primeira conta: a API não tem cadastro aberto, e um
endpoint de "primeiro acesso" ficaria exposto até alguém lembrar de usá-lo.

    centelha-admin criar --email ana@exemplo.org --nome "Ana"

A senha vem de CENTELHA_ADMIN_SENHA ou é pedida no terminal; nunca por argumento,
que fica no histórico do shell e na lista de processos.
"""

import argparse
import getpass
import os
import sys

from sqlalchemy import select

from .db import SessionLocal
from .dominio import contas
from .models import PapelUsuario, Usuario


def _ler_senha() -> str:
    senha = os.environ.get("CENTELHA_ADMIN_SENHA")
    if senha:
        return senha
    senha = getpass.getpass("Senha: ")
    if senha != getpass.getpass("Repita: "):
        raise SystemExit("as senhas não conferem")
    return senha


def criar(email: str, nome: str, papel: PapelUsuario, senha: str) -> Usuario:
    email = email.strip().lower()
    with SessionLocal() as session:
        if session.scalar(select(Usuario.id).where(Usuario.email == email)):
            raise SystemExit(f"já existe usuário com o e-mail {email}")
        usuario = Usuario(email=email, nome=nome, papel=papel, senha_hash=contas.gerar_hash(senha))
        session.add(usuario)
        session.flush()
        contas.registrar(
            session,
            "usuario_criado",
            None,
            "usuario",
            usuario.id,
            origem="cli",
            papel=papel.value,
        )
        session.commit()
        return usuario


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="centelha-admin")
    sub = parser.add_subparsers(dest="comando", required=True)
    c = sub.add_parser("criar", help="cria usuário do admin")
    c.add_argument("--email", required=True)
    c.add_argument("--nome", required=True)
    c.add_argument(
        "--papel",
        choices=[p.value for p in PapelUsuario],
        default=PapelUsuario.ADMINISTRADOR.value,
    )
    args = parser.parse_args(argv)
    try:
        usuario = criar(args.email, args.nome, PapelUsuario(args.papel), _ler_senha())
    except contas.SenhaInvalida as e:
        raise SystemExit(str(e)) from e
    print(f"criado: {usuario.email} ({usuario.papel.value}), id {usuario.id}", file=sys.stderr)


if __name__ == "__main__":
    main()
