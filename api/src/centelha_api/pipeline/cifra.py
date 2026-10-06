"""Formato .cent: a faixa cifrada que o app baixa e decifra bloco a bloco (ADR 0004).

    cabeçalho (32 bytes)
      0  "CENT"                 assinatura
      4  versão (u8) = 1
      5  3 bytes zerados
      8  tamanho do bloco claro (u32, big-endian) = 65536
     12  prefixo do nonce (8 bytes aleatórios)
     20  tamanho do áudio claro (u64, big-endian)
     28  4 bytes zerados
    blocos, um após o outro
      AES-256-GCM(bloco claro) + tag de 16 bytes; o último pode ser menor

O bloco i começa em 32 + i * (bloco + 16), então o app decifra só o trecho que o
player pede (avançar e recuar sem baixar tudo). Cada bloco usa o nonce
prefixo || i (u32) e autentica, como dado associado, o cabeçalho, o índice e se é o
último: bloco trocado, reordenado, de outra faixa ou arquivo cortado não decifra.

A chave de cada faixa (32 bytes aleatórios) fica no banco embrulhada pela
chave-mestra do servidor; só o app atestado a recebe (#73).
"""

import os
import struct
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ASSINATURA = b"CENT"
VERSAO = 1
FORMATO = "cent1"
TAMANHO_BLOCO = 64 * 1024
TAMANHO_TAG = 16
TAMANHO_CABECALHO = 32
TAMANHO_CHAVE = 32
_CABECALHO = struct.Struct(">4sB3xI8sQ4x")
# Separa o embrulho de chave de faixa de qualquer outro uso da chave-mestra.
_CONTEXTO_EMBRULHO = b"centelha-faixa-v1"


class ErroCifra(Exception):
    pass


@dataclass(frozen=True)
class Cabecalho:
    tamanho_bloco: int
    prefixo_nonce: bytes
    tamanho_claro: int

    @property
    def bytes(self) -> bytes:
        return _CABECALHO.pack(
            ASSINATURA, VERSAO, self.tamanho_bloco, self.prefixo_nonce, self.tamanho_claro
        )

    @property
    def blocos(self) -> int:
        return max(1, -(-self.tamanho_claro // self.tamanho_bloco))

    @classmethod
    def ler(cls, dados: bytes) -> "Cabecalho":
        if len(dados) < TAMANHO_CABECALHO:
            raise ErroCifra("arquivo menor que o cabeçalho")
        assinatura, versao, bloco, prefixo, tamanho = _CABECALHO.unpack(dados[:TAMANHO_CABECALHO])
        if assinatura != ASSINATURA:
            raise ErroCifra("não é um arquivo .cent")
        if versao != VERSAO:
            raise ErroCifra(f"versão {versao} do .cent não suportada")
        if bloco <= 0:
            raise ErroCifra("tamanho de bloco inválido")
        return cls(bloco, prefixo, tamanho)


def nova_chave() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def _nonce(cab: Cabecalho, indice: int) -> bytes:
    return cab.prefixo_nonce + struct.pack(">I", indice)


def _associado(cab: Cabecalho, indice: int) -> bytes:
    return cab.bytes + struct.pack(">IB", indice, int(indice == cab.blocos - 1))


def cifrar(claro: bytes, chave: bytes, tamanho_bloco: int = TAMANHO_BLOCO) -> bytes:
    cab = Cabecalho(tamanho_bloco, os.urandom(8), len(claro))
    aes = AESGCM(chave)
    partes = [cab.bytes]
    for i in range(cab.blocos):
        bloco = claro[i * tamanho_bloco : (i + 1) * tamanho_bloco]
        partes.append(aes.encrypt(_nonce(cab, i), bloco, _associado(cab, i)))
    return b"".join(partes)


def posicao_bloco(cab: Cabecalho, indice: int) -> tuple[int, int]:
    """Início e tamanho, no arquivo .cent, do bloco cifrado de índice dado."""
    if not 0 <= indice < cab.blocos:
        raise ErroCifra(f"bloco {indice} fora do arquivo ({cab.blocos} blocos)")
    inicio = TAMANHO_CABECALHO + indice * (cab.tamanho_bloco + TAMANHO_TAG)
    claro = min(cab.tamanho_bloco, cab.tamanho_claro - indice * cab.tamanho_bloco)
    return inicio, claro + TAMANHO_TAG


def decifrar_bloco(cab: Cabecalho, indice: int, cifrado: bytes, chave: bytes) -> bytes:
    try:
        return AESGCM(chave).decrypt(_nonce(cab, indice), cifrado, _associado(cab, indice))
    except InvalidTag as e:
        raise ErroCifra(f"bloco {indice} não confere (chave errada ou arquivo alterado)") from e


def decifrar(dados: bytes, chave: bytes) -> bytes:
    cab = Cabecalho.ler(dados)
    inicio_fim = [posicao_bloco(cab, i) for i in range(cab.blocos)]
    esperado = inicio_fim[-1][0] + inicio_fim[-1][1]
    if len(dados) != esperado:
        raise ErroCifra(f"arquivo com {len(dados)} bytes; o cabeçalho pede {esperado}")
    return b"".join(
        decifrar_bloco(cab, i, dados[inicio : inicio + n], chave)
        for i, (inicio, n) in enumerate(inicio_fim)
    )


def embrulhar(chave: bytes, mestra: bytes) -> bytes:
    """Chave da faixa cifrada pela chave-mestra, para guardar no banco: nonce + cifra."""
    nonce = os.urandom(12)
    return nonce + AESGCM(mestra).encrypt(nonce, chave, _CONTEXTO_EMBRULHO)


def desembrulhar(embrulhada: bytes, mestra: bytes) -> bytes:
    try:
        return AESGCM(mestra).decrypt(embrulhada[:12], embrulhada[12:], _CONTEXTO_EMBRULHO)
    except InvalidTag as e:
        raise ErroCifra("chave da faixa não abre com esta chave-mestra") from e
