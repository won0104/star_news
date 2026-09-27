"""PUBLIC edge confidence의 score provenance sidecar.

Semantic carrier(`LocalEventState`, `GroundedStatement`, `LocalEntity`, `LocalTimeFact`,
`AssertedByFact`)와 분리된 score lifecycle이다. Serving은 carrier가 버리는 decode/pair
logit을 closure 이후에도 안정적인 key(Event member ID, Statement ID, Entity candidate ID,
member×Time occurrence, Assertor evidence ID)로 모으고, PUBLIC projection은 validation을
통과해 실제로 출력되는 edge에만 confidence를 붙인다.

Confidence는 그 edge를 만든 판단 logit의 sigmoid다. 모든 원천 head는 BCE로 학습됐지만
양성/음성 cohort를 따로 평균한 loss라 prevalence calibration은 없다. 따라서 값은 [0,1]
model probability이며 calibration된 정답 확률로 해석하지 않는다. 원천이 없으면 기본값을
만들지 않고 projection이 실패한다.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING, Iterable, Mapping

if TYPE_CHECKING:
    from runtime.v3_pretraining.extraction_decode import DecodedSourceSpan


def logit_confidence(logit: float) -> float:
    """serving의 기존 decision probability와 같은 clamped sigmoid."""
    return 1.0 / (1.0 + math.exp(-max(-80.0, min(80.0, logit))))


@dataclass(frozen=True, slots=True)
class EdgeScore:
    """한 판단의 raw logit과 producer. confidence는 logit에서만 파생한다."""

    logit: float
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.logit, (int, float)) or isinstance(self.logit, bool) or \
                not math.isfinite(self.logit) or not self.source:
            raise ValueError("edge score needs a finite logit and producer")

    @property
    def confidence(self) -> float:
        return logit_confidence(self.logit)


def acceptance_edge_score(span: DecodedSourceSpan) -> EdgeScore:
    """Event/Statement 수용은 decision AND boundary gate이므로 min(σ(d), σ(b))=σ(min(d, b))."""
    if span.boundary_fitness_score is None:
        raise ValueError("Event/Statement acceptance confidence needs boundary-fitness score")
    return EdgeScore(min(span.extraction_score, span.boundary_fitness_score),
                     "DECISION_BOUNDARY_MIN")


def max_edge_score(scores: Iterable[EdgeScore], what: str) -> EdgeScore:
    """같은 PUBLIC edge로 합쳐진 지지 원천은 max로 모은다(평균·noisy-or 없음)."""
    rows = tuple(scores)
    if not rows:
        raise ValueError(f"{what} confidence provenance missing")
    return max(rows, key=lambda row: (row.logit, row.source))


@dataclass(frozen=True, slots=True)
class PublicEdgeScores:
    """Carrier가 싣지 않는 PUBLIC edge 판단 score. PUBLIC 생성 후 폐기 가능한 scalar다."""

    event_members: Mapping[str, EdgeScore]
    statements: Mapping[str, EdgeScore]
    entity_candidates: Mapping[str, EdgeScore]
    time_attachments: Mapping[tuple[str, str], EdgeScore]
    assertor_entities: Mapping[str, EdgeScore]

    def _lookup(self, table: Mapping, keys: Iterable, what: str) -> EdgeScore:
        missing = [key for key in keys if key not in table]
        if missing:
            raise ValueError(f"{what} confidence provenance missing: {missing[0]}")
        return max_edge_score((table[key] for key in keys), what)

    def covers(self, member_ids: tuple[str, ...]) -> EdgeScore:
        return self._lookup(self.event_members, member_ids, "COVERS")

    def contains_statement(self, statement_id: str) -> EdgeScore:
        return self._lookup(self.statements, (statement_id,), "CONTAINS_STATEMENT")

    def mentions(self, candidate_ids: tuple[str, ...]) -> EdgeScore:
        return self._lookup(self.entity_candidates, candidate_ids, "MENTIONS")

    def occurred_on(self, member_ids: tuple[str, ...], time_id: str) -> EdgeScore:
        return self._lookup(self.time_attachments,
                            tuple((member_id, time_id) for member_id in member_ids),
                            "OCCURRED_ON")

    def asserted_by(self, evidence_id: str) -> EdgeScore:
        return self._lookup(self.assertor_entities, (evidence_id,), "ASSERTED_BY")
