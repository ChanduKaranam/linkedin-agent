from __future__ import annotations

import asyncio
import time
import urllib.parse
import urllib.robotparser
from collections import defaultdict

import httpx

_USER_AGENT = "LinkedInAgent-TrendBot/0.1 (+https://github.com/ChanduKaranam/linkedin-agent)"
_ROBOTS_TTL = 86_400.0  # 24 h
_MAX_CACHE_ENTRIES = 500

# {robots_url: (parser, fetched_at_monotonic)}
_robots_cache: dict[str, tuple[urllib.robotparser.RobotFileParser, float]] = {}
_domain_last_request: dict[str, float] = defaultdict(float)
# Bounded lock dict — evict oldest when at cap
_domain_locks: dict[str, asyncio.Lock] = {}


def _get_domain_lock(domain: str) -> asyncio.Lock:
    if domain not in _domain_locks:
        if len(_domain_locks) >= _MAX_CACHE_ENTRIES:
            oldest = next(iter(_domain_locks))
            del _domain_locks[oldest]
        _domain_locks[domain] = asyncio.Lock()
    return _domain_locks[domain]


async def _fetch_robots(robots_url: str) -> urllib.robotparser.RobotFileParser:
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": _USER_AGENT}) as client:
            resp = await client.get(robots_url)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            else:
                rp.allow_all = True
    except Exception:
        rp.allow_all = True
    return rp


async def is_allowed(url: str, per_domain_rps: float = 0.5) -> bool:
    """Return True if robots.txt permits fetching url with our user-agent."""
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{base}/robots.txt"

    now = time.monotonic()
    entry = _robots_cache.get(robots_url)

    if entry is None or (now - entry[1]) > _ROBOTS_TTL:
        # Evict oldest if at cap before inserting
        if robots_url not in _robots_cache and len(_robots_cache) >= _MAX_CACHE_ENTRIES:
            oldest = next(iter(_robots_cache))
            del _robots_cache[oldest]
        rp = await _fetch_robots(robots_url)
        _robots_cache[robots_url] = (rp, now)
    else:
        rp = entry[0]

    return rp.can_fetch(_USER_AGENT, url)


async def polite_delay(domain: str, per_domain_rps: float = 0.5) -> None:
    """Enforce per-domain rate limit."""
    min_gap = 1.0 / per_domain_rps
    async with _get_domain_lock(domain):
        elapsed = time.monotonic() - _domain_last_request[domain]
        if elapsed < min_gap:
            await asyncio.sleep(min_gap - elapsed)
        _domain_last_request[domain] = time.monotonic()
