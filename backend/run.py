"""
Start the backend server.
Use this script instead of calling uvicorn directly — it applies the
Windows-specific fixes before uvicorn creates any event loop or I/O stream.

Usage:
    python run.py           # production
    python run.py --reload  # development (auto-reload on file changes)
"""
import os
import sys

# ── Fix 1: UTF-8 I/O ──────────────────────────────────────────────────────────
# Windows uses cp1252 by default. Crawl4AI prints Unicode arrows (→ ↓ ✓)
# to stdout; they crash with UnicodeEncodeError unless stdout is UTF-8.
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Fix 2: ProactorEventLoop ──────────────────────────────────────────────────
# SelectorEventLoop (Windows default for some uvicorn versions) cannot spawn
# subprocesses. Playwright needs ProactorEventLoop to launch Chromium.
import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    reload = "--reload" in sys.argv
    port = int(os.environ.get("PORT", 8000))
    # Bind to 0.0.0.0 on cloud hosts (Render sets PORT env var); 127.0.0.1 locally
    host = "0.0.0.0" if os.environ.get("RENDER") else "127.0.0.1"
    uvicorn.run(
        "src.backend.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )
