from __future__ import annotations

import re

# Lines that are pure nav / boilerplate — skip them
_JUNK_RE = re.compile(
    r"^(\s*[\[\(]?(?:skip|menu|nav|navigation|cookie|subscribe|sign in|log in|advertisement)"
    r"|\s*[|]{1,3}\s*$"
    r"|\s*©)",
    re.IGNORECASE,
)

_HEADING_RE = re.compile(r"^#{1,3}\s+", re.MULTILINE)


def chunk_markdown(
    md: str,
    chunk_size: int = 700,
    overlap: int = 100,
) -> list[str]:
    """Split markdown into overlapping text chunks.

    Strategy:
    1. Split on h1/h2/h3 headings first (natural document sections).
    2. Within each section, split by sentence boundary if still > chunk_size.
    3. Merge fragments shorter than chunk_size with their neighbour.
    """
    # Drop boilerplate lines
    clean_lines = [ln for ln in md.splitlines() if not _JUNK_RE.match(ln)]
    clean = "\n".join(clean_lines)

    # Split on headings
    sections = re.split(_HEADING_RE, clean)
    sections = [s.strip() for s in sections if s.strip()]

    chunks: list[str] = []
    for section in sections:
        if len(section) <= chunk_size:
            chunks.append(section)
        else:
            chunks.extend(_split_section(section, chunk_size, overlap))

    # Merge tiny fragments with previous chunk
    merged: list[str] = []
    for chunk in chunks:
        if merged and len(chunk) < chunk_size // 4:
            merged[-1] = merged[-1] + " " + chunk
        else:
            merged.append(chunk)

    return [c.strip() for c in merged if c.strip()]


def _split_section(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Sentence-boundary split with overlap."""
    # Split on sentence endings
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 <= chunk_size:
            current = (current + " " + sent).strip()
        else:
            if current:
                chunks.append(current)
            # Start new chunk with overlap from end of previous
            if chunks:
                tail = chunks[-1][-overlap:] if len(chunks[-1]) > overlap else chunks[-1]
                current = (tail + " " + sent).strip()
            else:
                current = sent
    if current:
        chunks.append(current)
    return chunks
