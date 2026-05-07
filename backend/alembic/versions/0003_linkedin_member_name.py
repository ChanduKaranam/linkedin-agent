"""Add member_name column to linkedin_account

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("linkedin_account", sa.Column("member_name", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("linkedin_account", "member_name")
