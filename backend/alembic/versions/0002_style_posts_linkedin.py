"""Add style_samples, style_profile, generated_posts, linkedin_account tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "style_samples",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("source_ref", sa.BigInteger, nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_style_samples_created", "style_samples", ["created_at"])

    op.create_table(
        "style_profile",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("profile_markdown", sa.Text, nullable=False, server_default=""),
        sa.Column("sample_count_at_last_refresh", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "generated_posts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("run_id", sa.String, nullable=False),
        sa.Column("run_date", sa.Date, nullable=False),
        sa.Column("slug", sa.String, nullable=False),
        sa.Column("content_markdown", sa.Text, nullable=False),
        sa.Column("tags_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String, nullable=False, server_default="draft"),
        sa.Column("linkedin_post_urn", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_gen_posts_run_date_slug", "generated_posts", ["run_date", "slug"])
    op.create_index("idx_gen_posts_run_id_slug", "generated_posts", ["run_id", "slug"])

    op.create_table(
        "linkedin_account",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("member_urn", sa.String, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("linkedin_account")
    op.drop_table("generated_posts")
    op.drop_table("style_profile")
    op.drop_table("style_samples")
