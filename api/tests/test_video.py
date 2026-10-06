import subprocess
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
    Publico,
    Segmento,
    TipoSegmento,
    Voz,
)
from centelha_api.pipeline import video, video_cli
from centelha_api.pipeline.audio import duracao_ms, ffmpeg_exe
from centelha_api.pipeline.video import TrechoLegenda, documento_ass, legendas


def test_legenda_segue_as_marcacoes_e_comeca_no_zero():
    """O vídeo começa no primeiro segmento do trecho; a legenda tem de começar junto,
    não no tempo do capítulo, senão aparece segundos depois da voz."""
    legs = legendas(
        [TrechoLegenda("Que é Deus?", 3820, 4960), TrechoLegenda("Inteligência.", 5460, 7220)]
    )
    assert [(x.texto, x.inicio_ms, x.fim_ms) for x in legs] == [
        ("Que é Deus?", 0, 1140),
        ("Inteligência.", 1640, 3400),
    ]


def test_segmento_longo_vira_blocos_contiguos():
    texto = " ".join(["palavra"] * 40)  # ~320 caracteres
    legs = legendas([TrechoLegenda(texto, 1000, 21000)])
    assert len(legs) > 1
    assert all(len(x.texto) <= video.BLOCO_MAX for x in legs)
    # Sem buraco nem sobreposição, e o último bloco termina com o segmento.
    assert all(a.fim_ms == b.inicio_ms for a, b in zip(legs, legs[1:], strict=False))
    assert (legs[0].inicio_ms, legs[-1].fim_ms) == (0, 20000)
    assert " ".join(x.texto for x in legs) == texto


def test_texto_nao_vira_comando_de_estilo():
    """Chave no ASS abre tag ({\\pos...}); texto de entrada não pode reposicionar nada."""
    ass = documento_ass(
        legendas([TrechoLegenda(r"a {\pos(0,0)} b", 0, 1000)]), "Ref {x}", None, 1000
    )
    assert "{" not in ass.split("[Events]")[1]


def test_sem_chamada_nao_ha_linha_de_chamada():
    com = documento_ass([], "Ref", "Ouça no app", 1000)
    sem = documento_ass([], "Ref", None, 1000)
    assert "Chamada,Ouça no app" in com
    assert ",Chamada," not in sem


@pytest.fixture
def audio_capitulo(tmp_path):
    """12 s de tom: faz o papel do áudio do capítulo."""
    destino = tmp_path / "capitulo.m4a"
    subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=12", "-c:a", "aac", str(destino)],
        check=True,
    )  # fmt: skip
    return destino


def test_monta_mp4_vertical_com_o_trecho_e_srt(audio_capitulo, tmp_path):
    trechos = [TrechoLegenda("Pergunta?", 3000, 4000), TrechoLegenda("Resposta longa.", 4500, 7000)]
    mp4 = video.montar_video(
        audio_capitulo,
        trechos,
        "O Livro dos Espíritos, questão 88",
        "Ouça no app",
        tmp_path / "saida" / "le-88",
    )
    assert mp4.exists() and mp4.suffix == ".mp4"
    # Duração = trecho + cauda, não o capítulo inteiro (12 s).
    assert abs(duracao_ms(mp4) - (4000 + video.CAUDA_MS)) < 150
    sonda = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(mp4)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stderr
    assert "1080x1920" in sonda and "Audio: aac" in sonda
    srt = mp4.with_suffix(".srt").read_text(encoding="utf-8")
    assert srt.startswith("1\n00:00:00,000 --> 00:00:01,000\nPergunta?")


def test_trecho_longo_demais_recusado(audio_capitulo, tmp_path):
    with pytest.raises(video.ErroVideo, match="passa de"):
        video.montar_video(
            audio_capitulo, [TrechoLegenda("x", 0, 70_000)], "Ref", None, tmp_path / "v"
        )


# --- CLI ----------------------------------------------------------------------


