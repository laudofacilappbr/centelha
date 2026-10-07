import base64
import io
import json
import os
from pathlib import Path

import pytest

from centelha_api.config import get_settings
from centelha_api.models import (
    Capitulo,
    Edicao,
    EstadoCapitulo,
    FaixaAudio,
    Obra,
    PapelVoz,
    Voz,
)
from centelha_api.pipeline import cifra, cloudflare, recifrar
from centelha_api.pipeline.armazenamento import ArmazenamentoLocal
from centelha_api.pipeline.faixa import audio_aberto

MESTRA = bytes(range(32))
URL = "https://audio.exemplo"


@pytest.fixture
def cfg(monkeypatch, tmp_path):
    c = get_settings()
    monkeypatch.setattr(c, "audio_dir", str(tmp_path / "audio"))
    monkeypatch.setattr(c, "audio_url_base", URL)
    monkeypatch.setattr(c, "audio_chave_mestra", base64.b64encode(MESTRA).decode())
    monkeypatch.setattr(c, "api_url_publica", "https://api.exemplo")
    monkeypatch.setattr(c, "cloudflare_zona", "")
    monkeypatch.setattr(c, "cloudflare_token", "")
    return c


@pytest.fixture
def armazenamento(cfg):
    return ArmazenamentoLocal(Path(cfg.audio_dir), URL)


@pytest.fixture
def faixas(session, cfg):
    """Duas versões abertas do mesmo capítulo e uma já cifrada."""
    cap = Capitulo(
        ordem=1, titulo="I", referencia_canonica="LE-C001", estado=EstadoCapitulo.PUBLICADO
    )
    ed = Edicao(
        obra=Obra(
            slug="o-livro-dos-espiritos",
            autor="Allan Kardec",
            titulo_original="Le Livre des Esprits",
            idioma_original="fr",
            sigla="LE",
        ),
        idioma="pt-BR",
        titulo="O Livro dos Espíritos",
        fonte="teste",
    )
    ed.capitulos = [cap]
    voz = Voz(idioma="pt-BR", motor="falso", voz_id="n", papel=PapelVoz.NARRADOR)
    session.add_all([ed, voz])
    session.flush()
    pasta = os.path.join(cfg.audio_dir, "le", "pt-BR", "e1")
    os.makedirs(pasta, exist_ok=True)
    criadas = []
    for versao in (1, 2):
        nome = f"le-c001-v{versao}.m4a"
        with open(os.path.join(pasta, nome), "wb") as f:
            f.write(b"m4a aberto " * 1000 + bytes([versao]))
        criadas.append(
            FaixaAudio(
                capitulo_id=cap.id,
                voz_id=voz.id,
                versao=versao,
                url=f"{URL}/le/pt-BR/e1/{nome}",
                duracao_ms=1000,
                marcacoes=[],
            )
        )
    chave = cifra.nova_chave()
    with open(os.path.join(pasta, "le-c001-v3.cent"), "wb") as f:
        f.write(cifra.cifrar(b"ja cifrada", chave))
    criadas.append(
        FaixaAudio(
            capitulo_id=cap.id,
            voz_id=voz.id,
            versao=3,
            url=f"{URL}/le/pt-BR/e1/le-c001-v3.cent",
            duracao_ms=1000,
            marcacoes=[],
            formato=cifra.FORMATO,
            chave_cifrada=cifra.embrulhar(chave, MESTRA),
        )
    )
    session.add_all(criadas)
    session.commit()
    return {"cap": cap, "faixas": criadas, "pasta": pasta}


