"""Restore server default on generated_posts.headline

Without a server default, any INSERT that omits headline (e.g. a running
server that hasn't picked up the ORM change yet) hits a NOT NULL violation.
The server default of '' acts as a safety net during rolling restarts.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("generated_posts", "headline", server_default="")


def downgrade() -> None:
    op.alter_column("generated_posts", "headline", server_default=None)
