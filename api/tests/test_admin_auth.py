import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from centelha_api import admin_cli
from centelha_api.dominio import contas
from centelha_api.dominio.permissoes import PERMISSOES_POR_PAPEL, Permissao, pode
from centelha_api.models import (
    Capitulo,
    Direitos,
    Edicao,
    EstadoCapitulo,
    Obra,
    PapelUsuario,
    RegistroAuditoria,
    SessaoAdmin,
    StatusDireitos,
    Usuario,
)

SENHA = "cavalo correto bateria grampo"


def _usuario(session, email="ana@exemplo.org", papel=PapelUsuario.ADMINISTRADOR, ativo=True):
    u = Usuario(
        email=email,
        nome=email.split("@")[0],
        papel=papel,
        ativo=ativo,
        senha_hash=contas.gerar_hash(SENHA),
    )
    session.add(u)
    session.commit()
    return u


def _entrar(client, email="ana@exemplo.org", senha=SENHA, ip="198.51.100.1"):
    return client.post(
        "/v1/admin/sessoes",
        json={"email": email, "senha": senha},
        headers={"cf-connecting-ip": ip},
    )


def _auth(client, email="ana@exemplo.org"):
    r = _entrar(client, email)
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _acoes(session):
    session.expire_all()
    return [
        r.acao for r in session.scalars(select(RegistroAuditoria).order_by(RegistroAuditoria.id))
    ]


# --- Senha e token no banco -------------------------------------------------


def test_senha_guardada_como_argon2id(session):
    """Vazamento do banco não pode entregar senhas: só o hash Argon2id é gravado."""
    u = _usuario(session)
    assert u.senha_hash.startswith("$argon2id$")
    assert SENHA not in u.senha_hash


def test_token_nao_fica_no_banco(client, session):
    """Quem lê a tabela de sessões não pode se passar por ninguém: só o SHA-256 do
    token é guardado, e o token não aparece em nenhuma coluna."""
    _usuario(session)
    token = _entrar(client).json()["token"]
    linha = session.execute(text("SELECT * FROM sessao_admin")).mappings().one()
    assert token not in json.dumps({k: str(v) for k, v in linha.items()})
    assert len(linha["token_hash"]) == 64


@pytest.mark.parametrize("curta", ["", "a" * (contas.SENHA_MIN - 1)])
def test_senha_curta_recusada(curta):
    with pytest.raises(contas.SenhaInvalida):
        contas.gerar_hash(curta)


# --- Login ------------------------------------------------------------------


def test_login_devolve_token_e_permissoes(client, session):
    _usuario(session, papel=PapelUsuario.REVISOR_TEXTO)
    r = _entrar(client)
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["usuario"]["papel"] == "revisor_texto"
    assert set(corpo["usuario"]["permissoes"]) == {"ver_admin", "editar_segmento", "aprovar_texto"}
    assert _acoes(session) == ["login"]


@pytest.mark.parametrize("caso", ["senha_errada", "email_desconhecido", "conta_desativada"])
def test_recusas_de_login_sao_indistinguiveis(client, session, caso):
    """Resposta diferente por motivo diria a um atacante quais e-mails têm conta."""
    _usuario(session, ativo=caso != "conta_desativada")
    email = "zeca@exemplo.org" if caso == "email_desconhecido" else "ana@exemplo.org"
    senha = "senha errada qualquer" if caso == "senha_errada" else SENHA
    r = _entrar(client, email, senha)
    assert r.status_code == 401
    assert r.json() == {"detail": "e-mail ou senha incorretos"}
    assert _acoes(session) == ["login_recusado"]


def test_email_desconhecido_tambem_calcula_hash(session, monkeypatch):
    """Sem verificar contra um hash fictício, o e-mail inexistente responde em
    microssegundos e o conhecido em dezenas de milissegundos: enumeração por tempo."""
    chamadas = []
    real = contas._hasher

    class Espiao:
        def verify(self, h, s):
            chamadas.append(h)
            return real.verify(h, s)

    monkeypatch.setattr(contas, "_hasher", Espiao())
    assert contas.autenticar(session, "ninguem@exemplo.org", SENHA) is None
    assert chamadas == [contas._HASH_FICTICIO]


def test_login_aceita_email_com_maiusculas(client, session):
    _usuario(session)
    assert _entrar(client, "Ana@Exemplo.ORG").status_code == 201


def test_forca_bruta_contra_uma_conta_barrada_mesmo_trocando_de_ip(client, session):
    """O limite por e-mail é o que segura ataque distribuído; o por IP não veria nada."""
    _usuario(session)
    for i in range(10):
        assert _entrar(client, senha="errada errada", ip=f"203.0.113.{i}").status_code == 401
    r = _entrar(client, ip="203.0.113.200")
    assert r.status_code == 429


# --- Sessão -----------------------------------------------------------------


