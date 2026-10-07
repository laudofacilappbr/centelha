"""Planos de estudo (#43): o roteiro versionado chega inteiro e válido ao app."""

import pytest
from pydantic import ValidationError

from centelha_api.routers import planos


def test_lista_os_tres_planos(client):
    r = client.get("/v1/planos")
    assert r.status_code == 200
    assert "max-age" in r.headers["cache-control"]
    assert {(p["slug"], p["dias"]) for p in r.json()} == {
        ("primeiros-passos", 15),
        ("o-evangelho-em-30-dias", 30),
        ("o-livro-dos-espiritos-em-90-dias", 90),
    }


def test_detalhe_e_404(client):
    r = client.get("/v1/planos/primeiros-passos")
    assert r.status_code == 200
    dia1 = r.json()["dias"][0]
    assert dia1 == {
        "dia": 1,
        "titulo": "Deus",
        "leituras": [{"sigla": "LE", "capitulo": None, "de": 1, "ate": 16}],
    }
    assert client.get("/v1/planos/nao-existe").status_code == 404


def test_le_em_90_dias_cobre_todas_as_questoes_uma_vez():
    """Cada questão de 1 a 1019 aparece em exatamente um dia, em ordem, e os blocos
    não atravessam capítulo (o roteiro foi gerado a partir dos limites deles)."""
    plano = next(p for p in planos.carregar().planos if p.slug.endswith("90-dias"))
    faixas = [(x.de, x.ate) for d in plano.dias for x in d.leituras if x.de is not None]
    vistas = [n for de, ate in faixas for n in range(de, ate + 1)]
    assert vistas == list(range(1, 1020))
    capitulos = [x.capitulo for d in plano.dias for x in d.leituras if x.capitulo]
    assert capitulos[:4] == ["LE-C001"] * 3 + ["LE-C002"]
    assert capitulos[-1] == "LE-C032"


def test_evangelho_passa_por_todos_os_capitulos():
    plano = next(p for p in planos.carregar().planos if p.slug == "o-evangelho-em-30-dias")
    refs = [x.capitulo for d in plano.dias for x in d.leituras]
    assert sorted(set(refs)) == [f"ESE-C{n:03d}" for n in range(1, 31)]


@pytest.mark.parametrize(
    "leitura",
    [
        {"sigla": "LE", "de": 20, "ate": 10},
        {"sigla": "LE", "de": 1, "ate": 1020},
        {"sigla": "ESE", "de": 1, "ate": 2},
        {"sigla": "ESE", "capitulo": "LE-C001"},
        {"sigla": "LE", "capitulo": "LE-C001", "de": 1, "ate": 2},
    ],
)
def test_leitura_invalida_e_recusada(leitura):
    """Roteiro quebrado falha ao carregar, não no app."""
    with pytest.raises(ValidationError):
        planos.Leitura.model_validate(leitura)


def test_dias_fora_de_ordem_sao_recusados():
    with pytest.raises(ValidationError, match="fora de ordem"):
        planos.Plano.model_validate(
            {
                "slug": "x",
                "titulo": "x",
                "descricao": "x",
                "dias": [
                    {"dia": 2, "titulo": "a", "leituras": [{"sigla": "LE", "de": 1, "ate": 2}]}
                ],
            }
        )
