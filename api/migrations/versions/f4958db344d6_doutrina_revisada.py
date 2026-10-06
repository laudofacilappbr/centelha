"""doutrina revisada

Revision ID: f4958db344d6
Revises: f1092e382dbc
Create Date: 2026-10-06 19:14:14.316460

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4958db344d6'
down_revision: Union[str, Sequence[str], None] = 'f1092e382dbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ANTIGOS = ("importado", "texto_revisado", "audio_gerado", "audio_revisado", "publicado")


def upgrade() -> None:
    """Estado da revisão doutrinária das adaptações juvenis e infantis (#49)."""
    # Autogenerate não enxerga valor novo de enum: vai à mão. Fora de transação não é
    # preciso desde o PostgreSQL 12, desde que o valor não seja usado nesta mesma.
    op.execute(
        "ALTER TYPE estadocapitulo ADD VALUE IF NOT EXISTS 'doutrina_revisada' "
        "AFTER 'texto_revisado'"
    )


def downgrade() -> None:
    """PostgreSQL não remove valor de enum: recria o tipo sem ele."""
    # Capítulo com doutrina aprovada volta a "texto revisado": a aprovação doutrinária
    # se perde, mas nenhum capítulo fica num estado que o código antigo não conhece.
    op.execute("UPDATE capitulo SET estado = 'texto_revisado' WHERE estado = 'doutrina_revisada'")
    op.execute("ALTER TYPE estadocapitulo RENAME TO estadocapitulo_antigo")
    valores = ", ".join(f"'{v}'" for v in ANTIGOS)
    op.execute(f"CREATE TYPE estadocapitulo AS ENUM ({valores})")
    op.execute(
        "ALTER TABLE capitulo ALTER COLUMN estado TYPE estadocapitulo "
        "USING estado::text::estadocapitulo"
    )
    op.execute("DROP TYPE estadocapitulo_antigo")
