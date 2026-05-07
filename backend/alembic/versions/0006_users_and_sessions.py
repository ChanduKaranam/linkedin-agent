"""Add primary key to users table and create auth_sessions

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    users_has_username = False

    if "users" not in table_names:
        op.create_table(
            "users",
            sa.Column("username", sa.String(255), primary_key=True),
            sa.Column("password", sa.String(255), nullable=False),
        )
        users_has_username = True
    else:
        user_columns = {col.get("name") for col in inspector.get_columns("users")}
        users_has_username = "username" in user_columns
        # Some hosted DBs may already contain a legacy/incompatible "users" table.
        # Only enforce constraints when the expected username column exists.
        if users_has_username:
            if "password" not in user_columns:
                op.add_column(
                    "users",
                    sa.Column("password", sa.String(255), nullable=False, server_default=""),
                )
            pk_constraint = inspector.get_pk_constraint("users")
            constrained_columns = (pk_constraint or {}).get("constrained_columns") or []
            if constrained_columns != ["username"]:
                if constrained_columns:
                    pk_name = (pk_constraint or {}).get("name")
                    if pk_name:
                        op.drop_constraint(pk_name, "users", type_="primary")
                op.create_primary_key("users_pkey", "users", ["username"])

    if users_has_username and "auth_sessions" not in table_names:
        op.create_table(
            "auth_sessions",
            sa.Column("token", sa.String(64), primary_key=True),
            sa.Column("username", sa.String(255), sa.ForeignKey("users.username", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("idx_auth_sessions_username", "auth_sessions", ["username"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "auth_sessions" in table_names:
        indexes = {idx.get("name") for idx in inspector.get_indexes("auth_sessions")}
        if "idx_auth_sessions_username" in indexes:
            op.drop_index("idx_auth_sessions_username", table_name="auth_sessions")
        op.drop_table("auth_sessions")

    if "users" in table_names:
        pk_constraint = inspector.get_pk_constraint("users")
        pk_name = (pk_constraint or {}).get("name")
        if pk_name:
            op.drop_constraint(pk_name, "users", type_="primary")
