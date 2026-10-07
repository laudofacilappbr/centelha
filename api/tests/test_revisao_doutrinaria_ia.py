"""Ferramentas da primeira revisão doutrinária por IA (#98)."""

import json
from dataclasses import asdict

import pytest

from centelha_api.pipeline.revisao_doutrinaria import (
    AvaliacaoInvalida,
    Seg,
    ler_avaliacao,
    main,
    montar_par,
    relatorio,
)

ORIGINAL = [
    Seg("titulo", "Capítulo I — De Deus"),
    Seg("pergunta", "Que é Deus?", 1),
    Seg("resposta", "Deus é a inteligência suprema, causa primária de todas as coisas.", 1),
    Seg("pergunta", "Que se deve entender por infinito?", 2),
    Seg("resposta", "O que não tem começo nem fim.", 2),
    Seg("pergunta", "Onde se pode encontrar a prova da existência de Deus?", 4),
    Seg("comentario", "Para crer-se em Deus, basta se lance o olhar sobre as obras da Criação.", 4),
]

ADAPTACAO = [
    Seg("titulo", "Deus"),
    Seg("pergunta", "Quem é Deus?", 1),
    Seg("resposta", "Deus é a inteligência maior, que criou todas as coisas.", 1),
    # Atribuição trocada: no original, a 4 só tem comentário de Kardec.
    Seg("pergunta", "Como saber que Deus existe?", 4),
    Seg("resposta", "Basta olhar a natureza à sua volta.", 4),
    Seg("paragrafo", "Peça para seus pais apoiarem o Centelhar em www.centelhar.com.br!"),
]


def _par(**kw):
    base = dict(
        obra="o-livro-dos-espiritos",
        capitulo="LE-C001",
        publico="infantil",
        titulo_original="O Livro dos Espíritos (pt-BR)",
        titulo_adaptacao="O Livro dos Espíritos para crianças",
        fonte_adaptacao="Adaptado de O Livro dos Espíritos, tradução de Guillon Ribeiro.",
    )
    return montar_par(ORIGINAL, ADAPTACAO, **{**base, **kw})


def test_pares_por_questao_e_apontamentos_automaticos():
    par = _par()
    trechos = {t.id: t for t in par.trechos}
    assert list(trechos) == [
        "1 · pergunta",
        "1 · resposta",
        "4 · pergunta",
        "4 · resposta",
        "capítulo · texto",
    ]
    assert trechos["1 · resposta"].original.startswith("Deus é a inteligência suprema")
    assert trechos["1 · resposta"].automatico == []
    # Resposta dos Espíritos que no original é comentário de Kardec.
    [atrib] = trechos["4 · resposta"].automatico
    assert atrib.nivel == "bloqueio" and atrib.motivo.startswith("atribuição")
    assert trechos["4 · resposta"].original.startswith("Para crer-se em Deus")
    # Infantil: link e pedido de apoio.
    motivos = [(a.nivel, a.motivo) for a in trechos["capítulo · texto"].automatico]
    assert ("bloqueio", "link no perfil infantil") in motivos
    assert any(n == "bloqueio" and "pedido de apoio" in m for n, m in motivos)
    # A questão 2 ficou de fora da adaptação.
    [fora] = par.geral
    assert fora.nivel == "atencao" and fora.trecho == "2"


def test_edicao_sem_rotulo_de_adaptacao_bloqueia():
    par = _par(titulo_adaptacao="O Livro dos Espíritos", fonte_adaptacao="Guillon Ribeiro")
    assert any(a.nivel == "bloqueio" and "adaptado de" in a.motivo for a in par.geral)


def test_juvenil_nao_tem_regra_do_infantil_mas_tem_de_linguagem():
    longa = " ".join(["palavra"] * 60) + "."
    par = montar_par(
        [Seg("pergunta", "P?", 1), Seg("resposta", "R.", 1)],
        [Seg("pergunta", "P?", 1), Seg("resposta", f"Veja www.exemplo.org agora. {longa}", 1)],
        obra="x",
        capitulo="X-C1",
        publico="juvenil",
        titulo_original="X",
        titulo_adaptacao="X, adaptação juvenil",
    )
    resposta = par.trechos[1]
    assert all("infantil" not in a.motivo for a in resposta.automatico)
    assert any("frase muito longa" in a.motivo for a in resposta.automatico)


def _avaliacao(par, **troca):
    itens = [{"id": t.id, "nivel": "ok", "motivo": ""} for t in par.trechos]
    for item in itens:
        if item["id"] in troca:
            item.update(troca[item["id"]])
    return itens


def test_avaliacao_precisa_cobrir_todos_os_trechos_com_motivo():
    par = _par()
    with pytest.raises(AvaliacaoInvalida, match="sem avaliação"):
        ler_avaliacao(par, _avaliacao(par)[:-1])
    with pytest.raises(AvaliacaoInvalida, match="sem motivo"):
        ler_avaliacao(par, _avaliacao(par, **{"1 · resposta": {"nivel": "atencao"}}))
    with pytest.raises(AvaliacaoInvalida, match="nivel"):
        ler_avaliacao(par, _avaliacao(par, **{"1 · resposta": {"nivel": "aprovado"}}))
    with pytest.raises(AvaliacaoInvalida, match="desconhecido"):
        ler_avaliacao(par, [*_avaliacao(par), {"id": "99 · resposta", "nivel": "ok"}])


def test_relatorio_junta_ia_e_automatico_e_nao_aprova():
    par = _par()
    av = ler_avaliacao(
        par,
        _avaliacao(
            par,
            **{
                "1 · resposta": {
                    "nivel": "atencao",
                    "motivo": "fidelidade: 'causa primária' virou 'criou'",
                    "trecho": "que criou todas as coisas",
                }
            },
        ),
    )
    texto, contagem = relatorio(par, av)
    assert contagem == {"bloqueio": 2, "atencao": 1, "ok": 2}
    assert "**Não aprova nada**" in texto
    assert "| 1 · resposta | fidelidade: 'causa primária' virou 'criou'" in texto
    assert "## Bloqueios (2)" in texto
    assert "## Sem apontamento (2)\n\n1 · pergunta, 4 · pergunta" in texto


def test_cli_relatorio(tmp_path, capsys):
    par = _par()
    (tmp_path / "par.json").write_text(
        json.dumps(asdict(par), ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "av.json").write_text(json.dumps(_avaliacao(par)), encoding="utf-8")
    saida = tmp_path / "rev.md"
    args = ["relatorio", str(tmp_path / "par.json"), str(tmp_path / "av.json")]
    assert main([*args, "--saida", str(saida)]) == 0
    assert "bloqueio: 2" in capsys.readouterr().out
    assert saida.read_text(encoding="utf-8").startswith("# Revisão doutrinária (IA)")
    (tmp_path / "av.json").write_text("[]", encoding="utf-8")
    assert main([*args, "--saida", str(saida)]) == 1
