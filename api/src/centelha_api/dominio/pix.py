"""Chave Pix e CNPJ publicados nas páginas de apoio (#40) e de campanha (#41)."""

import re

# Formatos de chave Pix do Banco Central, já sem espaços.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TELEFONE = re.compile(r"^\+55\d{10,11}$")
_ALEATORIA = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_CNPJ = re.compile(r"^\d{14}$")


def chave_pix(valor: str) -> str:
    """Normaliza a chave ou levanta ValueError com a mensagem para quem edita."""
    chave = re.sub(r"\s", "", valor)
    so_digitos = re.sub(r"[.\-/]", "", chave)
    if re.fullmatch(r"\d{11}", so_digitos):
        # CPF na página pública expõe o documento de quem recebe. Chave aleatória,
        # e-mail ou telefone recebem o mesmo Pix sem isso.
        raise ValueError("chave CPF não é aceita: use chave aleatória, e-mail ou telefone")
    if _CNPJ.fullmatch(so_digitos):
        return so_digitos
    if _ALEATORIA.fullmatch(chave.lower()):
        return chave.lower()
    if _TELEFONE.fullmatch(chave) or (len(chave) <= 77 and _EMAIL.fullmatch(chave)):
        return chave
    raise ValueError("chave Pix inválida: use chave aleatória, e-mail, telefone (+55…) ou CNPJ")


def cnpj(valor: str) -> str:
    """Só dígitos, com os dois verificadores conferidos.

    CNPJ digitado errado na página de campanha manda quem doa conferir outra
    instituição, ou nenhuma: é o dado que dá confiança à doação.
    """
    d = re.sub(r"[.\-/\s]", "", valor)
    if not _CNPJ.fullmatch(d) or len(set(d)) == 1:
        raise ValueError("CNPJ inválido: 14 dígitos")
    for n in (12, 13):
        pesos = list(range(n - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(int(x) * p for x, p in zip(d[:n], pesos, strict=True))
        dv = 0 if soma % 11 < 2 else 11 - soma % 11
        if int(d[n]) != dv:
            raise ValueError("CNPJ inválido: dígito verificador não confere")
    return d
