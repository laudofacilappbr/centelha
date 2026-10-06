import os

import pytest

from centelha_api.pipeline import cifra
from centelha_api.pipeline.cifra import Cabecalho, ErroCifra

CHAVE = bytes(range(32))
BLOCO = 1024


@pytest.mark.parametrize("tamanho", [0, 1, BLOCO, BLOCO + 1, 3 * BLOCO, 5 * BLOCO + 17])
def test_ida_e_volta(tamanho):
    claro = os.urandom(tamanho)
    cifrado = cifra.cifrar(claro, CHAVE, BLOCO)
    assert cifra.decifrar(cifrado, CHAVE) == claro
    # Nada do áudio aparece em claro no arquivo.
    if tamanho >= 16:
        assert claro[:16] not in cifrado


def test_cabecalho_e_tamanho_do_arquivo():
    cifrado = cifra.cifrar(b"x" * (2 * BLOCO + 10), CHAVE, BLOCO)
    cab = Cabecalho.ler(cifrado)
    assert cifrado[:5] == b"CENT\x01"
    assert (cab.tamanho_bloco, cab.tamanho_claro, cab.blocos) == (BLOCO, 2 * BLOCO + 10, 3)
    assert len(cifrado) == 32 + 3 * 16 + 2 * BLOCO + 10


def test_decifra_um_bloco_do_meio_sem_ler_o_resto():
    claro = os.urandom(4 * BLOCO + 100)
    cifrado = cifra.cifrar(claro, CHAVE, BLOCO)
    cab = Cabecalho.ler(cifrado[:32])
    inicio, n = cifra.posicao_bloco(cab, 2)
    assert (
        cifra.decifrar_bloco(cab, 2, cifrado[inicio : inicio + n], CHAVE)
        == claro[2 * BLOCO : 3 * BLOCO]
    )
    inicio, n = cifra.posicao_bloco(cab, 4)
    assert n == 100 + 16
    assert cifra.decifrar_bloco(cab, 4, cifrado[inicio : inicio + n], CHAVE) == claro[-100:]


def test_cada_arquivo_tem_nonce_proprio():
    assert cifra.cifrar(b"igual", CHAVE)[32:] != cifra.cifrar(b"igual", CHAVE)[32:]


def test_chave_errada():
    cifrado = cifra.cifrar(b"audio", CHAVE)
    with pytest.raises(ErroCifra, match="não confere"):
        cifra.decifrar(cifrado, cifra.nova_chave())


def test_byte_alterado():
    cifrado = bytearray(cifra.cifrar(os.urandom(3 * BLOCO), CHAVE, BLOCO))
    cifrado[32 + BLOCO + 20] ^= 1
    with pytest.raises(ErroCifra, match="bloco 1"):
        cifra.decifrar(bytes(cifrado), CHAVE)


def test_blocos_trocados_de_lugar():
    cifrado = cifra.cifrar(os.urandom(3 * BLOCO), CHAVE, BLOCO)
    cab = Cabecalho.ler(cifrado)
    (a, n), (b, _) = cifra.posicao_bloco(cab, 0), cifra.posicao_bloco(cab, 1)
    trocado = cifrado[:a] + cifrado[b : b + n] + cifrado[a : a + n] + cifrado[b + n :]
    with pytest.raises(ErroCifra):
        cifra.decifrar(trocado, CHAVE)


def test_arquivo_cortado_nao_passa():
    cifrado = cifra.cifrar(os.urandom(3 * BLOCO), CHAVE, BLOCO)
    with pytest.raises(ErroCifra, match="bytes"):
        cifra.decifrar(cifrado[: -(BLOCO + 16)], CHAVE)


def test_cabecalho_adulterado_para_esconder_o_corte():
    # Diminuir o tamanho declarado para fazer o penúltimo bloco parecer o último:
    # o cabeçalho e a marca de último bloco entram no dado autenticado.
    claro = os.urandom(3 * BLOCO)
    cifrado = cifra.cifrar(claro, CHAVE, BLOCO)
    cab = Cabecalho.ler(cifrado)
    falso = Cabecalho(cab.tamanho_bloco, cab.prefixo_nonce, 2 * BLOCO)
    cortado = falso.bytes + cifrado[32 : 32 + 2 * (BLOCO + 16)]
    with pytest.raises(ErroCifra):
        cifra.decifrar(cortado, CHAVE)


@pytest.mark.parametrize(
    "dados, motivo",
    [
        (b"CENT", "menor"),
        (b"MP4 " + bytes(28), "não é"),
        (b"CENT\x02" + bytes(27), "versão 2"),
    ],
)
def test_cabecalho_invalido(dados, motivo):
    with pytest.raises(ErroCifra, match=motivo):
        Cabecalho.ler(dados)


def test_chave_da_faixa_embrulhada_pela_mestra():
    mestra, chave = cifra.nova_chave(), cifra.nova_chave()
    embrulhada = cifra.embrulhar(chave, mestra)
    assert chave not in embrulhada
    assert cifra.desembrulhar(embrulhada, mestra) == chave
    with pytest.raises(ErroCifra, match="chave-mestra"):
        cifra.desembrulhar(embrulhada, cifra.nova_chave())
