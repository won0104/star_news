"""Step 3에서 고정한 Participant→Entity r2 index와 K16 bounded 경로.

Scalar posting/cheap rank만 소유한다. Learned scorer·threshold·Gold·raw graph는
소유하지 않으며, 기본 v2.2 경로는 이 session을 생성하지 않는다.
"""

from __future__ import annotations

from collections import Counter
from bisect import bisect_left
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable

from .core import (
    ArticleCandidateIndex, BudgetRouter, IndexedCandidate, RequestBudget,
    RouteDecision, RouteKeys, RoutingMode, RoutingPolicy, RoutingSummary,
    TierBudget, nested_tier_prefix,
)


FEATURE = "PARTICIPANT_RESOLUTION_FINE_INPUT_V22_V1"
ROLE_TYPE_PRIOR = {
    "ACTOR": frozenset(("PERSON", "ORGANIZATION")),
    "TARGET": frozenset(("PERSON", "ORGANIZATION", "PRODUCT")),
    "PLACE": frozenset(("LOCATION",)),
}


def _grams(value: str) -> set[str]:
    return {value[index:index + 2] for index in range(len(value) - 1)}


def _alias_key(value: str) -> str:
    # Surface text `all`은 global ALL sentinel이 아니라 정확한 alias key다.
    return "0:global:alias-sha256:" + sha256(value.encode("utf-8")).hexdigest()[:20]


def _overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])


