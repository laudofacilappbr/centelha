"""Aplica o dicionário de pronúncia como SSML.

Cada entrada vira <sub alias> (grafia que o motor lê certo) ou <phoneme> (IPA).
Termos mais longos primeiro, para "Allan Kardec" ganhar de "Kardec".
"""

import re
from dataclasses import dataclass
from xml.sax.saxutils import escape, quoteattr


@dataclass(frozen=True)
class EntradaPronuncia:
    termo: str
    substituicao: str | None = None
    ipa: str | None = None


# Seed inicial pt-BR: nomes franceses frequentes nas obras. Grafias aproximadas,
# a validar no teste de escuta (#1) e no revisor de áudio do admin.
SEED_PT_BR: list[EntradaPronuncia] = [
    EntradaPronuncia("Allan Kardec", "Alan Kardéc"),
    EntradaPronuncia("Kardec", "Kardéc"),
    EntradaPronuncia("Rivail", "Rivái"),
    EntradaPronuncia("Fénelon", "Fenelôn"),
    EntradaPronuncia("Fenélon", "Fenelôn"),
    EntradaPronuncia("Lacordaire", "Lacordér"),
    EntradaPronuncia("Vianney", "Vianê"),
    EntradaPronuncia("Lamennais", "Lamenê"),
    EntradaPronuncia("Rousseau", "Russô"),
    EntradaPronuncia("Hahnemann", "Rânemann"),
    EntradaPronuncia("Delanne", "Delâne"),
    EntradaPronuncia("Léon Denis", "Leôn Denî"),
    EntradaPronuncia("Swedenborg", "Svédenborg"),
    EntradaPronuncia("Erasto", "Érasto"),
]

# Seed francês: o motor em francês já lê os nomes franceses; aqui só os estrangeiros
# que ele costuma ler à francesa. Também a validar na escuta.
SEED_FR: list[EntradaPronuncia] = [
    EntradaPronuncia("Hahnemann", "Ânemane"),
    EntradaPronuncia("Swedenborg", "Svédenborg"),
    EntradaPronuncia("Pestalozzi", "Pestalotsi"),
    EntradaPronuncia("Channing", "Tchanigne"),
]

SEEDS: dict[str, list[EntradaPronuncia]] = {"pt-BR": SEED_PT_BR, "fr": SEED_FR}


def seed(idioma: str) -> list[EntradaPronuncia]:
    """Seed do idioma exato ou, sem ele, do idioma base ("fr-FR" usa o de "fr")."""
    return SEEDS.get(idioma) or SEEDS.get(idioma.split("-")[0], [])


def _padrao(entradas: list[EntradaPronuncia]) -> re.Pattern[str] | None:
    termos = sorted({e.termo for e in entradas}, key=len, reverse=True)
    if not termos:
        return None
    return re.compile(r"(?<!\w)(" + "|".join(re.escape(t) for t in termos) + r")(?!\w)")


def aplicar(texto: str, entradas: list[EntradaPronuncia]) -> str:
    """Devolve o texto escapado para SSML, com o dicionário aplicado (sem <speak>)."""
    por_termo = {e.termo: e for e in entradas}
    padrao = _padrao(entradas)
    if padrao is None:
        return escape(texto)
    partes: list[str] = []
    pos = 0
    for m in padrao.finditer(texto):
        partes.append(escape(texto[pos : m.start()]))
        termo = m.group(0)
        entrada = por_termo[termo]
        if entrada.ipa:
            partes.append(
                f'<phoneme alphabet="ipa" ph={quoteattr(entrada.ipa)}>{escape(termo)}</phoneme>'
            )
        elif entrada.substituicao:
            partes.append(f"<sub alias={quoteattr(entrada.substituicao)}>{escape(termo)}</sub>")
        else:
            partes.append(escape(termo))
        pos = m.end()
    partes.append(escape(texto[pos:]))
    return "".join(partes)


def termos_usados(texto: str, entradas: list[EntradaPronuncia]) -> set[str]:
    """Termos do dicionário que aplicar() usaria neste texto.

    Mesmo padrão da síntese, com o termo mais longo primeiro: com "Allan Kardec" no
    dicionário, mudar "Kardec" não afeta o trecho "Allan Kardec". Saber quais capítulos
    regenerar por outra regra (um LIKE, por exemplo) regeneraria capítulos à toa ou
    deixaria de regenerar algum."""
    padrao = _padrao(entradas)
    if padrao is None:
        return set()
    return {m.group(0) for m in padrao.finditer(texto)}


def documento_ssml(trechos: list[str], idioma: str = "pt-BR", pausa_ms: int = 600) -> str:
    """Junta trechos já processados por aplicar() num <speak>, com pausa entre eles."""
    corpo = f'<break time="{pausa_ms}ms"/>'.join(trechos)
    return f'<speak version="1.0" xml:lang={quoteattr(idioma)}>{corpo}</speak>'


def aplicar_texto(texto: str, entradas: list[EntradaPronuncia]) -> str:
    """Versão em texto puro, para motores sem SSML: troca o termo pela grafia de
    substituição. IPA não tem equivalente em texto e fica de fora."""
    por_termo = {e.termo: e for e in entradas}
    padrao = _padrao(entradas)
    if padrao is None:
        return texto
    return padrao.sub(lambda m: por_termo[m.group(0)].substituicao or m.group(0), texto)
