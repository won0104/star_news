"""Exact-value TIME representation canonicalization.

This policy only collapses already materializable point-like TIME identities.
It does not normalize text, infer dates, or use attachment proximity.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from .contracts import (
    CanonicalizationContext,
    CanonicalizationDecision,
    CanonicalizationResult,
)
from .evidence import preserved_evidence_references
from .policies import NoOpCanonicalizationPolicy
from ..provenance import PolicyProvenance
from ...temporal_identity import normalized_temporal_key


TEMPORAL_SURFACE_CANONICALIZATION_POLICY_ID = (
    "TEMPORAL_SURFACE_CANONICALIZATION_V1"
)
_POINT_GRANULARITIES = frozenset(
    {"YEAR", "QUARTER", "MONTH", "WEEK", "DAY", "HOUR", "MINUTE", "SECOND"}
)


def _normalization_key(row: Mapping[str, Any]) -> tuple[str, str, str, str] | None:
    properties = row.get("properties", {})
    value = properties.get("normalized_value")
    granularity = properties.get("granularity")
    status = properties.get("normalization_status", "NORMALIZED")
    semantic_type = properties.get("temporal_semantic_type", "POINT")
    if granularity not in _POINT_GRANULARITIES:
        return None
    key = normalized_temporal_key(
        {"status": status, "value": value, "granularity": granularity,
         "timezone": properties.get("timezone", properties.get("normalization", {}).get("timezone"))},
        semantic_type=str(semantic_type),
    )
    return key.parts() if key is not None else None


def _representative_key(row: Mapping[str, Any]) -> tuple[int, int, str]:
    evidence = tuple(row.get("evidence", ()))
    first_start = min((int(item["char_start"]) for item in evidence), default=10**18)
    first_end = min((int(item["char_end"]) for item in evidence), default=10**18)
    return first_start, first_end, str(row["node_id"])


class TemporalSurfaceCanonicalizationPolicy:
    """Collapse exact normalized point identities and preserve every surface."""

    policy_id = TEMPORAL_SURFACE_CANONICALIZATION_POLICY_ID
    policy_version = "1"
    target_scopes = ("TIME",)

    def apply(self, context: CanonicalizationContext) -> CanonicalizationResult:
        base = NoOpCanonicalizationPolicy().apply(context)
        decisions = [row for row in base.decisions if row.scope != "TIME"]
        groups: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
        diagnostics = []
        for row in context.resolved_state.time_expressions:
            key = _normalization_key(row)
            if key is None:
                group_key = ("PASS_THROUGH", str(row["node_id"]), "", "", "")
                diagnostics.append(
                    {
                        "scope": "TIME",
                        "source_identity_id": str(row["node_id"]),
                        "decision": "PASS_THROUGH",
                        "reason": "UNMATERIALIZABLE_OR_NON_POINT_TEMPORAL_IDENTITY",
                    }
                )
            else:
                group_key = key
            groups[group_key].append(row)

        for key in sorted(groups, key=lambda value: tuple(str(item) for item in value)):
            members = sorted(groups[key], key=_representative_key)
            member_ids = tuple(str(row["node_id"]) for row in members)
            representative = member_ids[0]
            collapse = len(member_ids) >= 2 and len(key) == 4
            decision_type = "COLLAPSE" if collapse else "PASS_THROUGH"
            reason = (
                "EXACT_NORMALIZED_POINT_IDENTITY"
                if collapse
                else "TEMPORAL_IDENTITY_PRESERVED"
            )
            references = tuple(
                sorted(
                    {
                        reference
                        for row in members
                        for reference in preserved_evidence_references(
                            str(row["node_id"]), row
                        )
                    }
                )
            )
            provenance = PolicyProvenance(
                policy_id=self.policy_id,
                policy_version=self.policy_version,
                decision_type=decision_type,
                source_ids=member_ids,
                representative_id=representative,
                member_ids=member_ids,
                reason=reason,
                source_stage="CANONICALIZATION",
                derived=True,
                model_generated=False,
            )
            decisions.append(
                CanonicalizationDecision(
                    policy_id=self.policy_id,
                    policy_version=self.policy_version,
                    scope="TIME",
                    input_ids=member_ids,
                    output_representative_id=representative,
                    member_ids=member_ids,
                    decision=decision_type,
                    reason=reason,
                    preserved_evidence_references=references,
                    provenance=provenance,
                    diagnostics=(
                        ("normalized_value", key[0] if len(key) == 4 else None),
                        ("granularity", key[1] if len(key) == 4 else None),
                        ("semantic_type", key[2] if len(key) == 4 else None),
                        ("timezone", key[3] if len(key) == 4 else None),
                    ),
                )
            )
        return CanonicalizationResult(
            context.resolved_state,
            tuple(decisions),
            tuple(diagnostics),
        )