def _span_bins(start: int, end: int, width: int = 16) -> tuple[int, ...]:
    first, last = start // width, (end - 1) // width
    if last - first < 8:
        return tuple(range(first, last + 1))
    return tuple(sorted({first + (last - first) * step // 7 for step in range(8)}))


def build_participant_index(catalog: list[dict], version: str, content_hash: str
                            ) -> tuple[ArticleCandidateIndex, dict[str, dict], Counter]:
    """기사당 한 번 만든 scalar index. Query×M global 전수 후보 검색은 없다."""
    by_id = {row["prediction_id"]: row for row in catalog}
    if len(by_id) != len(catalog):
        raise ValueError("PRIMARY catalog candidate IDs are not unique")
    gram_frequency = Counter(gram for row in catalog for gram in _grams(row["text_norm"]))
    salience = sorted(catalog, key=lambda row: (
        -row["promotion_score"], -row["entity_score"], row["prediction_id"]
    ))
    salience_ids = set()
    group_counts = Counter()
    for row in salience:
        group = str(row["cluster_index"])
        if group_counts[group] >= 2:
            continue
        group_counts[group] += 1
        salience_ids.add(row["prediction_id"])
        if len(salience_ids) >= 64:
            break
    rows = []
    for item in catalog:
        sentence = int(item["sentence_index"])
        keys = [f"local:sentence:{sentence}",
                f"0:near:sentence:{sentence}", f"1:near:sentence:{sentence}"]
        keys += [f"local:overlap:{sentence}:{bin_id}"
                 for bin_id in _span_bins(item["char_start"], item["char_end"])]
        if item["text_norm"]:
            keys.append(_alias_key(item["text_norm"]))
            keys += [f"2:global:ngram:{gram_frequency[gram]:06d}:{gram}"
                     for gram in _grams(item["text_norm"])]
        if item["prediction_id"] in salience_ids:
            keys.append("1:global:salience:top64")
        rows.append(IndexedCandidate(
            item["prediction_id"], version, content_hash, FEATURE, "ENTITY",
            int(item["char_start"]), int(item["char_end"]), "CANONICAL_PRIMARY",
            tuple(sorted(set(keys))), item["entity_type"],
            (("priority_tier", item["priority_tier"]),
             ("promotion_score", float(item["promotion_score"])),
             ("entity_score", float(item["entity_score"])),
             ("sentence_index", sentence), ("text_norm", item["text_norm"])),
            str(item["cluster_index"]),
        ))
    return ArticleCandidateIndex(rows, article_version_id=version,
                                 content_sha256=content_hash), by_id, gram_frequency


def participant_route_keys(query: dict, gram_frequency: Counter) -> RouteKeys:
    """Overlap/sentence→adjacent discourse→indexed global의 r2 순서를 보존한다."""
    sentence = int(query["sentence_index"])
    local = [f"local:overlap:{sentence}:{bin_id}"
             for bin_id in _span_bins(query["char_start"], query["char_end"])]
    local.append(f"local:sentence:{sentence}")
    near = ([f"0:near:sentence:{other}" for other in
             (sentence - 1, sentence + 1) if other >= 0]
            + [f"1:near:sentence:{other}" for other in
               (sentence - 2, sentence + 2) if other >= 0])
    global_ = ["1:global:salience:top64"]
    text = query["text_norm"]
    if text:
        global_.insert(0, _alias_key(text))
        grams = sorted(_grams(text), key=lambda gram: (gram_frequency[gram], gram))[:4]
        global_ += [f"2:global:ngram:{gram_frequency[gram]:06d}:{gram}"
                    for gram in grams if gram_frequency[gram]]
    return RouteKeys(query["article_version_id"], query["content_sha256"],
                     query["query_key"], FEATURE, tuple(local), tuple(near),
                     tuple(global_))


def participant_coarse_score(item: dict, query: dict) -> float:
    """Step 3의 기존 offset/text/type/priority scalar rank. Final confidence가 아니다."""
    left, right = query["text_norm"], item["text_norm"]
    overlap = _overlap((query["char_start"], query["char_end"]),
                       (item["char_start"], item["char_end"]))
    distance = abs(int(query["sentence_index"]) - int(item["sentence_index"]))
    return (
        4.0 * float(bool(left and left == right))
        + 1.5 * float(bool(left and right and (left in right or right in left)))
        + 2.0 * float(overlap)
        + 0.7 * float(distance == 0)
        + 0.25 * float(distance == 1)
        + 0.10 * float(distance == 2)
        + 0.30 * float(item["priority_tier"] == "TIER1_PROMOTED")
        + 0.20 * float(item["entity_type"] in ROLE_TYPE_PRIOR[query["role"]])
        + 0.20 * float(item["promotion_score"])
        + 0.10 * float(item["entity_score"])
    )


@dataclass(frozen=True, slots=True)
class ParticipantEntityBoundedContract:
    """Step 3 manifest SHA에 고정된 우선 K16 또는 단일 보정 K32 경로."""

    policy_id: str
    revision: str
    retrieval_policy_id: str
    selected_tiers: TierBudget
    identity_mention_quota: int
    query_visit_budget: int
    query_cheap_budget: int
    posting_visit_budget: int
    manifest_sha256: str

    def __post_init__(self) -> None:
        selected = (
            (self.policy_id, self.selected_tiers)
            in (("BCR_A_SHADOW_NESTED_R2_K16", TierBudget(8, 4, 4)),
                ("BCR_A_SHADOW_NESTED_R2_K32", TierBudget(16, 8, 8)))
        )
        if (not selected or self.revision != "r2"
            or self.retrieval_policy_id != "BCR_A_SHADOW_SCALAR_R2_K64"
            or self.identity_mention_quota != 2
            or self.query_visit_budget != 88
            or self.query_cheap_budget != 88
            or self.posting_visit_budget != 32
            or len(self.manifest_sha256) != 64):
            raise ValueError("Participant bounded contract must be fixed Step 3 r2 K16/K32")

    @classmethod
    def from_manifest(cls, path: str | Path, *, use_single_wider_alternative=False
                      ) -> "ParticipantEntityBoundedContract":
        file = Path(path).resolve()
        raw = file.read_bytes()
        manifest = json.loads(raw)
        selected = manifest["priority"]
        curve_path = file.parent / manifest["source_curve_path"]
        if (sha256(curve_path.read_bytes()).hexdigest()
            != manifest["source_curve_sha256"]):
            raise ValueError("selected r2 curve digest differs")
        if (manifest["status"] != "SHADOW_POLICY_SELECTED_PENDING_ACTUAL_PHASE_A_QUALITY_GATE"
            or manifest["revision"] != "r2"
            or selected["policy_id"] != "BCR_A_SHADOW_NESTED_R2_K16"
            or selected["shared_retrieval_policy_id"] != "BCR_A_SHADOW_SCALAR_R2_K64"
            or selected["k_total"] != 16
            or selected["tier_quota"] != {"LOCAL": 8, "NEAR": 4, "GLOBAL": 4}
            or selected["identity_mention_quota"] != 2
            or selected["query_visit_budget"] != 88
            or selected["query_cheap_budget"] != 88
            or selected["posting_visit_budget"] != 32
            or selected["request_budget_formula"] != "max(captured_query_count,1) * (88 + 88 + 64)"
            or selected["coarse_tie_break"] != "COARSE_DESC_CANDIDATE_ID_ASC"
            or selected["fine_argmax_semantics_to_preserve"] != "SCORE_DESC_PREDICTION_ID_DESC"):
            raise ValueError("Step 3 selected bounded policy/version changed")
        curve = json.loads(curve_path.read_text(encoding="utf-8"))
        k16 = curve["curve"]["16"]
        k64_policy = curve["curve"]["64"]["policy"]
        if (k16["target_survival_over_reachable_gold"] < 0.99
            or k16["nesting_violation_query_count"]
            or k16["request_budget_violation_count"]
            or k16["policy"]["retrieval_cost_basis"]
               != "SHARED_K64_UPPER_BOUND_FOR_EACH_NESTED_K"
            or k64_policy["tier_quota"]
               != {"LOCAL": 32, "NEAR": 16, "GLOBAL": 16}
            or k64_policy["query_fine_budget"] != 64):
            raise ValueError("Step 3 shadow policy lacks selection evidence")
        chosen_id = selected["policy_id"]
        chosen_tiers = TierBudget(8, 4, 4)
        if use_single_wider_alternative:
            alternate = manifest["single_wider_alternative"]
            k32 = curve["curve"]["32"]
            if (alternate["policy_id"] != "BCR_A_SHADOW_NESTED_R2_K32"
                or alternate["k_total"] != 32
                or alternate["tier_quota"] != {"LOCAL": 16, "NEAR": 8, "GLOBAL": 8}
                or k32["target_survival_over_reachable_gold"] < 0.99
                or k32["nesting_violation_query_count"]
                or k32["request_budget_violation_count"]):
                raise ValueError("Step 3 single wider K32 correction evidence changed")
            chosen_id = alternate["policy_id"]
            chosen_tiers = TierBudget(16, 8, 8)
        return cls(chosen_id, manifest["revision"],
                   selected["shared_retrieval_policy_id"], chosen_tiers,
                   2, 88, 88, 32, sha256(raw).hexdigest())

    def retrieval_policy(self, query_count: int) -> RoutingPolicy:
        """K16 tier prefix 전 K64 공유 방문 비용을 정확히 예약한다."""
        if query_count < 0:
            raise ValueError("aligned filler query count must be non-negative")
        return RoutingPolicy(
            self.retrieval_policy_id, self.revision,
            "participant_entity_primary", FEATURE, RoutingMode.BOUNDED,
            TierBudget(32, 16, 16), self.query_visit_budget,
            self.query_cheap_budget, 64,
            max(query_count, 1) * (88 + 88 + 64),
            self.posting_visit_budget, identity_mention_quota=self.identity_mention_quota,
        )


@dataclass(frozen=True, slots=True)
class ParticipantEntitySelection:
    selected_candidate_ids: tuple[str, ...]
    tier_selected_ids: dict[str, set[str]]
    decision: RouteDecision


class BoundedRescueIndex:
    """Sentence별 시작 offset posting에서 overlap만 제한 방문하는 임시 pool."""

    def __init__(self, by_sentence: dict[int, list[dict]]) -> None:
        self._rows = {}
        self._starts = {}
        self._max_width = {}
        for sentence, rows in by_sentence.items():
            ordered = tuple(sorted(rows, key=lambda row: (
                int(row["char_start"]), int(row["char_end"]),
                str(row["source_family_id"]), str(row["prediction_id"]),
            )))
            self._rows[int(sentence)] = ordered
            self._starts[int(sentence)] = tuple(int(row["char_start"]) for row in ordered)
            self._max_width[int(sentence)] = max(
                (int(row["char_end"]) - int(row["char_start"]) for row in ordered),
                default=0,
            )

    def retrieve(self, filler: dict, session: "ParticipantEntityBoundedSession"
                 ) -> tuple[tuple[dict, ...], int, bool]:
        sentence = int(filler["sentence_index"])
        rows = self._rows.get(sentence, ())
        if not rows:
            return (), 0, False
        start, end = int(filler["char_start"]), int(filler["char_end"])
        cursor = bisect_left(self._starts[sentence], start - self._max_width[sentence])
        visited = 0
        eligible = []
        exhausted = False
        future_minimum = session.remaining_queries * 3 * session.router.policy.tiers.global_
        cap = session.contract.posting_visit_budget
        while cursor < len(rows) and int(rows[cursor]["char_start"]) < end:
            if visited >= cap or (session.router.request.used_units + 1 >
                                  session.router.request.total_units - future_minimum):
                exhausted = True
                break
            row = rows[cursor]
            cursor += 1
            visited += 1
            session.router.request.used_units += 1
            if _overlap((start, end),
                        (int(row["char_start"]), int(row["char_end"]))):
                eligible.append(row)
        return tuple(eligible), visited, exhausted

    def close(self) -> None:
        self._rows.clear()
        self._starts.clear()
        self._max_width.clear()


class ParticipantEntityBoundedSession:
    """한 기사에서만 살아 있는 r2 scalar index·K16 tier-prefix router."""

    def __init__(self, contract: ParticipantEntityBoundedContract,
                 catalog: list[dict], version: str, content_hash: str,
                 query_count: int, *, rescue_index: dict[int, list[dict]] | None = None,
                 entity_inventory_lineage: tuple[str, str] | None = None,
                 ) -> None:
        if (entity_inventory_lineage is not None
            and (not isinstance(entity_inventory_lineage, tuple)
                 or len(entity_inventory_lineage) != 2
                 or entity_inventory_lineage[0] != "STRUCTURAL_T14_C6"
                 or len(entity_inventory_lineage[1]) != 64)):
            raise ValueError("Participant index received invalid bounded Entity lineage")
        self.contract = contract
        self.entity_inventory_lineage = entity_inventory_lineage
        # This request-local key pins both routers and the actual current PRIMARY
        # inventory. No previous broad Entity index is reused across requests.
        material = {
            "article_version_id": version,
            "content_sha256": content_hash,
            "participant_routing_policy_id": contract.policy_id,
            "participant_policy_manifest_sha256": contract.manifest_sha256,
            "entity_span_policy_id": (entity_inventory_lineage[0]
                                      if entity_inventory_lineage else "BCR_REFERENCE_V22_V1"),
            "entity_span_policy_sha256": (entity_inventory_lineage[1]
                                          if entity_inventory_lineage else "REFERENCE"),
            "canonical_primary_inventory": sorted(
                (row["prediction_id"], row["entity_type"],
                 int(row["sentence_index"]), int(row["char_start"]),
                 int(row["char_end"]), row["text_norm"], row["priority_tier"],
                 float(row["promotion_score"]), float(row["entity_score"]),
                 int(row["cluster_index"])) for row in catalog
            ),
        }
        self.cache_key = sha256(json.dumps(material, ensure_ascii=False,
                                           sort_keys=True).encode("utf-8")).hexdigest()
        self.index, self.by_id, self.gram_frequency = build_participant_index(
            catalog, version, content_hash,
        )
        policy = contract.retrieval_policy(query_count)
        self.router = BudgetRouter(policy, self.index,
                                   request=RequestBudget(policy.request_budget))
        self.rescue_index = BoundedRescueIndex(rescue_index or {})
        self.remaining_queries = query_count
        self._closed = False

    def assert_cache_identity(self, *, version: str, content_hash: str,
                              entity_inventory_lineage: tuple[str, str] | None,
                              cache_key: str) -> None:
        if (self._closed or self.index.article_version_id != version
            or self.index.content_sha256 != content_hash
            or self.entity_inventory_lineage != entity_inventory_lineage
            or self.cache_key != cache_key):
            raise ValueError("Participant index cache identity/policy/inventory mismatch")

    def route(self, filler: dict, eligible: Callable[[dict, dict], bool]
              ) -> ParticipantEntitySelection:
        if self._closed or self.remaining_queries <= 0:
            raise RuntimeError("bounded session has no remaining aligned filler query")
        query = {
            "article_version_id": self.index.article_version_id,
            "content_sha256": self.index.content_sha256,
            "query_key": filler["participant_evidence_id"],
            "sentence_index": int(filler["sentence_index"]),
            "char_start": int(filler["char_start"]),
            "char_end": int(filler["char_end"]),
            "text_norm": "".join(str(filler["text"]).casefold().split()),
            "role": filler["role"],
        }
        key = participant_route_keys(query, self.gram_frequency)
        decision = self.router.route(
            key,
            lambda row, _key: participant_coarse_score(self.by_id[row.candidate_id], query),
            eligibility=lambda row, _key: eligible(filler, self.by_id[row.candidate_id]),
        )
        ids, tier_ids = nested_tier_prefix(decision, self.contract.selected_tiers)
        selected_cap = (self.contract.selected_tiers.local
                        + self.contract.selected_tiers.near
                        + self.contract.selected_tiers.global_)
        if len(ids) > selected_cap or len(set(ids)) != len(ids):
            raise RuntimeError("r2 selected inventory violated")
        self.remaining_queries -= 1
        return ParticipantEntitySelection(ids, tier_ids, decision)

    def reserve_rescue(self, allowed_count: int) -> tuple[int, bool]:
        """PRIMARY 실패 때만 K16 overlap alternative를 request 잔여 예산 안에 둔다."""
        if allowed_count < 0 or self._closed:
            raise ValueError("invalid failed-filler rescue inventory/session")
        # 이후 query의 GLOBAL 방문·rank·fine 최소 예약 3×K64 global quota.
        future_minimum = self.remaining_queries * 3 * self.router.policy.tiers.global_
        available = max(0, self.router.request.total_units
                        - self.router.request.used_units - future_minimum)
        count = min(allowed_count, 16, available)
        self.router.request.used_units += count  # Retrieval visit는 별도로 이미 계수했다.
        return count, count < allowed_count

    def retrieve_rescue(self, filler: dict) -> tuple[tuple[dict, ...], int, bool]:
        if self._closed:
            raise RuntimeError("bounded rescue index already released")
        return self.rescue_index.retrieve(filler, self)

    def record_and_release(self, query_key: str, actual_fine_count: int
                           ) -> RoutingSummary:
        if self._closed:
            raise RuntimeError("bounded session released before fine scorer")
        summary = self.router.record_fine_scored(query_key, actual_fine_count)
        self.router.release_query(query_key)
        return summary

    def close(self) -> None:
        if self._closed:
            return
        if self.router._query:
            raise RuntimeError("bounded query census retained after fine handoff")
        self.index.close()
        self.rescue_index.close()
        self.by_id.clear()
        self.gram_frequency.clear()
        self.cache_key = None
        self._closed = True
