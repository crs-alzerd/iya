"""initial schema without native postgres enums

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True, index=True),
        sa.Column("username", sa.String(length=128), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.CheckConstraint("role in ('user', 'assistant', 'system')", name="ck_messages_role"),
    )

    op.create_table(
        "pinned_memories",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "conversation_summaries",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "reminders",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('pending', 'sent', 'cancelled', 'failed')", name="ck_reminders_status"),
    )

    op.create_table(
        "proactive_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending", index=True),
        sa.Column("planned_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('pending', 'sent', 'cancelled', 'failed')", name="ck_proactive_events_status"),
    )


def downgrade() -> None:
    op.drop_table("proactive_events")
    op.drop_table("reminders")
    op.drop_table("conversation_summaries")
    op.drop_table("pinned_memories")
    op.drop_table("messages")
    op.drop_table("telegram_users")
