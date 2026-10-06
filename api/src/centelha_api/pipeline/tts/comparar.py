"""Gera o mesmo trecho em vários motores para o teste de escuta (#1, #77).

    python -m centelha_api.pipeline.tts.comparar trecho.txt --saida amostras \\
        --motor azure:pt-BR-AntonioNeural \\
        --motor google:pt-BR-Neural2-B \\
        --motor piper:pt_BR-faber-medium \\
        [--perfil perguntas --voz-pergunta azure:pt-BR-FranciscaNeural]
        [--idioma fr-FR]   # trecho em francês, com vozes fr-FR-*
        [--modo ambos]     # por segmento e em bloco, para comparar a entonação

Cada motor vira um .m4a na pasta de saída, e resumo.json traz caracteres, duração e
tempo de síntese, para comparar custo junto com a escuta. Motor sem credencial é
pulado com o motivo, sem derrubar os outros. Com --modo ambos, cada motor gera
"-segmento.m4a" e "-bloco.m4a"; motor sem marcadores não gera o de bloco.
"""

import argparse
import json
import sys
from pathlib import Path

from ..ingestao.estrutura import estruturar
from ..ingestao.leitores import ler
from ..pronuncia import seed
from .gerar import MODOS, SegmentoParaVoz, Vozes, gerar_capitulo
from .motores import ErroTTS, aceita_marcas, motor


def _par(valor: str) -> tuple[str, str]:
    nome, _, voz = valor.partition(":")
    if not voz:
        raise argparse.ArgumentTypeError("use motor:voz, ex.: azure:pt-BR-AntonioNeural")
    return nome, voz


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arquivo", type=Path)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--motor", type=_par, action="append", required=True)
    parser.add_argument("--voz-pergunta", type=_par, action="append", default=[])
    parser.add_argument("--voz-resposta", type=_par, action="append", default=[])
    parser.add_argument("--perfil", choices=["generico", "perguntas"], default="generico")
    parser.add_argument("--idioma", default="pt-BR")
    parser.add_argument("--modo", choices=[*MODOS, "ambos"], default="segmento")
    args = parser.parse_args(argv)

    segmentos = [
        SegmentoParaVoz(i, s.tipo, s.texto)
        for i, s in enumerate(
            (s for c in estruturar(ler(args.arquivo), args.perfil) for s in c.segmentos), 1
        )
    ]
    extras_p = dict(args.voz_pergunta)
    extras_r = dict(args.voz_resposta)
    modos = list(MODOS) if args.modo == "ambos" else [args.modo]
    args.saida.mkdir(parents=True, exist_ok=True)
    resumo = {}
    for nome, voz in args.motor:
        vozes = Vozes(voz, extras_p.get(nome), extras_r.get(nome))
        for modo in modos:
            chave = f"{nome}:{voz}" if len(modos) == 1 else f"{nome}:{voz}:{modo}"
            try:
                m = motor(nome)
                if modo == "bloco" and not aceita_marcas(m):
                    raise ErroTTS(f"{nome} não devolve marcadores; sem modo bloco")
                destino = args.saida / (
                    f"{nome}-{voz}.m4a" if len(modos) == 1 else f"{nome}-{voz}-{modo}.m4a"
                )
                r = gerar_capitulo(
                    segmentos, m, vozes, seed(args.idioma), destino, args.idioma, modo=modo
                )
            except ErroTTS as e:
                resumo[chave] = {"erro": str(e)}
                print(f"{chave}: {e}", file=sys.stderr)
                continue
            resumo[chave] = {
                "arquivo": destino.name,
                "modo": r.modo,
                "pedidos": r.pedidos,
                "caracteres": r.caracteres,
                "duracao_s": round(r.faixa.duracao_ms / 1000, 1),
                "segundos_sintese": round(r.segundos_sintese, 1),
            }
    (args.saida / "resumo.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0 if any("arquivo" in v for v in resumo.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
