# AI & Tech Trend Agent

An autonomous AI agent that wakes up every day at **4:00 AM** (Asia/Kolkata), discovers what is trending in AI and technology, scrapes the relevant articles, groups them into coherent stories, and writes a headline + detailed summary for each trend. The results are served through a clean tabbed dashboard built with Next.js.

---

## How it works

```
Every day at 04:00
        │
        ▼
┌───────────────────┐
│  1. DISCOVER      │  Searches DuckDuckGo (or Tavily) for the configured
│                   │  queries, e.g. "latest AI model releases this week".
│                   │  Collects up to 30 unique URLs, filters noise,
│                   │  and respects robots.txt.
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  2. SCRAPE        │  Fetches each URL using Crawl4AI (Playwright-backed,
│                   │  returns clean Markdown). Falls back to httpx +
│                   │  trafilatura for simple pages. Results are cached
│                   │  on disk so a retry doesn't re-scrape.
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  3. CLUSTER       │  Sends article snippets to Mistral (via Google ADK +
│                   │  LiteLLM). The LLM groups articles discussing the
│                   │  same story into "trends". Falls back to a rule-based
│                   │  clusterer (title similarity + domain) if the LLM fails.
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  4. SUMMARIZE     │  For each trend cluster, Mistral writes a headline,
│                   │  one-liner, detailed Markdown write-up, and key
│                   │  bullet points. Results are deduplicated across days
│                   │  so the same story doesn't reappear the next day.
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  5. PERSIST       │  Saved to a local SQLite database.
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Next.js UI       │  One tab per headline. Click a tab to read the full
│                   │  write-up, key points, and source links.
└───────────────────┘
```

**Key design principle:** the topic is fully configurable. Edit one YAML file to switch from "AI & tech" to "Formula 1" or "finance" — no code changes needed.

---

## Tech stack

