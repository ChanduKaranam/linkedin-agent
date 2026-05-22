"""Add style_chosen and evaluation_json columns to generated_posts

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "generated_posts" in tables:
        columns = {c["name"] for c in inspector.get_columns("generated_posts")}
        if "style_chosen" not in columns:
            op.add_column(
                "generated_posts",
                sa.Column("style_chosen", sa.String(), nullable=True)
            )
        if "evaluation_json" not in columns:
            op.add_column(
                "generated_posts",
                sa.Column("evaluation_json", JSONB(), nullable=True)
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "generated_posts" in tables:
        columns = {c["name"] for c in inspector.get_columns("generated_posts")}
        if "style_chosen" in columns:
            op.drop_column("generated_posts", "style_chosen")
        if "evaluation_json" in columns:
            op.drop_column("generated_posts", "evaluation_json")
