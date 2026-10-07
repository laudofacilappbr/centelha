"""slug da edicao

Revision ID: c2d6bddb5315
Revises: f4958db344d6
Create Date: 2026-10-06 20:19:15.494192

"""
import re
import unicodedata
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d6bddb5315'
down_revision: Union[str, Sequence[str], None] = 'f4958db344d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('edicao', sa.Column('slug', sa.String(length=120), nullable=True))
    op.create_unique_constraint(
        'edicao_idioma_publico_slug_key', 'edicao', ['idioma', 'publico', 'slug']
    )
    # Edições já publicadas ganham o slug que a publicação daria (#48). Cópia da regra
    # de dominio/slug.py: a migração não importa código que pode mudar depois.
    conn = op.get_bind()
    usados: set[tuple[str, str, str]] = set()
    edicoes = conn.execute(
        sa.text("select id, idioma, publico::text, titulo from edicao "
                "where publicada_em is not null order by id")
    ).all()
    for id_, idioma, publico, titulo in edicoes:
        sem_acento = "".join(
            c for c in unicodedata.normalize("NFKD", titulo) if not unicodedata.combining(c)
        )
        base = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:120].rstrip("-")
        base = base or f"edicao-{id_}"
        slug, n = base, 2
        while (idioma, publico, slug) in usados:
            slug, n = f"{base}-{n}", n + 1
        usados.add((idioma, publico, slug))
        conn.execute(sa.text("update edicao set slug = :s where id = :i"), {"s": slug, "i": id_})


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('edicao_idioma_publico_slug_key', 'edicao', type_='unique')
    op.drop_column('edicao', 'slug')
