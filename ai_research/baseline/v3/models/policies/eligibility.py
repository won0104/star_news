"""구조적으로 불가능한 endpoint만 제거하는 high-recall hard mask."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .candidate_masks import CandidateDescriptor


@dataclass(frozen=True, slots=True)
class EligibilityConfig:
    allow_argument_evidence: bool = True
    allow_argument_typed_literal: bool = True


class EligibilityMask:
    """Surface/distance/trigger similarity를 사용하지 않는 baseline eligibility."""

    def __init__(self, config: EligibilityConfig | None = None) -> None:
        self.config = config or EligibilityConfig()

    def allow(self, task: str, source: CandidateDescriptor, target: CandidateDescriptor) -> bool:
        if task == "assertor":
            return source.kind == "STATEMENT" and target.kind == "ENTITY"
        if task == "argument":
            target_kinds = {"ENTITY", "TIME"}
            if self.config.allow_argument_evidence:
                target_kinds.add("EVIDENCE")
            if self.config.allow_argument_typed_literal:
                target_kinds.add("TYPED_LITERAL")
            return source.kind == "EVENT" and target.kind in target_kinds
        if task == "entity_coreference":
            return (
                source.kind == "ENTITY"
                and target.kind == "ENTITY"
                and source.candidate_id != target.candidate_id
            )
        if task == "event_coreference":
            return (
                source.kind == "EVENT"
                and target.kind == "EVENT"
                and source.candidate_id != target.candidate_id
            )
        if task in {"causal", "subevent"}:
            return (
                source.kind == "EVENT"
                and target.kind == "EVENT"
                and source.candidate_id != target.candidate_id
            )
        if task == "statement_about":
            return (
                source.kind == "STATEMENT"
                and target.kind in {"EVENT", "ENTITY"}
                and source.candidate_id != target.candidate_id
            )
        if task == "relation":
            return source.candidate_id != target.candidate_id and (
                (source.kind == "EVENT" and target.kind == "EVENT")
                or (source.kind == "STATEMENT" and target.kind in {"EVENT", "ENTITY"})
            )
        raise ValueError(f"unknown eligibility task: {task}")

    def filter_pairs(
        self,
        task: str,
        sources: Iterable[CandidateDescriptor],
        targets: Iterable[CandidateDescriptor],
        *,
        unordered: bool = False,
    ) -> list[tuple[CandidateDescriptor, CandidateDescriptor]]:
        output = []
        for source in sources:
            for target in targets:
                if unordered and source.candidate_id >= target.candidate_id:
                    continue
                if self.allow(task, source, target):
                    output.append((source, target))
        return output
