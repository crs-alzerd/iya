"""planning system: plans, habits, calendar, note links

Revision ID: 0004_planning_system
Revises: 0003_memory_fact_embeddings
Create Date: 2026-06-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_planning_system"
down_revision: Union[str, None] = "0003_memory_fact_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Расширяем существующую таблицу reminders (создана в 0001) под planning-систему.
    op.add_column("reminders", sa.Column("kind", sa.String(length=16), nullable=False, server_default="one_off"))
    op.add_column("reminders", sa.Column("recurrence_rule", sa.String(length=256), nullable=True))
    op.add_column("reminders", sa.Column("habit_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_reminders_habit_id", "reminders", ["habit_id"])
    op.create_check_constraint(
        "ck_reminders_kind",
        "reminders",
        "kind in ('one_off', 'recurring', 'habit_nudge')",
    )

    op.create_table(
        "planning_items",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="todo", index=True),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("parent_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('todo', 'in_progress', 'done', 'cancelled')", name="ck_planning_items_status"),
        sa.CheckConstraint("priority in ('low', 'normal', 'high', 'urgent')", name="ck_planning_items_priority"),
    )

    op.create_table(
        "habits",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("cadence", sa.String(length=16), nullable=False, server_default="daily"),
        sa.Column("schedule_time", sa.Time(timezone=False), nullable=True),
        sa.Column("target_per_period", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reminder_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("cadence in ('daily', 'weekly', 'monthly', 'custom')", name="ck_habits_cadence"),
        sa.CheckConstraint("status in ('active', 'paused', 'archived')", name="ck_habits_status"),
    )

    op.create_table(
        "habit_completions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("habit_id", sa.BigInteger(), sa.ForeignKey("habits.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )

    op.create_table(
        "calendar_bindings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider_kind", sa.String(length=16), nullable=False, server_default="mock"),
        sa.Column("calendar_name", sa.String(length=256), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("credentials_ref", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active", index=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider_kind in ('mock', 'caldav', 'google', 'ics')", name="ck_calendar_bindings_provider"),
        sa.CheckConstraint("status in ('active', 'disabled', 'error')", name="ck_calendar_bindings_status"),
    )

    op.create_table(
        "calendar_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("binding_id", sa.BigInteger(), sa.ForeignKey("calendar_bindings.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("external_id", sa.String(length=256), nullable=True, index=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="mock"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "note_links",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("telegram_users.telegram_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("note_path", sa.Text(), nullable=False),
        sa.Column("note_title", sa.Text(), nullable=True),
        sa.Column("relation", sa.String(length=16), nullable=False, server_default="reference"),
        sa.Column("planning_item_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("reminder_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("habit_id", sa.BigInteger(), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("relation in ('source', 'plan', 'log', 'reference')", name="ck_note_links_relation"),
    )


def downgrade() -> None:
    op.drop_table("note_links")
    op.drop_table("calendar_events")
    op.drop_table("calendar_bindings")
    op.drop_table("habit_completions")
    op.drop_table("habits")
    op.drop_table("planning_items")

    op.drop_constraint("ck_reminders_kind", "reminders", type_="check")
    op.drop_index("ix_reminders_habit_id", table_name="reminders")
    op.drop_column("reminders", "habit_id")
    op.drop_column("reminders", "recurrence_rule")
    op.drop_column("reminders", "kind")
