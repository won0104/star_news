"""Auditable deterministic point-time normalization for assembly V2.1."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import re
from typing import Any, Mapping

from .contracts import (
    DerivationContext,
    DerivationDecision,
    DerivationResult,
    DerivedFact,
)
from ..provenance import PolicyProvenance
from ...temporal_identity import normalized_temporal_key


TIME_NORMALIZER_V2_POLICY_ID = "TIME_NORMALIZER_V2"


def _stable_id(prefix: str, *parts: str) -> str:
    material = "\u241f".join(parts).encode("utf-8")
    return f"{prefix}-{sha256(material).hexdigest()[:24]}"


@dataclass(frozen=True, slots=True)
class TimeNormalizationV2Result:
    status: str
    value: str | None
    granularity: str | None
    reference_published_at: str | None
    timezone: str | None
    rule_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TimeNormalizerV2:
    """Normalize only explicit point dates and defensible day deictics."""

    policy_id = TIME_NORMALIZER_V2_POLICY_ID
    policy_version = "2"
    _DURATION = re.compile(
        r"(?:동안|주기|째|이내|이상|이하)$|\d+\s*(?:년|개월|달|주|일|시간|분)\s*간$"
    )
    _SET = re.compile(r"(?:매일|매주|매월|매년|마다|정기적으로)")
    _CONTEXT_DEPENDENT = re.compile(
        r"^(?:이날|당시|이듬해|전날|다음날|최근|현재|작년|지난해|올해|내년|오는)(?:\s|$)"
    )
    _DEICTIC_DAY_OFFSETS = {"그제": -2, "어제": -1, "오늘": 0, "내일": 1, "모레": 2}

    def normalize(
        self, text: str, published_at: str | None
    ) -> TimeNormalizationV2Result:
        raw = " ".join(str(text).strip().split())
        if not raw:
            return self._unresolved("EMPTY_EXPRESSION")
        if self._DURATION.search(raw):
            return self._unresolved("DURATION_NOT_POINT_TIME")
        if self._SET.search(raw):
            return self._unresolved("RECURRING_SET_NOT_POINT_TIME")
        if self._CONTEXT_DEPENDENT.search(raw):
            return self._unresolved("CONTEXT_DEPENDENT_REFERENCE_REQUIRED")

        absolute_ymd = re.fullmatch(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", raw)
        if absolute_ymd:
            return self._calendar_day(absolute_ymd.groups(), "EXPLICIT_KOREAN_YMD")
        iso_ymd = re.fullmatch(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", raw)
        if iso_ymd:
            return self._calendar_day(iso_ymd.groups(), "EXPLICIT_NUMERIC_YMD")
        absolute_ym = re.fullmatch(r"(\d{4})\s*년\s*(\d{1,2})\s*월", raw)
        if absolute_ym:
            year, month = map(int, absolute_ym.groups())
            if not 1 <= month <= 12:
                return self._unresolved("INVALID_EXPLICIT_YEAR_MONTH")
            return TimeNormalizationV2Result(
                "NORMALIZED", f"{year:04d}-{month:02d}", "MONTH", None, None,
                "EXPLICIT_KOREAN_YEAR_MONTH",
            )
        absolute_year = re.fullmatch(r"(\d{4})\s*년", raw)
        if absolute_year:
            return TimeNormalizationV2Result(
                "NORMALIZED", absolute_year.group(1), "YEAR", None, None,
                "EXPLICIT_KOREAN_YEAR",
            )

        if raw in self._DEICTIC_DAY_OFFSETS:
            if not published_at:
                return self._unresolved("PUBLISHED_AT_REQUIRED")
            try:
                anchor = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                return TimeNormalizationV2Result(
                    "UNRESOLVED", None, None, str(published_at), None,
                    "INVALID_PUBLISHED_AT",
                )
            return TimeNormalizationV2Result(
                "NORMALIZED",
                (anchor + timedelta(days=self._DEICTIC_DAY_OFFSETS[raw])).date().isoformat(),
                "DAY",
                str(published_at),
                anchor.tzname(),
                "ARTICLE_RELATIVE_EXPLICIT_DAY_DEICTIC",
            )
        return self._unresolved("UNSUPPORTED_OR_CONTEXT_DEPENDENT")

    @staticmethod
    def _unresolved(reason: str) -> TimeNormalizationV2Result:
        return TimeNormalizationV2Result(
            "UNRESOLVED", None, None, None, None, reason
        )

    @staticmethod
    def _calendar_day(groups, rule_id: str) -> TimeNormalizationV2Result:
        try:
            value = datetime(*map(int, groups)).date().isoformat()
        except ValueError:
            return TimeNormalizerV2._unresolved("INVALID_EXPLICIT_DATE")
        return TimeNormalizationV2Result(
            "NORMALIZED", value, "DAY", None, None, rule_id
        )


def _raw_time_rows(context: DerivationContext) -> tuple[Mapping[str, Any], ...]:
    values = context.canonical_state.resolved_state.unmaterialized_evidence.get(
        "time_expressions", ()
    )
    return tuple(values) if isinstance(values, (tuple, list)) else ()


class TimeNormalizerV2Policy:
    """Emit materializable TIME identity facts; unresolved evidence remains intact."""

    policy_id = TIME_NORMALIZER_V2_POLICY_ID
    policy_version = "2"

    def __init__(self, normalizer: TimeNormalizerV2 | None = None) -> None:
        self.normalizer = normalizer or TimeNormalizerV2()

    def apply(self, context: DerivationContext) -> DerivationResult:
        state = context.canonical_state.resolved_state
        article_id = str(state.article["article_id"])
        published_at = state.article.get("published_at")
        facts = []
        decisions = []
        for row in sorted(
            _raw_time_rows(context), key=lambda item: str(item.get("prediction_id", ""))
        ):
            prediction_id = str(row.get("prediction_id", ""))
            if not prediction_id:
                continue
            result = self.normalizer.normalize(str(row.get("text", "")), published_at)
            derived = result.status == "NORMALIZED"
            decision_type = "DERIVED" if derived else "NOT_DERIVED"
            provenance = PolicyProvenance(
                policy_id=self.policy_id,
                policy_version=self.policy_version,
                decision_type=decision_type,
                source_ids=(prediction_id,),
                representative_id=None,
                member_ids=(),
                reason=result.rule_id,
                source_stage="DETERMINISTIC_DERIVATION",
                derived=derived,
                model_generated=False,
            )
            if derived:
                identity_key = normalized_temporal_key(
                    result.to_dict(), semantic_type="POINT",
                )
                if identity_key is None:
                    raise ValueError("V2 derived TIME lacks a materializable identity key")
                time_identity_id = _stable_id(
                    "TIME", article_id, *identity_key.parts()
                )
                evidence = {
                    "article_id": article_id,
                    "sentence_index": int(row["sentence_index"]),
                    "char_start": int(row["char_start"]),
                    "char_end": int(row["char_end"]),
                    "text": str(row["text"]),
                    "prediction_id": prediction_id,
                    "confidence": float(row.get("score", 1.0)),
                }
                facts.append(
                    DerivedFact(
                        derived_kind="TIME_NORMALIZATION",
                        source_ids=(prediction_id,),
                        value={
                            "fact_id": _stable_id("DFACT", self.policy_id, prediction_id),
                            "article_id": article_id,
                            "source_time_prediction_id": prediction_id,
                            "canonical_time_identity_id": time_identity_id,
                            "normalized_value": result.value,
                            "granularity": result.granularity,
                            "temporal_semantic_type": identity_key.semantic_type,
                            "timezone": identity_key.timezone,
                            "normalization": result.to_dict(),
                            "source_evidence": evidence,
                            "source_normalization": dict(row.get("normalization", {})),
                        },
                        provenance=provenance,
                    )
                )
            decisions.append(
                DerivationDecision(
                    policy_id=self.policy_id,
                    policy_version=self.policy_version,
                    source_ids=(prediction_id,),
                    derived_kind="TIME_NORMALIZATION",
                    decision=decision_type,
                    reason=result.rule_id,
                    provenance=provenance,
                    diagnostics=(
                        ("text", str(row.get("text", ""))),
                        ("status", result.status),
                        ("normalized_value", result.value),
                        ("granularity", result.granularity),
                        ("v1_normalization", dict(row.get("normalization", {}))),
                    ),
                )
            )
        return DerivationResult(context.canonical_state, tuple(facts), tuple(decisions))
