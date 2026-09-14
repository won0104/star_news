"""Map KPF big_cls labels to Neo4j Topic nameKo strings."""

from __future__ import annotations

# KPF big_label -> Topic.nameKo (V1 seed)
BIG_CLS_TO_TOPIC_NAME_KO: dict[str, str] = {
    "정치": "정치",
    "경제": "경제",
    "사회": "사회",
    "문화": "문화",
    "국제": "국제",
    "스포츠": "스포츠",
    "IT_과학": "IT·과학",
}


def topic_name_ko(big_cls: str | None) -> str | None:
    if not big_cls:
        return None
    key = big_cls.strip()
    return BIG_CLS_TO_TOPIC_NAME_KO.get(key, key)
