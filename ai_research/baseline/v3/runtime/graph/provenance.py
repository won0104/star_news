"""공통 assembly policy provenance 계약.

Neural prediction lineage와 downstream deterministic decision을 같은 source로
표현하지 않도록 canonicalization/derivation 단계가 공유하는 최소 필드를 고정한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PolicyProvenance:
    """한 deterministic policy decision의 재현 가능한 출처."""

    policy_id: str
    policy_version: str
    decision_type: str
    source_ids: tuple[str, ...]
    representative_id: str | None
    member_ids: tuple[str, ...]
    reason: str
    source_stage: str
    derived: bool
    model_generated: bool

    def __post_init__(self) -> None:
        for name in (
            "policy_id",
            "policy_version",
            "decision_type",
            "reason",
            "source_stage",
        ):
            if not getattr(self, name):
                raise ValueError(f"policy provenance requires {name}")
        if self.representative_id is not None and self.member_ids:
            if self.representative_id not in self.member_ids:
                raise ValueError("policy representative must be a member identity")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
