# LinkedIn Agent

An AI-powered trend intelligence system that automatically discovers, scrapes, and synthesizes daily news on any topic, then helps you generate and publish LinkedIn posts and blog articles — written in your own voice.

---

## Table of Contents

- [What This Project Does](#what-this-project-does)
- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Backend Setup](#2-backend-setup)
  - [3. Frontend Setup](#3-frontend-setup)
  - [4. Database Setup](#4-database-setup)
  - [5. Environment Variables](#5-environment-variables)
  - [6. Topic Configuration](#6-topic-configuration)
  - [7. LinkedIn OAuth Setup](#7-linkedin-oauth-setup)
- [Running the Project](#running-the-project)
  - [Start the Backend](#start-the-backend)
  - [Start the Frontend](#start-the-frontend)
  - [Triggering the Pipeline Manually](#triggering-the-pipeline-manually)
- [Project Structure](#project-structure)
- [Detailed Project Explanation](#detailed-project-explanation)
  - [The Pipeline (How Trends Are Discovered)](#the-pipeline-how-trends-are-discovered)
  - [RAG Chat (Ask Questions About Trends)](#rag-chat-ask-questions-about-trends)
  - [Post Studio (Generate LinkedIn & Blog Posts)](#post-studio-generate-linkedin--blog-posts)
  - [Style Learning](#style-learning)
  - [LinkedIn Publishing](#linkedin-publishing)
  - [Deduplication System](#deduplication-system)
  - [Scheduler](#scheduler)
- [Operational Notes](#operational-notes)

---

## What This Project Does

LinkedIn Agent runs a daily AI pipeline that:

1. **Discovers** fresh articles from the web (via Tavily or DuckDuckGo) based on search queries you define in `topics.yaml`
2. **Scrapes** each article using a headless browser (Crawl4AI + Playwright)
3. **Synthesizes** 5–15 distinct story summaries using an LLM (Mistral via LiteLLM)
4. **Indexes** all scraped content into a PostgreSQL vector database (pgvector) for semantic search
5. **Exposes** all of this through a REST API and a React frontend where you can:
   - Browse today's AI/tech trends
   - Chat with an AI that has read all the articles (RAG)
   - Generate LinkedIn posts and blog articles from any trend
   - Publish directly to your LinkedIn profile

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Port 3000)                  │
│         Vite 6 + React 19 + React Router v7              │
│         Express proxy layer (server.ts)                  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (proxied /api/*)
┌──────────────────────▼──────────────────────────────────┐
│                   Backend (Port 8000)                    │
│                   FastAPI + Uvicorn                      │
│                                                          │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │  Pipeline   │  │ RAG Layer  │  │   Post Studio    │  │
│  │  (daily)    │  │ (pgvector) │  │  (LLM + style)   │  │
│  └──────┬──────┘  └─────┬──────┘  └────────┬─────────┘  │
│         │               │                  │             │
│  ┌──────▼───────────────▼──────────────────▼──────────┐  │
│  │              PostgreSQL + pgvector                  │  │
│  │   runs / trends / chunks / style_samples /          │  │
│  │   style_profile / generated_posts / linkedin_account│  │
│  └──────────────────────────────────────────────────── ┘  │
└─────────────────────────────────────────────────────────┘
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
       Tavily /    Crawl4AI     LinkedIn
      DuckDuckGo  (scraper)   Posts API
      (search)               (publish)
```

**Data flow:**
- Pipeline runs daily at a configured time (default 4:00 AM IST): search → scrape → LLM synthesize → persist to DB → index into pgvector
- Frontend fetches trends via REST API, enables chat over indexed content, and sends post generation requests to the backend LLM
- All API calls from the frontend go through the Express proxy in `server.ts` (no direct browser → FastAPI calls)

---

## Prerequisites

| Tool | Minimum Version | Notes |
|------|----------------|-------|
| Python | 3.10+ | 3.11 recommended |
| Node.js | 18+ | 20 LTS recommended |
| PostgreSQL | 14+ | Must have the `pgvector` extension |
| Git | any | — |

You also need at least one of the following:

- **Mistral API key** — for LLM synthesis and post generation (required)
- **Tavily API key** — for web search (optional; falls back to DuckDuckGo)

---

## Setup

### 1. Clone the Repository

```bash
git clone <repo-url>
cd LinkedIn_agent
```

### 2. Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv

# On Windows
.venv\Scripts\activate

# On macOS/Linux
source .venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# Install the backend package in editable mode
pip install -e .

# Install Playwright browser binaries (required for Crawl4AI scraping)
playwright install chromium
```

### 3. Frontend Setup

```bash
cd frontend
npm install
```

### 4. Database Setup

**Step 1: Create the PostgreSQL database**

```sql
-- Run in psql or any Postgres client
CREATE DATABASE trend_agent;
```

**Step 2: Install the pgvector extension** (must be done once per database)

```sql
\c trend_agent
CREATE EXTENSION IF NOT EXISTS vector;
```

**Step 3: Run database migrations**

```bash
cd backend

# Make sure your .env file is set up first (see next section)
alembic upgrade head
```

This creates all tables: `runs`, `trends`, `chat_messages`, `insights`, `chunks`, `style_samples`, `style_profile`, `generated_posts`, `linkedin_account`.

### 5. Environment Variables

Copy the example file and fill in your values:

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env`:

```env
# Required — LLM provider (Mistral)
MISTRAL_API_KEY=your_mistral_api_key_here

# Optional — better search quality (falls back to DuckDuckGo if not set)
TAVILY_API_KEY=your_tavily_api_key_here

# Required — PostgreSQL connection string
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/trend_agent

# Set to true to run the daily pipeline automatically inside the server process
ENABLE_INPROCESS_SCHEDULER=false

# Set to true to expose /docs (Swagger UI) and all /admin/* routes
DEBUG=false

# LinkedIn OAuth (only needed if you want to publish to LinkedIn)
LINKEDIN_CLIENT_ID=your_linkedin_client_id
LINKEDIN_CLIENT_SECRET=your_linkedin_client_secret
LINKEDIN_REDIRECT_URI=http://localhost:8000/admin/linkedin/callback
```

Copy the example file for the frontend too:

```bash
cd frontend
cp .env.example .env
```

Edit `frontend/.env`:

```env
BACKEND_URL=http://127.0.0.1:8000
PORT=3000
```

### 6. Topic Configuration

Edit `backend/topics.yaml` to control what the pipeline searches for:

```yaml
topic: AI & tech            # Human-readable topic name shown in the UI
timezone: Asia/Kolkata      # Scheduler timezone
schedule_hour: 4            # Run at 4:00 AM in the timezone above
schedule_minute: 0

queries:                    # Search queries sent to Tavily/DuckDuckGo
  - AI model releases last 24 hours
  - artificial intelligence news today
  - tech company announcements today
  - AI research papers released today
  - machine learning tools launched this week

limits:
  max_sources_per_run: 30   # Max URLs to scrape per run
  max_per_query: 10         # Max results per search query
  scrape_concurrency: 4     # Parallel scrapers
  scrape_timeout_seconds: 25

models:
  cluster: mistral/mistral-large-latest
  summarize: mistral/mistral-large-latest

dedup:
  cross_day_window: 7       # Days to look back for duplicate story detection

blocked_domains:            # Sites to skip entirely
  - pinterest.com
  - youtube.com/shorts
  - facebook.com
  - instagram.com
  - tiktok.com
  - medium.com
```

### 7. LinkedIn OAuth Setup

To enable publishing posts directly to LinkedIn:

1. Go to [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps) and create a new app
2. Under **Products**, request access to **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**
3. Under **Auth**, add the redirect URI: `http://localhost:8000/admin/linkedin/callback`
4. Copy your **Client ID** and **Client Secret** into `backend/.env`
5. Set `DEBUG=true` in `.env` (required to expose `/admin/*` routes)
6. Start the backend, open the frontend, and click **Connect LinkedIn** in the settings

> **Note:** LinkedIn access tokens expire after 60 days. You will need to reconnect when they expire — LinkedIn does not provide refresh tokens for personal OAuth flows.

---

## Running the Project

Open two terminal windows.

### Start the Backend

```bash
cd backend

# Activate the virtual environment first
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Windows: set UTF-8 encoding (required for Crawl4AI output)
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

# Start the server
python run.py
```

The backend starts at `http://localhost:8000`.

If `DEBUG=true` in your `.env`, the Swagger docs are available at `http://localhost:8000/docs`.

### Start the Frontend

```bash
cd frontend
npm run dev
```

The frontend starts at `http://localhost:3000`.

Open your browser and navigate to `http://localhost:3000`.

### Triggering the Pipeline Manually

The pipeline normally runs on the schedule defined in `topics.yaml`. To trigger it immediately:

**Option A — Via the API** (requires `DEBUG=true`):
```bash
curl -X POST http://localhost:8000/admin/run-now
```

**Option B — Reset and re-run today's pipeline** (deletes today's existing run first):
```bash
cd backend
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
.venv\Scripts\python.exe scripts/reset_today.py
```

> Warning: `reset_today.py` deletes ALL runs for today and runs the full pipeline synchronously. It takes approximately 30 minutes due to RAG indexing. Do not use while the backend is serving live traffic.

---

## Project Structure

```
LinkedIn_agent/
├── backend/
│   ├── src/backend/
│   │   ├── agent/              # LLM agents (synthesis, chat, post writing)
│   │   │   ├── tools/          # Web search, scraping, robots.txt tools
│   │   │   ├── trend_agent.py  # Daily synthesis + ad-hoc search synthesis
│   │   │   ├── chat_agent.py   # RAG chat with tool-calling loop
│   │   │   ├── post_writer.py  # LinkedIn & blog post generation
│   │   │   └── prompts.py      # All LLM prompt strings
│   │   ├── api/                # FastAPI routes
│   │   │   ├── main.py         # App factory, lifecycle, middleware
│   │   │   ├── routes_trends.py
│   │   │   ├── routes_search.py
│   │   │   ├── routes_chat.py
│   │   │   ├── routes_posts.py
│   │   │   ├── routes_admin.py
│   │   │   └── schemas.py      # Pydantic request/response types
│   │   ├── rag/                # Vector indexing and retrieval
│   │   │   ├── indexer.py      # Chunk + embed scraped pages
│   │   │   ├── embedder.py     # fastembed (BAAI/bge-small-en-v1.5)
│   │   │   ├── chunker.py      # Markdown → passage chunks
│   │   │   └── retriever.py    # Hybrid pgvector + BM25 search
│   │   ├── integrations/
│   │   │   └── linkedin.py     # OAuth 2.0 + Posts API publisher
│   │   ├── scheduler/
│   │   │   └── daily_job.py    # APScheduler wrapper
│   │   ├── style/
│   │   │   ├── collector.py    # Records user writing samples
│   │   │   └── profile.py      # Distils samples into a style guide
│   │   ├── config.py           # Settings (reads .env + topics.yaml)
│   │   ├── models.py           # Pydantic domain models
│   │   ├── db_models.py        # SQLAlchemy ORM models
│   │   ├── db.py               # Async session factory
│   │   ├── storage.py          # All DB CRUD operations
│   │   ├── pipeline.py         # 4-phase pipeline orchestrator
│   │   └── dedup.py            # URL and trend deduplication
│   ├── alembic/                # Database migrations
│   ├── data/                   # Runtime data (DB, scrape cache) — git-ignored
│   ├── logs/                   # Structured JSON logs — git-ignored
│   ├── scripts/
│   │   └── reset_today.py      # Manual pipeline reset utility
│   ├── tests/                  # Pytest test suite
│   ├── topics.yaml             # Topic + query configuration
│   ├── .env.example            # Environment variable template
│   ├── requirements.txt        # Python dependencies
│   ├── pyproject.toml          # Package metadata + tool config
│   └── run.py                  # Server entry point
│
└── frontend/
    ├── src/
    │   ├── components/         # Reusable React components
    │   │   ├── layout/         # Navbar + AppLayout
    │   │   ├── ChatPanel.tsx   # Collapsible RAG chat
    │   │   ├── PostEditor.tsx  # Post editor with regen + publish
    │   │   ├── PostLibrary.tsx # Scrollable post history list
    │   │   ├── PostStudio.tsx  # Tab wrapper (LinkedIn / Blog)
    │   │   ├── NewPostDialog.tsx  # Source picker modal
    │   │   ├── TrendList.tsx   # Left-sidebar trend browser
    │   │   ├── TrendDetail.tsx # Right-pane trend detail + chat
    │   │   └── ...
    │   ├── context/            # React Contexts
    │   │   ├── BackendStatusContext.tsx  # Health + dates + schedule
    │   │   ├── SearchModeContext.tsx     # Active search state
    │   │   ├── WorkspaceContext.tsx      # Workspace switcher
    │   │   └── TimeContext.tsx           # Timer display
    │   ├── pages/              # One component per route
    │   │   ├── Trends.tsx      # Daily trend browser
    │   │   ├── Searches.tsx    # On-demand research
    │   │   ├── LinkedInPost.tsx  # LinkedIn post library + editor
    │   │   └── BlogPost.tsx    # Blog post library + editor
    │   ├── lib/
    │   │   ├── api.ts          # Thin fetch wrappers
    │   │   └── utils.ts        # cn() helper
    │   ├── types.ts            # All shared TypeScript types
    │   ├── App.tsx             # Route definitions + provider stack
    │   └── index.css           # Urban Mono design tokens (Tailwind v4)
    ├── server.ts               # Express server + API proxy (25+ routes)
    ├── vite.config.ts          # Vite + Tailwind v4 plugin
    ├── package.json
    └── .env.example
```

---

## Detailed Project Explanation

### The Pipeline (How Trends Are Discovered)

The pipeline runs in four sequential phases, orchestrated by `pipeline.py`:

**Phase 1 — Discover**
- Sends each query from `topics.yaml` to Tavily (if configured) or DuckDuckGo
- Both are configured to only return results from the last 24 hours
- Deduplicates discovered URLs by domain + path normalization
- Filters out blocked domains and URLs disallowed by `robots.txt`

**Phase 2 — Scrape**
- Crawl4AI (headless Chromium via Playwright) fetches each URL and converts it to clean Markdown
- Scraped pages are cached to disk at `backend/data/cache/` (keyed by MD5 of the URL)
- Cache TTL is 18 hours — stale files are re-scraped on next access

**Phase 3 — Synthesise**
- All scraped Markdown is sent in a single LLM call to Mistral
- The LLM is instructed to identify 5–15 distinct stories, skip anything older than 1 day, and skip articles with no clear publication date signal
- Returns structured JSON: a list of stories, each with headline, one-liner, detailed Markdown summary, key points, and sources
- A post-LLM fuzzy deduplication step (rapidfuzz ≥80% similarity) removes reworded versions of the same story

**Phase 4 — Persist + Index**
- Each synthesized story is fingerprinted (SHA-256 of the normalized headline)
- The fingerprint is checked against the last 7 days — if a matching story was already seen, it is skipped
- New stories are written to the `trends` table
- All scraped pages are chunked into ~400-char passages, embedded using a local ONNX model (`BAAI/bge-small-en-v1.5` via fastembed), and bulk-inserted into the `chunks` table (pgvector)
- Embedding runs in a thread executor to avoid blocking the asyncio event loop

### RAG Chat (Ask Questions About Trends)

Every trend detail page has a chat panel. When you ask a question:

1. The query is embedded using the same local model
2. A hybrid search combines pgvector cosine similarity (semantic) with PostgreSQL BM25 full-text search
3. The top-k most relevant chunks are retrieved from the `chunks` table
4. The LLM (Mistral) receives the retrieved passages as context and answers your question
5. If it needs more information, it can call two tools: `web_search` (Tavily/DuckDuckGo) and `web_scrape` (Crawl4AI) — up to 4 tool calls per turn to prevent runaway costs
6. The response includes clickable source citations

Every message you send is automatically saved as a writing style sample (≥30 characters) to train the style learning system.

### Post Studio (Generate LinkedIn & Blog Posts)

The Post Studio lets you generate a post from any trend or search result. You can:

- Pick a source trend from the **New Post** dialog (searchable list of all trends from the last 7 days + all search runs)
- Optionally type instructions ("write from a skeptical perspective", "focus on the enterprise implications")
- Generate a LinkedIn post (~200 words, hook + insight + CTA) or a blog post (structured with sections)
- Edit the generated content inline
- Regenerate with different instructions if needed

All generated posts are saved to the `generated_posts` table and appear in the post library (left rail of the LinkedIn Post / Blog Post pages), grouped by date.

### Style Learning

Every time you interact with the app, your writing is observed:

- **Chat messages** (≥30 characters) → saved as style samples
- **Saved insights** → saved as style samples
- **Post edits** (your actual edits to generated content) → saved as style samples

When the corpus grows by 5% since the last refresh, the last 80 samples are sent to the LLM with a style distillation prompt. The output is a Markdown style guide (sentence length, tone, vocabulary, punctuation habits, etc.) stored in the `style_profile` table.

This style profile is injected into every post generation request, so posts converge toward your voice over time without any manual configuration.

### LinkedIn Publishing

Once your LinkedIn account is connected (via OAuth):

- The **Publish** button in the LinkedIn Post editor sends the post content to the LinkedIn Posts API (`/rest/posts`)
- Posts appear as text posts on your LinkedIn profile timeline
- The connection status and token expiry are shown in the UI
- Tokens are valid for 60 days; re-authorization is required after expiry

### Deduplication System

The system uses three layers to prevent duplicate stories:

| Layer | Where | How |
|-------|-------|-----|
| URL dedup | Phase 1 (Discover) | Normalizes URLs (strip UTM params, trailing slash, etc.) and deduplicates by domain+path |
| Fingerprint dedup | Phase 4 (Persist) | SHA-256 of normalized headline; checked against last 7 days in the DB |
| Fuzzy semantic dedup | Phase 4 (Persist) | `rapidfuzz.token_sort_ratio ≥ 80` on headline vs. all recent headlines; skips reworded versions of the same story |

### Scheduler

The daily pipeline is scheduled using APScheduler. There are two modes:

**In-process scheduler** (`ENABLE_INPROCESS_SCHEDULER=true` in `.env`):
- APScheduler runs inside the FastAPI process
- Automatically triggers the pipeline at the time configured in `topics.yaml`
- Also runs a catch-up job on startup if today's run is missing and the scheduled time has passed

**External scheduler** (default, `ENABLE_INPROCESS_SCHEDULER=false`):
- You are responsible for triggering `POST /admin/run-now` via cron, systemd, or a task scheduler
- Recommended for production to keep the pipeline and API isolated

---

## Operational Notes

**Windows users:** Always set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` before starting the backend or running scripts. Crawl4AI produces Unicode output that crashes the default cp1252 console codec.

**First run:** The first pipeline run downloads the fastembed ONNX model (~130 MB) to a local cache. This only happens once.

**Pipeline duration:** Each full pipeline run takes approximately 20–30 minutes — most of that is RAG indexing (embedding ~800 chunks across ~9 trends). The server remains responsive during indexing because `embed_batch` runs in a thread executor.

**Health check:** `GET /health` always returns immediately (`{"status": "ok"}`) regardless of pipeline state. It does not query the database. Use `GET /trends/dates` to check whether data is available.

**Running tests:**
```bash
cd backend
pytest                        # run all tests
pytest tests/test_storage.py  # single file
pytest -x                     # stop on first failure
```
