"""Add log_events table for DB-backed structured logging

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "log_events" in set(inspector.get_table_names()):
        return

    op.create_table(
        "log_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("logger_name", sa.String(120), nullable=False),
        sa.Column("event", sa.String(200), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("data", JSONB(), nullable=True),
        sa.Column("run_id", sa.String(64), nullable=True),
    )
    op.create_index("ix_log_events_ts", "log_events", ["ts"])
    op.create_index("ix_log_events_level_ts", "log_events", ["level", "ts"])
    op.create_index("ix_log_events_logger_ts", "log_events", ["logger_name", "ts"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "log_events" not in set(inspector.get_table_names()):
        return

    for idx in ("ix_log_events_level_ts", "ix_log_events_logger_ts", "ix_log_events_ts"):
        indexes = {i.get("name") for i in inspector.get_indexes("log_events")}
        if idx in indexes:
            op.drop_index(idx, table_name="log_events")
    op.drop_table("log_events")