@pytest.fixture
def capitulo_revisado(session, audio_capitulo, tmp_path, monkeypatch):
    monkeypatch.setenv("CENTELHA_AUDIO_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("CENTELHA_AUDIO_URL_BASE", "https://audio.exemplo")
    get_settings.cache_clear()
    (tmp_path / "audio" / "le").mkdir(parents=True)
    audio_capitulo.replace(tmp_path / "audio" / "le" / "c1.m4a")

    def criar(publico=Publico.ADULTO, estado=EstadoCapitulo.AUDIO_REVISADO):
        obra = Obra(
            slug=f"le-{publico}",
            autor="Allan Kardec",
            titulo_original="LE",
            idioma_original="fr",
            sigla=f"L{publico.value[0]}",
        )
        ed = Edicao(
            obra=obra, idioma="pt-BR", titulo="O Livro dos Espíritos", fonte="t", publico=publico
        )
        cap = Capitulo(ordem=1, titulo="I", referencia_canonica="LE-C1", estado=estado)
        cap.segmentos = [
            Segmento(
                ordem=1, tipo=TipoSegmento.PERGUNTA, texto="Que é o Espírito?", numero_questao=87
            ),
            Segmento(ordem=2, tipo=TipoSegmento.PERGUNTA, texto="Têm forma?", numero_questao=88),
            Segmento(
                ordem=3, tipo=TipoSegmento.RESPOSTA, texto="Para vós, não.", numero_questao=88
            ),
        ]
        ed.capitulos = [cap]
        voz = Voz(idioma="pt-BR", motor="falso", voz_id="n", papel=PapelVoz.NARRADOR)
        session.add_all([ed, voz])
        session.flush()
        ids = [x.id for x in cap.segmentos]
        session.add(
            FaixaAudio(
                capitulo_id=cap.id,
                voz_id=voz.id,
                url="https://audio.exemplo/le/c1.m4a",
                duracao_ms=12000,
                marcacoes=[
                    {"segmento_id": ids[0], "inicio_ms": 0, "fim_ms": 2000},
                    {"segmento_id": ids[1], "inicio_ms": 3000, "fim_ms": 4000},
                    {"segmento_id": ids[2], "inicio_ms": 4500, "fim_ms": 6000},
                ],
            )
        )
        session.commit()
        return cap

    yield criar
    get_settings.cache_clear()


def _capturar(monkeypatch):
    chamadas = {}

    def falso(audio, trechos, referencia, chamada, destino, fundo=None):
        chamadas.update(audio=audio, trechos=trechos, referencia=referencia, chamada=chamada)
        return Path(destino).with_suffix(".mp4")

    monkeypatch.setattr(video_cli, "montar_video", falso)
    return chamadas


def test_cli_monta_so_a_questao_pedida(capitulo_revisado, monkeypatch, tmp_path):
    cap = capitulo_revisado()
    c = _capturar(monkeypatch)
    assert (
        video_cli.main(
            ["--capitulo", str(cap.id), "--questao", "88", "--saida", str(tmp_path / "v")]
        )
        == 0
    )
    assert [t.texto for t in c["trechos"]] == ["Têm forma?", "Para vós, não."]
    assert c["referencia"] == "O Livro dos Espíritos, questão 88"
    assert c["chamada"] == video_cli.CHAMADA
    assert c["audio"].name == "c1.m4a"  # do disco, sem baixar


def test_cli_infantil_nunca_tem_chamada_para_o_app(capitulo_revisado, monkeypatch, tmp_path):
    """Regra do projeto: perfil infantil sem link nem chamada externa, mesmo sem a flag."""
    cap = capitulo_revisado(publico=Publico.INFANTIL)
    c = _capturar(monkeypatch)
    assert (
        video_cli.main(
            ["--capitulo", str(cap.id), "--segmentos", "2-3", "--saida", str(tmp_path / "v")]
        )
        == 0
    )
    assert c["chamada"] is None


def test_cli_recusa_audio_nao_revisado(capitulo_revisado, monkeypatch, tmp_path, capsys):
    cap = capitulo_revisado(estado=EstadoCapitulo.AUDIO_GERADO)
    c = _capturar(monkeypatch)
    assert (
        video_cli.main(
            ["--capitulo", str(cap.id), "--questao", "88", "--saida", str(tmp_path / "v")]
        )
        == 1
    )
    assert "revisado" in capsys.readouterr().err
    assert c == {}
