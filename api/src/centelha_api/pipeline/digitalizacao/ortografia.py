"""Atualização ortográfica: do Formulário de 1943 (edições FEB antigas) ao Acordo de 1990.

Só grafia. Nenhuma palavra de Guillon Ribeiro é trocada por outra; quem decide
redação é o revisor, não o script. Cada troca vai para a lista devolvida, que vira o
relatório de revisão. Na dúvida, a regra não troca e marca para conferir.

Regras, na ordem:
1. Acento grave das derivadas (lei de 1971): sòmente → somente, cafèzinho → cafezinho.
   O "à" da crase fica (à, às, àquele, àquilo).
2. Acento diferencial e de timbre abolido em 1971: êle → ele, sôbre → sobre. Por lista:
   uma regra geral pegaria "você", "três" e "pôde", que continuam acentuados.
3. Trema (1990): freqüente → frequente, agüentar → aguentar. Nomes próprios ficam
   (Müller).
4. Ditongos abertos em paroxítonas (1990): idéia → ideia, heróico → heroico. Oxítonas
   e monossílabas ficam (papéis, heróis, dói).
5. "êem" e "ôo" (1990): crêem → creem, vôo → voo.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Troca:
    antes: str
    depois: str
    regra: str


# Regra 2: formas de 1943 com acento que caiu em 1971. Minúsculas; a maiúscula inicial
# é preservada na troca.
_DIFERENCIAIS = {
    p: p.translate(str.maketrans("êô", "eo"))
    for p in """
    êle êles êste êstes êsse êsses aquêle aquêles dêle dêles nêle nêles dêste dêstes
    nêste nêstes dêsse dêsses nêsse nêsses daquêle daquêles naquêle naquêles
    sôbre côr côres acôrdo acôrdos govêrno govêrnos têrmo têrmos êrro êrros mêdo
    mêdos fôsse fôssem fôr fôrem fôra fôram fôramos estêve tivêsse sêlo gôsto
    rôsto almôço colhêr pôsto pôstos tôrre tôrres fôrça fôrças môço môça cêrca
    emprêgo emprêgos sossêgo socôrro pêso pêsos cêdo fôgo fôgos jôgo jôgos
    nôvo nôvos ôvo ôvos pôço fôlha fôlhas bôlsa bôlsas mêsmo mêsma mêsmos
    mêsmas gêlo cabêlo cabêlos espêlho espêlhos
    """.split()
}
# "pôde" (passado), "pôr" (verbo), "têm" e "vêm" (plural) continuam com acento.

_GRAVE_DERIVADA = re.compile(r"\b\w*[àèìòù]\w*\b", re.IGNORECASE)
_CRASE = {"à", "às", "àquele", "àqueles", "àquela", "àquelas", "àquilo"}
_SEM_GRAVE = str.maketrans("àèìòùÀÈÌÒÙ", "aeiouAEIOU")

_TREMA = re.compile(r"\b\w*[üÜ]\w*\b")
_SEM_TREMA = str.maketrans("üÜ", "uU")

# idéia, platéia, heróico, jóia: ditongo aberto com sílaba depois dele. Sem sílaba
# depois (papéis, heróis, dói), a palavra é oxítona ou monossílaba e mantém o acento.
_DITONGO_ABERTO = re.compile(r"\b(\w*?)([éóÉÓ])(i\w+)\b")
_EEM_OO = re.compile(r"\b(\w*?)(êem|ôo)(s?)\b", re.IGNORECASE)

# Palavras com ê/ô que continuam assim hoje; o resto com ê/ô vai para "conferir".
_CIRCUNFLEXO_ATUAL = set(
    """
    você vocês três mês português portuguêses pôde pôr têm vêm detêm mantêm contêm
    obtêm retêm provêm convêm intervêm advêm lê vê crê dê pêssego ênfase gênero
    gêneros gênio gênios ciência ciências experiência consciência paciência
    existência essência fenômeno fenômenos econômico cômodo âmbito
    ômega cônjuge
    """.split()
)


def _manter_caixa(original: str, nova: str) -> str:
    if original.isupper() and len(original) > 1:
        return nova.upper()
    if original[:1].isupper():
        return nova[:1].upper() + nova[1:]
    return nova


def atualizar(texto: str) -> tuple[str, list[Troca]]:
    trocas: list[Troca] = []

    def anotar(antes: str, depois: str, regra: str) -> str:
        if antes != depois:
            trocas.append(Troca(antes, depois, regra))
        return depois

    def grave(m: re.Match[str]) -> str:
        p = m.group(0)
        if p.lower() in _CRASE:
            return p
        return anotar(p, p.translate(_SEM_GRAVE), "acento grave (1971)")

    def diferencial(m: re.Match[str]) -> str:
        p = m.group(0)
        nova = _DIFERENCIAIS.get(p.lower())
        if nova is None:
            return p
        return anotar(p, _manter_caixa(p, nova), "acento diferencial (1971)")

    def trema(m: re.Match[str]) -> str:
        p = m.group(0)
        # Nome próprio estrangeiro (Müller) mantém o trema; "Freqüente" no começo da
        # frase também tem maiúscula, então só se poupa palavra sem gü/qü.
        if p[:1].isupper() and not re.search(r"[gqGQ][üÜ]", p):
            return p
        return anotar(p, p.translate(_SEM_TREMA), "trema (1990)")

    def ditongo(m: re.Match[str]) -> str:
        p = m.group(0)
        if m.group(3).lower() == "is":
            return p
        sem = m.group(2).translate(str.maketrans("éóÉÓ", "eoEO"))
        return anotar(p, m.group(1) + sem + m.group(3), "ditongo aberto em paroxítona (1990)")

    def eem_oo(m: re.Match[str]) -> str:
        p = m.group(0)
        sem = m.group(2).translate(str.maketrans("êôÊÔ", "eoEO"))
        return anotar(p, m.group(1) + sem + m.group(3), "hiato êem/ôo (1990)")

    texto = _GRAVE_DERIVADA.sub(grave, texto)
    texto = re.sub(r"\b\w*[êôÊÔ]\w*\b", diferencial, texto)
    texto = _TREMA.sub(trema, texto)
    texto = _DITONGO_ABERTO.sub(ditongo, texto)
    texto = _EEM_OO.sub(eem_oo, texto)
    return texto, trocas


def a_conferir(texto: str) -> list[str]:
    """Palavras com ê/ô que nem a lista de 1943 nem a de grafia atual cobrem.

    Podem ser corretas hoje (ex.: "metrônomo") ou um diferencial antigo que a lista não
    tem; o revisor decide, e a palavra entra numa das listas."""
    vistas: dict[str, None] = {}
    for m in re.finditer(r"\b\w*[êôÊÔ]\w*\b", texto):
        p = m.group(0).lower()
        if p in _CIRCUNFLEXO_ATUAL or p in _DIFERENCIAIS:
            continue
        # Proparoxítonas e terminações que levam circunflexo pela regra geral atual.
        if re.search(r"[êô]\w*[aeiou]\w*[aeiou]s?$", p) or re.search(r"ências?$", p):
            continue
        vistas.setdefault(p, None)
    return list(vistas)
