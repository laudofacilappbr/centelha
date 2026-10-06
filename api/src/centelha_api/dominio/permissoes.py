import enum

from ..models import PapelUsuario


class Permissao(enum.StrEnum):
    VER_ADMIN = "ver_admin"
    EDITAR_SEGMENTO = "editar_segmento"
    APROVAR_TEXTO = "aprovar_texto"
    OUVIR_AUDIO = "ouvir_audio"
    APONTAR_ERRO_AUDIO = "apontar_erro_audio"
    EDITAR_DICIONARIO = "editar_dicionario"
    APROVAR_AUDIO = "aprovar_audio"
    APROVAR_DIREITOS = "aprovar_direitos"
    PUBLICAR = "publicar"
    GERIR_USUARIOS = "gerir_usuarios"
    VER_AUDITORIA = "ver_auditoria"


# Tabela "Papéis" da especificação. Lista explícita, sem herança entre papéis: um
# revisor de áudio que "herdasse" do de texto ganharia edição de segmento sem
# ninguém ter decidido isso.
PERMISSOES_POR_PAPEL: dict[PapelUsuario, frozenset[Permissao]] = {
    PapelUsuario.ADMINISTRADOR: frozenset(Permissao),
    PapelUsuario.REVISOR_TEXTO: frozenset(
        {Permissao.VER_ADMIN, Permissao.EDITAR_SEGMENTO, Permissao.APROVAR_TEXTO}
    ),
    PapelUsuario.REVISOR_AUDIO: frozenset(
        {
            Permissao.VER_ADMIN,
            Permissao.OUVIR_AUDIO,
            Permissao.APONTAR_ERRO_AUDIO,
            Permissao.EDITAR_DICIONARIO,
            Permissao.APROVAR_AUDIO,
        }
    ),
}


def pode(papel: PapelUsuario, permissao: Permissao) -> bool:
    # Papel fora da tabela não pode nada (padrão restritivo).
    return permissao in PERMISSOES_POR_PAPEL.get(papel, frozenset())
