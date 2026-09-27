"""마지막 lane 소비 전에 scalar snapshot만 독립 DiagnosticSink로 보낸다.

PUBLIC/raw graph·tensor 소유권을 확장하지 않는다. Gold 연결은 별도 evaluator 책임이다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

from ..lifecycle import DiagnosticSink, _independent


@dataclass(frozen=True, slots=True)
class RoutingObservation:
    """A/B/C가 공유할 최소 query decision record; 전체 negative pair는 담지 않는다."""

    article_version_id: str
    content_sha256: str
    lane: str
    query_key: str
    feature_signature: str
    query_char_span: tuple[int, int] | None
    eligible_candidate_count: int
    selected_candidate_ids: tuple[str, ...]
    baseline_winner_id: str | None
    baseline_winner_score: float | None
    baseline_positive_count: int
    baseline_positive_top_ids: tuple[str, ...]
    canonical_remap_top: tuple[tuple[str, str], ...] = ()
    event_scored_pair_count: int = 0
    event_cluster_count: int = 0
    candidate_coordinates_top: tuple[tuple[str, str, int, int, str], ...] = ()
    query_role: str | None = None
    lane_census: tuple[tuple[str, int], ...] = ()
    event_pair_witness_top: tuple[tuple[str, str, float, str], ...] = ()

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value for value in (
            self.article_version_id, self.content_sha256,
            self.lane, self.query_key, self.feature_signature,
        )):
            raise ValueError("routing observation identity/signature is required")
        counts = (self.eligible_candidate_count, self.baseline_positive_count,
                  self.event_scored_pair_count, self.event_cluster_count)
        if any(not isinstance(value, int) or isinstance(value, bool) for value in counts):
            raise TypeError("routing observation counts must be scalar integers")
        if min(self.eligible_candidate_count, self.baseline_positive_count,
               self.event_scored_pair_count, self.event_cluster_count) < 0:
            raise ValueError("routing observation counts must be non-negative")
        arrays = (self.selected_candidate_ids, self.baseline_positive_top_ids,
                  self.canonical_remap_top, self.candidate_coordinates_top,
                  self.lane_census, self.event_pair_witness_top)
        if any(not isinstance(values, tuple) for values in arrays):
            raise TypeError("routing observation arrays must be immutable tuples")
        for values, width in ((self.canonical_remap_top, 2),
                              (self.candidate_coordinates_top, 5),
                              (self.lane_census, 2),
                              (self.event_pair_witness_top, 4)):
            if any(not isinstance(item, tuple) or len(item) != width for item in values):
                raise TypeError("routing observation rows must be fixed scalar tuples")
        if (len(self.selected_candidate_ids) > 64 or len(self.baseline_positive_top_ids) > 64
            or len(self.canonical_remap_top) > 8 or len(self.candidate_coordinates_top) > 16
            or len(self.lane_census) > 16 or len(self.event_pair_witness_top) > 16):
            raise ValueError("routing observation exceeds bounded inventory cap")
        if self.query_role is not None and not isinstance(self.query_role, str):
            raise TypeError("query role must be a scalar string")
        if self.baseline_winner_id is not None and not isinstance(self.baseline_winner_id, str):
            raise TypeError("baseline winner ID must be a scalar string")
        if any(not isinstance(value, str) for value in (
            *self.selected_candidate_ids, *self.baseline_positive_top_ids,
            *(part for row in self.canonical_remap_top for part in row),
        )):
            raise TypeError("routing observation IDs must be scalar strings")
        if self.query_char_span is not None:
            if (not isinstance(self.query_char_span, tuple)
                or len(self.query_char_span) != 2
                or any(not isinstance(value, int) or isinstance(value, bool)
                       for value in self.query_char_span)):
                raise TypeError("query character span must use scalar integers")
            if not 0 <= self.query_char_span[0] < self.query_char_span[1]:
                raise ValueError("query character span must be [start,end)")
        if (self.baseline_winner_score is not None
            and (not isinstance(self.baseline_winner_score, (int, float))
                 or not math.isfinite(self.baseline_winner_score))):
            raise ValueError("baseline winner score must be finite")
        for candidate_id, label, start, end, scope in self.candidate_coordinates_top:
            if any(not isinstance(value, str) for value in (candidate_id, label, scope)):
                raise TypeError("candidate descriptor cannot retain raw objects")
            if any(not isinstance(value, int) or isinstance(value, bool)
                   for value in (start, end)):
                raise TypeError("candidate coordinate must use scalar integers")
            if start < 0 or end <= start:
                raise ValueError("candidate coordinate must be [start,end)")
        for name, count in self.lane_census:
            if not isinstance(name, str) or not name or not isinstance(count, int) or count < 0:
                raise ValueError("lane census must contain named non-negative scalar counts")
        for left, right, score, status in self.event_pair_witness_top:
            if any(not isinstance(value, str) for value in (left, right, status)):
                raise TypeError("event pair witness cannot retain raw objects")
            if not isinstance(score, (int, float)) or not math.isfinite(score):
                raise ValueError("event pair witness score must be finite")


class StreamingRoutingObserver:
    """Capture sink는 독립 JSON scalar를 복사한다; raw owner는 받지 않는다."""

    def __init__(self, sink: DiagnosticSink) -> None:
        self._sink: DiagnosticSink | None = sink
        self.observed_count = 0

    def observe(self, observation: RoutingObservation) -> None:
        if self._sink is None:
            raise RuntimeError("routing observer already released")
        if not isinstance(observation, RoutingObservation):
            raise TypeError("routing observer accepts only typed scalar observations")
        self._sink.record("routing_snapshot", asdict(observation))
        self.observed_count += 1

    def observe_reference_scalar(self, kind: str, value: dict) -> None:
        """명시적 reference capture에서만 제한된 catalog/query/census를 기록한다."""
        if self._sink is None:
            raise RuntimeError("routing observer already released")
        if kind not in ("primary_catalog", "participant_query", "phase_b_census",
                        "phase_c_census") or not isinstance(value, dict):
            raise TypeError("unsupported reference scalar capture kind/value")
        detached = _independent(value)
        if kind == "primary_catalog" and len(detached.get("candidates", ())) > 64:
            raise ValueError("primary catalog chunk exceeds 64 scalar candidates")
        if kind == "participant_query" and len(detached.get("baseline_positive_top", ())) > 64:
            raise ValueError("participant positive inventory exceeds 64 pairs")
        self._sink.record(kind, detached)
        self.observed_count += 1

    def observe_bounded_scalar(self, kind: str, value: dict) -> None:
        """Emit bounded lane census without candidate/tensor capture."""
        if self._sink is None:
            raise RuntimeError("routing observer already released")
        if kind != "phase_b_bounded_census" or not isinstance(value, dict):
            raise TypeError("unsupported bounded scalar capture kind/value")
        self._sink.record(kind, _independent(value))
        self.observed_count += 1

    def close(self) -> None:
        self._sink = None

    def __enter__(self) -> "StreamingRoutingObserver":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
