"""Fluxo editorial do capítulo (especificação, seção Admin).

importado → texto revisado → áudio gerado → áudio revisado → publicado

Cada passo à frente é uma aprovação; cada reprovação volta um passo. "Áudio gerado"
não tem ação aqui: quem o grava é o worker ao concluir o job (#18/#19). "Publicado"
também não: a edição publica inteira em dominio/publicacao.py, que confere direitos.
"""

from dataclasses import dataclass

from ..models import Capitulo, EstadoCapitulo, PapelUsuario
from .permissoes import Permissao, pode

E = EstadoCapitulo


@dataclass(frozen=True)
class Transicao:
    de: EstadoCapitulo
    para: EstadoCapitulo
    permissao: Permissao
    # Reprovar sem dizer por quê obriga o próximo revisor a adivinhar o defeito.
    exige_motivo: bool = False


TRANSICOES: dict[str, Transicao] = {
    "aprovar_texto": Transicao(E.IMPORTADO, E.TEXTO_REVISADO, Permissao.APROVAR_TEXTO),
    # Reabrir o texto é o caminho para corrigir um erro achado depois da aprovação.
    "reabrir_texto": Transicao(
        E.TEXTO_REVISADO, E.IMPORTADO, Permissao.APROVAR_TEXTO, exige_motivo=True
    ),
    "aprovar_audio": Transicao(E.AUDIO_GERADO, E.AUDIO_REVISADO, Permissao.APROVAR_AUDIO),
    # Áudio reprovado volta a "texto revisado": o texto continua aprovado e o capítulo
    # aguarda nova geração. Erro que é de texto pede reabrir_texto em seguida.
    "reprovar_audio": Transicao(
        E.AUDIO_GERADO, E.TEXTO_REVISADO, Permissao.APROVAR_AUDIO, exige_motivo=True
    ),
    "reabrir_audio": Transicao(
        E.AUDIO_REVISADO, E.AUDIO_GERADO, Permissao.APROVAR_AUDIO, exige_motivo=True
    ),
    # Tira um capítulo do ar (o catálogo só mostra capítulo "publicado"). Fica com quem
    # publica, não com o revisor de áudio.
    "despublicar": Transicao(E.PUBLICADO, E.AUDIO_REVISADO, Permissao.PUBLICAR, exige_motivo=True),
}


class TransicaoInvalida(ValueError):
    pass


class SemPermissao(PermissionError):
    pass


def acoes_possiveis(capitulo: Capitulo, papel: PapelUsuario) -> list[str]:
    """Ações que este papel pode tomar agora; o admin mostra só esses botões."""
    return [
        nome
        for nome, t in TRANSICOES.items()
        if t.de == capitulo.estado and pode(papel, t.permissao)
    ]


def aplicar(
    capitulo: Capitulo, acao: str, papel: PapelUsuario, motivo: str | None = None
) -> Transicao:
    t = TRANSICOES.get(acao)
    if t is None:
        raise TransicaoInvalida(f"ação desconhecida: {acao}")
    # Permissão antes do estado: quem não pode agir não descobre o estado pela mensagem.
    if not pode(papel, t.permissao):
        raise SemPermissao(acao)
    if capitulo.estado != t.de:
        raise TransicaoInvalida(
            f"{acao} exige capítulo em '{t.de.value}', está em '{capitulo.estado.value}'"
        )
    if t.exige_motivo and not (motivo or "").strip():
        raise TransicaoInvalida(f"{acao} exige motivo")
    capitulo.estado = t.para
    return t


def texto_editavel(capitulo: Capitulo) -> bool:
    # Só durante a revisão de texto. Editar depois deixaria áudio e marcações de tempo
    # descolados do texto; para corrigir, reabre-se o texto (e o áudio é refeito).
    return capitulo.estado == E.IMPORTADO
