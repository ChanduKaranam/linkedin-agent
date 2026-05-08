from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_TOPICS_YAML = Path(__file__).parent.parent.parent / "topics.yaml"
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_LOGS_DIR = Path(__file__).parent.parent.parent / "logs"
_CACHE_DIR = _DATA_DIR / "cache"
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Limits(BaseModel):
    max_sources_per_run: int = 30
    max_per_query: int = 10
    scrape_timeout_seconds: int = 25
    scrape_concurrency: int = 4
    per_domain_rps: float = 0.5
    summarize_max_chars_per_source: int = 6000
    cluster_snippet_chars: int = 400
    cache_ttl_hours: int = 18
    max_articles_for_synthesis: int = 25  # cap articles sent to LLM


class Models(BaseModel):
    cluster: str = "mistral/mistral-small-latest"
    summarize: str = "mistral/mistral-small-latest"


class ChatBudget(BaseModel):
    max_tool_calls: int = 4
    max_history_turns: int = 12
    source_chars_per_doc: int = 6000


class Dedup(BaseModel):
    cross_day_window: int = 3


class TopicConfig(BaseModel):
    topic: str
    timezone: str = "Asia/Kolkata"
    schedule_hour: int = Field(default=4, ge=0, le=23)
    schedule_minute: int = Field(default=0, ge=0, le=59)
    queries: Annotated[list[str], Field(min_length=1, max_length=8)]
    limits: Limits = Limits()
    models: Models = Models()
    chat: ChatBudget = ChatBudget()
    dedup: Dedup = Dedup()
    blocked_domains: list[str] = []

    @field_validator("queries")
    @classmethod
    def queries_not_empty(cls, v: list[str]) -> list[str]:
        if any(not q.strip() for q in v):
            raise ValueError("queries must not contain empty strings")
        return v

    def is_domain_blocked(self, domain: str) -> bool:
        for pattern in self.blocked_domains:
            if "*" in pattern:
                regex = re.escape(pattern).replace(r"\*", ".*")
                if re.fullmatch(regex, domain, re.IGNORECASE):
                    return True
            elif domain.lower() == pattern.lower():
                return True
        return False


