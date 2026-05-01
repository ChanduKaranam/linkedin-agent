"""Initial schema: all tables + pgvector chunks

Revision ID: 0001
Revises:
Create Date: 2026-04-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "runs",
        sa.Column("run_id", sa.String, primary_key=True),
        sa.Column("run_date", sa.Date, nullable=False),
        sa.Column("topic", sa.String, nullable=False),
        sa.Column("kind", sa.String, nullable=False, server_default="daily"),
        sa.Column("state", sa.String, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trend_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("warnings", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.UniqueConstraint("run_date", "topic", name="uq_runs_date_topic"),
    )
    op.create_index("idx_runs_kind_topic_date", "runs", ["kind", "topic", "run_date"])

    op.create_table(
        "trends",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String, sa.ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_date", sa.Date, nullable=False),
        sa.Column("slug", sa.String, nullable=False),
        sa.Column("headline", sa.Text, nullable=False),
        sa.Column("one_liner", sa.Text, nullable=False),
        sa.Column("detailed_markdown", sa.Text, nullable=False),
        sa.Column("key_points_json", JSONB, nullable=False),
        sa.Column("sources_json", JSONB, nullable=False),
        sa.Column("fingerprint", sa.String, nullable=False),
        sa.Column("seen_again", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_date", "slug", name="uq_trends_date_slug"),
    )
    op.create_index("idx_trends_run_date", "trends", ["run_date"])
    op.create_index("idx_trends_fingerprint", "trends", ["fingerprint"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String, nullable=False),
        sa.Column("run_date", sa.Date, nullable=False),
        sa.Column("slug", sa.String, nullable=False),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("citations_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("used_web", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_chat_date_slug", "chat_messages", ["run_date", "slug", "created_at"])
    op.create_index("idx_chat_run_slug", "chat_messages", ["run_id", "slug", "created_at"])

    op.create_table(
        "insights",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String, nullable=False),
        sa.Column("run_date", sa.Date, nullable=False),
        sa.Column("slug", sa.String, nullable=False),
        sa.Column("user_perspective", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("tags_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_insights_date_slug", "insights", ["run_date", "slug"])
    op.create_index("idx_insights_run_slug", "insights", ["run_id", "slug"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("trend_id", sa.BigInteger, sa.ForeignKey("trends.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String, nullable=False),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("source_title", sa.Text, nullable=False),
        sa.Column("source_domain", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("tsv", TSVECTOR, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("trend_id", "source_url", "chunk_index", name="uq_chunk_trend_source_idx"),
    )
    op.create_index("idx_chunks_trend_id", "chunks", ["trend_id"])
    op.execute(
        "CREATE INDEX idx_chunks_tsv_gin ON chunks USING GIN (tsv)"
    )
    op.execute(
        "CREATE INDEX idx_chunks_embedding_ivfflat "
        "ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    # Trigger: auto-populate tsv from text on insert/update
    op.execute("""
        CREATE OR REPLACE FUNCTION chunks_tsv_update() RETURNS trigger AS $$
        BEGIN
            NEW.tsv := to_tsvector('english', NEW.text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER chunks_tsv_trigger
        BEFORE INSERT OR UPDATE OF text ON chunks
        FOR EACH ROW EXECUTE FUNCTION chunks_tsv_update()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS chunks_tsv_trigger ON chunks")
    op.execute("DROP FUNCTION IF EXISTS chunks_tsv_update()")
    op.drop_table("chunks")
    op.drop_table("insights")
    op.drop_table("chat_messages")
    op.drop_table("trends")
    op.drop_table("runs")
    op.execute("DROP EXTENSION IF EXISTS vector")