def test_sem_token_ou_token_invalido(client, session):
    assert client.get("/v1/admin/eu").status_code == 401
    r = client.get("/v1/admin/eu", headers={"Authorization": "Bearer inventado"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_logout_revoga(client, session):
    _usuario(session)
    h = _auth(client)
    assert client.get("/v1/admin/eu", headers=h).status_code == 200
    assert client.delete("/v1/admin/sessoes/atual", headers=h).status_code == 204
    assert client.get("/v1/admin/eu", headers=h).status_code == 401


def test_sessao_expirada(client, session):
    _usuario(session)
    h = _auth(client)
    session.execute(
        SessaoAdmin.__table__.update().values(expira_em=datetime.now(UTC) - timedelta(seconds=1))
    )
    session.commit()
    assert client.get("/v1/admin/eu", headers=h).status_code == 401


def test_desativar_derruba_sessao_na_hora(client, session):
    """Desligar alguém tem que valer agora, não quando o token expirar daqui a 12 h."""
    _usuario(session)
    beto = _usuario(session, "beto@exemplo.org", PapelUsuario.REVISOR_AUDIO)
    h_ana, h_beto = _auth(client), _auth(client, "beto@exemplo.org")
    assert client.get("/v1/admin/eu", headers=h_beto).status_code == 200
    r = client.patch(f"/v1/admin/usuarios/{beto.id}", json={"ativo": False}, headers=h_ana)
    assert r.status_code == 200
    assert client.get("/v1/admin/eu", headers=h_beto).status_code == 401


def test_trocar_senha_derruba_as_outras_sessoes(client, session):
    _usuario(session)
    h1, h2 = _auth(client), _auth(client)
    r = client.post(
        "/v1/admin/eu/senha",
        json={"senha_atual": SENHA, "senha_nova": "outra senha bem comprida"},
        headers=h1,
    )
    assert r.status_code == 204
    assert client.get("/v1/admin/eu", headers=h1).status_code == 200
    assert client.get("/v1/admin/eu", headers=h2).status_code == 401
    assert _entrar(client, senha="outra senha bem comprida").status_code == 201


def test_trocar_senha_exige_a_atual(client, session):
    _usuario(session)
    h = _auth(client)
    r = client.post(
        "/v1/admin/eu/senha",
        json={"senha_atual": "não é esta", "senha_nova": "outra senha bem comprida"},
        headers=h,
    )
    assert r.status_code == 403


# --- Papéis -----------------------------------------------------------------


def test_tabela_de_papeis_da_especificacao():
    """Especificação, seção Admin: administrador tudo; revisor de texto edita segmento e
    aprova texto; revisor de áudio ouve, aponta erro, edita dicionário e aprova áudio.
    Nenhum revisor publica, aprova direitos ou gere contas."""
    texto, audio = PapelUsuario.REVISOR_TEXTO, PapelUsuario.REVISOR_AUDIO
    assert PERMISSOES_POR_PAPEL[PapelUsuario.ADMINISTRADOR] == frozenset(Permissao)
    assert pode(texto, Permissao.APROVAR_TEXTO) and not pode(texto, Permissao.APROVAR_AUDIO)
    assert pode(audio, Permissao.EDITAR_DICIONARIO) and not pode(audio, Permissao.EDITAR_SEGMENTO)
    for revisor in (texto, audio):
        for p in (
            Permissao.PUBLICAR,
            Permissao.APROVAR_DIREITOS,
            Permissao.EDITAR_DIREITOS,
            Permissao.GERIR_USUARIOS,
            Permissao.VER_AUDITORIA,
        ):
            assert not pode(revisor, p), (revisor, p)


@pytest.mark.parametrize("papel", [PapelUsuario.REVISOR_TEXTO, PapelUsuario.REVISOR_AUDIO])
@pytest.mark.parametrize(
    "metodo,rota",
    [
        ("get", "/v1/admin/usuarios"),
        ("post", "/v1/admin/usuarios"),
        ("get", "/v1/admin/auditoria"),
        ("post", "/v1/admin/edicoes/1/publicar"),
    ],
)
def test_revisor_barrado_nas_rotas_de_administrador(client, session, papel, metodo, rota):
    _usuario(session, papel=papel)
    h = _auth(client)
    corpo = (
        {"email": "x@exemplo.org", "nome": "X", "papel": "administrador", "senha": SENHA}
        if rota.endswith("usuarios") and metodo == "post"
        else None
    )
    r = client.request(metodo.upper(), rota, headers=h, json=corpo)
    assert r.status_code == 403


def test_administrador_cria_revisor(client, session):
    _usuario(session)
    h = _auth(client)
    r = client.post(
        "/v1/admin/usuarios",
        json={"email": "Bia@Exemplo.org", "nome": "Bia", "papel": "revisor_audio", "senha": SENHA},
        headers=h,
    )
    assert r.status_code == 201
    assert r.json()["email"] == "bia@exemplo.org"
    assert _entrar(client, "bia@exemplo.org").status_code == 201
    dup = client.post(
        "/v1/admin/usuarios",
        json={"email": "bia@exemplo.org", "nome": "B", "papel": "revisor_texto", "senha": SENHA},
        headers=h,
    )
    assert dup.status_code == 409


@pytest.mark.parametrize("mudanca", [{"papel": "revisor_texto"}, {"ativo": False}])
def test_nao_remove_o_ultimo_administrador(client, session, mudanca):
    """Sem administrador ativo ninguém mais cria contas nem publica: só voltaria pelo
    banco ou pela CLI no servidor."""
    ana = _usuario(session)
    h = _auth(client)
    r = client.patch(f"/v1/admin/usuarios/{ana.id}", json=mudanca, headers=h)
    assert r.status_code == 409
    session.refresh(ana)
    assert ana.papel == PapelUsuario.ADMINISTRADOR and ana.ativo

    _usuario(session, "carla@exemplo.org")
    r = client.patch(f"/v1/admin/usuarios/{ana.id}", json=mudanca, headers=h)
    assert r.status_code == 200


def test_redefinir_senha_de_outro_revoga_e_nao_registra_a_senha(client, session):
    _usuario(session)
    beto = _usuario(session, "beto@exemplo.org", PapelUsuario.REVISOR_TEXTO)
    h_ana, h_beto = _auth(client), _auth(client, "beto@exemplo.org")
    nova = "senha provisoria do beto"
    r = client.patch(f"/v1/admin/usuarios/{beto.id}", json={"senha": nova}, headers=h_ana)
    assert r.status_code == 200
    assert client.get("/v1/admin/eu", headers=h_beto).status_code == 401
    log = client.get("/v1/admin/auditoria?acao=usuario_alterado", headers=h_ana).json()
    assert log[0]["detalhes"] == {"senha": "redefinida"}
    assert nova not in json.dumps(log)


# --- Quem publicou o quê ----------------------------------------------------


def _edicao(session, status_direitos):
    obra = Obra(
        slug="o-evangelho",
        autor="Allan Kardec",
        titulo_original="L'Évangile",
        idioma_original="fr",
        sigla="ESE",
    )
    edicao = Edicao(obra=obra, idioma="pt-BR", titulo="O Evangelho", fonte="teste")
    edicao.capitulos.append(
        Capitulo(
            ordem=1, titulo="C1", referencia_canonica="ESE-01", estado=EstadoCapitulo.AUDIO_REVISADO
        )
    )
    edicao.direitos = Direitos(status=status_direitos)
    session.add(edicao)
    session.commit()
    return edicao


def test_publicacao_registra_quem_publicou(client, session):
    ana = _usuario(session)
    edicao = _edicao(session, StatusDireitos.APROVADO)
    h = _auth(client)
    r = client.post(f"/v1/admin/edicoes/{edicao.id}/publicar", headers=h)
    assert r.status_code == 200
    log = client.get(f"/v1/admin/auditoria?alvo_tipo=edicao&alvo_id={edicao.id}", headers=h).json()
    assert [(x["acao"], x["usuario_id"]) for x in log] == [("edicao_publicada", ana.id)]


def test_publicacao_sem_direitos_bloqueada_e_registrada(client, session):
    """A regra de direitos não pode ser contornada pela rota do admin, e a tentativa
    fica no log com o motivo."""
    _usuario(session)
    edicao = _edicao(session, StatusDireitos.PENDENTE)
    h = _auth(client)
    r = client.post(f"/v1/admin/edicoes/{edicao.id}/publicar", headers=h)
    assert r.status_code == 409
    assert "direitos" in r.json()["detail"]
    session.refresh(edicao)
    assert edicao.publicada_em is None
    log = client.get("/v1/admin/auditoria?acao=publicacao_bloqueada", headers=h).json()
    assert "direitos" in log[0]["detalhes"]["motivo"]


# --- CLI --------------------------------------------------------------------


def test_cli_cria_primeiro_administrador(client, session, monkeypatch):
    monkeypatch.setenv("CENTELHA_ADMIN_SENHA", SENHA)
    admin_cli.main(["criar", "--email", "Raiz@Exemplo.org", "--nome", "Raiz"])
    assert _entrar(client, "raiz@exemplo.org").json()["usuario"]["papel"] == "administrador"
    assert "usuario_criado" in _acoes(session)


def test_cli_recusa_senha_curta(session, monkeypatch):
    monkeypatch.setenv("CENTELHA_ADMIN_SENHA", "curta")
    with pytest.raises(SystemExit):
        admin_cli.main(["criar", "--email", "raiz@exemplo.org", "--nome", "Raiz"])
    assert session.scalar(select(Usuario.id)) is None
