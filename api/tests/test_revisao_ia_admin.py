"""Relatório da revisão por IA anexado ao capítulo adaptado no admin (#98)."""

import json
from dataclasses import asdict

import pytest
from sqlalchemy import select

from centelha_api.dominio import contas
from centelha_api.models import (
    Capitulo,
    Edicao,
    EstadoCapitulo,
    Obra,
    PapelUsuario,
    Publico,
    RegistroAuditoria,
    RevisaoIA,
    Segmento,
    TipoSegmento,
    Usuario,
)
from centelha_api.pipeline import revisao_doutrinaria

SENHA = "cavalo correto bateria grampo"


def _login(client, session, email, papel):
    session.add(Usuario(email=email, nome=email, papel=papel, senha_hash=contas.gerar_hash(SENHA)))
    session.commit()
    r = client.post("/v1/admin/sessoes", json={"email": email, "senha": SENHA})
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def h_admin(client, session):
    return _login(client, session, "ana@exemplo.org", PapelUsuario.ADMINISTRADOR)


@pytest.fixture
def caps(session):
    obra = Obra(
        slug="o-livro-dos-espiritos",
        autor="Allan Kardec",
        titulo_original="Le Livre des Esprits",
        idioma_original="fr",
        sigla="LE",
    )

    def edicao(publico, titulo, texto):
        e = Edicao(obra=obra, idioma="pt-BR", publico=publico, titulo=titulo, fonte="Adaptado de…")
        c = Capitulo(
            ordem=1, titulo="I", referencia_canonica="LE-C001", estado=EstadoCapitulo.TEXTO_REVISADO
        )
        c.segmentos = [
            Segmento(ordem=1, tipo=TipoSegmento.PERGUNTA, texto="Que é Deus?", numero_questao=1),
            Segmento(ordem=2, tipo=TipoSegmento.RESPOSTA, texto=texto, numero_questao=1),
        ]
        e.capitulos = [c]
        session.add(e)
        return c

    adulto = edicao(Publico.ADULTO, "O Livro dos Espíritos", "Deus é a inteligência suprema.")
    infantil = edicao(
        Publico.INFANTIL, "O Livro dos Espíritos para crianças", "Deus é a maior inteligência."
    )
    session.commit()
    return {"adulto": adulto, "infantil": infantil}


DADOS = {"relatorio": "# Revisão doutrinária (IA)\n\nNada.", "bloqueios": 1, "atencoes": 2, "ok": 3}


def test_anexa_e_o_detalhe_mostra_a_ultima(client, session, h_admin, caps):
    url = f"/v1/admin/capitulos/{caps['infantil'].id}"
    assert client.get(url, headers=h_admin).json()["revisao_ia"] is None
    r = client.post(f"{url}/revisoes-ia", json=DADOS, headers=h_admin)
    assert r.status_code == 201, r.text
    assert r.json()["bloqueios"] == 1
    client.post(f"{url}/revisoes-ia", json={**DADOS, "bloqueios": 0}, headers=h_admin)
    detalhe = client.get(url, headers=h_admin).json()
    assert detalhe["revisao_ia"]["bloqueios"] == 0
    assert "relatorio" not in detalhe["revisao_ia"]
    # Informa, não trava: a aprovação da doutrina continua disponível para quem pode.
    assert "aprovar_doutrina" in detalhe["acoes"]
    lista = client.get(f"{url}/revisoes-ia", headers=h_admin).json()
    assert [x["bloqueios"] for x in lista] == [0, 1]
    assert lista[0]["relatorio"].startswith("# Revisão doutrinária")
    acoes = session.scalars(
        select(RegistroAuditoria.acao).where(RegistroAuditoria.acao == "revisao_ia_anexada")
    ).all()
    assert len(acoes) == 2


def test_capitulo_adulto_nao_recebe(client, h_admin, caps):
    r = client.post(
        f"/v1/admin/capitulos/{caps['adulto'].id}/revisoes-ia", json=DADOS, headers=h_admin
    )
    assert r.status_code == 409


def test_revisor_ve_mas_nao_anexa(client, session, caps):
    h = _login(client, session, "rev@exemplo.org", PapelUsuario.REVISOR_TEXTO)
    url = f"/v1/admin/capitulos/{caps['infantil'].id}/revisoes-ia"
    assert client.post(url, json=DADOS, headers=h).status_code == 403
    assert client.get(url, headers=h).status_code == 200


def test_cli_anexa_pelo_capitulo_do_par(tmp_path, session, caps, capsys):
    cap = caps["infantil"]
    par = revisao_doutrinaria.montar_par(
        [revisao_doutrinaria.Seg("pergunta", "Que é Deus?", 1)],
        [revisao_doutrinaria.Seg("pergunta", "Que é Deus?", 1)],
        obra="o-livro-dos-espiritos",
        capitulo="LE-C001",
        publico="infantil",
        titulo_original="O Livro dos Espíritos",
        titulo_adaptacao="O Livro dos Espíritos para crianças",
    )
    par.capitulo_id = cap.id
    (tmp_path / "par.json").write_text(json.dumps(asdict(par)), encoding="utf-8")
    (tmp_path / "av.json").write_text(
        json.dumps([{"id": "1 · pergunta", "nivel": "ok", "motivo": ""}]), encoding="utf-8"
    )
    args = ["relatorio", str(tmp_path / "par.json"), str(tmp_path / "av.json")]
    assert revisao_doutrinaria.main([*args, "--saida", str(tmp_path / "r.md"), "--anexar"]) == 0
    assert "relatório anexado ao capítulo" in capsys.readouterr().out
    session.expire_all()
    [revisao] = session.scalars(select(RevisaoIA).where(RevisaoIA.capitulo_id == cap.id)).all()
    assert revisao.usuario_id is None
    assert revisao.relatorio.startswith("# Revisão doutrinária (IA)")
