"""Drop noisy Entity spans before they enter the Neo4j-oriented schema."""

from __future__ import annotations

import re
import unicodedata

# Full-span pronouns / kinship stand-ins (not real named entities).
# Match on stripped canonicalName only (exact), not substrings.
ENTITY_PRONOUNS: frozenset[str] = frozenset(
    {
        # personal / demonstrative
        "그",
        "그녀",
        "그들",
        "그녀들",
        "그이",
        "그분",
        "그들",
        "이",
        "저",
        "얘",
        "걔",
        "쟤",
        "이쪽",
        "그쪽",
        "저쪽",
        "나",
        "너",
        "우리",
        "저희",
        "당신",
        "본인",
        "자신",
        "자기",
        "자기들",
        "여러분",
        # kinship used as pronoun-like mentions
        "형",
        "동생",
        "누나",
        "언니",
        "오빠",
        "형님",
        "아우",
        "형수",
        "제수",
        "시동생",
        "처남",
        "매형",
        "고모",
        "이모",
        "삼촌",
        "외삼촌",
        "할아버지",
        "할머니",
        "아버지",
        "어머니",
        "아빠",
        "엄마",
        "아들",
        "딸",
        "남편",
        "아내",
        "부인",
        "배우자",
    }
)

_QUOTE_AND_WRAP = "\"'“”‘’「」『』[]()（）〈〉<>《》·…⋯–—-"


def normalize_entity_name(name: str) -> str:
    """NFC + strip outer whitespace/quotes for comparison."""
    text = unicodedata.normalize("NFC", str(name or "")).strip()
    text = text.strip(_QUOTE_AND_WRAP).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def is_noise_entity_name(name: str | None) -> bool:
    """True if this should not become an Entity node."""
    if name is None:
        return True
    raw = unicodedata.normalize("NFC", str(name)).strip()
    if not raw:
        return True

    # Entire span is quotes / punctuation (e.g. `"`, `""`, `…`)
    if not re.search(r"[0-9A-Za-z가-힣]", raw):
        return True

    core = normalize_entity_name(raw)
    if not core:
        return True
    if not re.search(r"[0-9A-Za-z가-힣]", core):
        return True

    # Single Latin punctuation leftovers after strip
    if len(core) == 1 and not re.match(r"[0-9A-Za-z가-힣]", core):
        return True

    if core in ENTITY_PRONOUNS:
        return True

    return False
