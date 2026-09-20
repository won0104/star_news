"""A/B/C lane adapter가 공유하는 request-local 조회·예산·선택 계약.

Index는 최소 scalar/좌표만 소유한다. 전체 scorer universe를 만들거나 Gold를 읽지
않으며, bounded mode도 production에 연결되기 전의 비활성 인터페이스다.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Callable, Iterable


class RoutingMode(str, Enum):
    REFERENCE = "reference"
    SHADOW = "shadow"
    BOUNDED = "bounded"


TIERS = ("LOCAL", "NEAR", "GLOBAL")
FORBIDDEN_GLOBAL_KEYS = frozenset({"ALL", "*", "__ALL__", "GLOBAL_ALL"})


@dataclass(frozen=True, slots=True)
class TierBudget:
    local: int
    near: int
    global_: int
    rescue: int = 0

    def __post_init__(self) -> None:
        if any(not isinstance(value, int) or isinstance(value, bool)
               for value in (self.local, self.near, self.global_, self.rescue)):
            raise TypeError("tier budgets must be scalar integers")
        if min(self.local, self.near, self.global_, self.rescue) < 0:
            raise ValueError("tier budgets must be non-negative")

    def quota(self, tier: str) -> int:
        return {"LOCAL": self.local, "NEAR": self.near,
                "GLOBAL": self.global_, "RESCUE_ONLY": self.rescue}[tier]


@dataclass(frozen=True, slots=True)
class RoutingPolicy:
    policy_id: str
    revision: str
    lane: str
    feature_contract: str
    mode: RoutingMode
    tiers: TierBudget
    query_visit_budget: int
    query_cheap_budget: int
    query_fine_budget: int
    request_budget: int
    posting_visit_budget: int
    future_request_reserve: int = 0
    tie_break: str = "COARSE_DESC_CANDIDATE_ID_ASC"
    coarse_artifact_hash: str | None = None
    identity_mention_quota: int = 0

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value for value in (
            self.policy_id, self.revision, self.lane, self.feature_contract,
        )):
            raise ValueError("routing policy identity and feature contract are required")
        if self.coarse_artifact_hash is not None and not isinstance(self.coarse_artifact_hash, str):
            raise TypeError("coarse artifact hash must be a scalar string")
        if any(not isinstance(value, int) or isinstance(value, bool) for value in (
            self.query_visit_budget, self.query_cheap_budget,
            self.query_fine_budget, self.request_budget,
            self.posting_visit_budget, self.future_request_reserve,
            self.identity_mention_quota,
        )):
            raise TypeError("query/request/posting budgets must be scalar integers")
        if any(value <= 0 for value in (
            self.query_visit_budget, self.query_cheap_budget,
            self.query_fine_budget, self.request_budget, self.posting_visit_budget,
        )) or self.future_request_reserve < 0:
            raise ValueError("query/request/posting budgets must be positive")
        if self.tie_break != "COARSE_DESC_CANDIDATE_ID_ASC":
            raise ValueError("unsupported routing tie-break")
        if self.identity_mention_quota < 0:
            raise ValueError("identity mention quota must be non-negative")
        if not isinstance(self.mode, RoutingMode) or not isinstance(self.tiers, TierBudget):
            raise TypeError("routing mode and tier budget must be immutable contracts")
        if self.mode is not RoutingMode.REFERENCE and self.tiers.global_ <= 0:
            raise ValueError("shadow/bounded routing requires a GLOBAL reserve")
        if (self.query_visit_budget < self.tiers.global_
            or self.query_cheap_budget < self.tiers.global_
            or self.query_fine_budget < self.tiers.global_
            or self.request_budget < 3 * self.tiers.global_ + self.future_request_reserve):
            raise ValueError("query/request budget cannot cover GLOBAL visit/rank/fine reserve")


@dataclass(frozen=True, slots=True)
class IndexedCandidate:
    candidate_id: str
    article_version_id: str
    content_sha256: str
    feature_contract: str
    kind: str
    char_start: int
    char_end: int
    scope: str
    bucket_keys: tuple[str, ...]
    type_label: str = ""
    cheap_features: tuple[tuple[str, str | int | float | bool], ...] = ()
    identity_group: str = ""

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value for value in (
            self.candidate_id, self.article_version_id, self.content_sha256,
            self.feature_contract,
            self.kind, self.scope,
        )):
            raise ValueError("candidate identity/feature contract is required")
        if any(not isinstance(value, int) or isinstance(value, bool)
               for value in (self.char_start, self.char_end)):
            raise TypeError("candidate character span must use scalar integers")
        if self.char_start < 0 or self.char_end <= self.char_start:
            raise ValueError("candidate character span must be [start,end)")
        if not isinstance(self.type_label, str):
            raise TypeError("candidate type label must be a scalar string")
        if not isinstance(self.identity_group, str):
            raise TypeError("candidate identity group must be a scalar string")
        if not isinstance(self.bucket_keys, tuple) or not self.bucket_keys or any(
            not isinstance(key, str) or not key
                                       for key in self.bucket_keys):
            raise ValueError("candidate needs explicit indexed bucket keys")
        if not isinstance(self.cheap_features, tuple) or any(
            not isinstance(item, tuple) or len(item) != 2
            for item in self.cheap_features
        ):
            raise TypeError("candidate cheap feature rows must be immutable scalar pairs")
        if any(not isinstance(name, str) or not name
               or isinstance(value, float) and not math.isfinite(value)
               or not isinstance(value, (str, int, float, bool))
               for name, value in self.cheap_features):
            raise ValueError("indexed cheap features must be finite scalars")


class ArticleCandidateIndex:
    """요청에서 한 번 만든 inverted index; posting은 ID 정렬 후 제한 방문한다."""

    def __init__(self, candidates: Iterable[IndexedCandidate],
                 *, article_version_id: str | None = None,
                 content_sha256: str | None = None) -> None:
        rows: dict[str, IndexedCandidate] = {}
        postings: dict[str, list[str]] = defaultdict(list)
        article_version: str | None = article_version_id
        content_hash: str | None = content_sha256
        for row in candidates:
            if not isinstance(row, IndexedCandidate):
                raise TypeError("article index accepts only typed scalar candidate rows")
            if article_version is None:
                article_version = row.article_version_id
            if content_hash is None:
                content_hash = row.content_sha256
            if (row.article_version_id != article_version
                or row.content_sha256 != content_hash or row.candidate_id in rows):
                raise ValueError("index must contain one article hash and unique candidate IDs")
            rows[row.candidate_id] = row
            for key in set(row.bucket_keys):
                postings[key].append(row.candidate_id)
        if article_version is None or content_hash is None:
            raise ValueError("empty candidate index needs article version/content hash")
        self.article_version_id = article_version
        self.content_sha256 = content_hash
        self._rows = rows
        self._postings = {key: tuple(sorted(ids)) for key, ids in postings.items()}
        self._closed = False

    def posting(self, key: str) -> tuple[str, ...]:
        if self._closed:
            raise RuntimeError("candidate index already released")
        return self._postings.get(key, ())

    def row(self, candidate_id: str) -> IndexedCandidate:
        if self._closed:
            raise RuntimeError("candidate index already released")
        return self._rows[candidate_id]

    def close(self) -> None:
        self._rows.clear()
        self._postings.clear()
        self._closed = True

    def __enter__(self) -> "ArticleCandidateIndex":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def owner_census(self) -> dict[str, int | bool]:
        return {"candidate_count": len(self._rows), "posting_count": len(self._postings),
                "released": self._closed}


@dataclass(frozen=True, slots=True)
class RouteKeys:
    article_version_id: str
    content_sha256: str
    query_key: str
    feature_contract: str
    local: tuple[str, ...]
    near: tuple[str, ...]
    global_: tuple[str, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value for value in (
            self.article_version_id, self.content_sha256,
            self.query_key, self.feature_contract,
        )):
            raise ValueError("route query identity/feature contract is required")
        if any(not isinstance(keys, tuple) for keys in (self.local, self.near, self.global_)):
            raise TypeError("route bucket keys must be immutable tuples")
        if any(not isinstance(key, str) or not key
               for key in (*self.local, *self.near, *self.global_)):
            raise ValueError("route bucket keys must be explicit non-empty strings")
        if any(key.strip().upper() in FORBIDDEN_GLOBAL_KEYS
               or key.rsplit(":", 1)[-1].strip().upper() in FORBIDDEN_GLOBAL_KEYS
               for key in self.global_):
            raise ValueError("global ALL fallback is forbidden")
        # Bucket 수집 순서가 set/hash에서 왔어도 방문·overflow 순서는 고정한다.
        for name in ("local", "near", "global_"):
            object.__setattr__(self, name, tuple(sorted(set(getattr(self, name)))))

    def keys(self, tier: str) -> tuple[str, ...]:
        return {"LOCAL": self.local, "NEAR": self.near, "GLOBAL": self.global_}[tier]


@dataclass(slots=True)
class _QueryUsage:
    feature_contract: str
    routed: bool = False
    visited: int = 0
    cheaply_ranked: int = 0
    fine_scored: int = 0
    retained: int = 0
    skipped_by_budget: int = 0
    budget_exhausted: bool = False
    exhaustion_reasons: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class RouteDecision:
    policy_id: str
    mode: RoutingMode
    query_key: str
    selected_candidate_ids: tuple[str, ...]
    route_counts: tuple[tuple[str, int], ...]
    visited: int
    cheaply_ranked: int
    retained: int
    skipped_by_budget: int
    complete_search: bool
    budget_exhausted: bool
    exhaustion_reasons: tuple[str, ...]

    def fine_input_ids(self, reference_ids: Iterable[str]) -> tuple[str, ...]:
        """Shadow는 reference fine 입력을 그대로 보존하고 bounded만 selected를 쓴다."""
        if self.mode is RoutingMode.BOUNDED:
            return self.selected_candidate_ids
        return tuple(reference_ids)


def nested_tier_prefix(
    decision: RouteDecision, tiers: TierBudget,
) -> tuple[tuple[str, ...], dict[str, set[str]]]:
    """같은 제한 방문 결과의 LOCAL/NEAR/GLOBAL prefix를 더 작은 fine budget에 준다.

    호출자는 실제 fine 입력 전에 이 ID를 사용한다. 새 retrieval을 수행하지 않으므로
    작은 K도 원래 decision의 방문·cheap rank 비용을 공유한다.
    """
    counts = dict(decision.route_counts)
    if set(counts) != {"LOCAL", "NEAR", "GLOBAL"}:
        raise ValueError("route decision must contain three tier counts")
    local_stop = counts["LOCAL"]
    near_stop = local_stop + counts["NEAR"]
    if near_stop + counts["GLOBAL"] != len(decision.selected_candidate_ids):
        raise ValueError("tier counts differ from selected candidate IDs")
    local = decision.selected_candidate_ids[:local_stop][:tiers.local]
    near = decision.selected_candidate_ids[local_stop:near_stop][:tiers.near]
    global_ = decision.selected_candidate_ids[near_stop:][:tiers.global_]
    ids = tuple((*local, *near, *global_))
    return ids, {"LOCAL": set(local), "NEAR": set(near), "GLOBAL": set(global_)}


@dataclass(frozen=True, slots=True)
class RoutingSummary:
    query_key: str
    visited: int
    cheaply_ranked: int
    fine_scored: int
    retained: int
    skipped_by_budget: int
    budget_exhausted: bool
    exhaustion_reasons: tuple[str, ...]
    request_used: int
    request_remaining: int


class RequestBudget:
    """한 기사에서 여러 lane router가 공유하는 총 작업 단위 상한."""

    def __init__(self, total_units: int) -> None:
        if not isinstance(total_units, int) or isinstance(total_units, bool) or total_units <= 0:
            raise ValueError("request total budget must be positive")
        self.total_units = total_units
        self.used_units = 0


@dataclass(slots=True)
class RoutingExecutionLedger:
    """Full article inference, offline lane scoring, coarse training을 섞지 않는다."""

    model_load_count: int = 0
    article_inference_count: int = 0
    offline_lane_scoring_count: int = 0
    coarse_training_count: int = 0

    def add(self, name: str, count: int = 1) -> None:
        if name not in (
            "model_load_count", "article_inference_count",
            "offline_lane_scoring_count", "coarse_training_count",
        ) or count < 0:
            raise ValueError("unknown execution ledger field or negative count")
        setattr(self, name, getattr(self, name) + count)

    def snapshot(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in (
            "model_load_count", "article_inference_count",
            "offline_lane_scoring_count", "coarse_training_count",
        )}


class BudgetRouter:
    """한 article의 lane/query가 공유하는 방문·cheap·fine/request 계수기."""

    def __init__(self, policy: RoutingPolicy, index: ArticleCandidateIndex,
                 *, request: RequestBudget | None = None) -> None:
        self.policy = policy
        self.index = index
        self._query: dict[str, _QueryUsage] = {}
        self.request = request or RequestBudget(policy.request_budget)
        if self.request.total_units != policy.request_budget:
            raise ValueError("lane policy differs from shared request budget")

    def _usage(self, query_key: str, feature_contract: str) -> _QueryUsage:
        if feature_contract != self.policy.feature_contract:
            raise ValueError("query feature version differs from routing policy")
        existing = self._query.get(query_key)
        if existing is None:
            existing = _QueryUsage(feature_contract)
            self._query[query_key] = existing
        elif existing.feature_contract != feature_contract:
            raise ValueError("same query reused with another feature version")
        return existing

    def _charge(self, usage: _QueryUsage, kind: str, tier: str) -> bool:
        # LOCAL/NEAR가 global visit+rank+fine 몫을 가져가지 못한다.
        reserve = (3 * self.policy.tiers.global_ if tier != "GLOBAL" else 0)
        if self.request.used_units + 1 > (self.request.total_units
                                          - self.policy.future_request_reserve - reserve):
            usage.exhaustion_reasons.add("REQUEST_BUDGET_EXHAUSTED")
            usage.budget_exhausted = True
            return False
        current = getattr(usage, kind)
        limit = {"visited": self.policy.query_visit_budget,
                 "cheaply_ranked": self.policy.query_cheap_budget,
                 "retained": self.policy.query_fine_budget}[kind]
        if tier != "GLOBAL":
            limit -= self.policy.tiers.global_
        if current + 1 > limit:
            usage.exhaustion_reasons.add(f"QUERY_{kind.upper()}_BUDGET_EXHAUSTED")
            usage.budget_exhausted = True
            return False
        setattr(usage, kind, current + 1)
        self.request.used_units += 1
        return True

    def route(self, query: RouteKeys,
              coarse_ranker: Callable[[IndexedCandidate, RouteKeys], float],
              *, eligibility: Callable[[IndexedCandidate, RouteKeys], bool] | None = None
              ) -> RouteDecision:
        """명시 bucket만 제한 방문한다. 조회·rank 후 quota별 union을 반환한다."""
        if (query.article_version_id != self.index.article_version_id
            or query.content_sha256 != self.index.content_sha256):
            raise ValueError("route article version/content hash differs from index")
        usage = self._usage(query.query_key, query.feature_contract)
        if usage.routed:
            raise ValueError("one query may be routed only once")
        usage.routed = True
        selected: list[str] = []
        selected_set: set[str] = set()
        identity_counts: dict[str, int] = defaultdict(int)
        route_counts: list[tuple[str, int]] = []
        for tier in TIERS:
            quota = self.policy.tiers.quota(tier)
            if quota == 0:
                route_counts.append((tier, 0))
                continue
            ranked: dict[str, float] = {}
            for key in query.keys(tier):
                posting = self.index.posting(key)
                visited_here = 0
                for candidate_id in posting:
                    if visited_here >= self.policy.posting_visit_budget:
                        usage.exhaustion_reasons.add("POSTING_VISIT_BUDGET_EXHAUSTED")
                        usage.budget_exhausted = True
                        break
                    if not self._charge(usage, "visited", tier):
                        break
                    visited_here += 1
                    if candidate_id in ranked:
                        continue
                    row = self.index.row(candidate_id)
                    if row.feature_contract != self.policy.feature_contract:
                        raise ValueError("candidate feature version differs from routing policy")
                    if eligibility is not None and not eligibility(row, query):
                        continue
                    if not self._charge(usage, "cheaply_ranked", tier):
                        usage.skipped_by_budget += 1
                        break
                    score = float(coarse_ranker(row, query))
                    if not math.isfinite(score):
                        raise ValueError("coarse rank must be finite")
                    ranked[candidate_id] = score
                if visited_here < len(posting):
                    usage.skipped_by_budget += len(posting) - visited_here
                    usage.budget_exhausted = True
            if quota:
                added = 0
                for candidate_id in sorted(ranked, key=lambda item: (-ranked[item], item)):
                    if candidate_id in selected_set:
                        continue
                    if added >= quota:
                        break
                    group = self.index.row(candidate_id).identity_group
                    if (group and self.policy.identity_mention_quota
                        and identity_counts[group] >= self.policy.identity_mention_quota):
                        continue
                    if not self._charge(usage, "retained", tier):
                        usage.skipped_by_budget += 1
                        break
                    selected.append(candidate_id)
                    selected_set.add(candidate_id)
                    added += 1
                    if group:
                        identity_counts[group] += 1
            route_counts.append((tier, len(selected) - sum(count for _, count in route_counts)))
        return RouteDecision(
            self.policy.policy_id, self.policy.mode, query.query_key,
            tuple(selected), tuple(route_counts), usage.visited,
            usage.cheaply_ranked, usage.retained, usage.skipped_by_budget,
            not usage.budget_exhausted, usage.budget_exhausted,
            tuple(sorted(usage.exhaustion_reasons)),
        )

    def record_fine_scored(self, query_key: str, count: int) -> RoutingSummary:
        """Reference/shadow는 broad fine count를 관찰하고 bounded만 예산을 집행한다."""
        if count < 0 or query_key not in self._query:
            raise ValueError("fine count needs a routed query and non-negative count")
        usage = self._query[query_key]
        if self.policy.mode is RoutingMode.BOUNDED and usage.fine_scored + count > usage.retained:
            raise ValueError("bounded fine scorer exceeded selected candidate inventory")
        # 선정 시 fine slot을 request/query budget에 예약했다. Shadow의 broad fine 수는
        # 관찰값이며 선정 후보의 정밀 예산을 소비했다고 주장하지 않는다.
        usage.fine_scored += count
        return self.summary(query_key)

    def summary(self, query_key: str) -> RoutingSummary:
        usage = self._query[query_key]
        return RoutingSummary(
            query_key, usage.visited, usage.cheaply_ranked, usage.fine_scored,
            usage.retained, usage.skipped_by_budget, usage.budget_exhausted,
            tuple(sorted(usage.exhaustion_reasons)), self.request.used_units,
            self.request.total_units - self.request.used_units,
        )

    def release_query(self, query_key: str) -> None:
        """마지막 count 소비 뒤 query scalar만 버리고 shared request 사용량은 유지한다."""
        usage = self._query.pop(query_key)
        if not usage.routed:
            raise ValueError("cannot release an unrouted query")
