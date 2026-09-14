"""Article content preprocessing (line filter aligned with test_pipeline)."""

from __future__ import annotations

import re


def preprocess_content(content: str, min_length: int = 10) -> str:
    """Return cleaned body joined by newlines; empty if nothing usable."""
    if not isinstance(content, str):
        raise ValueError("Article content must be a string.")
    paragraphs: list[str] = []
    seen: set[str] = set()
    for paragraph in content.splitlines():
        paragraph = re.sub(r"\s+", " ", paragraph.strip())
        if not paragraph or len(paragraph) < min_length or "@" in paragraph:
            continue
        if not re.search(r'[.!?。？！]["\'”’)\]]*(?:\s*(?:\[[^\]]+\]|<[^>]+>))*$', paragraph):
            continue
        if paragraph not in seen:
            seen.add(paragraph)
            paragraphs.append(paragraph)
    return "\n".join(paragraphs)
