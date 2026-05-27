"""Add user_id column for per-user data isolation

- Adds user_id SERIAL PK to users table
- Adds user_id FK to auth_sessions, chat_messages, insights, style_samples, generated_posts
- Recreates style_profile and linkedin_account tables with user_id as PK
- Adds user_id to runs table for adhoc search runs

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # ── 1. users — add user_id SERIAL PK, keep username unique ──────────────
    if "users" in tables:
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "user_id" not in user_cols:
            op.execute("ALTER TABLE users ADD COLUMN user_id INTEGER")
            op.execute("CREATE SEQUENCE IF NOT EXISTS users_user_id_seq OWNED BY users.user_id")
            op.execute("ALTER TABLE users ALTER COLUMN user_id SET DEFAULT nextval('users_user_id_seq')")

        # Drop old FK on auth_sessions BEFORE changing users PK
        if "auth_sessions" in tables:
            fks = inspector.get_foreign_keys("auth_sessions")
            for fk in fks:
                if fk.get("name"):
                    op.execute(f"ALTER TABLE auth_sessions DROP CONSTRAINT {fk['name']}")

        # Backfill and change PK
        op.execute("SELECT setval('users_user_id_seq', COALESCE((SELECT MAX(user_id) FROM users), 0) + 1, false)")
        op.execute("UPDATE users SET user_id = nextval('users_user_id_seq') WHERE user_id IS NULL")
        op.execute("ALTER TABLE users ALTER COLUMN user_id SET NOT NULL")
        op.execute("ALTER TABLE users DROP CONSTRAINT users_pkey CASCADE")
        op.execute("ALTER TABLE users ADD PRIMARY KEY (user_id)")
        op.execute("ALTER TABLE users ADD CONSTRAINT users_username_key UNIQUE (username)")

    # ── 2. auth_sessions — add user_id, link FK ────────────────────────────
    if "auth_sessions" in tables:
        cols = {c["name"] for c in inspector.get_columns("auth_sessions")}
        if "user_id" not in cols:
            op.execute("ALTER TABLE auth_sessions ADD COLUMN user_id INTEGER")
        op.execute(
            "UPDATE auth_sessions s SET user_id = u.user_id "
            "FROM users u WHERE s.username = u.username"
        )
        op.execute("ALTER TABLE auth_sessions ALTER COLUMN user_id SET NOT NULL")
        op.execute(
            "ALTER TABLE auth_sessions ADD CONSTRAINT fk_auth_sessions_user_id "
            "FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE"
        )

    # ── 3. chat_messages — add user_id ──────────────────────────────────────
    if "chat_messages" in tables:
        cols = {c["name"] for c in inspector.get_columns("chat_messages")}
        if "user_id" not in cols:
            op.execute("ALTER TABLE chat_messages ADD COLUMN user_id INTEGER")
            op.execute("UPDATE chat_messages SET user_id = (SELECT MIN(user_id) FROM users)")
            op.execute("ALTER TABLE chat_messages ALTER COLUMN user_id SET NOT NULL")
            op.execute(
                "ALTER TABLE chat_messages ADD CONSTRAINT fk_chat_messages_user_id "
                "FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE"
            )

    # ── 4. insights — add user_id ───────────────────────────────────────────
    if "insights" in tables:
        cols = {c["name"] for c in inspector.get_columns("insights")}
        if "user_id" not in cols:
            op.execute("ALTER TABLE insights ADD COLUMN user_id INTEGER")
            op.execute("UPDATE insights SET user_id = (SELECT MIN(user_id) FROM users)")
            op.execute("ALTER TABLE insights ALTER COLUMN user_id SET NOT NULL")
            op.execute(
                "ALTER TABLE insights ADD CONSTRAINT fk_insights_user_id "
                "FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE"
            )

    # ── 5. style_samples — add user_id ──────────────────────────────────────
    if "style_samples" in tables:
        cols = {c["name"] for c in inspector.get_columns("style_samples")}
        if "user_id" not in cols:
            op.execute("ALTER TABLE style_samples ADD COLUMN user_id INTEGER")
            op.execute("UPDATE style_samples SET user_id = (SELECT MIN(user_id) FROM users)")
            op.execute("ALTER TABLE style_samples ALTER COLUMN user_id SET NOT NULL")
            op.execute(
                "ALTER TABLE style_samples ADD CONSTRAINT fk_style_samples_user_id "
                "FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE"
            )

    # ── 6. generated_posts — add user_id ────────────────────────────────────
    if "generated_posts" in tables:
        cols = {c["name"] for c in inspector.get_columns("generated_posts")}
        if "user_id" not in cols:
            op.execute("ALTER TABLE generated_posts ADD COLUMN user_id INTEGER")
            op.execute("UPDATE generated_posts SET user_id = (SELECT MIN(user_id) FROM users)")
            op.execute("ALTER TABLE generated_posts ALTER COLUMN user_id SET NOT NULL")
            op.execute(
                "ALTER TABLE generated_posts ADD CONSTRAINT fk_generated_posts_user_id "
                "FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE"
            )

    # ── 7. style_profile — recreate with user_id PK ─────────────────────────
    if "style_profile" in tables:
        cols = {c["name"] for c in inspector.get_columns("style_profile")}
        if "user_id" not in cols:
            op.create_table(
                "style_profile_new",
                sa.Column("user_id", sa.Integer(), primary_key=True),
                sa.Column("profile_markdown", sa.Text(), nullable=False, server_default=""),
                sa.Column("sample_count_at_last_refresh", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            )
            first_user = bind.execute(
                sa.text("SELECT MIN(user_id) FROM users")
            ).scalar()
            if first_user:
                bind.execute(
                    sa.text(
                        "INSERT INTO style_profile_new (user_id, profile_markdown, sample_count_at_last_refresh, updated_at) "
                        "SELECT :uid, profile_markdown, sample_count_at_last_refresh, updated_at "
                        "FROM style_profile WHERE id = 1"
                    ),
                    {"uid": first_user},
                )
            op.execute("ALTER TABLE style_profile_new ADD FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE")
            op.drop_table("style_profile")
            op.rename_table("style_profile_new", "style_profile")

    # ── 8. linkedin_account — recreate with user_id PK ──────────────────────
    if "linkedin_account" in tables:
        cols = {c["name"] for c in inspector.get_columns("linkedin_account")}
        if "user_id" not in cols:
            op.create_table(
                "linkedin_account_new",
                sa.Column("user_id", sa.Integer(), primary_key=True),
                sa.Column("access_token", sa.Text(), nullable=False),
                sa.Column("refresh_token", sa.Text(), nullable=True),
                sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("member_urn", sa.String(), nullable=False),
                sa.Column("member_name", sa.Text(), nullable=True),
            )
            first_user = bind.execute(
                sa.text("SELECT MIN(user_id) FROM users")
            ).scalar()
            if first_user:
                bind.execute(
                    sa.text(
                        "INSERT INTO linkedin_account_new (user_id, access_token, refresh_token, expires_at, member_urn, member_name) "
                        "SELECT :uid, access_token, refresh_token, expires_at, member_urn, member_name "
                        "FROM linkedin_account WHERE id = 1"
                    ),
                    {"uid": first_user},
                )
            op.execute("ALTER TABLE linkedin_account_new ADD FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE")
            op.drop_table("linkedin_account")
            op.rename_table("linkedin_account_new", "linkedin_account")

    # ── 9. runs — add user_id (nullable, for adhoc search runs) ────────────
    if "runs" in tables:
        cols = {c["name"] for c in inspector.get_columns("runs")}
        if "user_id" not in cols:
            op.execute("ALTER TABLE runs ADD COLUMN user_id INTEGER")
            op.execute(
                "ALTER TABLE runs ADD CONSTRAINT fk_runs_user_id "
                "FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE SET NULL"
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # Reverse order (roughly)

    # 9. runs — drop user_id
    if "runs" in tables:
        cols = {c["name"] for c in inspector.get_columns("runs")}
        if "user_id" in cols:
            op.execute("ALTER TABLE runs DROP CONSTRAINT fk_runs_user_id")
            op.execute("ALTER TABLE runs DROP COLUMN user_id")

    # 8. linkedin_account — restore singleton
    if "linkedin_account" in tables:
        cols = {c["name"] for c in inspector.get_columns("linkedin_account")}
        if "user_id" in cols and "id" not in cols:
            op.create_table(
                "linkedin_account_old",
                sa.Column("id", sa.Integer(), primary_key=True, server_default=sa.text("1")),
                sa.Column("access_token", sa.Text(), nullable=False),
                sa.Column("refresh_token", sa.Text(), nullable=True),
                sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("member_urn", sa.String(), nullable=False),
                sa.Column("member_name", sa.Text(), nullable=True),
            )
            bind.execute(
                sa.text(
                    "INSERT INTO linkedin_account_old (id, access_token, refresh_token, expires_at, member_urn, member_name) "
                    "SELECT 1, access_token, refresh_token, expires_at, member_urn, member_name "
                    "FROM linkedin_account LIMIT 1"
                )
            )
            op.drop_table("linkedin_account")
            op.rename_table("linkedin_account_old", "linkedin_account")

    # 7. style_profile — restore singleton
    if "style_profile" in tables:
        cols = {c["name"] for c in inspector.get_columns("style_profile")}
        if "user_id" in cols and "id" not in cols:
            op.create_table(
                "style_profile_old",
                sa.Column("id", sa.Integer(), primary_key=True, server_default=sa.text("1")),
                sa.Column("profile_markdown", sa.Text(), nullable=False, server_default=""),
                sa.Column("sample_count_at_last_refresh", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            )
            bind.execute(
                sa.text(
                    "INSERT INTO style_profile_old (id, profile_markdown, sample_count_at_last_refresh, updated_at) "
                    "SELECT 1, profile_markdown, sample_count_at_last_refresh, updated_at "
                    "FROM style_profile LIMIT 1"
                )
            )
            op.drop_table("style_profile")
            op.rename_table("style_profile_old", "style_profile")

    # 6. generated_posts
    if "generated_posts" in tables:
        cols = {c["name"] for c in inspector.get_columns("generated_posts")}
        if "user_id" in cols:
            op.execute("ALTER TABLE generated_posts DROP CONSTRAINT fk_generated_posts_user_id")
            op.execute("ALTER TABLE generated_posts DROP COLUMN user_id")

    # 5. style_samples
    if "style_samples" in tables:
        cols = {c["name"] for c in inspector.get_columns("style_samples")}
        if "user_id" in cols:
            op.execute("ALTER TABLE style_samples DROP CONSTRAINT fk_style_samples_user_id")
            op.execute("ALTER TABLE style_samples DROP COLUMN user_id")

    # 4. insights
    if "insights" in tables:
        cols = {c["name"] for c in inspector.get_columns("insights")}
        if "user_id" in cols:
            op.execute("ALTER TABLE insights DROP CONSTRAINT fk_insights_user_id")
            op.execute("ALTER TABLE insights DROP COLUMN user_id")

    # 3. chat_messages
    if "chat_messages" in tables:
        cols = {c["name"] for c in inspector.get_columns("chat_messages")}
        if "user_id" in cols:
            op.execute("ALTER TABLE chat_messages DROP CONSTRAINT fk_chat_messages_user_id")
            op.execute("ALTER TABLE chat_messages DROP COLUMN user_id")

    # 2. auth_sessions
    if "auth_sessions" in tables:
        cols = {c["name"] for c in inspector.get_columns("auth_sessions")}
        if "user_id" in cols:
            op.execute("ALTER TABLE auth_sessions DROP CONSTRAINT fk_auth_sessions_user_id")
            op.execute("ALTER TABLE auth_sessions DROP COLUMN user_id")
            # Restore FK on username
            op.execute(
                "ALTER TABLE auth_sessions ADD CONSTRAINT auth_sessions_username_fkey "
                "FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE"
            )

    # 1. users — restore username PK
    if "users" in tables:
        cols = {c["name"] for c in inspector.get_columns("users")}
        if "user_id" in cols:
            op.execute("ALTER TABLE users DROP CONSTRAINT users_username_key")
            op.execute("ALTER TABLE users DROP CONSTRAINT users_pkey")
            op.execute("ALTER TABLE users ADD PRIMARY KEY (username)")
            op.execute("ALTER TABLE users DROP COLUMN user_id")
