import base64
import os
import subprocess
from datetime import UTC, datetime

import pytest

from centelha_api.config import get_settings
from centelha_api.models import (
    Capitulo,
    Direitos,
    Edicao,
    EstadoCapitulo,
    FaixaAudio,
    Obra,
    PapelVoz,
    StatusDireitos,
    Voz,
)
from centelha_api.pipeline import cifra, exportar
from centelha_api.pipeline.audio import duracao_ms, ffmpeg_exe

URL = "https://audio.exemplo"


def _tom(destino, segundos):
    subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration={segundos}", "-c:a", "aac", str(destino)],
        check=True,
    )  # fmt: skip
    return destino.read_bytes()


@pytest.fixture
def edicao(session, tmp_path, monkeypatch):
    """Edição publicada: cap. 1 cifrado (3 s), cap. 2 aberto (2 s), cap. 3 não publicado,
    cap. 4 só com faixa de motor sem licença."""
    mestra = os.urandom(32)
    pasta = tmp_path / "audio"
    pasta.mkdir()
    monkeypatch.setenv("CENTELHA_AUDIO_DIR", str(pasta))
    monkeypatch.setenv("CENTELHA_AUDIO_URL_BASE", URL)
    monkeypatch.setenv("CENTELHA_AUDIO_CHAVE_MESTRA", base64.b64encode(mestra).decode())
    get_settings.cache_clear()

    chave = cifra.nova_chave()
    (pasta / "c1.cent").write_bytes(cifra.cifrar(_tom(tmp_path / "a.m4a", 3), chave))
    (pasta / "c2.m4a").write_bytes(_tom(tmp_path / "b.m4a", 2))

    obra = Obra(
        slug="le", autor="Allan Kardec", titulo_original="LE", idioma_original="fr", sigla="LE"
    )
    ed = Edicao(
        obra=obra,
        idioma="pt-BR",
        titulo="O Livro dos Espíritos",
        tradutor="Guillon Ribeiro",
        fonte="FEB, 1944",
        publicada_em=datetime.now(UTC),
    )
    ed.direitos = Direitos(status=StatusDireitos.APROVADO)
    publicado = EstadoCapitulo.PUBLICADO
    ed.capitulos = [
        Capitulo(
            ordem=1, titulo="CAPÍTULO I — De Deus", referencia_canonica="C1", estado=publicado
        ),
        Capitulo(
            ordem=2, titulo="Capítulo II / Elementos", referencia_canonica="C2", estado=publicado
        ),
        Capitulo(
            ordem=3, titulo="III", referencia_canonica="C3", estado=EstadoCapitulo.AUDIO_GERADO
        ),
        Capitulo(ordem=4, titulo="IV", referencia_canonica="C4", estado=publicado),
    ]
    falso = Voz(idioma="pt-BR", motor="falso", voz_id="n", papel=PapelVoz.NARRADOR)
    piper = Voz(idioma="pt-BR", motor="piper", voz_id="p", papel=PapelVoz.NARRADOR)
    session.add_all([ed, falso, piper])
    session.flush()
    c1, c2, c3, c4 = ed.capitulos
    session.add_all(
        [
            FaixaAudio(capitulo_id=c1.id, voz_id=falso.id, url=f"{URL}/c1.cent", duracao_ms=3000,
                       marcacoes=[], formato=cifra.FORMATO,
                       chave_cifrada=cifra.embrulhar(chave, mestra)),
            FaixaAudio(capitulo_id=c2.id, voz_id=falso.id, url=f"{URL}/c2.m4a", duracao_ms=2000,
                       marcacoes=[]),
            FaixaAudio(capitulo_id=c3.id, voz_id=falso.id, url=f"{URL}/c2.m4a", duracao_ms=2000,
                       marcacoes=[]),
            FaixaAudio(capitulo_id=c4.id, voz_id=piper.id, url=f"{URL}/c2.m4a", duracao_ms=2000,
                       marcacoes=[]),
        ]
    )  # fmt: skip
    session.commit()
    yield ed
    get_settings.cache_clear()


def test_exporta_so_o_publicado_em_m4a_aberto_e_numerado(session, edicao, tmp_path):
    saida = tmp_path / "exportacao"
    arquivos = exportar.exportar(session, edicao.id, saida, "S-2026-014")
    assert [a.name for a in arquivos] == [
        "1-capitulo-i-de-deus.m4a",
        "2-capitulo-ii-elementos.m4a",
    ]
    # A .cent saiu decifrada: AAC que qualquer player abre, com a duração do capítulo.
    for arquivo, ms in zip(arquivos, [3000, 2000], strict=True):
        assert arquivo.read_bytes()[4:8] == b"ftyp"
        assert abs(duracao_ms(arquivo) - ms) < 150
    leiame = (saida / "LEIAME.txt").read_text(encoding="utf-8")
    assert "S-2026-014" in leiame
    assert "tradução de Guillon Ribeiro" in leiame
    assert "Não redistribua" in leiame


def test_edicao_nao_publicada_ou_sem_direitos_nao_sai(session, edicao, tmp_path):
    edicao.direitos.status = StatusDireitos.PENDENTE
    session.commit()
    with pytest.raises(exportar.ErroExportacao, match="direitos"):
        exportar.exportar(session, edicao.id, tmp_path / "x", "S-1")
    edicao.direitos.status = StatusDireitos.APROVADO
    edicao.publicada_em = None
    session.commit()
    with pytest.raises(exportar.ErroExportacao, match="publicada"):
        exportar.exportar(session, edicao.id, tmp_path / "x", "S-1")
    assert not (tmp_path / "x").exists()


def test_cli(session, edicao, tmp_path, capsys):
    saida = tmp_path / "cli"
    assert (
        exportar.main(["--edicao", str(edicao.id), "--saida", str(saida), "--pedido", "S-9"]) == 0
    )
    assert capsys.readouterr().out.strip() == f"2 capítulos em {saida}"
    assert exportar.main(["--edicao", "999999", "--saida", str(saida), "--pedido", "S-9"]) == 1
