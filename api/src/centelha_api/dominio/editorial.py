"""Fluxo editorial do capítulo (especificação, seção Admin).

importado → texto revisado → áudio gerado → áudio revisado → publicado

Adaptação juvenil ou infantil (#49) tem um passo a mais, antes do áudio:

importado → texto revisado → doutrina revisada → áudio gerado → …

Cada passo à frente é uma aprovação; cada reprovação volta um passo. "Áudio gerado"
não tem ação aqui: quem o grava é o worker ao concluir o job (#18/#19). "Publicado"
também não: a edição publica inteira em dominio/publicacao.py, que confere direitos.
"""

from dataclasses import dataclass

from ..models import Capitulo, EstadoCapitulo, PapelUsuario, Publico
from .permissoes import Permissao, pode

E = EstadoCapitulo
TODOS = frozenset(Publico)
ADAPTACOES = frozenset({Publico.JUVENIL, Publico.INFANTIL})


@dataclass(frozen=True)
class Transicao:
    de: EstadoCapitulo
    para: EstadoCapitulo
    permissao: Permissao
    # Reprovar sem dizer por quê obriga o próximo revisor a adivinhar o defeito.
    exige_motivo: bool = False
    # Públicos das edições em que a ação existe.
    publicos: frozenset[Publico] = TODOS
    # Destino quando a edição é adaptação, se diferente de `para`.
    para_adaptacao: EstadoCapitulo | None = None

    def destino(self, publico: Publico) -> EstadoCapitulo:
        if publico in ADAPTACOES and self.para_adaptacao is not None:
            return self.para_adaptacao
        return self.para


TRANSICOES: dict[str, Transicao] = {
    "aprovar_texto": Transicao(E.IMPORTADO, E.TEXTO_REVISADO, Permissao.APROVAR_TEXTO),
    # Reabrir o texto é o caminho para corrigir um erro achado depois da aprovação.
    "reabrir_texto": Transicao(
        E.TEXTO_REVISADO, E.IMPORTADO, Permissao.APROVAR_TEXTO, exige_motivo=True
    ),
    # Adaptação não vira áudio sem uma pessoa conferir doutrina e linguagem
    # (especificação, Versões infantil e juvenil). A IA pode ler antes (#98); não aprova.
    "aprovar_doutrina": Transicao(
        E.TEXTO_REVISADO, E.DOUTRINA_REVISADA, Permissao.APROVAR_DOUTRINA, publicos=ADAPTACOES
    ),
    # Volta um passo, como toda reprovação. Problema doutrinário costuma ser de texto:
    # reabrir_texto em seguida leva para onde o texto se edita.
    "reprovar_doutrina": Transicao(
        E.DOUTRINA_REVISADA,
        E.TEXTO_REVISADO,
        Permissao.APROVAR_DOUTRINA,
        exige_motivo=True,
        publicos=ADAPTACOES,
    ),
    "aprovar_audio": Transicao(E.AUDIO_GERADO, E.AUDIO_REVISADO, Permissao.APROVAR_AUDIO),
    # Áudio reprovado volta para antes do áudio: o texto (e, na adaptação, a doutrina)
    # continua aprovado e o capítulo aguarda nova geração. Erro que é de texto pede
    # reabrir_texto ou reprovar_doutrina em seguida.
    "reprovar_audio": Transicao(
        E.AUDIO_GERADO,
        E.TEXTO_REVISADO,
        Permissao.APROVAR_AUDIO,
        exige_motivo=True,
        para_adaptacao=E.DOUTRINA_REVISADA,
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
    publico = capitulo.edicao.publico
    return [
        nome
        for nome, t in TRANSICOES.items()
        if t.de == capitulo.estado and publico in t.publicos and pode(papel, t.permissao)
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
    publico = capitulo.edicao.publico
    if publico not in t.publicos:
        raise TransicaoInvalida(f"{acao} não se aplica a edição {publico.value}")
    if capitulo.estado != t.de:
        raise TransicaoInvalida(
            f"{acao} exige capítulo em '{t.de.value}', está em '{capitulo.estado.value}'"
        )
    if t.exige_motivo and not (motivo or "").strip():
        raise TransicaoInvalida(f"{acao} exige motivo")
    capitulo.estado = t.destino(publico)
    return t


def pode_gerar_audio(capitulo: Capitulo) -> bool:
    """Texto aprovado (e, na adaptação, doutrina aprovada) ou áudio já existente: gerar
    de novo é permitido e devolve o capítulo para "áudio gerado"."""
    if capitulo.estado in (E.AUDIO_GERADO, E.AUDIO_REVISADO):
        return True
    if capitulo.edicao.publico in ADAPTACOES:
        return capitulo.estado == E.DOUTRINA_REVISADA
    return capitulo.estado == E.TEXTO_REVISADO


def texto_editavel(capitulo: Capitulo) -> bool:
    # Só durante a revisão de texto. Editar depois deixaria áudio e marcações de tempo
    # descolados do texto; para corrigir, reabre-se o texto (e o áudio é refeito).
    return capitulo.estado == E.IMPORTADO
