"""Endpoints do admin: sessão, usuários, auditoria e publicação.

Separados dos endpoints públicos (site-landing-page.md: "endpoints públicos de leitura
sem autenticação, separados dos endpoints do admin"). Tudo aqui exige sessão, exceto
o próprio login.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_session
from ..dominio import contas
from ..dominio.permissoes import PERMISSOES_POR_PAPEL, Permissao, pode
from ..dominio.publicacao import PublicacaoBloqueada, publicar_edicao
from ..models import Edicao, PapelUsuario, RegistroAuditoria, SessaoAdmin, Usuario
from ..ratelimit import JanelaDeslizante, ip_do_cliente

router = APIRouter(prefix="/v1/admin", tags=["admin"])
limitador_login = JanelaDeslizante()
_bearer = HTTPBearer(auto_error=False)

# Token em cabeçalho Authorization, não em cookie: sem cookie não há CSRF a tratar,
# e a stack da interface do admin ainda não foi escolhida.
_NAO_AUTENTICADO = HTTPException(
    status.HTTP_401_UNAUTHORIZED, "não autenticado", headers={"WWW-Authenticate": "Bearer"}
)


def sessao_atual(
    credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> SessaoAdmin:
    if credenciais is None:
        raise _NAO_AUTENTICADO
    sessao = contas.resolver_sessao(session, credenciais.credentials)
    if sessao is None:
        raise _NAO_AUTENTICADO
    return sessao


def exigir(permissao: Permissao) -> Callable[..., Usuario]:
    def dependencia(sessao: SessaoAdmin = Depends(sessao_atual)) -> Usuario:
        if not pode(sessao.usuario.papel, permissao):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "sem permissão")
        return sessao.usuario

    return dependencia


pode_ver_admin = exigir(Permissao.VER_ADMIN)
pode_gerir_usuarios = exigir(Permissao.GERIR_USUARIOS)
pode_ver_auditoria = exigir(Permissao.VER_AUDITORIA)
pode_publicar = exigir(Permissao.PUBLICAR)


# --- Esquemas ---------------------------------------------------------------


def _senha(**kw):
    return Field(min_length=contas.SENHA_MIN, max_length=contas.SENHA_MAX, **kw)


class Login(BaseModel):
    email: EmailStr = Field(max_length=320)
    # Sem mínimo no login: a regra de tamanho vale para senha nova, não para tentativa.
    senha: str = Field(max_length=contas.SENHA_MAX)


class UsuarioSaida(BaseModel):
    id: int
    email: str
    nome: str
    papel: PapelUsuario
    ativo: bool
    permissoes: list[Permissao]

    @classmethod
    def de(cls, u: Usuario) -> "UsuarioSaida":
        return cls(
            id=u.id,
            email=u.email,
            nome=u.nome,
            papel=u.papel,
            ativo=u.ativo,
            permissoes=sorted(PERMISSOES_POR_PAPEL.get(u.papel, frozenset())),
        )


class SessaoCriada(BaseModel):
    token: str
    expira_em: datetime
    usuario: UsuarioSaida


class TrocaSenha(BaseModel):
    senha_atual: str = Field(max_length=contas.SENHA_MAX)
    senha_nova: str = _senha()


class NovoUsuario(BaseModel):
    email: EmailStr = Field(max_length=320)
    nome: str = Field(min_length=1, max_length=200)
    papel: PapelUsuario
    senha: str = _senha()


class AlteracaoUsuario(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    papel: PapelUsuario | None = None
    ativo: bool | None = None
    senha: str | None = _senha(default=None)


class RegistroSaida(BaseModel):
    id: int
    criado_em: datetime
    usuario_id: int | None
    acao: str
    alvo_tipo: str | None
    alvo_id: int | None
    detalhes: dict
    ip: str | None


# --- Sessão -----------------------------------------------------------------


@router.post("/sessoes", status_code=status.HTTP_201_CREATED)
def entrar(dados: Login, request: Request, session: Session = Depends(get_session)) -> SessaoCriada:
    cfg = get_settings()
    ip = ip_do_cliente(request)
    email = dados.email.lower()
    for chave in (f"ip:{ip}", f"email:{email}"):
        if not limitador_login.permitir(
            chave, cfg.admin_login_limite, cfg.admin_login_janela_segundos
        ):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "muitas tentativas")
    usuario = contas.autenticar(session, email, dados.senha)
    if usuario is None:
        contas.registrar(session, "login_recusado", None, ip=ip, email=email)
        session.commit()
        # Mesma mensagem para e-mail inexistente, senha errada e conta desativada.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "e-mail ou senha incorretos")
    token, sessao = contas.criar_sessao(session, usuario, timedelta(hours=cfg.admin_sessao_horas))
    contas.registrar(session, "login", usuario, ip=ip)
    session.commit()
    return SessaoCriada(token=token, expira_em=sessao.expira_em, usuario=UsuarioSaida.de(usuario))


@router.delete("/sessoes/atual", status_code=status.HTTP_204_NO_CONTENT)
def sair(
    request: Request,
    sessao: SessaoAdmin = Depends(sessao_atual),
    session: Session = Depends(get_session),
) -> None:
    sessao.revogada_em = func.now()
    contas.registrar(session, "logout", sessao.usuario, ip=ip_do_cliente(request))
    session.commit()


@router.get("/eu")
def eu(usuario: Usuario = Depends(pode_ver_admin)) -> UsuarioSaida:
    return UsuarioSaida.de(usuario)


@router.post("/eu/senha", status_code=status.HTTP_204_NO_CONTENT)
def trocar_senha(
    dados: TrocaSenha,
    request: Request,
    sessao: SessaoAdmin = Depends(sessao_atual),
    session: Session = Depends(get_session),
) -> None:
    usuario = sessao.usuario
    cfg = get_settings()
    # Sessão roubada não deve virar oráculo para adivinhar a senha atual.
    if not limitador_login.permitir(
        f"senha:{usuario.id}", cfg.admin_login_limite, cfg.admin_login_janela_segundos
    ):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "muitas tentativas")
    if contas.autenticar(session, usuario.email, dados.senha_atual) is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "senha atual incorreta")
    usuario.senha_hash = contas.gerar_hash(dados.senha_nova)
    # Quem troca a senha porque desconfia de vazamento espera que as outras sessões caiam.
    contas.revogar_sessoes(session, usuario.id, exceto_id=sessao.id)
    contas.registrar(
        session, "senha_trocada", usuario, "usuario", usuario.id, ip_do_cliente(request)
    )
    session.commit()


# --- Usuários ---------------------------------------------------------------


@router.get("/usuarios")
def listar_usuarios(
    _: Usuario = Depends(pode_gerir_usuarios),
    session: Session = Depends(get_session),
) -> list[UsuarioSaida]:
    return [UsuarioSaida.de(u) for u in session.scalars(select(Usuario).order_by(Usuario.id))]


@router.post("/usuarios", status_code=status.HTTP_201_CREATED)
def criar_usuario(
    dados: NovoUsuario,
    request: Request,
    autor: Usuario = Depends(pode_gerir_usuarios),
    session: Session = Depends(get_session),
) -> UsuarioSaida:
    email = dados.email.lower()
    if session.scalar(select(Usuario.id).where(Usuario.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "e-mail já cadastrado")
    novo = Usuario(
        email=email, nome=dados.nome, papel=dados.papel, senha_hash=contas.gerar_hash(dados.senha)
    )
    session.add(novo)
    session.flush()
    contas.registrar(
        session,
        "usuario_criado",
        autor,
        "usuario",
        novo.id,
        ip_do_cliente(request),
        papel=novo.papel.value,
    )
    session.commit()
    return UsuarioSaida.de(novo)


@router.patch("/usuarios/{usuario_id}")
def alterar_usuario(
    usuario_id: int,
    dados: AlteracaoUsuario,
    request: Request,
    autor: Usuario = Depends(pode_gerir_usuarios),
    session: Session = Depends(get_session),
) -> UsuarioSaida:
    alvo = session.get(Usuario, usuario_id)
    if alvo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "usuário não encontrado")
    perde_admin = (
        alvo.papel == PapelUsuario.ADMINISTRADOR
        and alvo.ativo
        and (
            (dados.papel is not None and dados.papel != PapelUsuario.ADMINISTRADOR)
            or dados.ativo is False
        )
    )
    if perde_admin:
        # Trava as linhas dos administradores ativos: dois administradores rebaixando
        # um ao outro ao mesmo tempo deixariam o sistema sem ninguém para gerir contas.
        admins = session.scalars(
            select(Usuario.id)
            .where(Usuario.papel == PapelUsuario.ADMINISTRADOR, Usuario.ativo.is_(True))
            .with_for_update()
        ).all()
        if len(admins) <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "é o último administrador ativo")

    mudancas: dict[str, object] = {}
    if dados.nome is not None and dados.nome != alvo.nome:
        alvo.nome = dados.nome
        mudancas["nome"] = dados.nome
    if dados.papel is not None and dados.papel != alvo.papel:
        mudancas["papel"] = [alvo.papel.value, dados.papel.value]
        alvo.papel = dados.papel
    if dados.ativo is not None and dados.ativo != alvo.ativo:
        alvo.ativo = dados.ativo
        mudancas["ativo"] = dados.ativo
        if not dados.ativo:
            contas.revogar_sessoes(session, alvo.id)
    if dados.senha is not None:
        alvo.senha_hash = contas.gerar_hash(dados.senha)
        contas.revogar_sessoes(session, alvo.id)
        # Registra que a senha mudou, nunca o valor.
        mudancas["senha"] = "redefinida"
    if mudancas:
        contas.registrar(
            session,
            "usuario_alterado",
            autor,
            "usuario",
            alvo.id,
            ip_do_cliente(request),
            **mudancas,
        )
    session.commit()
    return UsuarioSaida.de(alvo)


# --- Auditoria e publicação -------------------------------------------------


@router.get("/auditoria")
def auditoria(
    _: Usuario = Depends(pode_ver_auditoria),
    session: Session = Depends(get_session),
    acao: str | None = None,
    alvo_tipo: str | None = None,
    alvo_id: int | None = None,
    limite: int = 100,
) -> list[RegistroSaida]:
    consulta = select(RegistroAuditoria).order_by(RegistroAuditoria.id.desc())
    if acao:
        consulta = consulta.where(RegistroAuditoria.acao == acao)
    if alvo_tipo:
        consulta = consulta.where(RegistroAuditoria.alvo_tipo == alvo_tipo)
    if alvo_id is not None:
        consulta = consulta.where(RegistroAuditoria.alvo_id == alvo_id)
    consulta = consulta.limit(max(1, min(limite, 500)))
    return [
        RegistroSaida.model_validate(r, from_attributes=True) for r in session.scalars(consulta)
    ]


@router.post("/edicoes/{edicao_id}/publicar")
def publicar(
    edicao_id: int,
    request: Request,
    autor: Usuario = Depends(pode_publicar),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    edicao = session.get(Edicao, edicao_id)
    if edicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "edição não encontrada")
    ip = ip_do_cliente(request)
    try:
        # A regra de direitos continua só em publicar_edicao; aqui só se registra quem pediu.
        publicar_edicao(edicao)
    except PublicacaoBloqueada as e:
        session.rollback()
        contas.registrar(
            session, "publicacao_bloqueada", autor, "edicao", edicao_id, ip, motivo=str(e)
        )
        session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    contas.registrar(session, "edicao_publicada", autor, "edicao", edicao.id, ip)
    session.commit()
    return {"id": edicao.id, "publicada_em": edicao.publicada_em}
