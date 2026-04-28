from __future__ import annotations

from backend.dedup import compute_fingerprint, deduplicate_urls
from backend.models import Source


def _source(url: str) -> Source:
    return Source(url=url, title="T", domain="example.com")


def test_fingerprint_order_independent() -> None:
    sources_a = [_source("https://example.com/a"), _source("https://example.com/b")]
    sources_b = [_source("https://example.com/b"), _source("https://example.com/a")]
    assert compute_fingerprint("Same Headline", sources_a) == compute_fingerprint("Same Headline", sources_b)


def test_fingerprint_different_headlines() -> None:
    sources = [_source("https://example.com/a")]
    assert compute_fingerprint("Headline A", sources) != compute_fingerprint("Headline B", sources)


def test_fingerprint_utm_stripped() -> None:
    a = [_source("https://example.com/article?utm_source=twitter")]
    b = [_source("https://example.com/article")]
    assert compute_fingerprint("X", a) == compute_fingerprint("X", b)


def test_deduplicate_urls_removes_utm() -> None:
    urls = [
        "https://example.com/page?utm_source=google",
        "https://example.com/page",
        "https://example.com/page/",
    ]
    result = deduplicate_urls(urls)
    assert len(result) == 1


def test_deduplicate_urls_keeps_different() -> None:
    urls = ["https://example.com/a", "https://example.com/b"]
    result = deduplicate_urls(urls)
    assert len(result) == 2
