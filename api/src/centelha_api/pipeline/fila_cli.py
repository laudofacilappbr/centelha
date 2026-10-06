"""Operação do pipeline de áudio pela linha de comando (até o admin ter tela para isso).

    python -m centelha_api.pipeline.fila_cli vozes-criar --idioma pt-BR --motor azure \\
        --voz-id pt-BR-AntonioNeural --papel narrador
    (francês: --idioma fr-FR com fr-FR-HenriNeural, fr-FR-Neural2-B ou fr_FR-siwis-medium;
    a voz precisa ter o mesmo idioma da edição)
    python -m centelha_api.pipeline.fila_cli pronuncias-seed [--idioma fr-FR]
    python -m centelha_api.pipeline.fila_cli enfileirar --edicao 1 --motor azure \\
        --narrador 1 [--pergunta 2 --resposta 3] [--capitulo 5]
    python -m centelha_api.pipeline.fila_cli status [--edicao 1]
"""

import argparse
import sys

from sqlalchemy import func, select

from ..db import SessionLocal
from ..models import Capitulo, EstadoJob, JobAudio, PapelVoz, Pronuncia, Voz
from .jobs import ESTADOS_QUE_GERAM, JobRecusado, enfileirar
from .pronuncia import seed


def _vozes_criar(s, a):
    voz = Voz(idioma=a.idioma, motor=a.motor, voz_id=a.voz_id, papel=PapelVoz(a.papel))
    s.add(voz)
    s.commit()
    print(f"voz {voz.id}: {voz.motor}:{voz.voz_id} ({voz.papel.value}, {voz.idioma})")


def _pronuncias_seed(s, a):
    existentes = set(s.scalars(select(Pronuncia.termo).where(Pronuncia.idioma == a.idioma)))
    novas = [e for e in seed(a.idioma) if e.termo not in existentes]
    s.add_all(
        Pronuncia(idioma=a.idioma, termo=e.termo, substituicao=e.substituicao, ipa=e.ipa)
        for e in novas
    )
    s.commit()
    print(f"{len(novas)} termos novos; {len(existentes)} já existiam e ficaram como estavam")


def _enfileirar(s, a):
    filtro = Capitulo.edicao_id == a.edicao
    if a.capitulo:
        filtro &= Capitulo.id == a.capitulo
    capitulos = s.scalars(select(Capitulo).where(filtro).order_by(Capitulo.ordem)).all()
    vozes = {i: s.get(Voz, i) for i in (a.narrador, a.pergunta, a.resposta) if i}
    if a.narrador not in vozes or None in vozes.values():
        print("voz inexistente", file=sys.stderr)
        return 1
    ok = pulados = 0
    for cap in capitulos:
        if cap.estado not in ESTADOS_QUE_GERAM:
            pulados += 1
            continue
        try:
            enfileirar(
                s,
                cap,
                a.motor,
                vozes[a.narrador],
                vozes.get(a.pergunta),
                vozes.get(a.resposta),
            )
            s.commit()
            ok += 1
        except JobRecusado as e:
            print(f"capítulo {cap.ordem}: {e}", file=sys.stderr)
    print(f"{ok} capítulos na fila; {pulados} pulados por não terem texto revisado")
    return 0


def _status(s, a):
    consulta = select(
        JobAudio.estado, func.count(), func.coalesce(func.sum(JobAudio.caracteres), 0)
    )
    if a.edicao:
        consulta = consulta.join(Capitulo).where(Capitulo.edicao_id == a.edicao)
    linhas = s.execute(consulta.group_by(JobAudio.estado)).all()
    for estado, n, caracteres in linhas:
        print(f"{estado.value:<11} {n:>5}  caracteres: {caracteres}")
    falhas = s.scalars(
        select(JobAudio).where(JobAudio.estado == EstadoJob.FALHOU).order_by(JobAudio.id)
    ).all()
    for j in falhas[-10:]:
        print(f"  falhou job {j.id} capítulo {j.capitulo_id}: {(j.erro or '')[:120]}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)

    v = sub.add_parser("vozes-criar")
    v.add_argument("--idioma", required=True)
    v.add_argument("--motor", required=True)
    v.add_argument("--voz-id", required=True)
    v.add_argument("--papel", choices=[x.value for x in PapelVoz], default="narrador")

    ps = sub.add_parser("pronuncias-seed")
    # O mesmo idioma da edição: o dicionário é lido por igualdade (pt-BR, fr-FR...).
    ps.add_argument("--idioma", default="pt-BR")

    e = sub.add_parser("enfileirar")
    e.add_argument("--edicao", type=int, required=True)
    e.add_argument("--capitulo", type=int)
    e.add_argument("--motor", required=True)
    e.add_argument("--narrador", type=int, required=True)
    e.add_argument("--pergunta", type=int)
    e.add_argument("--resposta", type=int)

    st = sub.add_parser("status")
    st.add_argument("--edicao", type=int)

    a = p.parse_args(argv)
    acoes = {
        "vozes-criar": _vozes_criar,
        "pronuncias-seed": _pronuncias_seed,
        "enfileirar": _enfileirar,
        "status": _status,
    }
    with SessionLocal() as s:
        return acoes[a.comando](s, a) or 0


if __name__ == "__main__":
    sys.exit(main())
