"""memory fact embeddings

Revision ID: 0003_memory_fact_embeddings
Revises: 0002_manifest_v2_core
Create Date: 2026-06-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_memory_fact_embeddings"
down_revision: Union[str, None] = "0002_manifest_v2_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Эмбеддинг факта как JSON-массив float'ов. NULL — ещё не посчитан;
    # backfill идёт лениво в фоне после консолидации памяти.
    op.add_column("memory_facts", sa.Column("embedding", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("memory_facts", "embedding")
