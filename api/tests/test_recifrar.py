"""Recifrar as faixas .m4a antigas (#73): nada se perde, nada aberto sobra."""

import base64
import json
import os

import pytest

from centelha_api.config import get_settings
from centelha_api.models import Capitulo, Edicao, FaixaAudio, Obra, PapelVoz, Voz
from centelha_api.pipeline import cifra, recifrar

MESTRA = os.urandom(32)
BASE = "https://audio.exemplo"


@pytest.fixture
def audio(monkeypatch, tmp_path):
    raiz = tmp_path / "audio"
    monkeypatch.setenv("CENTELHA_AUDIO_DIR", str(raiz))
    monkeypatch.setenv("CENTELHA_AUDIO_URL_BASE", BASE)
    monkeypatch.setenv("CENTELHA_AUDIO_CIFRAR", "true")
    monkeypatch.setenv("CENTELHA_AUDIO_CHAVE_MESTRA", base64.b64encode(MESTRA).decode())
    monkeypatch.delenv("CENTELHA_CLOUDFLARE_ZONE_ID", raising=False)
    monkeypatch.delenv("CENTELHA_CLOUDFLARE_TOKEN", raising=False)
    get_settings.cache_clear()
    yield raiz
    get_settings.cache_clear()


def _faixas(session, raiz, quantas=2):
    """Faixas .m4a como as gravadas antes da cifragem, com o arquivo no volume."""
    obra = Obra(
        slug="o-livro-dos-espiritos",
        autor="Allan Kardec",
        titulo_original="Le Livre des Esprits",
        idioma_original="fr",
        sigla="LE",
    )
    ed = Edicao(obra=obra, idioma="pt-BR", titulo="O Livro dos Espíritos", fonte="teste")
    voz = Voz(idioma="pt-BR", motor="falso", voz_id="n", papel=PapelVoz.NARRADOR)
    session.add_all([ed, voz])
    session.flush()
    faixas = []
    for n in range(1, quantas + 1):
        cap = Capitulo(edicao=ed, ordem=n, titulo=str(n), referencia_canonica=f"LE-C00{n}")
        relativo = f"le/pt-BR/e{ed.id}/le-c00{n}-v2.m4a"
        arquivo = raiz / relativo
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        # Mais de um bloco de 64 KiB, para a cifra por blocos valer de verdade.
        arquivo.write_bytes(os.urandom(150_000))
        faixa = FaixaAudio(
            capitulo=cap,
            voz_id=voz.id,
            versao=2,
            url=f"{BASE}/{relativo}",
            duracao_ms=1000,
            marcacoes=[{"segmento_id": 1, "inicio_ms": 0, "fim_ms": 900}],
        )
        session.add(faixa)
        faixas.append(faixa)
    session.commit()
    return faixas


def test_recifra_apaga_o_aberto_e_mantem_versao_e_marcacoes(session, audio):
    faixas = _faixas(session, audio)
    originais = {f.id: (audio / f.url.removeprefix(BASE + "/")).read_bytes() for f in faixas}

    rel = recifrar.executar(session, MESTRA)

    assert rel.falhas == []
    assert sorted(rel.recifradas) == sorted(originais)
    assert rel.apagados == [f"{BASE}/le/pt-BR/e1/le-c00{n}-v2.m4a" for n in (1, 2)]
    for faixa in faixas:
        session.refresh(faixa)
        assert faixa.formato == cifra.FORMATO
        assert faixa.url.endswith("-v2.cent")
        assert faixa.versao == 2 and faixa.marcacoes[0]["fim_ms"] == 900
        chave = cifra.desembrulhar(faixa.chave_cifrada, MESTRA)
        publicado = (audio / faixa.url.removeprefix(BASE + "/")).read_bytes()
        assert cifra.decifrar(publicado, chave) == originais[faixa.id]
    assert list(audio.rglob("*.m4a")) == []


