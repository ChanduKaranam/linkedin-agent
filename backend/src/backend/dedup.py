from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _canonical_url(url: str) -> str:
    """Strip UTM params, fragments, trailing slash."""
    import urllib.parse

    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
    filtered = {k: v for k, v in params.items() if not k.lower().startswith("utm_")}
    new_query = urllib.parse.urlencode(filtered, doseq=True)
    clean = parsed._replace(query=new_query, fragment="")
    return urllib.parse.urlunparse(clean).rstrip("/")


def compute_fingerprint(headline: str) -> str:
    """Stable hash of normalized headline. Headline-only so the same story
    produces the same fingerprint across runs regardless of which sources were fetched."""
    return hashlib.sha1(_normalize(headline).encode("utf-8")).hexdigest()


def deduplicate_urls(urls: list[str]) -> list[str]:
    """Remove duplicate URLs after canonicalization, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        canon = _canonical_url(url)
        if canon not in seen:
            seen.add(canon)
            result.append(url)
    return result
