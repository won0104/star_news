"""Reusable positive-equivalence evidence contracts for public identities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .event_view import EventIdentityView


EQUIVALENCE_DECISIONS = (
    "PROVEN_EQUIVALENT",
    "INSUFFICIENT_EVIDENCE",
    "SEMANTIC_EXPANSION",
    "SEMANTIC_CONFLICT",
)


@dataclass(frozen=True, slots=True)
class EventSupportSignature:
    """Observed resolved support; absence is not an equivalence witness."""

    actor_ids: tuple[str, ...]
    target_ids: tuple[str, ...]
    place_ids: tuple[str, ...]
    normalized_times: tuple[tuple[str, str | None], ...]
    ambiguous_role_ids: tuple[str, ...]
    source_eventframe_ids: tuple[str, ...]
    support_provenance_ids: tuple[str, ...]

    @classmethod
    def from_view(cls, view: EventIdentityView) -> "EventSupportSignature":
        roles = {
            role: tuple(sorted(view.role_targets(role)))
            for role in ("ACTOR", "TARGET", "PLACE")
        }
        role_memberships: dict[str, set[str]] = {}
        for role, identity_ids in roles.items():
            for identity_id in identity_ids:
                role_memberships.setdefault(identity_id, set()).add(role)
        provenance = tuple(
            dict.fromkeys(
                value
                for support in (*view.role_support, *view.time_support)
                for value in support.evidence_references
            )
        )
        return cls(
            actor_ids=roles["ACTOR"],
            target_ids=roles["TARGET"],
            place_ids=roles["PLACE"],
            normalized_times=tuple(
                sorted(view.normalized_times(), key=lambda row: (row[0], str(row[1])))
            ),
            ambiguous_role_ids=tuple(
                sorted(
                    identity_id
                    for identity_id, memberships in role_memberships.items()
                    if len(memberships) > 1
                )
            ),
            source_eventframe_ids=view.source_eventframe_ids,
            support_provenance_ids=provenance,
        )

    @property
    def observed_support_count(self) -> int:
        return sum(
            len(values)
            for values in (
                self.actor_ids,
                self.target_ids,
                self.place_ids,
                self.normalized_times,
            )
        )

    def semantic_values(self) -> tuple[tuple[str, tuple[Any, ...]], ...]:
        return (
            ("ACTOR", self.actor_ids),
            ("TARGET", self.target_ids),
            ("PLACE", self.place_ids),
            ("TIME", self.normalized_times),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EquivalenceEvidence:
    """Five-axis proof record; every axis must pass for equivalence."""

    structural_compatibility: bool
    anchor_predicate_proof: bool
    support_equivalence_proof: bool
    delta_silence_proof: bool
    conflict_free: bool
    shared_support_witnesses: tuple[str, ...]
    anchor_member_prediction_ids: tuple[str, ...]
    internal_member_predicate_witness_ids: tuple[str, ...]
    delta_event_witness_ids: tuple[str, ...]
    delta_trigger_witness_ids: tuple[str, ...]
    diagnostic_flags: tuple[str, ...]
    left_support_signature: EventSupportSignature
    right_support_signature: EventSupportSignature

    @property
    def proven(self) -> bool:
        return all(
            (
                self.structural_compatibility,
                self.anchor_predicate_proof,
                self.support_equivalence_proof,
                self.delta_silence_proof,
                self.conflict_free,
                bool(self.shared_support_witnesses),
            )
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proven_equivalent"] = self.proven
        return payload


@dataclass(frozen=True, slots=True)
class EquivalenceDecision:
    decision: str
    reason: str
    evidence: EquivalenceEvidence

    def __post_init__(self) -> None:
        if self.decision not in EQUIVALENCE_DECISIONS:
            raise ValueError(f"unsupported equivalence decision: {self.decision}")
        if (self.decision == "PROVEN_EQUIVALENT") != self.evidence.proven:
            raise ValueError("PROVEN_EQUIVALENT must match the complete evidence proof")

    @property
    def proven_equivalent(self) -> bool:
        return self.decision == "PROVEN_EQUIVALENT"

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "proven_equivalent": self.proven_equivalent,
            "evidence": self.evidence.to_dict(),
        }
