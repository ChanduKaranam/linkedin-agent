from __future__ import annotations

import asyncio
import time
import urllib.parse
import urllib.robotparser
from collections import defaultdict

import httpx

_USER_AGENT = "LinkedInAgent-TrendBot/0.1 (+https://github.com/ChanduKaranam/linkedin-agent)"
_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}
_domain_last_request: dict[str, float] = defaultdict(float)
_domain_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def is_allowed(url: str, per_domain_rps: float = 0.5) -> bool:
    """Return True if robots.txt permits fetching url with our user-agent."""
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{base}/robots.txt"

    if robots_url not in _robots_cache:
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
        _robots_cache[robots_url] = rp

    return _robots_cache[robots_url].can_fetch(_USER_AGENT, url)


async def polite_delay(domain: str, per_domain_rps: float = 0.5) -> None:
    """Enforce per-domain rate limit."""
    min_gap = 1.0 / per_domain_rps
    async with _domain_locks[domain]:
        elapsed = time.monotonic() - _domain_last_request[domain]
        if elapsed < min_gap:
            await asyncio.sleep(min_gap - elapsed)
        _domain_last_request[domain] = time.monotonic()
