from __future__ import annotations

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        UniqueConstraint("run_date", "topic", name="uq_runs_date_topic"),
        Index("idx_runs_kind_topic_date", "kind", "topic", "run_date"),
    )

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False, default="daily")
    state: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trend_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    trends: Mapped[list[Trend]] = relationship("Trend", back_populates="run", cascade="all, delete-orphan")


class Trend(Base):
    __tablename__ = "trends"
    __table_args__ = (
        UniqueConstraint("run_date", "slug", name="uq_trends_date_slug"),
        Index("idx_trends_run_date", "run_date"),
        Index("idx_trends_fingerprint", "fingerprint"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    one_liner: Mapped[str] = mapped_column(Text, nullable=False)
    detailed_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    key_points_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    sources_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    seen_again: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    run: Mapped[Run] = relationship("Run", back_populates="trends")
    chunks: Mapped[list[Chunk]] = relationship("Chunk", back_populates="trend", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("idx_chat_date_slug", "run_date", "slug", "created_at"),
        Index("idx_chat_run_slug", "run_id", "slug", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    used_web: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Insight(Base):
    __tablename__ = "insights"
    __table_args__ = (
        Index("idx_insights_date_slug", "run_date", "slug"),
        Index("idx_insights_run_slug", "run_id", "slug"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    user_perspective: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StyleSample(Base):
    __tablename__ = "style_samples"
    __table_args__ = (Index("idx_style_samples_created", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, nullable=False)  # chat | insight | post_edit
    source_ref: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StyleProfile(Base):
    __tablename__ = "style_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    profile_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sample_count_at_last_refresh: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GeneratedPost(Base):
    __tablename__ = "generated_posts"
    __table_args__ = (
        Index("idx_gen_posts_run_date_slug", "run_date", "slug"),
        Index("idx_gen_posts_run_id_slug", "run_id", "slug"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # linkedin | blog
    run_id: Mapped[str] = mapped_column(String, nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    tags_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")  # draft | edited | published
    linkedin_post_urn: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LinkedInAccount(Base):
    __tablename__ = "linkedin_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    member_urn: Mapped[str] = mapped_column(String, nullable=False)
    member_name: Mapped[str | None] = mapped_column(Text, nullable=True)


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("trend_id", "source_url", "chunk_index", name="uq_chunk_trend_source_idx"),
        Index("idx_chunks_trend_id", "trend_id"),
        # ivfflat and GIN indexes created in Alembic migration (not expressible here)
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trend_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trends.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_title: Mapped[str] = mapped_column(Text, nullable=False)
    source_domain: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # 384-dim for BAAI/bge-small-en-v1.5
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    # stored tsvector for BM25 — populated by Postgres trigger (see migration)
    tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    trend: Mapped[Trend] = relationship("Trend", back_populates="chunks")
