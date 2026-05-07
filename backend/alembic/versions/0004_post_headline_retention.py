"""Add headline to generated_posts for post-deletion survivability

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add column with a default so existing rows get an empty string initially
    op.add_column(
        "generated_posts",
        sa.Column("headline", sa.Text, nullable=False, server_default=""),
    )

    # Backfill from trends — use the most-recent trend headline for each (run_date, slug) pair
    op.execute(
        """
        UPDATE generated_posts AS gp
        SET headline = t.headline
        FROM (
            SELECT DISTINCT ON (run_date, slug) run_date, slug, headline
            FROM trends
            ORDER BY run_date, slug, id DESC
        ) AS t
        WHERE gp.run_date = t.run_date
          AND gp.slug = t.slug
          AND gp.headline = ''
        """
    )

    # Remove the server default — future inserts must supply headline explicitly
    op.alter_column("generated_posts", "headline", server_default=None)


def downgrade() -> None:
    op.drop_column("generated_posts", "headline")
