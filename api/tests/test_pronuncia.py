import xml.etree.ElementTree as ET

from centelha_api.pipeline.pronuncia import (
    SEED_PT_BR,
    EntradaPronuncia,
    aplicar,
    documento_ssml,
)


def test_termo_mais_longo_ganha():
    saida = aplicar("Allan Kardec escreveu; Kardec revisou.", SEED_PT_BR)
    assert saida == (
        '<sub alias="Alan Kardéc">Allan Kardec</sub> escreveu; '
        '<sub alias="Kardéc">Kardec</sub> revisou.'
    )


def test_respeita_limite_de_palavra():
    entradas = [EntradaPronuncia("Erasto", "Érasto")]
    assert aplicar("Erastos e Erasto.", entradas) == 'Erastos e <sub alias="Érasto">Erasto</sub>.'


def test_ipa_tem_prioridade_e_escapa_aspas():
    entradas = [EntradaPronuncia("Kardec", substituicao="Kardéc", ipa='kaʁ"dɛk')]
    assert aplicar("Kardec", entradas) == (
        '<phoneme alphabet="ipa" ph=\'kaʁ"dɛk\'>Kardec</phoneme>'
    )


def test_escapa_xml_do_texto():
    assert aplicar("a < b & c", []) == "a &lt; b &amp; c"
    assert aplicar("Kardec & <cia>", SEED_PT_BR).endswith("&amp; &lt;cia&gt;")


def test_documento_e_xml_valido():
    trechos = [aplicar(t, SEED_PT_BR) for t in ("Pergunta a Kardec?", "Resposta & nota.")]
    doc = documento_ssml(trechos)
    raiz = ET.fromstring(doc)
    assert raiz.tag == "speak"
    assert raiz.attrib["{http://www.w3.org/XML/1998/namespace}lang"] == "pt-BR"
    assert len(raiz.findall("break")) == 1
