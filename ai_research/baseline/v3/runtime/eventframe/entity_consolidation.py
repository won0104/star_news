"""Entity accepted rows의 priority 이후 boundary family를 닫는다.

이 provisional decoder는 동일 type·동일 source occurrence의 명백한
외곽 조사/구두점 대안만 경쟁시킨다. Entity identity는 후속 coreference 책임이다.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping


_OUTER = " \t\r\n.,;:!?()[]{}\"'“”‘’「」『』"
_PARTICLE = re.compile(r"(?:에서는|으로는|로는|에게서|께서는|에서|에게|께서|까지|부터|으로|로|은|는|이|가|을|를|의|에|와|과|도)$")


@dataclass(frozen=True, slots=True)
class EntityBoundaryPolicy:
    policy_id: str
    max_rescue_per_family: int

    @classmethod
    def load(cls, path: Path | None = None) -> "EntityBoundaryPolicy":
        path = path or Path(__file__).resolve().parents[1] / "configs/entity-mention-v22.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if (value.get("schema_version") != "articlelocal-entity-mention-policy-v22-v1"
            or value.get("policy_id") != "V22_ENTITY_BOUNDARY_COMPETITION_V1"
            or value.get("priority_input") != "FULL_ACCEPTED_SET_BEFORE_COMPETITION"
            or value.get("rescue_scope") != "FAILED_FILLER_OVERLAP_ONLY"):
            raise ValueError("unsupported Entity boundary policy")
        limit = int(value["max_rescue_per_family"])
        if not 0 <= limit <= 2:
            raise ValueError("Entity rescue limit must be bounded")
        return cls(value["policy_id"], limit)


def _core_occurrence(mention: Mapping[str, Any]) -> tuple[int, int, str]:
    """원문 absolute offset을 유지하며 외곽 문장 부호와 조사만 제거한다."""
    text = str(mention["text"])
    start = int(mention["char_start"])
    left = len(text) - len(text.lstrip(_OUTER))
    right = len(text.rstrip(_OUTER))
    core = text[left:right]
    suffix = _PARTICLE.search(core) if len(core) >= 3 else None
    if suffix and len(core[:suffix.start()]) >= 2:
        core = core[:suffix.start()]
    return start + left, start + left + len(core), core.casefold()


def _family_id(article_version_id: str, signature: tuple[object, ...]) -> str:
    material = "\u241f".join((article_version_id, *(str(part) for part in signature)))
    return "EFAM-" + sha256(material.encode("utf-8")).hexdigest()[:20]


def _rank(mention: Mapping[str, Any], priority: Mapping[str, Any]) -> tuple[object, ...]:
    start, end, _core = _core_occurrence(mention)
    boundary_extra = (int(mention["char_end"]) - int(mention["char_start"])) - (end - start)
    return (
        priority.get("priority_tier") == "TIER1_PROMOTED",
        float(priority.get("promotion_score", 0.0)),
        float(mention["score"]),
        -boundary_extra,
        -int(mention["char_start"]),
        -int(mention["char_end"]),
        str(mention["prediction_id"]),
    )


def close_entity_mentions(
    article_version_id: str,
    accepted_mentions: tuple[Mapping[str, Any], ...],
    priority_decisions: tuple[Mapping[str, Any], ...],
    *,
    policy: EntityBoundaryPolicy,
    diagnostic_sink=None,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], dict[str, Any]]:
    """원 accepted set의 priority 결정 뒤 PRIMARY와 제한 rescue를 분리한다.

    반환 priority는 live PRIMARY에만 대응한다. 흡수된 원 결정은 독립 AUDIT
    record로 남기며 rescue는 일반 identity/PUBLIC inventory에 들어가지 않는다.
    """
    by_id = {row["entity_prediction_id"]: row for row in priority_decisions}
    if priority_decisions and set(by_id) != {row["prediction_id"] for row in accepted_mentions}:
        raise ValueError("priority decisions must cover the original accepted Entity set")
    groups: dict[tuple[object, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for mention in accepted_mentions:
        start, end, core = _core_occurrence(mention)
        # 같은 표면이 문서의 다른 원문 위치에 나타나도 occurrence를 공유하지 않는다.
        signature = (int(mention["sentence_index"]), mention["entity_type"], start, end, core)
        groups[signature].append(mention)

    primary: list[dict[str, Any]] = []
    live_priorities: list[dict[str, Any]] = []
    rescue: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for signature, members in sorted(groups.items(), key=lambda item: item[0]):
        ranked = sorted(members, key=lambda row: _rank(row, by_id.get(row["prediction_id"], {})), reverse=True)
        winner = ranked[0]
        family_id = _family_id(article_version_id, signature)
        primary.append(dict(winner))
        if winner["prediction_id"] in by_id:
            live_priorities.append(dict(by_id[winner["prediction_id"]]))
        counts["families"] += 1
        counts["absorbed"] += len(ranked) - 1
        for ordinal, alternate in enumerate(ranked[1:]):
            priority = by_id.get(alternate["prediction_id"], {})
            keep_rescue = ordinal < policy.max_rescue_per_family
            if keep_rescue:
                rescue.append({
                    "prediction_id": alternate["prediction_id"],
                    "canonical_entity_prediction_id": winner["prediction_id"],
                    "source_family_id": family_id,
                    "article_version_id": article_version_id,
                    "sentence_index": alternate["sentence_index"],
                    "char_start": alternate["char_start"],
                    "char_end": alternate["char_end"],
                    "text": alternate["text"],
                    "entity_type": alternate["entity_type"],
                    "entity_score": float(alternate["score"]),
                    "promotion_score": float(priority.get("promotion_score", 0.0)),
                    "priority_tier": priority.get("priority_tier", "UNPRIORITIZED"),
                    "lifetime": "RESOLUTION_ONLY",
                    "consumer": "FAILED_FILLER_OVERLAP_ONLY",
                })
                counts["rescue_only"] += 1
            if diagnostic_sink is not None:
                diagnostic_sink.record("decision", {
                    "component": "entity_boundary_competition",
                    "article_version_id": article_version_id,
                    "source_family_id": family_id,
                    "absorbed_prediction_id": alternate["prediction_id"],
                    "primary_prediction_id": winner["prediction_id"],
                    "char_start": alternate["char_start"],
                    "char_end": alternate["char_end"],
                    "priority_tier": priority.get("priority_tier"),
                    "promotion_score": priority.get("promotion_score"),
                    "decision": "RESCUE_ONLY" if keep_rescue else "DISCARD_BOUNDARY_VARIANT",
                })
        if len(ranked) > 1 and diagnostic_sink is not None:
            diagnostic_sink.record("decision", {
                "component": "entity_boundary_family",
                "article_version_id": article_version_id,
                "source_family_id": family_id,
                "primary_prediction_id": winner["prediction_id"],
                "family_size": len(ranked),
                "policy_id": policy.policy_id,
            })
    trace = {
        "stage": "③ Entity mention boundary closure",
        "component": "Entity canonical PRIMARY / RESCUE_ONLY",
        "policy_id": policy.policy_id,
        "input_count": len(accepted_mentions),
        "candidate_count": len(accepted_mentions),
        "output_count": len(primary),
        "family_count": counts["families"],
        "absorbed_count": counts["absorbed"],
        "rescue_only_count": counts["rescue_only"],
        "drop_reason_counts": {"ABSORBED_BOUNDARY_VARIANT": counts["absorbed"]},
    }
    return tuple(primary), tuple(live_priorities), tuple(rescue), trace