| Layer | Technology |
|---|---|
| Agent framework | [Google ADK](https://google.github.io/adk-docs/) (`google-adk`) |
| LLM | [Mistral](https://mistral.ai/) via [LiteLLM](https://docs.litellm.ai/) (swappable) |
| Web scraper | [Crawl4AI](https://crawl4ai.com/) + httpx + trafilatura |
| Search | DuckDuckGo (`ddgs`) — free, no key · [Tavily](https://tavily.com/) optional |
| API | [FastAPI](https://fastapi.tiangolo.com/) |
| Database | SQLite (WAL mode, zero setup) |
| Scheduler | Windows Task Scheduler (prod) / APScheduler in-process (dev) |
| Frontend | [Next.js 16](https://nextjs.org/) · Tailwind CSS · react-markdown |

---

## Prerequisites

Before starting, make sure you have:

- **Python 3.11 or newer** — check with `python --version`
- **Node.js 20 or newer** — check with `node --version`
- **Git** — to clone the repo

---

## Step 1 — Get API keys

### Mistral API key (required)

Mistral is the LLM that reads the scraped articles and writes the trend summaries.

1. Go to [console.mistral.ai](https://console.mistral.ai)
2. Sign up or log in
3. Navigate to **API Keys** in the left sidebar
4. Click **Create new key**, give it a name (e.g. `trend-agent`)
5. Copy the key — it looks like `sk-xxxxxxxxxxxxxxxxxxxxxxxxx`

> **Cost:** The agent uses `mistral-small-latest` by default. A full daily run costs roughly **$0.08 USD**. You can switch to `mistral-large-latest` in `topics.yaml` for higher quality at ~$0.80/run.

### Tavily API key (optional but recommended)

Tavily gives better, more recent search results than DuckDuckGo. Without it the agent still works — it just uses DuckDuckGo for free.

1. Go to [app.tavily.com](https://app.tavily.com)
2. Sign up and navigate to **API**
3. Copy your API key — it looks like `tvly-xxxxxxxxxxxxxxxxx`

> **Cost:** Tavily has a free tier of 1,000 searches/month, which is more than enough for a daily run with 5 queries.

---

## Step 2 — Clone and configure

```bash
git clone https://github.com/ChanduKaranam/linkedin-agent.git
cd linkedin-agent
```

### Configure the backend

```bash
cd backend
copy .env.example .env
```

Open `.env` in any text editor and fill in your keys:

```env
# Required — paste your Mistral key here
MISTRAL_API_KEY=sk-your-mistral-key-here

# Optional — paste your Tavily key here for better search results
TAVILY_API_KEY=tvly-your-tavily-key-here

# Set to true to enable the /admin/* endpoints (needed to trigger a run manually)
DEBUG=true

# Set to true if you want the scheduler to run inside the FastAPI server (dev mode)
ENABLE_INPROCESS_SCHEDULER=false
```

Save and close the file.

> **Security:** The `.env` file is in `.gitignore` and will never be committed to Git. Never share this file or paste your keys anywhere publicly.

### Configure the frontend

```bash
cd ../frontend
copy .env.local.example .env.local
```

The defaults in `.env.local` work out of the box for local development — no changes needed unless your backend runs on a different port.

---

## Step 3 — Install dependencies

### Backend

```bash
cd backend

# Create a virtual environment
python -m venv .venv

# Activate it (Windows)
.venv\Scripts\activate

# Install all Python packages
pip install -e ".[dev]"

# Install the Playwright browser used by Crawl4AI
python -m playwright install chromium
```

This will take 2–3 minutes on the first run.

### Frontend

```bash
cd frontend
npm install
```

---

## Step 4 — Run the application

You need two terminal windows open at the same time.

### Terminal 1 — Start the backend API server

```bash
cd backend
.venv\Scripts\activate
uvicorn backend.api.main:app --port 8000 --reload
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### Terminal 2 — Start the frontend

```bash
cd frontend
npm run dev
```

You should see:

```
▲ Next.js 16
  - Local: http://localhost:3000
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Step 5 — Trigger the first run

The agent normally runs at 4:00 AM automatically. To test it right now without waiting:

```bash
# Trigger a run
curl -X POST http://localhost:8000/admin/run-now
```

This returns a `run_id`. The pipeline runs in the background (takes 1–3 minutes depending on internet speed and how many articles are found).

Poll the run status until it shows `completed`:

```bash
curl http://localhost:8000/admin/runs/<paste-run_id-here>
```

When the state is `completed`, refresh [http://localhost:3000](http://localhost:3000) — you will see tabs with today's trends.

### What the UI looks like

- **Tabs row** — one tab per trend headline, scrollable horizontally
- **Click a tab** — see the full write-up, key bullet points, and source links
- **Source chips** — click any chip to open the original article in a new tab

---

## Scheduling (automatic daily runs)

### Recommended: Windows Task Scheduler

This is the most reliable option — it survives reboots and FastAPI crashes.

Open PowerShell as Administrator and run:

```powershell
schtasks /Create /SC DAILY /TN "TrendAgent" `
  /TR "C:\path\to\linkedin-agent\backend\.venv\Scripts\python.exe -m backend.scheduler.daily_job" `
  /ST 04:00 /RL HIGHEST
```

Replace `C:\path\to\linkedin-agent` with the actual path on your machine.

Test that it fires correctly:

```powershell
schtasks /Run /TN "TrendAgent"
```

Check `backend\logs\agent.log` to see the run output.

### Dev alternative: in-process scheduler

If you don't want to set up Task Scheduler, set `ENABLE_INPROCESS_SCHEDULER=true` in your `.env` file. The FastAPI server will schedule the job at 4:00 AM itself. This is simpler but the job stops running if the server crashes.

---

## Changing the topic

Edit `backend/topics.yaml` — no code changes needed:

```yaml
topic: "Formula 1"
queries:
  - "Formula 1 news this week"
  - "F1 team updates"
  - "F1 race results recent"
  - "Formula 1 driver announcements"
```

Restart the backend server, trigger a new run, and the agent will start covering F1 instead of AI/tech.

---

## Project structure

```
linkedin-agent/
├── backend/
│   ├── pyproject.toml              # Python dependencies (pinned)
│   ├── topics.yaml                 # Topic config — edit this to change domain
│   ├── .env.example                # Copy to .env and fill in your keys
│   └── src/backend/
│       ├── config.py               # Reads .env and topics.yaml, validates both
│       ├── models.py               # Shared data schemas (Pydantic)
│       ├── storage.py              # SQLite read/write + schema migrations
│       ├── dedup.py                # Prevents the same trend from repeating daily
│       ├── pipeline.py             # The 4-phase orchestrator (discover→scrape→cluster→summarize)
│       ├── agent/
│       │   ├── trend_agent.py      # Google ADK LlmAgent setup for Mistral
│       │   ├── prompts.py          # LLM prompt templates (injection-resistant)
│       │   └── tools/
│       │       ├── search.py       # DuckDuckGo / Tavily search
│       │       ├── scrape.py       # Crawl4AI + httpx/trafilatura fallback
│       │       └── robots.py       # robots.txt + per-domain rate limiting
│       ├── api/
│       │   ├── main.py             # FastAPI app + scheduler lifespan
│       │   ├── routes_trends.py    # GET /health, /trends/today, /trends/{date}/{slug}
│       │   └── routes_admin.py     # POST /admin/run-now, GET /admin/runs (DEBUG only)
│       └── scheduler/
│           └── daily_job.py        # Standalone script for Windows Task Scheduler
├── frontend/
│   ├── app/
│   │   ├── page.tsx                # Main tabbed dashboard (client component)
│   │   ├── layout.tsx
│   │   └── api/                    # Next.js proxy routes → backend
│   └── components/
│       ├── TrendTabs.tsx           # Horizontal tab list, keyboard-accessible
│       ├── TrendDetail.tsx         # Full trend view: write-up + sources
│       └── EmptyState.tsx          # Handles backend-down / no-run states
└── README.md
```

---

## API reference

These endpoints are exposed by the FastAPI backend at `http://localhost:8000`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Backend status + latest run date + trend count |
| `GET` | `/trends/today` | List of today's trend headlines |
| `GET` | `/trends/by-date/YYYY-MM-DD` | Trends for a specific date |
| `GET` | `/trends/YYYY-MM-DD/{slug}` | Full detail for one trend |
| `POST` | `/admin/run-now` | Trigger a pipeline run immediately (`DEBUG=true` required) |
| `GET` | `/admin/runs/{run_id}` | Poll run status (`DEBUG=true` required) |
| `GET` | `/admin/runs` | List recent runs with state and error info (`DEBUG=true` required) |

Interactive docs are available at [http://localhost:8000/docs](http://localhost:8000/docs) when `DEBUG=true`.

---

## Environment variables reference

All variables go in `backend/.env`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `MISTRAL_API_KEY` | **Yes** | — | Your Mistral API key. Get one at [console.mistral.ai](https://console.mistral.ai) |
| `TAVILY_API_KEY` | No | — | Tavily search key for better results. Get one at [app.tavily.com](https://app.tavily.com). Falls back to DuckDuckGo if not set. |
| `DEBUG` | No | `false` | Set `true` to enable `/admin/*` endpoints and interactive API docs |
| `ENABLE_INPROCESS_SCHEDULER` | No | `false` | Set `true` to run the 4 AM job inside the FastAPI process (dev only) |
| `TZ` | No | `Asia/Kolkata` | Timezone for the scheduler |
| `LITELLM_REQUEST_TIMEOUT` | No | `60` | Seconds before an LLM request times out |

---

## Troubleshooting

**"No trends yet" on the UI after a run**
- Check the run state: `curl http://localhost:8000/admin/runs/<run_id>`
- If `state` is `failed`, read `last_error` — common causes are `NO_SOURCES` (all search queries returned nothing) or `LLM_AUTH` (bad API key)
- Check `backend/logs/agent.log` for the full structured log

**Backend returns 404 on `/admin/run-now`**
- You need `DEBUG=true` in `backend/.env`. Restart the server after changing it.

**Crawl4AI / Playwright errors on first run**
- Make sure you ran `python -m playwright install chromium` inside the activated virtual environment

**"Backend unreachable" on the frontend**
- Make sure the FastAPI server is running: `curl http://localhost:8000/health` should return `{"status":"ok",...}`
- Check that `BACKEND_URL` in `frontend/.env.local` matches the port the server is running on (default `http://127.0.0.1:8000`)

**Mistral 429 rate limit errors**
- The agent retries automatically with backoff. If it keeps failing, you may have hit your Mistral plan's RPM limit. Wait a few minutes and re-trigger.

---

## Running the tests

Unit and mocked-integration tests run with no network access and no API keys needed:

```bash
cd backend
.venv\Scripts\activate
pytest -q
```

Tests cover: SQLite schema migrations, dedup fingerprinting, URL canonicalization, and a full pipeline run with stubbed search/scrape/LLM responses.
