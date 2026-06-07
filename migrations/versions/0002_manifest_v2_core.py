"""manifest v2 core architecture

Revision ID: 0002_manifest_v2_core
Revises: 0001_initial
Create Date: 2026-06-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_manifest_v2_core"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "memory_facts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("salience_score", sa.Float(), nullable=False, server_default="1.0", index=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active", index=True),
        sa.Column("superseded_by", sa.BigInteger(), nullable=True),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('active', 'superseded', 'archived')", name="ck_memory_facts_status"),
        sa.CheckConstraint("author in ('user', 'iya', 'extracted')", name="ck_memory_facts_author"),
        sa.CheckConstraint("source in ('manual', 'extracted', 'inferred', 'reflection')", name="ck_memory_facts_source"),
    )

    # Backfill existing pinned memories into the new salience-aware fact table.
    op.execute(
        """
        INSERT INTO memory_facts (
            id, telegram_user_id, text, author, source, confidence, salience_score,
            status, last_confirmed_at, created_at, updated_at
        )
        SELECT
            id, telegram_user_id, content, 'user', 'manual', 1.0, 1.0,
            'active', created_at, created_at, created_at
        FROM pinned_memories
        ON CONFLICT DO NOTHING
        """
    )
    op.execute("SELECT setval(pg_get_serial_sequence('memory_facts', 'id'), COALESCE((SELECT MAX(id) FROM memory_facts), 1))")

    op.create_table(
        "memory_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("pinned_memories", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("conversation_summary", sa.Text(), nullable=True),
        sa.Column("reason", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "self_state",
        sa.Column("telegram_user_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("composure", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("warmth_now", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("engagement", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("fatigue", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("playfulness", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "self_memories",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("salience_score", sa.Float(), nullable=False, server_default="0.5", index=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "relationship_state",
        sa.Column("telegram_user_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("closeness", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("trust", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("shared_history_len", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("inside_refs", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "llm_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("kind", sa.String(length=32), nullable=False, index=True),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, index=True),
        sa.Column("tokens_input", sa.BigInteger(), nullable=True),
        sa.Column("tokens_output", sa.BigInteger(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.BigInteger(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    op.create_table(
        "mode_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("profile", sa.String(length=32), nullable=False, index=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.add_column("proactive_events", sa.Column("dedup_key", sa.String(length=256), nullable=True))
    op.add_column("proactive_events", sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_proactive_events_dedup_key", "proactive_events", ["dedup_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_proactive_events_dedup_key", table_name="proactive_events")
    op.drop_column("proactive_events", "fired_at")
    op.drop_column("proactive_events", "dedup_key")
    op.drop_table("mode_events")
    op.drop_table("llm_requests")
    op.drop_table("relationship_state")
    op.drop_table("self_memories")
    op.drop_table("self_state")
    op.drop_table("memory_snapshots")
    op.drop_table("memory_facts")
