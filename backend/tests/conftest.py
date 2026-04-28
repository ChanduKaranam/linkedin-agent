from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

import pytest

from backend.storage import init_db


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    db = tmp_path / "test.db"
    init_db(db)
    return db


@pytest.fixture()
def tmp_cache(tmp_path: Path) -> Path:
    cache = tmp_path / "cache"
    cache.mkdir()
    return cache


@pytest.fixture()
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture()
def sample_search_results(fixture_dir: Path) -> list[dict]:
    return json.loads((fixture_dir / "search_results.json").read_text())


FIXTURE_MARKDOWN = """
# OpenAI Releases GPT-5

OpenAI today announced GPT-5, its most capable model to date.
The model shows dramatic improvements in multi-step reasoning,
code generation, and long-context understanding.

## Key improvements
- 40% better on MMLU benchmarks
- Supports 200k token context window
- Native tool use without fine-tuning

The release marks a significant leap forward for the AI industry.
Competitors including Google and Anthropic are expected to respond with their own announcements.
"""

FIXTURE_MARKDOWN_2 = """
# Google DeepMind Unveils New AlphaFold

DeepMind's AlphaFold team published a major update that can now predict RNA
structures with accuracy approaching wet-lab experiments.

## Highlights
- RNA structure prediction accuracy: 94%
- Open-source weights available
- Applications in drug discovery

Researchers expect this to accelerate work on RNA-based therapeutics.
"""
