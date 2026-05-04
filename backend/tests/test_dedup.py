from __future__ import annotations

from backend.dedup import compute_fingerprint, deduplicate_urls


def test_fingerprint_same_headline() -> None:
    assert compute_fingerprint("Same Headline") == compute_fingerprint("Same Headline")


def test_fingerprint_different_headlines() -> None:
    assert compute_fingerprint("Headline A") != compute_fingerprint("Headline B")


def test_fingerprint_case_and_punctuation_insensitive() -> None:
    assert compute_fingerprint("OpenAI Launches GPT-5!") == compute_fingerprint("openai launches gpt5")


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