def test_cifra_as_abertas_apaga_o_m4a_e_lista_a_purga(session, armazenamento, faixas):
    originais = {f.id: audio_aberto(f) for f in faixas["faixas"][:2]}
    r = recifrar.recifrar(session, armazenamento, MESTRA)
    assert r.cifradas == 2
    assert r.puladas == []
    assert sorted(os.listdir(faixas["pasta"])) == [
        "le-c001-v1.cent",
        "le-c001-v2.cent",
        "le-c001-v3.cent",
    ]
    for f in faixas["faixas"][:2]:
        session.refresh(f)
        assert f.formato == cifra.FORMATO
        assert f.url.endswith(".cent")
        # O mesmo áudio de antes, agora só com a chave da faixa.
        assert audio_aberto(f) == originais[f.id]
    cap = faixas["cap"].id
    assert r.a_purgar == [
        f"{URL}/le/pt-BR/e1/le-c001-v1.m4a",
        f"https://api.exemplo/v1/capitulos/{cap}",
        f"{URL}/le/pt-BR/e1/le-c001-v2.m4a",
        f"https://api.exemplo/v1/capitulos/{cap}",
    ]


def test_rodar_de_novo_nao_faz_nada(session, armazenamento, faixas):
    recifrar.recifrar(session, armazenamento, MESTRA)
    r = recifrar.recifrar(session, armazenamento, MESTRA)
    assert (r.cifradas, r.puladas, r.a_purgar) == (0, [], [])


def test_simular_e_limite_nao_mexem_em_nada(session, armazenamento, faixas):
    r = recifrar.recifrar(session, armazenamento, MESTRA, simular=True)
    assert r.cifradas == 2
    assert "le-c001-v1.m4a" in os.listdir(faixas["pasta"])
    r = recifrar.recifrar(session, armazenamento, MESTRA, limite=1)
    assert r.cifradas == 1
    assert sorted(os.listdir(faixas["pasta"]))[:2] == ["le-c001-v1.cent", "le-c001-v2.m4a"]


def test_arquivo_ausente_pula_e_mantem_a_faixa(session, armazenamento, faixas):
    os.remove(os.path.join(faixas["pasta"], "le-c001-v1.m4a"))
    r = recifrar.recifrar(session, armazenamento, MESTRA)
    assert r.cifradas == 1
    assert len(r.puladas) == 1
    v1 = faixas["faixas"][0]
    session.refresh(v1)
    assert v1.formato == "m4a"
    assert v1.url.endswith(".m4a")


def test_cli_sem_chave_mestra_falha(cfg, monkeypatch, capsys):
    monkeypatch.setattr(cfg, "audio_chave_mestra", "")
    assert recifrar.main(["--simular"]) == 1


def test_cli_sem_cloudflare_lista_as_urls(session, faixas, capsys):
    assert recifrar.main([]) == 0
    saida = capsys.readouterr().out
    assert "2 faixas cifradas" in saida
    assert "purgue estas URLs no painel" in saida
    assert "le-c001-v1.m4a" in saida


class _Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_purga_em_lotes_de_30(cfg, monkeypatch):
    monkeypatch.setattr(cfg, "cloudflare_zona", "zona123")
    monkeypatch.setattr(cfg, "cloudflare_token", "tok")
    pedidos = []

    def urlopen(pedido, timeout):
        pedidos.append(pedido)
        return _Resposta(json.dumps({"success": True}).encode())

    monkeypatch.setattr(cloudflare.urllib.request, "urlopen", urlopen)
    urls = [f"{URL}/x{i}.m4a" for i in range(31)]
    assert cloudflare.purgar(urls) is True
    assert [len(json.loads(p.data)["files"]) for p in pedidos] == [30, 1]
    assert pedidos[0].full_url.endswith("/zones/zona123/purge_cache")
    assert pedidos[0].get_header("Authorization") == "Bearer tok"


def test_purga_recusada_vira_erro(cfg, monkeypatch):
    monkeypatch.setattr(cfg, "cloudflare_zona", "z")
    monkeypatch.setattr(cfg, "cloudflare_token", "t")
    monkeypatch.setattr(
        cloudflare.urllib.request,
        "urlopen",
        lambda p, timeout: _Resposta(b'{"success": false, "errors": [{"code": 10000}]}'),
    )
    with pytest.raises(cloudflare.ErroPurga, match="recusou"):
        cloudflare.purgar(["https://audio.exemplo/a.m4a"])


def test_purga_sem_configuracao_nao_chama_nada(cfg):
    assert cloudflare.purgar(["https://audio.exemplo/a.m4a"]) is False