def load_topic_config(path: Path = _TOPICS_YAML) -> TopicConfig:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return TopicConfig.model_validate(data)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    mistral_api_key: str = ""
    tavily_api_key: str = ""
    debug: bool = False
    enable_inprocess_scheduler: bool = False
    tz: str = "Asia/Kolkata"
    litellm_request_timeout: int = 60
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/trend_agent"
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = "http://localhost:8000/admin/linkedin/callback"
    frontend_base_url: str = "http://localhost:3000"
    linkedin_token_key: str = ""  # Fernet key for token encryption — generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    slack_bot_token: str = ""
    slack_default_channel_id: str = ""
    session_cookie_name: str = "session_id"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    # Production controls for ad-hoc search memory/cost pressure.
    adhoc_max_sources_per_run: int = 16
    adhoc_max_per_query: int = 6
    adhoc_scrape_concurrency: int = 4
    adhoc_summarize_max_chars_per_source: int = 2500
    rag_disable_rerank: bool = False
    # Use API-based embedding (Mistral) instead of local fastembed model.
    # Saves ~120 MB RAM on constrained hosts. Auto-enabled on Render.
    rag_use_api_embed: bool = False
    run_pipeline_in_web_process: bool = True
    worker_poll_seconds: int = 5
    db_pool_size: int = 2
    db_max_overflow: int = 3
    db_pool_timeout: int = 20
    db_pool_recycle: int = 900
    # Skips Crawl4AI/Playwright; uses httpx+trafilatura only.
    # Auto-detects Render (RENDER env var) — override with SCRAPE_USE_HTTPX_ONLY=false
    # if you need JS rendering on Render (requires playwright install step).
    scrape_use_httpx_only: bool = False
    # Optional Jina AI Reader API key for higher rate limits (free without key: ~20 RPM).
    # Sign up at https://jina.ai to get a key.
    jina_api_key: str = ""
    # Max sources to discover per pipeline run on Render (lower = less peak RAM)
    render_max_sources_per_run: int = 15
    render_max_per_query: int = 5

    @model_validator(mode="after")
    def _auto_render_settings(self) -> "Settings":
        import os
        on_render = bool(os.environ.get("RENDER"))
        if on_render and not os.environ.get("SCRAPE_USE_HTTPX_ONLY"):
            object.__setattr__(self, "scrape_use_httpx_only", True)
        # Disable cross-encoder reranker on Render — saves ~110 MB of RAM.
        if on_render and not os.environ.get("RAG_DISABLE_RERANK"):
            object.__setattr__(self, "rag_disable_rerank", True)
        # Use API-based embedding on Render — saves ~120 MB (no fastembed model loaded).
        # RAG still works fully via Mistral's embedding API.
        if on_render and not os.environ.get("RAG_USE_API_EMBED"):
            object.__setattr__(self, "rag_use_api_embed", True)
        # Cap ad-hoc scrape concurrency to 2 on Render to keep peak RAM under 512 MB.
        if on_render and not os.environ.get("ADHOC_SCRAPE_CONCURRENCY"):
            object.__setattr__(self, "adhoc_scrape_concurrency", 2)
        # Tighter DB pool on Render — fewer idle connections = less RSS.
        if on_render and not os.environ.get("DB_POOL_SIZE"):
            object.__setattr__(self, "db_pool_size", 1)
        if on_render and not os.environ.get("DB_MAX_OVERFLOW"):
            object.__setattr__(self, "db_max_overflow", 2)
        # Reduce max chars per source on Render to lower peak string memory.
        if on_render and not os.environ.get("ADHOC_SUMMARIZE_MAX_CHARS_PER_SOURCE"):
            object.__setattr__(self, "adhoc_summarize_max_chars_per_source", 1500)
        return self
    auth_last_seen_update_seconds: int = 300
    auth_cache_ttl_seconds: int = 20

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Ensure async SQLAlchemy URL and tolerate provider-specific URL params."""
        if v is None:
            return v
        url = str(v).strip()
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]


        split = urlsplit(url)
        if split.query:
            params = parse_qsl(split.query, keep_blank_values=True)
            rewritten: list[tuple[str, str]] = []
            for key, value in params:
                if key.lower() == "sslmode" and not any(k.lower() == "ssl" for k, _ in params):
                    rewritten.append(("ssl", value or "require"))
                else:
                    rewritten.append((key, value))
            url = urlunsplit((split.scheme, split.netloc, split.path, urlencode(rewritten), split.fragment))
        return url

    @property
    def db_path(self) -> Path:
        # Kept for one-shot migration script only; not used at runtime.
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        return _DATA_DIR / "trends.db"

    @property
    def logs_dir(self) -> Path:
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        return _LOGS_DIR

    @property
    def cache_dir(self) -> Path:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return _CACHE_DIR


_settings: Settings | None = None
_topic_config: TopicConfig | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_topic_config() -> TopicConfig:
    global _topic_config
    if _topic_config is None:
        cfg = load_topic_config()
        # On Render, cap limits to keep peak memory under 512 MB
        import os
        if os.environ.get("RENDER"):
            settings = get_settings()
            cfg = cfg.model_copy(update={
                "limits": cfg.limits.model_copy(update={
                    "max_sources_per_run": min(cfg.limits.max_sources_per_run, settings.render_max_sources_per_run),
                    "max_per_query": min(cfg.limits.max_per_query, settings.render_max_per_query),
                    "scrape_concurrency": min(cfg.limits.scrape_concurrency, 2),
                    "summarize_max_chars_per_source": min(cfg.limits.summarize_max_chars_per_source, 3000),
                    "max_articles_for_synthesis": min(cfg.limits.max_articles_for_synthesis, 15),
                })
            })
        _topic_config = cfg
    return _topic_config


def get_schedule_info() -> dict:
    cfg = get_topic_config()
    return {"hour": cfg.schedule_hour, "minute": cfg.schedule_minute, "timezone": cfg.timezone}


def update_schedule(hour: int, minute: int) -> None:
    global _topic_config
    with open(_TOPICS_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    data["schedule_hour"] = hour
    data["schedule_minute"] = minute
    with open(_TOPICS_YAML, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    _topic_config = None
