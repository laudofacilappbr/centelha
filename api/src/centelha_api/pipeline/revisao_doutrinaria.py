"""Primeira revisão doutrinária e de linguagem das adaptações, feita por IA (#98, #76 D).

    python -m centelha_api.pipeline.revisao_doutrinaria montar --capitulo 42 --saida par.json
    python -m centelha_api.pipeline.revisao_doutrinaria relatorio par.json avaliacao.json \\
        --saida revisao.md

`montar` põe lado a lado o capítulo adaptado (juvenil ou infantil) e o do original da
mesma obra, trecho a trecho: questões pelo número, subquestão e tipo; o resto do capítulo
junto. Já faz o que não precisa de leitura: link e pedido de apoio no infantil, rótulo
"adaptado de", atribuição (resposta que no original é comentário), trechos sem par e
frases longas para o público. A leitura de cada par é da IA, pela skill
`revisao-doutrinaria`, que grava a avaliação em JSON; `relatorio` junta as duas.

Nada aqui aprova: a transição "aprovar_doutrina" no admin continua sendo de uma pessoa.
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

NIVEIS = ("ok", "atencao", "bloqueio")
_GRAVIDADE = {n: i for i, n in enumerate(NIVEIS)}

# Frase média acima disso pede atenção (palavras por frase). Referência de leitura
# fácil: até ~15 palavras para crianças, ~20 para adolescentes.
LIMITE_FRASE = {"infantil": 15, "juvenil": 22}
_LINK = re.compile(r"https?://|www\.|\.com\b|\.org\b|\.br\b", re.IGNORECASE)
# Perfil infantil: nada de pedido de dinheiro nem chamada para fora (regra do repositório).
# Verbos com as flexões de pedido ("apoiem", "apoiarem"), sem pegar "apoio" e "baixinho",
# comuns em texto para criança.
_CHAMADA = re.compile(
    r"\b(apoi(?:e|em|ar|arem|ando)|contribu(?:a|am|ir|indo)|doe|doem|doar|doa[çc](?:[ãa]o|[õo]es)"
    r"|pix|assin(?:e|em|ar)|compr(?:e|em)|baix(?:e|em) o app|acess(?:e|em)|cliqu(?:e|em)|site"
    r"|instagram|youtube|whatsapp|tiktok|soutien|faites un don|donate|download)\b",
    re.IGNORECASE,
)
_ROTULO = re.compile(r"adapta|adapté|adaptación|adapted", re.IGNORECASE)
_FRASE = re.compile(r"[^.!?…]+[.!?…]*")


@dataclass
class Seg:
    """O que a revisão precisa de um segmento (do banco ou de teste)."""

    tipo: str
    texto: str
    numero_questao: int | None = None
    subquestao: str | None = None


@dataclass
class Apontamento:
    nivel: str
    motivo: str
    trecho: str = ""


@dataclass
class Trecho:
    id: str
    original: str
    adaptacao: str
    automatico: list[Apontamento] = field(default_factory=list)


@dataclass
class Par:
    obra: str
    capitulo: str
    publico: str
    original: str
    adaptacao: str
    trechos: list[Trecho] = field(default_factory=list)
    geral: list[Apontamento] = field(default_factory=list)
    # Id do capítulo adaptado no banco, para anexar o relatório (--anexar).
    capitulo_id: int | None = None


def _chave(s: Seg) -> str:
    if s.numero_questao is None:
        return "capítulo · texto"
    return f"{s.numero_questao}{s.subquestao or ''} · {s.tipo}"


def _agrupar(segmentos: list[Seg]) -> dict[str, str]:
    """Chave → texto, na ordem; títulos ficam de fora (cada edição escreve o seu)."""
    r: dict[str, list[str]] = {}
    for s in segmentos:
        if s.tipo == "titulo":
            continue
        r.setdefault(_chave(s), []).append(s.texto)
    return {k: "\n".join(v) for k, v in r.items()}


def _linguagem(texto: str, publico: str) -> list[Apontamento]:
    limite = LIMITE_FRASE.get(publico)
    if not limite or not texto.strip():
        return []
    frases = [f for f in _FRASE.findall(texto) if f.strip()]
    tamanhos = [len(f.split()) for f in frases]
    r = []
    longas = [f.strip() for f, n in zip(frases, tamanhos, strict=True) if n > limite * 2]
    media = sum(tamanhos) / len(tamanhos)
    if media > limite:
        r.append(
            Apontamento(
                "atencao", f"frases longas para o público {publico} (média {media:.0f} palavras)"
            )
        )
    for f in longas[:3]:
        r.append(Apontamento("atencao", "frase muito longa", f[:160]))
    return r


def montar_par(
    original: list[Seg],
    adaptacao: list[Seg],
    *,
    obra: str,
    capitulo: str,
    publico: str,
    titulo_original: str,
    titulo_adaptacao: str,
    fonte_adaptacao: str = "",
) -> Par:
    par = Par(obra, capitulo, publico, titulo_original, titulo_adaptacao)
    if not _ROTULO.search(f"{titulo_adaptacao} {fonte_adaptacao}"):
        par.geral.append(
            Apontamento(
                "bloqueio",
                "a edição não se apresenta como adaptação: título ou fonte precisam dizer "
                '"adaptado de…" (dossiê da #3, pergunta 5)',
            )
        )
    go, ga = _agrupar(original), _agrupar(adaptacao)
    for chave, texto in ga.items():
        trecho = Trecho(chave, go.get(chave, ""), texto)
        if chave not in go:
            n_sub, _, tipo = chave.partition(" · ")
            if tipo == "resposta" and f"{n_sub} · comentario" in go:
                trecho.original = go[f"{n_sub} · comentario"]
                trecho.automatico.append(
                    Apontamento(
                        "bloqueio",
                        "atribuição: vira resposta dos Espíritos o que no original é "
                        "comentário de Kardec",
                    )
                )
            else:
                trecho.automatico.append(
                    Apontamento("atencao", "trecho sem correspondente no original")
                )
        if publico == "infantil":
            for regex, motivo in (
                (_LINK, "link no perfil infantil"),
                (_CHAMADA, "chamada externa ou pedido de apoio no perfil infantil"),
            ):
                if m := regex.search(texto):
                    inicio = max(0, m.start() - 40)
                    trecho.automatico.append(
                        Apontamento("bloqueio", motivo, texto[inicio : m.end() + 40])
                    )
        trecho.automatico += _linguagem(texto, publico)
        par.trechos.append(trecho)
    faltando = [k for k in go if k not in ga and k != "capítulo · texto"]
    perguntas = [k for k in faltando if k.endswith(" · pergunta")]
    if perguntas:
        par.geral.append(
            Apontamento(
                "atencao",
                "questões do original fora da adaptação (pode ser escolha editorial; "
                "confira se nada essencial ficou de fora)",
                ", ".join(k.split(" · ")[0] for k in perguntas),
            )
        )
    return par


# --- Avaliação da IA e relatório -----------------------------------------------------


class AvaliacaoInvalida(ValueError):
    pass


def ler_avaliacao(par: Par, dados: list[dict]) -> dict[str, Apontamento]:
    """Um item por trecho, com nivel em ok/atencao/bloqueio e motivo; sem lacunas."""
    ids = {t.id for t in par.trechos}
    r: dict[str, Apontamento] = {}
    for item in dados:
        tid, nivel = item.get("id"), item.get("nivel")
        if tid not in ids:
            raise AvaliacaoInvalida(f"trecho desconhecido na avaliação: {tid!r}")
        if nivel not in NIVEIS:
            raise AvaliacaoInvalida(f"{tid}: nivel {nivel!r} (use {', '.join(NIVEIS)})")
        if nivel != "ok" and not str(item.get("motivo", "")).strip():
            raise AvaliacaoInvalida(f"{tid}: {nivel} sem motivo")
        r[tid] = Apontamento(nivel, str(item.get("motivo", "")), str(item.get("trecho", "")))
    if faltam := sorted(ids - r.keys()):
        raise AvaliacaoInvalida(f"trechos sem avaliação: {', '.join(faltam)}")
    return r


def _celula(t: str) -> str:
    return t.replace("|", "\\|").replace("\n", " ")


def relatorio(par: Par, avaliacao: dict[str, Apontamento]) -> tuple[str, dict[str, int]]:
    """Markdown e a contagem por nível (trechos, mais os bloqueios da edição)."""
    linhas_por_nivel: dict[str, list[str]] = {"bloqueio": [], "atencao": []}
    sem_apontamento: list[str] = []
    for t in par.trechos:
        todos = [avaliacao[t.id], *t.automatico]
        pior = max(todos, key=lambda a: _GRAVIDADE[a.nivel]).nivel
        if pior == "ok":
            sem_apontamento.append(t.id)
            continue
        motivos = "; ".join(
            f"{a.motivo}" + (f" («{a.trecho}»)" if a.trecho else "")
            for a in todos
            if a.nivel != "ok"
        )
        linhas_por_nivel[pior].append(
            f"| {_celula(t.id)} | {_celula(motivos)} | {_celula(t.adaptacao[:200])} |"
        )
    contagem = {
        "bloqueio": len(linhas_por_nivel["bloqueio"])
        + sum(a.nivel == "bloqueio" for a in par.geral),
        "atencao": len(linhas_por_nivel["atencao"]),
        "ok": len(sem_apontamento),
    }
    saida = [
        f"# Revisão doutrinária (IA): {par.adaptacao}, {par.capitulo}",
        "",
        "Primeira leitura feita por IA. **Não aprova nada**: a aprovação da doutrina é no "
        "admin, por uma pessoa (#76).",
        "",
        f"- Público: {par.publico}",
        f"- Original comparado: {par.original}",
        f"- Trechos: {len(par.trechos)} · bloqueio: {contagem['bloqueio']} · atenção: "
        f"{contagem['atencao']} · ok: {contagem['ok']}",
        "",
    ]
    if par.geral:
        saida += ["## Edição", ""]
        saida += [
            f"- **{a.nivel}**: {a.motivo}" + (f" ({a.trecho})" if a.trecho else "")
            for a in par.geral
        ]
        saida.append("")
    for nivel, titulo in (("bloqueio", "Bloqueios"), ("atencao", "Atenção")):
        saida += [f"## {titulo} ({len(linhas_por_nivel[nivel])})", ""]
        if linhas_por_nivel[nivel]:
            saida += [
                "| Trecho | Motivo | Adaptação |",
                "| --- | --- | --- |",
                *linhas_por_nivel[nivel],
                "",
            ]
        else:
            saida += ["Nenhum.", ""]
    saida += [
        f"## Sem apontamento ({len(sem_apontamento)})",
        "",
        ", ".join(sem_apontamento) or "Nenhum.",
        "",
    ]
    return "\n".join(saida), contagem


def _par_de_json(dados: dict) -> Par:
    par = Par(**{k: dados[k] for k in ("obra", "capitulo", "publico", "original", "adaptacao")})
    par.capitulo_id = dados.get("capitulo_id")
    par.geral = [Apontamento(**a) for a in dados.get("geral", [])]
    par.trechos = [
        Trecho(
            t["id"],
            t["original"],
            t["adaptacao"],
            [Apontamento(**a) for a in t.get("automatico", [])],
        )
        for t in dados["trechos"]
    ]
    return par


# --- Linha de comando ----------------------------------------------------------------


def _montar_do_banco(capitulo_id: int, original_edicao_id: int | None) -> Par:
    from sqlalchemy import select

    from ..db import SessionLocal
    from ..models import Capitulo, Edicao, Publico

    with SessionLocal() as s:
        cap = s.get(Capitulo, capitulo_id)
        if cap is None:
            raise ValueError("capítulo não encontrado")
        ed = cap.edicao
        if ed.publico == Publico.ADULTO:
            raise ValueError(
                "o capítulo é de edição adulta: a revisão doutrinária é das adaptações"
            )
        if original_edicao_id:
            original = s.get(Edicao, original_edicao_id)
        else:
            # O original da mesma obra no mesmo idioma (Guillon Ribeiro para pt-BR).
            original = s.scalar(
                select(Edicao)
                .where(
                    Edicao.obra_id == ed.obra_id,
                    Edicao.publico == Publico.ADULTO,
                    Edicao.idioma == ed.idioma,
                )
                .order_by(Edicao.id)
            )
        if original is None:
            raise ValueError("sem edição original; use --original-edicao")
        cap_original = next(
            (c for c in original.capitulos if c.referencia_canonica == cap.referencia_canonica),
            None,
        )
        if cap_original is None:
            raise ValueError(f"o original não tem o capítulo {cap.referencia_canonica}")

        def segs(c) -> list[Seg]:
            return [Seg(x.tipo.value, x.texto, x.numero_questao, x.subquestao) for x in c.segmentos]

        par = montar_par(
            segs(cap_original),
            segs(cap),
            obra=ed.obra.slug,
            capitulo=cap.referencia_canonica,
            publico=ed.publico.value,
            titulo_original=f"{original.titulo} ({original.idioma})",
            titulo_adaptacao=ed.titulo,
            fonte_adaptacao=ed.fonte,
        )
        par.capitulo_id = cap.id
        return par


def anexar(session, capitulo, relatorio_md: str, contagem: dict[str, int], usuario=None, ip=None):
    """Guarda o relatório no capítulo adaptado, para quem aprova no admin (#98).
    ValueError se o capítulo não é de adaptação."""
    from ..dominio import contas
    from ..models import Publico, RevisaoIA

    if capitulo.edicao.publico == Publico.ADULTO:
        raise ValueError("o capítulo é de edição adulta: a revisão doutrinária é das adaptações")
    revisao = RevisaoIA(
        capitulo_id=capitulo.id,
        relatorio=relatorio_md,
        bloqueios=contagem["bloqueio"],
        atencoes=contagem["atencao"],
        ok=contagem["ok"],
        usuario_id=usuario.id if usuario else None,
    )
    session.add(revisao)
    session.flush()
    contas.registrar(
        session, "revisao_ia_anexada", usuario, "capitulo", capitulo.id, ip,
        revisao_id=revisao.id, bloqueios=revisao.bloqueios, atencoes=revisao.atencoes,
    )  # fmt: skip
    return revisao


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="revisao_doutrinaria", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="comando", required=True)
    m = sub.add_parser("montar", help="par original × adaptação de um capítulo, em JSON")
    m.add_argument("--capitulo", type=int, required=True, help="id do capítulo adaptado")
    m.add_argument("--original-edicao", type=int, help="padrão: edição adulta do mesmo idioma")
    m.add_argument("--saida", type=Path, required=True)
    r = sub.add_parser("relatorio", help="junta o par e a avaliação da IA em Markdown")
    r.add_argument("par", type=Path)
    r.add_argument("avaliacao", type=Path)
    r.add_argument("--saida", type=Path, required=True)
    r.add_argument(
        "--anexar",
        action="store_true",
        help="grava o relatório no capítulo, no banco, para quem aprova no admin",
    )
    a = p.parse_args(argv)

    if a.comando == "montar":
        try:
            par = _montar_do_banco(a.capitulo, a.original_edicao)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
        a.saida.write_text(json.dumps(asdict(par), ensure_ascii=False, indent=2), encoding="utf-8")
        automaticos = sum(len(t.automatico) for t in par.trechos) + len(par.geral)
        print(
            f"{len(par.trechos)} trechos; {automaticos} apontamentos automáticos; par em {a.saida}"
        )
        return 0

    try:
        par = _par_de_json(json.loads(a.par.read_text(encoding="utf-8")))
        avaliacao = ler_avaliacao(par, json.loads(a.avaliacao.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError) as e:
        print(e, file=sys.stderr)
        return 1
    texto, contagem = relatorio(par, avaliacao)
    a.saida.write_text(texto, encoding="utf-8")
    if a.anexar:
        if par.capitulo_id is None:
            print("o par não tem capitulo_id: monte-o de novo com 'montar'", file=sys.stderr)
            return 1
        from ..db import SessionLocal
        from ..models import Capitulo

        with SessionLocal() as s:
            capitulo = s.get(Capitulo, par.capitulo_id)
            if capitulo is None:
                print("capítulo não encontrado", file=sys.stderr)
                return 1
            try:
                revisao = anexar(s, capitulo, texto, contagem)
            except ValueError as e:
                print(e, file=sys.stderr)
                return 1
            s.commit()
            print(f"relatório anexado ao capítulo {capitulo.id} (revisão {revisao.id})")
    print(
        f"bloqueio: {contagem['bloqueio']} · atenção: {contagem['atencao']} · "
        f"ok: {contagem['ok']}; relatório em {a.saida}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
