import base64
import os
import subprocess

import pytest

from centelha_api.config import get_settings
from centelha_api.models import (
    Capitulo,
    Edicao,
    EstadoCapitulo,
    FaixaAudio,
    Obra,
    PapelVoz,
    Segmento,
    TipoSegmento,
    Voz,
)
from centelha_api.pipeline import amostra, cifra
from centelha_api.pipeline.armazenamento import ArmazenamentoLocal
from centelha_api.pipeline.audio import duracao_ms, ffmpeg_exe

URL = "https://audio.exemplo"


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    mestra = os.urandom(32)
    monkeypatch.setenv("CENTELHA_AUDIO_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("CENTELHA_AUDIO_URL_BASE", URL)
    monkeypatch.setenv("CENTELHA_AUDIO_CHAVE_MESTRA", base64.b64encode(mestra).decode())
    get_settings.cache_clear()
    yield {"mestra": mestra, "dir": tmp_path / "audio"}
    get_settings.cache_clear()


@pytest.fixture
def capitulo(session, ambiente, tmp_path):
    """Capítulo com faixa .cent de 12 s; a questão 88 vai de 3 s a 7 s."""
    claro = tmp_path / "c.m4a"
    subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=12", "-c:a", "aac", str(claro)],
        check=True,
    )  # fmt: skip
    chave = cifra.nova_chave()
    (ambiente["dir"] / "le").mkdir(parents=True)
    (ambiente["dir"] / "le" / "c1-v1.cent").write_bytes(cifra.cifrar(claro.read_bytes(), chave))

    def criar(estado=EstadoCapitulo.AUDIO_REVISADO, marcar=True):
        obra = Obra(
            slug="le", autor="Kardec", titulo_original="LE", idioma_original="fr", sigla="LE"
        )
        ed = Edicao(obra=obra, idioma="pt-BR", titulo="O Livro dos Espíritos", fonte="t")
        cap = Capitulo(ordem=1, titulo="I", referencia_canonica="LE-C1", estado=estado)
        cap.segmentos = [
            Segmento(ordem=1, tipo=TipoSegmento.PERGUNTA, texto="Antes?", numero_questao=87),
            Segmento(ordem=2, tipo=TipoSegmento.PERGUNTA, texto="Têm forma?", numero_questao=88),
            Segmento(
                ordem=3, tipo=TipoSegmento.RESPOSTA, texto="Para vós, não.", numero_questao=88
            ),
        ]
        ed.capitulos = [cap]
        voz = Voz(idioma="pt-BR", motor="falso", voz_id="n", papel=PapelVoz.NARRADOR)
        session.add_all([ed, voz])
        session.flush()
        ids = [s.id for s in cap.segmentos]
        marcas = [
            {"segmento_id": ids[0], "inicio_ms": 0, "fim_ms": 2500},
            {"segmento_id": ids[1], "inicio_ms": 3000, "fim_ms": 4500},
        ]
        if marcar:
            marcas.append({"segmento_id": ids[2], "inicio_ms": 5000, "fim_ms": 7000})
        session.add(
            FaixaAudio(
                capitulo_id=cap.id,
                voz_id=voz.id,
                url=f"{URL}/le/c1-v1.cent",
                duracao_ms=12000,
                marcacoes=marcas,
                formato=cifra.FORMATO,
                chave_cifrada=cifra.embrulhar(chave, ambiente["mestra"]),
            )
        )
        session.commit()
        return cap

    return criar


def test_caminho_da_amostra_sai_da_url_da_faixa(ambiente):
    assert amostra.chave_da_amostra(f"{URL}/le/pt-BR/e1/le-c001-v2.cent", 88) == (
        "le/pt-BR/e1/le-c001-v2.q88.m4a"
    )
    assert amostra.url_da_amostra(f"{URL}/le/c1-v1.cent", 88) == f"{URL}/le/c1-v1.q88.m4a"
    with pytest.raises(amostra.ErroAmostra):
        amostra.chave_da_amostra("https://outro.exemplo/x.cent", 1)


def test_corta_a_questao_da_faixa_cifrada_em_m4a_aberto(session, capitulo, ambiente):
    cap = capitulo()
    arm = ArmazenamentoLocal(ambiente["dir"], URL)
    url = amostra.gerar(session, cap.id, 88, arm)
    assert url == f"{URL}/le/c1-v1.q88.m4a"
    arquivo = ambiente["dir"] / "le" / "c1-v1.q88.m4a"
    assert arquivo.read_bytes()[4:8] == b"ftyp"  # aberto: o navegador toca
    # Questão de 3 s a 7 s, com a margem dos dois lados.
    assert abs(duracao_ms(arquivo) - (4000 + 2 * amostra.MARGEM_MS)) < 120
    # A faixa do capítulo continua só cifrada.
    assert sorted(p.name for p in arquivo.parent.iterdir()) == ["c1-v1.cent", "c1-v1.q88.m4a"]


def test_so_audio_revisado_vira_amostra(session, capitulo, ambiente):
    cap = capitulo(estado=EstadoCapitulo.AUDIO_GERADO)
    with pytest.raises(amostra.ErroAmostra, match="revisado"):
        amostra.gerar(session, cap.id, 88, ArmazenamentoLocal(ambiente["dir"], URL))


def test_questao_sem_marcacao_completa_e_recusada(session, capitulo, ambiente):
    cap = capitulo(marcar=False)
    arm = ArmazenamentoLocal(ambiente["dir"], URL)
    with pytest.raises(amostra.ErroAmostra, match="marcação"):
        amostra.gerar(session, cap.id, 88, arm)
    with pytest.raises(amostra.ErroAmostra, match="marcação"):
        amostra.gerar(session, cap.id, 999, arm)


def test_cli(session, capitulo, ambiente, capsys):
    cap = capitulo()
    assert amostra.main(["--capitulo", str(cap.id), "--questao", "88"]) == 0
    assert capsys.readouterr().out.strip() == f"{URL}/le/c1-v1.q88.m4a"
    assert amostra.main(["--capitulo", "999999", "--questao", "88"]) == 1
