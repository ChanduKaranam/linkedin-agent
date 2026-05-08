"""Add FKs, indexes, expires_at for auth sessions, text_hash for style samples

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # ── chat_messages: FK to runs ON DELETE CASCADE ──────────────────────────
    if "chat_messages" in tables:
        existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("chat_messages")}
        if "fk_chat_messages_run_id" not in existing_fks:
            # Orphan rows would block FK creation — delete them first
            bind.execute(sa.text(
                "DELETE FROM chat_messages "
                "WHERE run_id IS NOT NULL AND run_id NOT IN (SELECT run_id FROM runs)"
            ))
            op.create_foreign_key(
                "fk_chat_messages_run_id",
                "chat_messages", "runs",
                ["run_id"], ["run_id"],
                ondelete="CASCADE",
            )

    # ── insights: make run_id nullable, then FK ON DELETE SET NULL ────────────
    if "insights" in tables:
        cols = {c["name"]: c for c in inspector.get_columns("insights")}
        if "run_id" in cols and not cols["run_id"].get("nullable", False):
            op.alter_column("insights", "run_id", nullable=True)

        existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("insights")}
        if "fk_insights_run_id" not in existing_fks:
            # Null-out orphan run_ids rather than deleting the insight
            bind.execute(sa.text(
                "UPDATE insights SET run_id = NULL "
                "WHERE run_id IS NOT NULL AND run_id NOT IN (SELECT run_id FROM runs)"
            ))
            op.create_foreign_key(
                "fk_insights_run_id",
                "insights", "runs",
                ["run_id"], ["run_id"],
                ondelete="SET NULL",
            )

    # ── generated_posts: make run_id nullable, then FK ON DELETE SET NULL ────
    if "generated_posts" in tables:
        cols = {c["name"]: c for c in inspector.get_columns("generated_posts")}
        if "run_id" in cols and not cols["run_id"].get("nullable", False):
            op.alter_column("generated_posts", "run_id", nullable=True)

        existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("generated_posts")}
        if "fk_gen_posts_run_id" not in existing_fks:
            bind.execute(sa.text(
                "UPDATE generated_posts SET run_id = NULL "
                "WHERE run_id IS NOT NULL AND run_id NOT IN (SELECT run_id FROM runs)"
            ))
            op.create_foreign_key(
                "fk_gen_posts_run_id",
                "generated_posts", "runs",
                ["run_id"], ["run_id"],
                ondelete="SET NULL",
            )

    # ── generated_posts: composite index for list queries ────────────────────
    if "generated_posts" in tables:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("generated_posts")}
        if "idx_gen_posts_kind_status_updated" not in existing_indexes:
            op.create_index(
                "idx_gen_posts_kind_status_updated",
                "generated_posts",
                ["kind", "status", "updated_at"],
            )

    # ── auth_sessions: add expires_at ────────────────────────────────────────
    if "auth_sessions" in tables:
        existing_cols = {c["name"] for c in inspector.get_columns("auth_sessions")}
        if "expires_at" not in existing_cols:
            # Add as nullable first; backfill from last_seen_at + 30 days; then make NOT NULL
            op.add_column(
                "auth_sessions",
                sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            )
            bind.execute(sa.text(
                "UPDATE auth_sessions SET expires_at = last_seen_at + INTERVAL '30 days'"
            ))
            op.alter_column("auth_sessions", "expires_at", nullable=False)

        existing_indexes = {idx["name"] for idx in inspector.get_indexes("auth_sessions")}
        if "idx_auth_sessions_expires_at" not in existing_indexes:
            op.create_index("idx_auth_sessions_expires_at", "auth_sessions", ["expires_at"])

    # ── style_samples: add text_hash for deduplication ───────────────────────
    if "style_samples" in tables:
        existing_cols = {c["name"] for c in inspector.get_columns("style_samples")}
        if "text_hash" not in existing_cols:
            op.add_column(
                "style_samples",
                sa.Column("text_hash", sa.String(64), nullable=True),
            )
            # Backfill hashes for existing rows using MD5 (available in Postgres)
            bind.execute(sa.text(
                "UPDATE style_samples SET text_hash = md5(text)"
            ))

        existing_indexes = {idx["name"] for idx in inspector.get_indexes("style_samples")}
        if "idx_style_samples_hash" not in existing_indexes:
            op.create_index("idx_style_samples_hash", "style_samples", ["text_hash"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    def _drop_index_if_exists(table: str, idx: str) -> None:
        idxs = {i["name"] for i in inspector.get_indexes(table)} if table in tables else set()
        if idx in idxs:
            op.drop_index(idx, table_name=table)

    def _drop_fk_if_exists(table: str, fk: str) -> None:
        fks = {f["name"] for f in inspector.get_foreign_keys(table)} if table in tables else set()
        if fk in fks:
            op.drop_constraint(fk, table, type_="foreignkey")

    _drop_index_if_exists("style_samples", "idx_style_samples_hash")
    if "style_samples" in tables:
        cols = {c["name"] for c in inspector.get_columns("style_samples")}
        if "text_hash" in cols:
            op.drop_column("style_samples", "text_hash")

    _drop_index_if_exists("auth_sessions", "idx_auth_sessions_expires_at")
    if "auth_sessions" in tables:
        cols = {c["name"] for c in inspector.get_columns("auth_sessions")}
        if "expires_at" in cols:
            op.drop_column("auth_sessions", "expires_at")

    _drop_index_if_exists("generated_posts", "idx_gen_posts_kind_status_updated")
    _drop_fk_if_exists("generated_posts", "fk_gen_posts_run_id")
    if "generated_posts" in tables:
        op.alter_column("generated_posts", "run_id", nullable=False)

    _drop_fk_if_exists("insights", "fk_insights_run_id")
    if "insights" in tables:
        op.alter_column("insights", "run_id", nullable=False)

    _drop_fk_if_exists("chat_messages", "fk_chat_messages_run_id")