def test_execucao_interrompida_depois_do_commit_e_terminada_pela_seguinte(session, audio):
    """Cifrou e fez commit, mas caiu antes de apagar: o .m4a é apagado na próxima."""
    [faixa] = _faixas(session, audio, 1)
    recifrar.recifrar(faixa, MESTRA)
    session.commit()
    assert len(list(audio.rglob("*.m4a"))) == 1

    rel = recifrar.executar(session, MESTRA)
    assert rel.recifradas == []
    assert rel.apagados == [f"{BASE}/le/pt-BR/e1/le-c001-v2.m4a"]
    assert list(audio.rglob("*.m4a")) == []


def test_nao_apaga_aberto_que_nao_confere_com_o_cifrado(session, audio):
    """O .m4a só sai quando o .cent decifra exatamente nele: arquivo trocado no meio do
    caminho fica, e a falha aparece."""
    [faixa] = _faixas(session, audio, 1)
    recifrar.recifrar(faixa, MESTRA)
    session.commit()
    aberto = audio / "le/pt-BR/e1/le-c001-v2.m4a"
    aberto.write_bytes(b"outro audio")

    rel = recifrar.executar(session, MESTRA)
    assert rel.apagados == []
    assert "não confere" in rel.falhas[0]
    assert aberto.exists()


def test_arquivo_ausente_nao_muda_o_banco(session, audio):
    [faixa] = _faixas(session, audio, 1)
    (audio / "le/pt-BR/e1/le-c001-v2.m4a").unlink()
    rel = recifrar.executar(session, MESTRA)
    assert "não existe" in rel.falhas[0]
    session.refresh(faixa)
    assert (faixa.formato, faixa.chave_cifrada) == ("m4a", None)


def test_purge_em_lotes_de_30_e_erro_da_cloudflare():
    pedidos = []

    def enviar(pedido):
        pedidos.append(pedido)
        return {"success": True}

    urls = [f"{BASE}/x{n}.m4a" for n in range(65)]
    recifrar.purgar(urls, "zona", "tok", enviar)
    assert [len(json.loads(p.data)["files"]) for p in pedidos] == [30, 30, 5]
    assert pedidos[0].full_url.endswith("/zones/zona/purge_cache")
    assert pedidos[0].get_header("Authorization") == "Bearer tok"

    with pytest.raises(recifrar.ErroPurge, match="recusado"):
        recifrar.purgar(urls[:1], "zona", "tok", lambda p: {"success": False, "errors": ["x"]})


def test_cli_recusa_com_cifragem_desligada(audio, monkeypatch, capsys):
    """O app atual só toca .m4a: recifrar antes de ele decifrar tira o áudio do ar."""
    monkeypatch.setenv("CENTELHA_AUDIO_CIFRAR", "false")
    get_settings.cache_clear()
    assert recifrar.main(["--executar"]) == 2
    assert "desligada" in capsys.readouterr().err


def test_cli_sem_executar_so_lista(session, audio, capsys):
    _faixas(session, audio, 1)
    assert recifrar.main([]) == 0
    saida = capsys.readouterr().out
    assert "1 faixas .m4a para cifrar" in saida
    assert len(list(audio.rglob("*.m4a"))) == 1
    assert list(audio.rglob("*.cent")) == []


def test_cli_executa_e_lista_urls_sem_token(session, audio, capsys):
    _faixas(session, audio, 1)
    assert recifrar.main(["--executar"]) == 0
    saida = capsys.readouterr().out
    assert "Purgue à mão" in saida
    assert f"{BASE}/le/pt-BR/e1/le-c001-v2.m4a" in saida


def test_cli_purga_com_token(session, audio, monkeypatch, capsys):
    _faixas(session, audio, 1)
    monkeypatch.setenv("CENTELHA_CLOUDFLARE_ZONE_ID", "zona")
    monkeypatch.setenv("CENTELHA_CLOUDFLARE_TOKEN", "tok")
    get_settings.cache_clear()
    pedidos = []
    monkeypatch.setattr(recifrar, "_enviar", lambda p: pedidos.append(p) or {"success": True})
    assert recifrar.main(["--executar"]) == 0
    assert json.loads(pedidos[0].data)["files"] == [f"{BASE}/le/pt-BR/e1/le-c001-v2.m4a"]
    assert "purge pedido" in capsys.readouterr().out
