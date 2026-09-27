"""Canonical EventMention→Time occurrence의 Step 5 bounded scalar routing.

저장 capture의 Time fine 비용이 작아 top64 global reserve로 관찰 범위의 모든
occurrence를 보존한다. Normalization, learned four-feature scorer와 PUBLIC은 소유하지
않는다. Clause는 원문 문장 안의 punctuation offset bucket이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re

from .core import (
    ArticleCandidateIndex, BudgetRouter, IndexedCandidate, RequestBudget,
    RouteDecision, RouteKeys, RoutingMode, RoutingPolicy, RoutingSummary, TierBudget,
)


FEATURE = "EVENT_TIME_FOUR_PAIR_FEATURES_V22_V1"
_CLAUSE_BOUNDARY = re.compile(r"[,;:!?…]")


@dataclass(frozen=True, slots=True)
class TemporalBoundedContract:
    """저장 shadow SHA와 fixed r1 K80 정책에 고정된 명시적 분석 계약."""

    policy_id: str
    revision: str
    tiers: TierBudget
    visit_budget: int
    cheap_budget: int
    fine_budget: int
    posting_budget: int
    manifest_sha256: str

    def __post_init__(self) -> None:
        if (self.policy_id != "BCR_A_TIME_OCCURRENCE_R1_K80"
            or self.revision != "r1" or self.tiers != TierBudget(8, 8, 64)
            or self.visit_budget != 192 or self.cheap_budget != 192
            or self.fine_budget != 80 or self.posting_budget != 64
            or len(self.manifest_sha256) != 64):
            raise ValueError("Time bounded contract must be fixed Step 5 r1 K80")

    @classmethod
    def from_manifest(cls, path: str | Path) -> "TemporalBoundedContract":
        file = Path(path).resolve()
        raw = file.read_bytes()
        manifest = json.loads(raw)
        shadow = file.parent / manifest["source_shadow_path"]
        if sha256(shadow.read_bytes()).hexdigest() != manifest["source_shadow_sha256"]:
            raise ValueError("Time source shadow digest differs")
        basis = json.loads(shadow.read_text(encoding="utf-8"))
        if (manifest["status"] != "SHADOW_SELECTED_PENDING_SMALL_GATE"
            or manifest["policy_id"] != "BCR_A_TIME_OCCURRENCE_R1_K80"
            or manifest["revision"] != "r1"
            or manifest["feature_contract"] != FEATURE
            or manifest["selected"] != {"LOCAL": 8, "NEAR": 8, "GLOBAL": 64}
            or manifest["query_visit_budget"] != 192
            or manifest["query_cheap_budget"] != 192
            or manifest["query_fine_budget"] != 80
            or manifest["posting_visit_budget"] != 64
            or manifest["request_budget_formula"]
               != "max(event_count,1) * (192 + 192 + 80)"
            or manifest["global_index"] != "FINITE_TIME_SCORE_TOP64_POSTING"
            or manifest["coarse_rank"]
               != "TIME_SCORE_AND_TEXT_OFFSET_DISTANCE_NO_PUBLISHED_AT"
            or manifest["global_all_fallback"] is not False
            or manifest["rescue_budget"] != 0
            or manifest["multiple_positive_attachments"] is not True
            or basis["reference_article_count"] != 40
            or basis["captured_max_accepted_pre_occurrence_per_article"] > 64
            or basis["profiled_max_canonical_time_occurrence_count"] > 64):
            raise ValueError("Time shadow-selected policy or evidence changed")
        return cls(manifest["policy_id"], manifest["revision"], TierBudget(8, 8, 64),
                   192, 192, 80, 64, sha256(raw).hexdigest())

    def routing_policy(self, event_count: int) -> RoutingPolicy:
        if event_count < 0:
            raise ValueError("canonical EventMention count must be non-negative")
        return RoutingPolicy(
            self.policy_id, self.revision, "event_time_attachment", FEATURE,
            RoutingMode.BOUNDED, self.tiers, self.visit_budget, self.cheap_budget,
            self.fine_budget, max(event_count, 1) * 464, self.posting_budget,
        )


class TemporalBoundedSession:
    """한 요청의 punctuation clause/문장/near/global posting과 query 예산."""

    def __init__(self, contract: TemporalBoundedContract, prepared, events, times):
        self.contract = contract
        self._closed = False
        self._remaining = len(events)
        self._time_index_by_id = {row["prediction_id"]: index
                                  for index, row in enumerate(times)}
        if len(self._time_index_by_id) != len(times):
            raise ValueError("canonical Time occurrence IDs are not unique")
        self._article_version = prepared.article.article_version_id
        self._content_sha = sha256(prepared.article.content.encode("utf-8")).hexdigest()
        self._clause_cuts = {}
        for sentence in prepared.sentences:
            index = int(sentence["sentence_index"])
            start, end = int(sentence["start"]), int(sentence["end"])
            self._clause_cuts[index] = tuple(
                start + match.start() for match in
                _CLAUSE_BOUNDARY.finditer(prepared.article.content[start:end])
            )
        top64 = {
            row["prediction_id"] for row in sorted(times, key=lambda row: (
                -float(row["score"]), row["prediction_id"],
            ))[:64]
        }
        self.unindexed_global_count = max(0, len(times) - 64)
        rows = []
        for row in times:
            sentence = int(row["sentence_index"])
            keys = [f"local:clause:{sentence}:{self._clause(sentence, int(row['char_start']))}",
                    f"local:sentence:{sentence}",
                    f"near:sentence:{sentence}"]
            if row["prediction_id"] in top64:
                keys.append("global:finite-time-score-top64")
            rows.append(IndexedCandidate(
                row["prediction_id"], self._article_version, self._content_sha,
                FEATURE, "TIME", int(row["char_start"]), int(row["char_end"]),
                "CANONICAL_TIME_OCCURRENCE", tuple(keys),
                cheap_features=(("sentence_index", sentence),
                                ("time_score", float(row["score"]))),
            ))
        self.index = ArticleCandidateIndex(rows,
                                           article_version_id=self._article_version,
                                           content_sha256=self._content_sha)
        policy = contract.routing_policy(len(events))
        self.router = BudgetRouter(policy, self.index,
                                   request=RequestBudget(policy.request_budget))
        self._events_seen = set()

    def _clause(self, sentence: int, start: int) -> int:
        return sum(cut < start for cut in self._clause_cuts.get(sentence, ()))

    def route(self, event: dict) -> RouteDecision:
        if self._closed or self._remaining <= 0:
            raise RuntimeError("Time session has no remaining canonical EventMention")
        query_id = str(event["prediction_id"])
        if query_id in self._events_seen:
            raise ValueError("canonical EventMention query ID repeated")
        sentence = int(event["sentence_index"])
        clause = self._clause(sentence, int(event["char_start"]))
        keys = RouteKeys(
            self._article_version, self._content_sha, query_id, FEATURE,
            (f"local:clause:{sentence}:{clause}", f"local:sentence:{sentence}"),
            tuple(f"near:sentence:{other}" for other in
                  (sentence - 2, sentence - 1, sentence + 1, sentence + 2)
                  if other >= 0),
            ("global:finite-time-score-top64",),
        )
        start, end = int(event["char_start"]), int(event["char_end"])
        def cheap_score(row, _keys):
            features = dict(row.cheap_features)
            time_sentence = features["sentence_index"]
            return (2.0 * float(row.char_start >= start and row.char_end <= end)
                    + 0.6 * float(time_sentence == sentence)
                    + 0.2 * float(abs(time_sentence - sentence) <= 2)
                    + 0.4 * float(features["time_score"])
                    - min(1.0, abs(row.char_start - start) / 10000.0))

        decision = self.router.route(keys, cheap_score)
        self._events_seen.add(query_id)
        self._remaining -= 1
        return decision

    def selected_indices(self, decision: RouteDecision) -> tuple[int, ...]:
        return tuple(self._time_index_by_id[candidate_id]
                     for candidate_id in decision.selected_candidate_ids)

    def record_and_release(self, event_id: str, actual_fine_count: int
                           ) -> RoutingSummary:
        if self._closed:
            raise RuntimeError("Time session released before fine scorer")
        summary = self.router.record_fine_scored(event_id, actual_fine_count)
        self.router.release_query(event_id)
        return summary

    @property
    def remaining_queries(self) -> int:
        return self._remaining

    def close(self) -> None:
        if self._closed:
            return
        if self._remaining or self.router._query:
            raise RuntimeError("Time query/router state survives final consumer")
        self.index.close()
        self._time_index_by_id.clear()
        self._clause_cuts.clear()
        self._events_seen.clear()
        self._closed = True
