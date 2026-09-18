"""Article content preprocessing (line filter aligned with test_pipeline)."""

from __future__ import annotations

import re
import unicodedata

# Emoji / pictograph blocks + variation selectors / ZWJ used in emoji sequences.
_EMOJI_RE = re.compile(
    "["
    "\U0000200D"  # ZWJ
    "\U0000FE0E\U0000FE0F"  # variation selectors
    "\U0000203C\U00002049"  # ‼ ⁉
    "\U00002122\U00002139"  # ™ ℹ
    "\U00002194-\U00002199"
    "\U000021A9-\U000021AA"
    "\U0000231A-\U0000231B"
    "\U00002328"
    "\U000023CF"
    "\U000023E9-\U000023F3"
    "\U000023F8-\U000023FA"
    "\U000024C2"
    "\U000025A0-\U000025FF"  # geometric shapes (△▲◆■●○ 등)
    "\U00002600-\U000026FF"  # misc symbols (☀★♥…)
    "\U00002700-\U000027BF"  # dingbats
    "\U00002934-\U00002935"
    "\U00002B05-\U00002B07"
    "\U00002B1B-\U00002B1C"
    "\U00002B50"
    "\U00002B55"
    "\U00003030"
    "\U0000303D"
    "\U00003297"
    "\U00003299"
    "\U0001F000-\U0001F02F"
    "\U0001F0A0-\U0001F0FF"
    "\U0001F100-\U0001F1FF"
    "\U0001F200-\U0001F2FF"
    "\U0001F300-\U0001F9FF"  # emoticons / pictographs
    "\U0001FA00-\U0001FAFF"  # extended pictographs
    "\U0001F3FB-\U0001F3FF"  # skin tones
    "]+",
    flags=re.UNICODE,
)

# Po(문장부호)이지만 뉴스 본문 장식/불릿으로만 쓰이는 기호.
# 한글·한자·일반 문장부호(· … “ ” 등)는 여기에 넣지 않는다.
_DECORATIVE_PO = frozenset("※☆★○●◎◇◆□■▷▶➔➡➤")


def _strip_emoji_and_symbols(text: str) -> str:
    """Remove emojis/decorative marks; keep Hangul, Hanja, Latin, digits, normal punctuation.

    Examples:
      ``△최영상`` → ``최영상``
      ``金正恩`` → ``金正恩`` (한자 유지)
    """
    text = _EMOJI_RE.sub("", text)
    kept: list[str] = []
    for ch in text:
        if ch in _DECORATIVE_PO:
            continue
        # So = Symbol, other (이모지·도형 잔여). Cs/Co = surrogate / private-use.
        # Lo(한글·한자) / Po(일반 문장부호) / Nd(숫자) 등은 유지.
        if unicodedata.category(ch) in {"So", "Cs", "Co"}:
            continue
        kept.append(ch)
    cleaned = re.sub(r"\s+", " ", "".join(kept)).strip()
    # "했다 😀." → "했다 ." 같은 잔여 공백 정리
    return re.sub(r"\s+([.!?。？！,，、;；:：])", r"\1", cleaned)


def preprocess_content(content: str, min_length: int = 10) -> str:
    """Return cleaned body joined by newlines; empty if nothing usable."""
    if not isinstance(content, str):
        raise ValueError("Article content must be a string.")
    paragraphs: list[str] = []
    seen: set[str] = set()
    for paragraph in content.splitlines():
        paragraph = re.sub(r"\s+", " ", paragraph.strip())
        paragraph = _strip_emoji_and_symbols(paragraph)
        if not paragraph or len(paragraph) < min_length or "@" in paragraph:
            continue
        if not re.search(r'[.!?。？！]["\'”’)\]]*(?:\s*(?:\[[^\]]+\]|<[^>]+>))*$', paragraph):
            continue
        if paragraph not in seen:
            seen.add(paragraph)
            paragraphs.append(paragraph)
    return "\n".join(paragraphs)
