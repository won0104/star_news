"""Time accepted boundary hypotheses를 원문 occurrence로 닫고 feature를 이관한다.

V1 normalization은 identity용 원본 surface view로 보존한다. 여기의 외곽
형식 비교는 별도 decoder 정책이며 V2/legacy graph derivation 규칙이 아니다.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from ..temporal_identity import TemporalIdentityKey, normalized_temporal_key


_OUTER = " \t\r\n.,;:!?()[]{}\"'“”‘’「」『』"
_PARTICLE = re.compile(r"(?:에서는|으로는|로는|에는|에서|에게|까지|부터|으로|로|은|는|이|가|을|를|의|에|도)$")
_SET = re.compile(r"매일|매주|매월|매년|마다|정기적으로")
_DURATION = re.compile(r"(?:동안|간|주기|째|이내|이상|이하)$")
_YEAR = re.compile(r"\d{4}\s*년")
_MONTH = re.compile(r"\d{1,2}\s*월")
_DAY = re.compile(r"\d{1,2}\s*일")
_ZONE = re.compile(r"\b(?:UTC|GMT|KST|[+-]\d{2}:?\d{2})\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class TimeOccurrencePolicy:
    policy_id: str

    @classmethod
    def load(cls, path: Path | None = None) -> "TimeOccurrencePolicy":
        path = path or Path(__file__).resolve().parents[1] / "configs/time-mention-v22.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if (value.get("schema_version") != "articlelocal-time-mention-policy-v22-v1"
            or value.get("policy_id") != "V22_TIME_OCCURRENCE_CONSOLIDATION_V1"
            or value.get("normalization_acceptance_gate") is not False
            or value.get("identity_before_attachment") is not False):
            raise ValueError("unsupported Time occurrence policy")
        return cls(value["policy_id"])


@dataclass(frozen=True, slots=True)
class TemporalMentionState:
    """Event identity의 마지막 소비를 위한 raw text 없는 compact occurrence."""

    prediction_id: str
    temporal_occurrence_id: str
    article_version_id: str
    sentence_index: int
    char_start: int
    char_end: int
    aligned: tuple[int, int, int] | None
    semantic_type: str
    v1_status: str
    normalized_key: TemporalIdentityKey | None
    unresolved: bool

    def feature_row(self) -> dict[str, Any]:
        key = self.normalized_key
        return {
            "prediction_id": self.prediction_id,
            "temporal_occurrence_id": self.temporal_occurrence_id,
            "article_version_id": self.article_version_id,
            "sentence_index": self.sentence_index,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "aligned": list(self.aligned) if self.aligned is not None else None,
            "semantic_type": self.semantic_type,
            "normalization": {
                "status": self.v1_status,
                "value": key.value if key else None,
                "granularity": key.granularity if key else None,
                "timezone": key.timezone if key else None,
            },
            "unresolved": self.unresolved,
        }


def _surface_core(row: Mapping[str, Any]) -> tuple[int, int, str]:
    text = str(row["text"])
    start = int(row["char_start"])
    left = len(text) - len(text.lstrip(_OUTER))
    right = len(text.rstrip(_OUTER))
    core = text[left:right]
    particle = _PARTICLE.search(core) if len(core) > 2 else None
    if particle and len(core[:particle.start()]) >= 2:
        core = core[:particle.start()]
    return start + left, start + left + len(core), core.casefold()


def _semantics(text: str, normalization: Mapping[str, Any]) -> tuple[str, str | None, str | None]:
    semantic_type = "SET" if _SET.search(text) else "DURATION" if _DURATION.search(text) else "POINT"
    granularity = normalization.get("granularity")
    if not granularity and semantic_type == "POINT":
        granularity = "DAY" if _DAY.search(text) else "MONTH" if _MONTH.search(text) else "YEAR" if _YEAR.search(text) else None
    zone = _ZONE.search(text)
    return semantic_type, str(granularity) if granularity else None, zone.group().upper() if zone else normalization.get("timezone")


def _align(prepared, start: int, end: int) -> tuple[int, int, int] | None:
    for sentence in prepared.sentences:
        if not (int(sentence["start"]) <= start and end <= int(sentence["end"])):
            continue
        tokens = [token for token in sentence["tokens"]
                  if int(token["end"]) > start and int(token["start"]) < end]
        if tokens:
            return (int(sentence["sentence_index"]), int(tokens[0]["token_index"]),
                    int(tokens[-1]["token_index"]) + 1)
    return None


def close_temporal_occurrences(
    prepared,
    accepted_hypotheses: tuple[Mapping[str, Any], ...],
    *,
    normalizer,
    policy: TimeOccurrencePolicy,
    diagnostic_sink=None,
) -> tuple[tuple[dict[str, Any], ...], tuple[TemporalMentionState, ...], dict[str, Any]]:
    """추출 acceptance 이후만 V1을 사용해 동등한 occurrence의 boundary를 닫는다."""
    enriched = []
    for row in accepted_hypotheses:
        normalization = normalizer.normalize(str(row["text"]), prepared.article.published_at).to_dict()
        enriched.append({**row, "normalization": normalization})
    groups: dict[tuple[object, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in enriched:
        start, end, core = _surface_core(row)
        # 조사/구두점이 붙은 raw surface의 V1 view는 보존한다. family 비교에는
        # 동일 source core의 별도 deterministic 형식 view를 사용한다.
        core_view = normalizer.normalize(core, prepared.article.published_at).to_dict()
        semantic_type, granularity, timezone = _semantics(core, core_view)
        key = normalized_temporal_key(core_view, semantic_type=semantic_type, timezone=timezone)
        # 정규화값이 서로 다른 accepted row는 같은 surface라도 family가 아니다.
        signature = (
            int(row["sentence_index"]), start, end, core, semantic_type,
            granularity, timezone, key.value if key else None,
        )
        groups[signature].append(row)

    occurrences: list[dict[str, Any]] = []
    states: list[TemporalMentionState] = []
    counts: Counter[str] = Counter()
    for signature, members in sorted(groups.items(), key=lambda item: tuple(str(part) for part in item[0])):
        def rank(row):
            # normalization 성공은 acceptance gate가 아니며, 같은 family 안의
            # 형식 선호일 뿐이다. unresolved-only family도 PRIMARY를 갖는다.
            return (
                row["normalization"]["status"] == "NORMALIZED",
                float(row["score"]),
                -(int(row["char_end"]) - int(row["char_start"])),
                -int(row["char_start"]), str(row["prediction_id"]),
            )
        ranked = sorted(members, key=rank, reverse=True)
        winner = ranked[0]
        semantic_type, _granularity, timezone = _semantics(str(winner["text"]), winner["normalization"])
        identity_key = normalized_temporal_key(winner["normalization"], semantic_type=semantic_type, timezone=timezone)
        occurrence = dict(winner)
        occurrence["temporal_semantic_type"] = semantic_type
        occurrence["temporal_occurrence_id"] = "TOCC-" + sha256(
            f'{prepared.article.article_version_id}|{winner["prediction_id"]}'.encode("utf-8")
        ).hexdigest()[:20]
        occurrences.append(occurrence)
        states.append(TemporalMentionState(
            str(winner["prediction_id"]), occurrence["temporal_occurrence_id"],
            prepared.article.article_version_id,
            int(winner["sentence_index"]), int(winner["char_start"]), int(winner["char_end"]),
            _align(prepared, int(winner["char_start"]), int(winner["char_end"])),
            semantic_type, str(winner["normalization"]["status"]), identity_key,
            identity_key is None,
        ))
        counts["family"] += 1
        counts["absorbed"] += len(ranked) - 1
        counts["unresolved"] += int(identity_key is None)
        for alternate in ranked[1:]:
            if diagnostic_sink is not None:
                diagnostic_sink.record("decision", {
                    "component": "time_occurrence_boundary",
                    "article_version_id": prepared.article.article_version_id,
                    "absorbed_prediction_id": alternate["prediction_id"],
                    "canonical_prediction_id": winner["prediction_id"],
                    "char_start": alternate["char_start"],
                    "char_end": alternate["char_end"],
                    "decision": "ABSORB_EQUIVALENT_BOUNDARY",
                    "policy_id": policy.policy_id,
                })
    trace = {
        "stage": "③ Time occurrence boundary closure",
        "component": "Canonical TimeMention",
        "policy_id": policy.policy_id,
        "input_count": len(accepted_hypotheses),
        "candidate_count": len(accepted_hypotheses),
        "output_count": len(occurrences),
        "family_count": counts["family"],
        "absorbed_count": counts["absorbed"],
        "unresolved_count": counts["unresolved"],
        "drop_reason_counts": {"ABSORBED_EQUIVALENT_BOUNDARY": counts["absorbed"]},
    }
    return tuple(occurrences), tuple(states), trace
