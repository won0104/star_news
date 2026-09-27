"""Gold 없는 source-token endpoint 제안과 exact 문자 복원.

정책 예산은 임시이며 production threshold가 아니다. 제한에 걸리면 partial을
명시한다. 중복 window는 절대 문자 좌표로 닫고 반복 occurrence는 보존한다.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field, replace
from heapq import nsmallest
import math
from types import SimpleNamespace

import torch

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from models.v3_pretraining.exact_span import KIND_LAYER
from models.v3_pretraining.extraction_heads import ENTITY_TYPES, STATEMENT_TYPES
from models.v3_pretraining.extraction_heads import PARTICIPANT_ROLES
from runtime.v3_pretraining.exact_feature_cache import (NativeEntityStateRow,
                                                        RequestExactFeatureCache,
                                                        exact_source_features)
from runtime.candidate_routing.span_budget import (
    Budget as StructuralBudget, Lane as StructuralLane,
    TIME_CUES, pair_candidate_count, unary_positions,
)
from runtime.eventframe.candidate_iteration import iter_bounded_span_candidates
from runtime.v3_pretraining.source_layout import SourceLayout, SourceWindow, SpanAlignment
from runtime.v3_pretraining.v23_features import (canonical_scores, event_candidate_state,
                                                  local_source_states, native_states,
                                                  NativeCandidateBatch, sentence_cell)


V23_PARTICIPANT_CHAR_CACHE_LIMIT = 8192
V23_NATIVE_DECODE_CHUNK_SIZE = {"ENTITY": 256, "TIME": 1024}


@dataclass(frozen=True, slots=True)
class DecodeBudget:
    max_starts: int = 64
    max_ends: int = 64
    max_pairs: int = 256
    chunk_size: int = 64
    status: str = "PROVISIONAL_ENGINEERING_ONLY"

    def __post_init__(self) -> None:
        if min(self.max_starts, self.max_ends, self.max_pairs, self.chunk_size) <= 0:
            raise ValueError("decode budgets must be positive")


@dataclass(frozen=True, slots=True)
class DecodedSourceSpan:
    kind: str
    label: str | None
    start: int
    end: int
    text: str
    score: float
    start_window_id: str
    end_window_id: str
    score_components: tuple[tuple[str, float], ...] = ()
    subtype_scores: tuple[tuple[str, float], ...] = ()
    provenance_windows: tuple[tuple[str, str], ...] = ()
    route_provenance: tuple["RouteProvenance", ...] = ()
    boundary_fitness_score: float | None = None

    @property
    def extraction_score(self) -> float:
        """Final exact-candidate decision logit used by rank/legacy acceptance."""
        return self.score


def _window_provenance(span: DecodedSourceSpan) -> tuple[tuple[str, str], ...]:
    return span.provenance_windows or ((span.start_window_id, span.end_window_id),)


def _merge_window_provenance(winner: DecodedSourceSpan,
                             other: DecodedSourceSpan) -> DecodedSourceSpan:
    merged = tuple(dict.fromkeys(_window_provenance(winner) + _window_provenance(other)))
    routes = tuple(sorted(
        set(winner.route_provenance + other.route_provenance),
        key=lambda row: row.order_key,
    ))
    return replace(winner, provenance_windows=merged, route_provenance=routes)


@dataclass(frozen=True, slots=True)
class RouteProvenance:
    """한 absolute candidate가 어느 retrieval route/window에서 왔는지 보존한다."""

    route: str
    start_window_id: str
    end_window_id: str
    retrieval_score: float
    producer: str = "V3_WINDOW"

    def __post_init__(self) -> None:
        if (self.route not in ("in_window", "cross_window")
                or not self.start_window_id or not self.end_window_id
                or not math.isfinite(self.retrieval_score) or not self.producer):
            raise ValueError("route provenance is invalid")

    @property
    def order_key(self) -> tuple[int, str, str, float, str]:
        return (0 if self.route == "in_window" else 1,
                self.start_window_id, self.end_window_id,
                -self.retrieval_score, self.producer)


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    """Fine scoring 전 absolute source candidate와 모든 route provenance."""

    kind: str
    start: int
    end: int
    route_provenance: tuple[RouteProvenance, ...]
    route_rank_scores: tuple[tuple[str, float], ...]
    route_rank_windows: tuple[tuple[str, str, str], ...]

    def __post_init__(self) -> None:
        routes = {row.route for row in self.route_provenance}
        if (self.kind not in KIND_LAYER or not 0 <= self.start < self.end
                or not self.route_provenance
                or routes != {name for name, _score in self.route_rank_scores}
                or routes != {name for name, _start, _end in self.route_rank_windows}):
            raise ValueError("route candidate contract differs")

    @property
    def key(self) -> tuple[str, int, int]:
        return self.kind, self.start, self.end

    def rank_score(self, route: str) -> float:
        return dict(self.route_rank_scores)[route]

    def rank_windows(self, route: str) -> tuple[str, str]:
        rows = {name: (start, end) for name, start, end in self.route_rank_windows}
        return rows[route]

    @property
    def diagnostic_provenance(self) -> RouteProvenance:
        """Trace용 retrieval score 하나를 score 비교 없이 고른다.

        Exact feature의 primary window는 이 값이 아니라 layout의 containing
        window를 기준으로 ``_route_candidate_alignment``가 별도로 결정한다.
        """
        in_window = [row for row in self.route_provenance if row.route == "in_window"]
        pool = in_window or list(self.route_provenance)
        return min(pool, key=lambda row: (row.start_window_id, row.end_window_id))


def _raw_route_candidate(*, kind: str, start: int, end: int, route: str,
                         start_window_id: str, end_window_id: str,
                         score: float, producer: str = "V3_WINDOW") -> RouteCandidate:
    provenance = RouteProvenance(route, start_window_id, end_window_id,
                                 score, producer)
    return RouteCandidate(kind, start, end, (provenance,), ((route, score),),
                          ((route, start_window_id, end_window_id),))


@dataclass(frozen=True, slots=True)
class RetrievalBudget:
    """Profile-bound retrieval settings; article cap is active only in V3_WINDOW.

    V23_BASELINE ignores the D3 route quota and article guard for other kinds.
    Participant uses max_scored_candidates as its per-Event×role fine budget.
    """

    per_window_starts: int = 12
    per_window_ends: int = 12
    per_window_pairs: int = 16
    proposal_top_k: int = 16          # EVENT/STATEMENT in-window joint proposal cell
    max_span_tokens: int = 48         # in-window 폭 상한. cross-window는 별도 경로가 맡는다
    cross_window_starts: int = 12
    cross_window_ends: int = 12
    cross_window_pairs: int = 24
    max_scored_candidates: int = 192  # V3 article guard / V23 Participant fine budget
    chunk_size: int = 32
    status: str = "PROVISIONAL_ENGINEERING_ONLY"
    candidate_profile: str = "V3_WINDOW"  # old artifacts omit this field

    def __post_init__(self) -> None:
        if min(self.per_window_starts, self.per_window_ends, self.per_window_pairs,
               self.proposal_top_k, self.max_span_tokens, self.cross_window_starts,
               self.cross_window_ends, self.cross_window_pairs,
               self.max_scored_candidates, self.chunk_size) <= 0:
            raise ValueError("retrieval budgets must be positive")
        if self.candidate_profile == "V3_WINDOW" and self.max_scored_candidates % 2:
            raise ValueError("D3 route quota needs an even fine-scoring budget")
        if self.candidate_profile not in ("V3_WINDOW", "V23_BASELINE"):
            raise ValueError("unknown source candidate profile")
        if self.candidate_profile == "V23_BASELINE" and (
                self.proposal_top_k != 32 or self.max_span_tokens != 96):
            raise ValueError("v2.3 baseline requires TOP32 and 96-token semantic cells")

    @property
    def route_quota(self) -> int:
        """D3는 default 192를 두 route에 96/96으로 똑같이 예약한다."""
        if self.candidate_profile == "V23_BASELINE":
            raise ValueError("v2.3 baseline has no route quota")
        return self.max_scored_candidates // 2


@dataclass(frozen=True, slots=True)
class RetrievalTrace:
    """후보 수·방문량·정밀 평가량을 분리해 기록한다."""

    visited_cells: int = 0
    in_window_proposed: int = 0
    cross_window_proposed: int = 0
    unique_candidates: int = 0
    scored_candidates: int = 0
    dropped_by_article_guard: int = 0
    width_masked_cells: int = 0  # 폭 제한으로 제외한 격자 cell. 설계 파라미터이며 partial이 아니다
    in_window_deduplicated: int = 0
    cross_window_deduplicated: int = 0
    in_window_quota_selected: int = 0
    cross_window_quota_selected: int = 0
    quota_borrowed_by_in_window: int = 0
    quota_borrowed_by_cross_window: int = 0
    union_deduplicated: int = 0
    both_route_provenance: int = 0
    fine_scored_in_window: int = 0
    fine_scored_cross_window: int = 0
    fine_scored_both_route: int = 0

    def as_dict(self, *, final_cap_count: int | None = None) -> dict[str, int]:
        result = {
            "visited_cells": self.visited_cells,
            "raw_in_window_candidates": self.in_window_proposed,
            "raw_cross_window_candidates": self.cross_window_proposed,
            # 이전 artifact reader와의 호환 alias.
            "in_window_proposed": self.in_window_proposed,
            "cross_window_proposed": self.cross_window_proposed,
            "in_window_deduplicated": self.in_window_deduplicated,
            "cross_window_deduplicated": self.cross_window_deduplicated,
            "in_window_quota_selected": self.in_window_quota_selected,
            "cross_window_quota_selected": self.cross_window_quota_selected,
            "quota_borrowed_by_in_window": self.quota_borrowed_by_in_window,
            "quota_borrowed_by_cross_window": self.quota_borrowed_by_cross_window,
            "quota_borrowing_count": (self.quota_borrowed_by_in_window
                                      + self.quota_borrowed_by_cross_window),
            "union_deduplicated": self.union_deduplicated,
            "both_route_provenance": self.both_route_provenance,
            "fine_scored_in_window": self.fine_scored_in_window,
            "fine_scored_cross_window": self.fine_scored_cross_window,
            "fine_scored_both_route": self.fine_scored_both_route,
            "unique_candidates": self.unique_candidates,
            "final_fine_scored_count": self.scored_candidates,
            "scored_candidates": self.scored_candidates,
            "dropped_by_article_guard": self.dropped_by_article_guard,
            "width_masked_cells": self.width_masked_cells,
        }
        if final_cap_count is not None:
            if final_cap_count < 0:
                raise ValueError("final cap count cannot be negative")
            result["final_cap_count"] = final_cap_count
        return result


def _merge_route_candidate(left: RouteCandidate,
                           right: RouteCandidate) -> RouteCandidate:
    if left.key != right.key:
        raise ValueError("only the same absolute candidate can merge")
    provenance = tuple(sorted(
        set(left.route_provenance + right.route_provenance),
        key=lambda row: row.order_key,
    ))
    scores = dict(left.route_rank_scores)
    scores.update(right.route_rank_scores)
    windows = {name: (start, end)
               for name, start, end in left.route_rank_windows}
    windows.update({name: (start, end)
                    for name, start, end in right.route_rank_windows})
    return RouteCandidate(
        left.kind, left.start, left.end, provenance,
        tuple(sorted(scores.items())),
        tuple((name, *windows[name]) for name in sorted(windows)),
    )


def _deduplicate_route(candidates: list[RouteCandidate], *, route: str) -> list[RouteCandidate]:
    """한 route 안에서만 score를 비교하고 모든 source-window 근거를 남긴다."""
    grouped: dict[tuple[str, int, int], list[RouteCandidate]] = {}
    for row in candidates:
        if {item.route for item in row.route_provenance} != {route}:
            raise ValueError("route-local dedup received another route")
        grouped.setdefault(row.key, []).append(row)
    result: list[RouteCandidate] = []
    for key in sorted(grouped):
        rows = grouped[key]
        ranked = sorted(
            rows,
            key=lambda row: (
                -row.rank_score(route), row.start, row.end,
                *row.rank_windows(route),
            ),
        )
        winner = ranked[0]
        provenance = tuple(sorted(
            {item for row in rows for item in row.route_provenance},
            key=lambda item: item.order_key,
        ))
        result.append(RouteCandidate(
            winner.kind, winner.start, winner.end, provenance,
            ((route, winner.rank_score(route)),),
            ((route, *winner.rank_windows(route)),),
        ))
    return sorted(
        result,
        key=lambda row: (
            -row.rank_score(route), row.start, row.end,
            *row.rank_windows(route),
        ),
    )


def select_route_candidates(*, in_window: list[RouteCandidate],
                            cross_window: list[RouteCandidate],
                            retrieval: RetrievalBudget) -> tuple[tuple[RouteCandidate, ...], RetrievalTrace]:
    """D3의 route-local rank, 96/96 reserve, union dedup과 borrowing을 수행한다.

    서로 다른 route score는 어느 비교식에도 함께 들어가지 않는다. 초기 quota 뒤
    빈 slot은 in→cross round-robin으로 보충한다.
    """
    local = _deduplicate_route(in_window, route="in_window")
    cross = _deduplicate_route(cross_window, route="cross_window")
    full_union: dict[tuple[str, int, int], RouteCandidate] = {}
    for row in (*local, *cross):
        old = full_union.get(row.key)
        full_union[row.key] = row if old is None else _merge_route_candidate(old, row)
    full_keys = set(full_union)
    both_keys = {row.key for row in local} & {row.key for row in cross}
    quota = retrieval.route_quota
    initial_local = local[:quota]
    initial_cross = cross[:quota]
    selected: dict[tuple[str, int, int], RouteCandidate] = {}

    def add(row: RouteCandidate) -> bool:
        old = selected.get(row.key)
        if old is None:
            selected[row.key] = row
            return True
        selected[row.key] = _merge_route_candidate(old, row)
        return False

    for row in initial_local:
        add(row)
    for row in initial_cross:
        add(row)
    positions = {"in_window": len(initial_local), "cross_window": len(initial_cross)}
    pools = {"in_window": local, "cross_window": cross}
    borrowed = {"in_window": 0, "cross_window": 0}
    while len(selected) < retrieval.max_scored_candidates:
        progressed = False
        for route in ("in_window", "cross_window"):
            position = positions[route]
            if position >= len(pools[route]):
                continue
            row = pools[route][position]
            positions[route] += 1
            progressed = True
            if add(row):
                borrowed[route] += 1
                if len(selected) >= retrieval.max_scored_candidates:
                    break
        if not progressed:
            break
    # 한 route occurrence가 quota 밖이더라도 다른 route에서 같은 absolute span이
    # fine-scoring 대상으로 선택됐다면 raw producer provenance는 전부 보존한다.
    ordered = tuple(full_union[key] for key in sorted(selected))
    trace = RetrievalTrace(
        in_window_proposed=len(in_window),
        cross_window_proposed=len(cross_window),
        in_window_deduplicated=len(local),
        cross_window_deduplicated=len(cross),
        in_window_quota_selected=len(initial_local),
        cross_window_quota_selected=len(initial_cross),
        quota_borrowed_by_in_window=borrowed["in_window"],
        quota_borrowed_by_cross_window=borrowed["cross_window"],
        union_deduplicated=len(full_keys),
        both_route_provenance=len(both_keys),
        fine_scored_in_window=sum(
            "in_window" in {item.route for item in row.route_provenance}
            for row in ordered
        ),
        fine_scored_cross_window=sum(
            "cross_window" in {item.route for item in row.route_provenance}
            for row in ordered
        ),
        fine_scored_both_route=sum(
            {item.route for item in row.route_provenance}
            == {"in_window", "cross_window"}
            for row in ordered
        ),
        unique_candidates=len(full_keys),
        scored_candidates=len(ordered),
        dropped_by_article_guard=max(0, len(full_keys) - len(ordered)),
    )
    return ordered, trace


def select_v23_candidates(*, local: list[RouteCandidate],
                          extension: list[RouteCandidate]) -> tuple[tuple[RouteCandidate, ...], RetrievalTrace]:
    """Forward the complete v2.3 bounded stream; add only uncovered cross spans.

    Structural and endpoint ranks have different meanings and never compete here.
    The deduplication key is the exact source coordinate, not a score or a Gold ID.
    """
    local_rows = _deduplicate_route(
        [row for row in local if row.route_provenance[0].route == "in_window"],
        route="in_window")
    bounded_cross = _deduplicate_route(
        [row for row in local if row.route_provenance[0].route == "cross_window"],
        route="cross_window")
    selected = {row.key: row for row in local_rows}
    for row in bounded_cross:
        selected[row.key] = (_merge_route_candidate(selected[row.key], row)
                             if row.key in selected else row)
    extension_rows = _deduplicate_route(extension, route="cross_window")
    extension_added = 0
    for row in extension_rows:
        if row.key not in selected:
            selected[row.key] = row
            extension_added += 1
        # A duplicate belongs to the v2.3 producer, including its rank/provenance.
    ordered = tuple(selected[key] for key in sorted(selected))
    local_keys = {row.key for row in local_rows}
    both_count = sum({part.route for part in row.route_provenance} ==
                     {"in_window", "cross_window"} for row in ordered)
    cross_count = sum(any(part.route == "cross_window" for part in row.route_provenance)
                      for row in ordered)
    trace = RetrievalTrace(
        in_window_proposed=sum(row.route_provenance[0].route == "in_window" for row in local),
        cross_window_proposed=sum(row.route_provenance[0].route == "cross_window" for row in local)
        + len(extension),
        in_window_deduplicated=len(local_rows),
        cross_window_deduplicated=len(bounded_cross) + extension_added,
        union_deduplicated=len(ordered),
        both_route_provenance=both_count,
        fine_scored_in_window=len(local_keys),
        fine_scored_cross_window=cross_count,
        fine_scored_both_route=both_count,
        unique_candidates=len(ordered), scored_candidates=len(ordered),
        dropped_by_article_guard=0)
    return ordered, trace


def _bound_v23_participant_fine_routes(
        rows: tuple[RouteCandidate, ...], limit: int) -> tuple[RouteCandidate, ...]:
    """Keep the highest B2 proposals before exact feature and fine-head work."""
    if limit <= 0:
        raise ValueError("Participant fine candidate budget must be positive")

    def rank(row: RouteCandidate) -> tuple:
        local = any(item.route == "in_window" for item in row.route_provenance)
        route = "in_window" if local else "cross_window"
        return (0 if local else 1, -row.rank_score(route), row.start, row.end)

    return tuple(sorted(nsmallest(limit, rows, key=rank), key=lambda row: row.key))


V23_EXPENSIVE_ARTICLE_SAFETY_CEILING = {"ENTITY": 65_536, "TIME": 65_536}


def _v23_expensive_safety_guard(
        rows: tuple[RouteCandidate, ...], trace: RetrievalTrace, *, kind: str,
        limit: int) -> tuple[tuple[RouteCandidate, ...], RetrievalTrace]:
    """Bound only pathological V23 fine-scoring streams by existing cheap rank.

    The native bounded producer precedes the additive exact extension because
    their rank scores have different contracts. Within each producer, the
    structural score and exact coordinates give a deterministic order.
    """
    if kind not in V23_EXPENSIVE_ARTICLE_SAFETY_CEILING or limit <= 0:
        raise ValueError("V23 expensive safety guard needs Entity/Time and positive limit")
    if len(rows) <= limit:
        return rows, trace

    def rank(row: RouteCandidate) -> tuple[object, ...]:
        native = any(part.producer == "V23_BOUNDED" for part in row.route_provenance)
        return (0 if native else 1,
                -max(score for _route, score in row.route_rank_scores),
                row.start, row.end,
                tuple(sorted((part.route, part.start_window_id, part.end_window_id)
                             for part in row.route_provenance)))

    retained = tuple(sorted(sorted(rows, key=rank)[:limit], key=lambda row: row.key))
    return retained, replace(trace, scored_candidates=len(retained),
                             dropped_by_article_guard=len(rows) - len(retained),
                             fine_scored_in_window=sum(any(
                                 part.route == "in_window" for part in row.route_provenance)
                                 for row in retained),
                             fine_scored_cross_window=sum(any(
                                 part.route == "cross_window" for part in row.route_provenance)
                                 for row in retained),
                             fine_scored_both_route=sum(len({
                                 part.route for part in row.route_provenance}) == 2
                                 for row in retained))


@dataclass(frozen=True, slots=True)
class _V23RouteRecipe:
    """Compact pre-cap source route; materialize provenance only after selection."""

    kind: str
    start: int
    end: int
    route: str
    start_window_id: str
    end_window_id: str
    score: float
    producer: str

    @property
    def key(self) -> tuple[str, int, int]:
        return self.kind, self.start, self.end


def _v23_recipe(row: RouteCandidate | _V23RouteRecipe) -> _V23RouteRecipe:
    if isinstance(row, _V23RouteRecipe):
        return row
    if len(row.route_rank_scores) != 1:
        raise ValueError("compact V23 route needs one route-local score")
    route, score = row.route_rank_scores[0]
    if len(row.route_provenance) != 1 or row.route_provenance[0].route != route:
        raise ValueError("compact V23 route needs one raw provenance")
    start_window, end_window = row.rank_windows(route)
    return _V23RouteRecipe(row.kind, row.start, row.end, route,
                           start_window, end_window, score,
                           row.route_provenance[0].producer)


@dataclass(slots=True)
class _V23RouteBucket:
    """Keep one route winner; allocate duplicate evidence only when it exists."""

    in_winner: _V23RouteRecipe | None = None
    cross_winner: _V23RouteRecipe | None = None
    in_sources: list[_V23RouteRecipe] | None = None
    cross_sources: list[_V23RouteRecipe] | None = None

    def add(self, recipe: _V23RouteRecipe) -> None:
        if recipe.route == "in_window":
            winner_attr, source_attr = "in_winner", "in_sources"
        elif recipe.route == "cross_window":
            winner_attr, source_attr = "cross_winner", "cross_sources"
        else:
            raise ValueError("V23 raw route differs")
        winner = getattr(self, winner_attr)
        if winner is None:
            setattr(self, winner_attr, recipe)
            return
        sources = getattr(self, source_attr)
        if sources is None:
            sources = [winner]
            setattr(self, source_attr, sources)
        sources.append(recipe)
        # The former route-local sort retained the first row on an exact tie.
        if (-recipe.score, recipe.start, recipe.end,
                recipe.start_window_id, recipe.end_window_id) < (
                -winner.score, winner.start, winner.end,
                winner.start_window_id, winner.end_window_id):
            setattr(self, winner_attr, recipe)

    def sources(self) -> tuple[_V23RouteRecipe, ...]:
        return tuple(self.in_sources or ((self.in_winner,) if self.in_winner else ())) + \
            tuple(self.cross_sources or ((self.cross_winner,) if self.cross_winner else ()))


def _select_v23_candidates_capped(
        *, local: list[RouteCandidate | _V23RouteRecipe],
        extension: list[RouteCandidate], kind: str, limit: int
        ) -> tuple[tuple[RouteCandidate, ...], RetrievalTrace]:
    """Single-pass route closure followed by producer-ordered bounded selection.

    This is the Entity/Time request path. The public uncapped selector and
    guard remain available for legacy callers and parity fixtures.
    """
    if kind not in V23_EXPENSIVE_ARTICLE_SAFETY_CEILING or limit <= 0:
        raise ValueError("V23 compact selection needs Entity/Time and positive limit")
    routes: dict[tuple[str, int, int], _V23RouteBucket] = {}

    def add(recipe: _V23RouteRecipe) -> None:
        if recipe.kind != kind:
            raise ValueError("V23 compact candidate kind differs")
        bucket = routes.get(recipe.key)
        if bucket is None:
            bucket = _V23RouteBucket()
            routes[recipe.key] = bucket
        bucket.add(recipe)

    in_proposed = cross_proposed = 0
    for row in local:
        recipe = _v23_recipe(row)
        if recipe.route == "in_window":
            in_proposed += 1
        elif recipe.route == "cross_window":
            cross_proposed += 1
        else:
            raise ValueError("V23 local route differs")
        add(recipe)
    native_keys = set(routes)
    in_unique = sum(row.in_winner is not None for row in routes.values())
    cross_unique_native = sum(row.cross_winner is not None for row in routes.values())
    cross_proposed += len(extension)
    for row in extension:
        recipe = _v23_recipe(row)
        if recipe.route != "cross_window" or recipe.producer != "V23_EXACT_EXTENSION":
            raise ValueError("V23 exact extension route differs")
        if recipe.key not in native_keys:
            add(recipe)
    extension_added = len(routes) - len(native_keys)
    union_count = len(routes)
    both_count = sum(row.in_winner is not None and row.cross_winner is not None
                     for row in routes.values())
    cross_count = sum(row.cross_winner is not None for row in routes.values())

    def cheap_rank(item: tuple[tuple[str, int, int], _V23RouteBucket]) -> tuple:
        key, bucket = item
        winners = tuple(row for row in (bucket.in_winner, bucket.cross_winner)
                        if row is not None)
        native = any(row.producer == "V23_BOUNDED" for row in winners)
        return (0 if native else 1,
                -max(row.score for row in winners),
                key[1], key[2])

    retained = (nsmallest(limit, routes.items(), key=cheap_rank)
                if union_count > limit else routes.items())
    selected = []
    selected_buckets = []
    for key, bucket in retained:
        evidence = {RouteProvenance(recipe.route, recipe.start_window_id,
                                    recipe.end_window_id, recipe.score,
                                    recipe.producer)
                    for recipe in bucket.sources()}
        provenance = tuple(sorted(evidence, key=lambda row: row.order_key))
        winners = (("cross_window", bucket.cross_winner),
                   ("in_window", bucket.in_winner))
        scores = tuple((route, winner.score) for route, winner in winners
                       if winner is not None)
        windows = tuple((route, winner.start_window_id, winner.end_window_id)
                        for route, winner in winners if winner is not None)
        selected.append(RouteCandidate(kind, key[1], key[2], provenance, scores, windows))
        selected_buckets.append(bucket)
    selected.sort(key=lambda row: row.key)
    trace = RetrievalTrace(
        in_window_proposed=in_proposed,
        cross_window_proposed=cross_proposed,
        in_window_deduplicated=in_unique,
        cross_window_deduplicated=cross_unique_native + extension_added,
        union_deduplicated=union_count,
        both_route_provenance=both_count,
        fine_scored_in_window=sum(row.in_winner is not None for row in selected_buckets),
        fine_scored_cross_window=sum(row.cross_winner is not None for row in selected_buckets),
        fine_scored_both_route=sum(row.in_winner is not None and
                                   row.cross_winner is not None for row in selected_buckets),
        unique_candidates=union_count,
        scored_candidates=len(selected),
        dropped_by_article_guard=union_count - len(selected),
    )
    return tuple(selected), trace


@dataclass(frozen=True, slots=True)
class DecodeResult:
    spans: tuple[DecodedSourceSpan, ...]
    eligible_pairs: int
    scored_pairs: int
    invalid_predictions: int
    partial: bool
    policy_status: str
    retrieval: RetrievalTrace = RetrievalTrace()
    partial_causes: tuple[tuple[str, int], ...] = ()
    materialization: tuple[tuple[str, int], ...] = ()


class _ParticipantExactClosure:
    """Close B2 coordinates as scalar recipes before materializing source spans.

    Native coordinates own matching char extensions. The map retains the
    minimal per-coordinate winner/provenance needed for exact duplicate closure;
    the optional limit bounds the later Participant fine-scoring universe.
    """

    def __init__(self, limit: int | None):
        self.limit = limit
        self.native: dict[tuple[int, int], tuple] = {}
        self.extensions: dict[tuple[int, int], tuple] = {}
        self.native_inputs = 0
        self.extension_inputs = 0

    @staticmethod
    def _merge(winner: tuple, other: tuple) -> tuple:
        fields = list(winner)
        fields[7] = tuple(dict.fromkeys(winner[7] + other[7]))
        fields[8] = tuple(sorted(set(winner[8] + other[8]),
                                 key=lambda row: row.order_key))
        return tuple(fields)

    def add_native(self, row: tuple) -> None:
        self.native_inputs += 1
        key = row[0], row[1]
        old = self.native.get(key)
        if old is None:
            self.native[key] = row
        elif row[2] > old[2]:
            self.native[key] = self._merge(row, old)
        else:
            self.native[key] = self._merge(old, row)

    def add_extension(self, row: tuple) -> None:
        self.extension_inputs += 1
        key = row[0], row[1]
        old = self.extensions.get(key)
        self.extensions[key] = row if old is None else self._merge(old, row)

    def finish(self, *, content: str, role: str) -> tuple[tuple[DecodedSourceSpan, ...], int]:
        closed = self.native
        for key, row in self.extensions.items():
            old = closed.get(key)
            closed[key] = row if old is None else self._merge(old, row)
        count = len(closed)
        top = (closed.values() if self.limit is None else
               nsmallest(self.limit, closed.values(),
                         key=lambda row: (-row[2], row[0], row[1])))
        spans = tuple(sorted((DecodedSourceSpan(
            "PARTICIPANT", role, row[0], row[1], content[row[0]:row[1]],
            row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9])
            for row in top), key=lambda row: (row.start, row.end, row.kind)))
        return spans, count


class _ParticipantTop32(_ParticipantExactClosure):
    """Historical, explicitly requested Top32 shadow accumulator."""

    def __init__(self, limit: int):
        super().__init__(limit)


@dataclass(slots=True)
class SourceDecodeContext:
    """한 요청의 generic endpoint와 bridge 좌표만 소유한다."""

    layout_id: int
    token_state_id: int
    window_index: dict[str, int]
    bridge_positions: tuple[tuple[tuple[int, int], ...], ...]
    generic_endpoints: torch.Tensor | None
    participant_alignments: dict[tuple[int, int], SpanAlignment] = field(default_factory=dict)
    participant_cells: dict[tuple[int, int], tuple | None] = field(default_factory=dict)
    # B2 char extension depends on source coordinates, not Event owner or role.
    # Retain only two detached scalars per span; never retain exact-span states.
    participant_char_residuals: dict[tuple[int, int], tuple[float, float]] = field(default_factory=dict)
    v23_structural_index: _V23StructuralIndex | None = None
    runtime_layout: SourceLayout | None = None
    closed: bool = False

    def release_generic_endpoints(self) -> None:
        self.generic_endpoints = None

    def close(self) -> None:
        self.release_generic_endpoints()
        self.window_index.clear()
        self.bridge_positions = ()
        self.participant_alignments.clear()
        self.participant_cells.clear()
        self.participant_char_residuals.clear()
        self.v23_structural_index = None
        if self.runtime_layout is not None:
            self.runtime_layout.clear_runtime_indexes()
            self.runtime_layout = None
        self.closed = True


def _cached_v23_participant_char_rows(*, layout: SourceLayout, batch: ArticleBatch,
                                      backbone: BackboneOutput, shared: SharedForwardLease,
                                      core: V3Core, context: SourceDecodeContext,
                                      chunk: list[RouteCandidate],
                                      aligned: list[SpanAlignment],
                                      exact_feature_cache: RequestExactFeatureCache | None = None
                                      ) -> list[tuple[float, float]]:
    """Reuse owner-independent B2 char residuals without retaining span tensors."""
    cache = context.participant_char_residuals
    keys = [(row.start, row.end) for row in chunk]
    cached = [cache.get(key) for key in keys]
    missing: dict[tuple[int, int], int] = {}
    for index, (key, value) in enumerate(zip(keys, cached)):
        if value is None:
            missing.setdefault(key, index)
    computed: dict[tuple[int, int], tuple[float, float]] = {}
    if missing:
        output = exact_source_features(
            layout=layout, batch=batch, backbone=backbone, shared=shared, core=core,
            rows=[(aligned[index], "PARTICIPANT") for index in missing.values()],
            cache=exact_feature_cache)
        values = output.residuals.detach().cpu().tolist()
        computed = {key: (float(value[0]), float(value[1]))
                    for key, value in zip(missing, values)}
        for key, value in computed.items():
            if len(cache) >= V23_PARTICIPANT_CHAR_CACHE_LIMIT:
                cache.clear()
            cache[key] = value
    return [value if value is not None else computed[key]
            for key, value in zip(keys, cached)]


@dataclass(frozen=True, slots=True)
class V23ParticipantBoundaryRows:
    """Request-local Event B2 endpoints, shared by all three role decoders."""

    layout_id: int
    token_state_id: int
    event_start: int
    event_end: int
    sentence_rows: tuple[int, ...]
    probabilities: torch.Tensor
    geometry: tuple[_V23B2Geometry, ...]


@dataclass(frozen=True, slots=True)
class _V23B2Geometry:
    """Source-only sentence geometry shared by one Event's three role decoders."""

    positions: torch.Tensor
    pair_first: torch.Tensor
    pair_last: torch.Tensor
    wide_per_start: torch.Tensor
    char_starts: tuple[int, ...]
    char_ends: tuple[int, ...]


def _v23_b2_geometry(window: SourceWindow) -> _V23B2Geometry:
    tokens = window.tokens
    count = len(tokens)
    indices = torch.arange(count)
    first, last = torch.nonzero(
        (indices[:, None] <= indices[None, :]) &
        (indices[None, :] - indices[:, None] < 49), as_tuple=True)
    return _V23B2Geometry(
        torch.tensor([token.position for token in tokens], dtype=torch.long),
        first, last, (count - indices - 49).clamp_min(0),
        tuple(token.start for token in tokens),
        tuple(token.end for token in tokens))


def precompute_v23_participant_boundaries(*, layout: SourceLayout,
                                          batch: ArticleBatch,
                                          shared: SharedForwardLease,
                                          core: V3Core,
                                          events: list[tuple[str, SpanAlignment, torch.Tensor]],
                                          event_chunk_size: int = 16
                                          ) -> dict[str, V23ParticipantBoundaryRows]:
    """Run one three-role B2 boundary forward per bounded Event chunk."""
    if event_chunk_size <= 0 or shared.closed or shared.token_states is None:
        raise ValueError("live source states and positive Event chunk size are required")
    if len({event_id for event_id, _, _ in events}) != len(events):
        raise ValueError("Participant Event IDs must be unique")
    result: dict[str, V23ParticipantBoundaryRows] = {}
    for offset in range(0, len(events), event_chunk_size):
        chunk = events[offset:offset + event_chunk_size]
        geometry_by_row: dict[int, _V23B2Geometry] = {}
        owners: list[tuple[str, SpanAlignment, tuple[int, ...], int, int]] = []
        state_rows = []
        token_rows = []
        mask_rows = []
        event_positions = []
        for event_id, alignment, state in chunk:
            rows = _participant_sentence_rows(layout, alignment.start)
            if not rows:
                raise ValueError("V23 Participant Event has no sentence-local B2 row")
            first = len(state_rows)
            for position in rows:
                if position not in geometry_by_row:
                    geometry_by_row[position] = _v23_b2_geometry(layout.windows[position])
                cell = sentence_cell(layout, alignment.start, alignment.end,
                                     layout.windows[position].window_id)
                state_rows.append(state)
                token_rows.append(shared.token_states[0, position])
                mask_rows.append(batch.source_token_mask[0, position])
                event_positions.append((position, cell[1], cell[2]) if cell is not None
                                       else (position, 0, 0))
            owners.append((event_id, alignment, rows, first, len(state_rows)))
        logits = core.task_modules["participant"].boundary(
            torch.stack(state_rows), torch.stack(token_rows),
            torch.tensor(event_positions, dtype=torch.long,
                         device=shared.token_states.device),
            torch.stack(mask_rows))
        # One float32->float64 promotion per Event chunk preserves the former
        # Python-float endpoint comparisons and serves all three role decoders.
        probabilities = torch.sigmoid(logits).detach().cpu().to(torch.float64)
        for event_id, alignment, rows, first, last in owners:
            result[event_id] = V23ParticipantBoundaryRows(
                id(layout), id(shared.token_states),
                alignment.start, alignment.end, rows,
                probabilities[first:last],
                tuple(geometry_by_row[row] for row in rows))
    return result


def _participant_sentence_rows(layout: SourceLayout, start: int) -> tuple[int, ...]:
    """Index only the Event sentence while preserving every overlapping B2 row."""
    sentence = bisect_right(
        layout.sentence_spans, (start, len(layout.article.content))) - 1
    if (sentence < 0 or
            not layout.sentence_spans[sentence][0] <= start <
                    layout.sentence_spans[sentence][1]):
        return ()
    return tuple(position for position, window in
                 layout.sentence_windows_by_index[sentence]
                 if any(token.start <= start < token.end for token in window.tokens))


def source_decode_context(layout: SourceLayout, shared: SharedForwardLease,
                          core: V3Core) -> SourceDecodeContext:
    """generic 다섯 kind의 endpoint를 한 번 계산하고 bridge lookup을 고정한다."""
    if shared.closed or shared.token_states is None:
        raise RuntimeError("source decode needs a live shared representation")
    window_index = {window.window_id: row for row, window in enumerate(layout.windows)}
    local_position = {(window.window_id, token.source_index): token.position
                      for window in layout.windows if window.view == "bridge"
                      for token in window.tokens}
    positions = tuple(tuple((window_index[window_id], local_position[window_id, token.source_index])
                            for window_id in layout.bridge_windows_by_token[token.source_index])
                      for token in layout.bridge_tokens)
    return SourceDecodeContext(id(layout), id(shared.token_states), window_index, positions,
                               core.exact_source_span.endpoint_logits(shared.token_states),
                               runtime_layout=layout)


def _bulk_v23_bridge_endpoints(*, endpoints: torch.Tensor, task_boundary,
                               bridge_positions: tuple, channel: int
                               ) -> list[tuple[float, float]]:
    """Read V23 Entity/Time bridge endpoint evidence in source-token order.

    The old path converted each float32 tensor scalar to a Python float before
    adding boundary evidence. Keep that double-precision addition after two
    bulk transfers so cross-window ranking and tie breaks remain unchanged.
    """
    positions = [position for token_positions in bridge_positions
                 for position in token_positions]
    if not positions:
        return []
    index = torch.tensor(positions, dtype=torch.long, device=endpoints.device)
    generic = endpoints[0, index[:, 0], index[:, 1], channel, :].detach().cpu().tolist()
    boundary = (task_boundary.start_logits[0, index[:, 0], index[:, 1], 0].detach().cpu().tolist(),
                task_boundary.end_logits[0, index[:, 0], index[:, 1], 0].detach().cpu().tolist()
                ) if task_boundary is not None else None
    return [(float(pair[0]) + (float(boundary[0][row]) if boundary is not None else 0.0),
             float(pair[1]) + (float(boundary[1][row]) if boundary is not None else 0.0))
            for row, pair in enumerate(generic)]


def event_source_state(*, alignment: SpanAlignment, layout: SourceLayout,
                       batch: ArticleBatch, backbone: BackboneOutput,
                       shared: SharedForwardLease, core: V3Core,
                       profile: str = "V3_WINDOW") -> torch.Tensor:
    """한 Event의 세 role이 공유할 exact-span representation을 만든다."""
    if layout.reconstruct(alignment) != (alignment.start, alignment.end, alignment.text):
        raise ValueError("Event source alignment differs")
    if "participant" not in core.task_modules:
        raise ValueError("Event-conditioned Participant head is not registered")
    if profile == "V23_BASELINE":
        native = event_candidate_state(
            layout=layout, batch=batch, backbone=backbone, shared=shared,
            core=core, start=alignment.start, end=alignment.end)
        if native is not None:
            return native
    elif profile != "V3_WINDOW":
        raise ValueError("unknown Event source representation profile")
    return core.exact_source_span(
        layout=layout, batch=batch, backbone=backbone,
        token_states=shared.token_states, sentence_states=shared.sentence_states,
        document_state=shared.document_state, candidate_encoder=core.candidate_span,
        rows=((alignment, "EVENT"),)).states[0]


def precompute_v23_event_states(*, layout: SourceLayout,
                                batch: ArticleBatch, backbone: BackboneOutput,
                                shared: SharedForwardLease, core: V3Core,
                                events: list[tuple[str, SpanAlignment]],
                                event_chunk_size: int = 16,
                                exact_feature_cache: RequestExactFeatureCache | None = None
                                ) -> dict[str, torch.Tensor]:
    """Batch native Event representations; exact-only extensions remain separate."""
    if event_chunk_size <= 0 or shared.closed or shared.token_states is None:
        raise ValueError("live source states and positive Event chunk size are required")
    if len({event_id for event_id, _ in events}) != len(events):
        raise ValueError("Participant Event IDs must be unique")
    states: dict[str, torch.Tensor] = {}
    for offset in range(0, len(events), event_chunk_size):
        chunk = events[offset:offset + event_chunk_size]
        local = []
        exact = []
        for event_id, alignment in chunk:
            if layout.reconstruct(alignment) != (
                    alignment.start, alignment.end, alignment.text):
                raise ValueError("Event source alignment differs")
            row = sentence_cell(layout, alignment.start, alignment.end)
            (local if row is not None else exact).append((event_id, alignment))
        if local:
            encoded = local_source_states(
                kind="EVENT", layout=layout, batch=batch, backbone=backbone,
                shared=shared, core=core,
                rows=[(alignment.start, alignment.end) for _, alignment in local])
            states.update((event_id, encoded[index])
                          for index, (event_id, _) in enumerate(local))
        if exact:
            encoded = exact_source_features(
                layout=layout, batch=batch, backbone=backbone,
                shared=shared, core=core,
                rows=[(alignment, "EVENT") for _, alignment in exact],
                cache=exact_feature_cache).states
            states.update((event_id, encoded[index])
                          for index, (event_id, _) in enumerate(exact))
    return states


def _window_token_rows(layout: SourceLayout) -> tuple[tuple[int, tuple[tuple[int, int], ...]], ...]:
    """window row별 (token position, source token index) 목록."""
    return tuple((row, tuple((token.position, token.source_index) for token in window.tokens))
                 for row, window in enumerate(layout.windows))


def _stable_joint_window_cells(block: torch.Tensor, eligible: torch.Tensor,
                               limit: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Joint proposal의 top cells를 score↓, start↑, end↑로 안정 정렬한다.

    ``eligible``의 row-major 순서는 token/absolute start-end 순서와 같다. Stable
    tensor sort가 같은 score의 이 순서를 유지하므로, 모든 cell을 Python scalar로
    읽지 않고도 기존 deterministic tie-break를 보존한다.
    """
    if (block.ndim != 2 or eligible.shape != block.shape
            or eligible.dtype != torch.bool or limit <= 0):
        raise ValueError("joint proposal selection needs a 2-D score/mask and positive limit")
    flat_cells = torch.nonzero(eligible.reshape(-1), as_tuple=False).flatten()
    count = min(limit, int(flat_cells.numel()))
    if not count:
        empty_scores = block.new_empty((0,))
        empty_cells = torch.empty((0,), dtype=torch.long, device=block.device)
        return empty_scores, empty_cells, empty_cells
    flat_scores = block.reshape(-1).index_select(0, flat_cells)
    order = torch.argsort(flat_scores, descending=True, stable=True)[:count]
    selected_cells = flat_cells.index_select(0, order)
    selected_scores = flat_scores.index_select(0, order)
    width = block.shape[1]
    return (selected_scores,
            torch.div(selected_cells, width, rounding_mode="floor"),
            torch.remainder(selected_cells, width))


def _joint_window_candidates(*, kind: str, window: SourceWindow,
                             block: torch.Tensor, eligible: torch.Tensor,
                             limit: int, producer: str = "V3_WINDOW") -> list[RouteCandidate]:
    """선택된 작은 tensor만 한 번 CPU로 옮겨 absolute route 후보를 만든다."""
    scores, starts, ends = _stable_joint_window_cells(block, eligible, limit)
    selected = torch.stack((scores, starts.to(scores.dtype), ends.to(scores.dtype)), dim=-1)
    rows = selected.detach().cpu().tolist()
    return [
        _raw_route_candidate(
            kind=kind,
            start=window.tokens[int(start_offset)].start,
            end=window.tokens[int(end_offset)].end,
            route="in_window",
            start_window_id=window.window_id,
            end_window_id=window.window_id,
            score=float(score),
            producer=producer,
        )
        for score, start_offset, end_offset in rows
    ]


@dataclass(frozen=True, slots=True)
class _V23StructuralPair:
    """One lane-independent source token pair with both lane ranks attached."""

    key: tuple[int, int, int]
    width: int
    source_token_count: int
    entity_valid: int
    time_valid: int
    entity_rank: float
    time_rank: float


@dataclass(slots=True)
class _V23StructuralIndex:
    """Request-owned sentence geometry shared by the V23 Entity and Time lanes."""

    layout_id: int
    prepared: SimpleNamespace
    pairs: tuple[_V23StructuralPair, ...]
    tokens: dict[tuple[int, int], dict]
    windows_by_sentence: dict[int, list[SourceWindow]]
    unary: dict[tuple[int, int, bool], tuple[tuple[int, ...], int]] = field(default_factory=dict)
    pair_windows: dict[tuple[int, int, int], tuple[SourceWindow, SourceWindow]] = field(
        default_factory=dict)

    @classmethod
    def build(cls, layout: SourceLayout) -> _V23StructuralIndex:
        by_sentence: dict[int, dict[int, object]] = {}
        windows_by_sentence: dict[int, list[SourceWindow]] = {}
        for window in layout.windows:
            if window.view != "sentence":
                continue
            by_sentence.setdefault(window.sentence_index, {}).update(
                (token.source_index, token) for token in window.tokens)
            windows_by_sentence.setdefault(window.sentence_index, []).append(window)
        sentences = [{"sentence_index": sentence_index, "sentence_id": str(sentence_index),
                      "tokens": [{"token_index": index, "start": token.start,
                                  "end": token.end} for index, token in sorted(tokens.items())]}
                     for sentence_index, tokens in sorted(by_sentence.items())]
        prepared = SimpleNamespace(article=layout.article, sentences=sentences)
        token_lookup = {(row["sentence_index"], token["token_index"]): token
                        for row in sentences for token in row["tokens"]}
        pairs = []
        content = layout.article.content
        for sentence in sentences:
            tokens = sentence["tokens"]
            for left_index, left in enumerate(tokens):
                for right_index in range(left_index, min(len(tokens), left_index + 21)):
                    right = tokens[right_index]
                    width = right_index - left_index + 1
                    text = content[left["start"]:right["end"]]
                    base = 8.0 / (1.0 + width)
                    edge = 0.05 * float(text[:1].isalnum() and text[-1:].isalnum())
                    entity_valid = (pair_candidate_count(left, right, 56)
                                    if width <= 20 else 0)
                    time_valid = pair_candidate_count(left, right, 44)
                    pairs.append(_V23StructuralPair(
                        (sentence["sentence_index"], left["token_index"],
                         right["token_index"] + 1), width, len(tokens),
                        entity_valid, time_valid,
                        base + 0.08 * float(len(text) <= 56) + edge
                        + 0.12 * float(any(char.isdigit() for char in text)),
                        base + 0.08 * float(len(text) <= 44) + edge
                        + 2.0 * float(bool(TIME_CUES.search(text))),
                    ))
        return cls(id(layout), prepared, tuple(pairs), token_lookup,
                   windows_by_sentence)

    def options(self, key: tuple[int, int, int], *, start: bool,
                cap: int) -> tuple[int, ...]:
        token_index = key[1] if start else key[2] - 1
        cache_key = key[0], token_index, start
        cached = self.unary.get(cache_key)
        if cached is None:
            cached = unary_positions(self.prepared.article.content,
                                     self.tokens[key[0], token_index],
                                     start=start, cap=8)
            self.unary[cache_key] = cached
        return cached[0][:cap]

    def windows(self, key: tuple[int, int, int]
                ) -> tuple[SourceWindow, SourceWindow]:
        cached = self.pair_windows.get(key)
        if cached is not None:
            return cached
        candidates = self.windows_by_sentence[key[0]]
        containing = [window for window in candidates
                      if window.tokens[0].source_index <= key[1] and
                      key[2] - 1 <= window.tokens[-1].source_index]
        if containing:
            window = min(containing, key=lambda item: item.window_id)
            result = window, window
        else:
            left = min((window for window in candidates
                        if window.tokens[0].source_index <= key[1] <=
                        window.tokens[-1].source_index), key=lambda item: item.window_id)
            right = min((window for window in candidates
                         if window.tokens[0].source_index <= key[2] - 1 <=
                         window.tokens[-1].source_index), key=lambda item: item.window_id)
            result = left, right
        self.pair_windows[key] = result
        return result


def _v23_bounded_span_candidates(*, kind: str, layout: SourceLayout,
                                 retrieval: RetrievalBudget,
                                 context: SourceDecodeContext | None = None,
                                 compact: bool = False
                                 ) -> tuple[list[RouteCandidate | _V23RouteRecipe], int]:
    """Apply lane-specific T/C selection over one request's source geometry."""
    if kind == "ENTITY":
        lane = StructuralLane("ENTITY", 20, 56, 256, 5)
        structural = StructuralBudget("STRUCTURAL_T14_C6", 14, 1536, 0.125, 6)
    elif kind == "TIME":
        lane = StructuralLane("TIME", 21, 44, 1024, 1)
        structural = StructuralBudget("STRUCTURAL_T16_C8", 16, 2048, 0.15, 8)
    else:
        raise ValueError("v2.3 structural selector applies only to Entity/Time")
    if context is not None:
        if context.layout_id != id(layout) or context.closed:
            raise ValueError("V23 structural index belongs to another request")
        if context.v23_structural_index is None:
            context.v23_structural_index = _V23StructuralIndex.build(layout)
        index = context.v23_structural_index
    else:
        index = _V23StructuralIndex.build(layout)
    eligible = [pair for pair in index.pairs
                if (pair.entity_valid if kind == "ENTITY" else pair.time_valid)]
    rank = lambda pair: pair.entity_rank if kind == "ENTITY" else pair.time_rank
    ordering = lambda pair: (-rank(pair), pair.width, pair.key)
    by_sentence: dict[int, list[_V23StructuralPair]] = {}
    for pair in eligible:
        by_sentence.setdefault(pair.key[0], []).append(pair)
    selected_keys: set[tuple[int, int, int]] = set()
    for sentence_pairs in by_sentence.values():
        quota = min(structural.window_cap,
                    structural.token_multiplier * sentence_pairs[0].source_token_count)
        selected_keys.update(pair.key for pair in sorted(sentence_pairs, key=ordering)[:quota])
    global_quota = math.ceil(structural.global_reserve_fraction * len(eligible))
    selected_keys.update(pair.key for pair in sorted(eligible, key=ordering)[:global_quota])
    boundaries: dict[tuple[int, int, int], tuple[set[int], set[int]]] = {}
    rank_by_pair: dict[tuple[int, int, int], float] = {}
    for pair in eligible:
        if pair.key not in selected_keys:
            continue
        starts = index.options(pair.key, start=True, cap=structural.boundary_options)
        ends = index.options(pair.key, start=False, cap=structural.boundary_options)
        if any(0 < end - start <= lane.max_chars for start in starts for end in ends):
            boundaries[pair.key] = set(starts), set(ends)
            rank_by_pair[pair.key] = rank(pair)
    proposals: list[RouteCandidate | _V23RouteRecipe] = []
    for row in iter_bounded_span_candidates(
            index.prepared, boundaries, max_token_width=lane.max_tokens,
            max_character_width=lane.max_chars):
        key = (row["sentence_index"], row["token_start"], row["token_end"])
        left_window, right_window = index.windows(key)
        route = "in_window" if left_window == right_window else "cross_window"
        recipe = _V23RouteRecipe(kind, row["char_start"], row["char_end"], route,
                                 left_window.window_id, right_window.window_id,
                                 rank_by_pair[key], "V23_BOUNDED")
        proposals.append(recipe if compact else _raw_route_candidate(
            kind=recipe.kind, start=recipe.start, end=recipe.end,
            route=recipe.route, start_window_id=recipe.start_window_id,
            end_window_id=recipe.end_window_id, score=recipe.score,
            producer=recipe.producer))
    return proposals, len(proposals)


def _v23_trigger_candidates(*, layout: SourceLayout, task_boundary,
                            endpoint_threshold: float | None
                            ) -> tuple[list[RouteCandidate], int, int]:
    """Propose up to four Trigger coordinates per sentence from endpoint logits.

    The endpoint gate is cheap retrieval. Bounded survivors receive exact
    span_score decisions and a separate final acceptance threshold later.
    """
    by_sentence: dict[int, dict[tuple[int, int], tuple[float, SourceWindow]]] = {}
    visited = width_masked = 0
    for row, window in enumerate(layout.windows):
        if window.view != "sentence":
            continue
        tokens = window.tokens
        positions = torch.tensor([token.position for token in tokens],
                                 dtype=torch.long, device=task_boundary.start_logits.device)
        starts = torch.sigmoid(task_boundary.start_logits[0, row, :, 0]).index_select(0, positions)
        ends = torch.sigmoid(task_boundary.end_logits[0, row, :, 0]).index_select(0, positions)
        offsets = torch.arange(len(tokens), device=starts.device)
        width = offsets[None, :] - offsets[:, None]
        if endpoint_threshold is None:
            start_allowed = torch.ones_like(starts, dtype=torch.bool)
            end_allowed = torch.ones_like(ends, dtype=torch.bool)
        else:
            # The former Python float comparison did not round the calibrated
            # threshold to float32. Compare the small endpoint vectors in bulk.
            start_allowed = torch.tensor(
                [value >= endpoint_threshold for value in starts.detach().cpu().tolist()],
                dtype=torch.bool, device=starts.device)
            end_allowed = torch.tensor(
                [value >= endpoint_threshold for value in ends.detach().cpu().tolist()],
                dtype=torch.bool, device=ends.device)
        width_masked += int((start_allowed[:, None] & (width >= 64)).sum())
        eligible = (start_allowed[:, None] & end_allowed[None, :] &
                    (width >= 0) & (width < 64))
        pair_indices = torch.nonzero(eligible, as_tuple=False)
        products = starts.index_select(0, pair_indices[:, 0]) * \
            ends.index_select(0, pair_indices[:, 1])
        # Preserve the former float32 product followed by Python sqrt/log and
        # row-major pair order, while transferring all pair scalars together.
        packed = torch.column_stack((pair_indices.to(products.dtype), products)).detach().cpu().tolist()
        pool = by_sentence.setdefault(window.sentence_index, {})
        for first_index, last_index, product in packed:
            first, last = tokens[int(first_index)], tokens[int(last_index)]
            probability = math.sqrt(product)
            score = math.log(max(probability, 1e-8)) - math.log(max(1 - probability, 1e-8))
            key = (first.start, last.end)
            old = pool.get(key)
            if old is None or score > old[0]:
                pool[key] = (score, window)
        visited += len(packed)
    proposals = []
    for rows in by_sentence.values():
        used_starts: set[int] = set()
        used_ends: set[int] = set()
        for (start, end), (score, window) in sorted(
                rows.items(), key=lambda item: (-item[1][0], *item[0])):
            if start in used_starts or end in used_ends:
                continue
            proposals.append(_raw_route_candidate(
                kind="TRIGGER", start=start, end=end, route="in_window",
                start_window_id=window.window_id, end_window_id=window.window_id,
                score=score, producer="V23_TRIGGER_GREEDY"))
            used_starts.add(start)
            used_ends.add(end)
            if len(used_starts) >= 4:
                break
    return proposals, visited, width_masked


def _v23_participant_candidates(*, layout: SourceLayout,
                                sentence_rows: list[int], role_logits: torch.Tensor | None,
                                role: str, endpoint_threshold: float | None,
                                probabilities: torch.Tensor | tuple | None = None,
                                geometry: tuple[_V23B2Geometry, ...] | None = None
                                ) -> tuple[list[RouteCandidate], int, int]:
    """B2 independent start/end Cartesian candidates in the Event sentence."""
    # Collapse equal coordinates as scalar rows before constructing route
    # objects; every distinct coordinate still reaches the fine scorer.
    compact: dict[tuple[int, int], tuple[float, str, set[tuple[str, float]]]] = {}
    visited = width_masked = 0
    role_index = PARTICIPANT_ROLES.index(role)
    # The same endpoint probability is reused in many Cartesian pairs. One
    # device transfer avoids a synchronization for every pair without pruning.
    if probabilities is None:
        if role_logits is None:
            raise ValueError("V23 B2 needs precomputed probabilities or boundary logits")
        probabilities = torch.sigmoid(role_logits).detach().cpu()
    if geometry is not None and len(geometry) != len(sentence_rows):
        raise ValueError("B2 geometry differs from sentence rows")
    for local_row, window_row in enumerate(sentence_rows):
        window = layout.windows[window_row]
        cell = (geometry[local_row] if geometry is not None else
                _v23_b2_geometry(window))
        # Compare in float64: .tolist() in the former scalar path promoted the
        # stored float32 endpoint probability before comparing to the threshold.
        row = torch.as_tensor(probabilities[local_row], dtype=torch.float64)
        starts = row.index_select(0, cell.positions)[:, role_index, 0]
        ends = row.index_select(0, cell.positions)[:, role_index, 1]
        accepted_starts = (starts >= endpoint_threshold if endpoint_threshold is not None
                           else torch.ones_like(starts, dtype=torch.bool))
        accepted_ends = (ends >= endpoint_threshold if endpoint_threshold is not None
                         else torch.ones_like(ends, dtype=torch.bool))
        width_masked += int((accepted_starts.to(torch.long) * cell.wide_per_start).sum())
        eligible = accepted_starts.index_select(0, cell.pair_first) & \
            accepted_ends.index_select(0, cell.pair_last)
        selected = torch.nonzero(eligible, as_tuple=False).flatten()
        first_indices = cell.pair_first.index_select(0, selected).tolist()
        last_indices = cell.pair_last.index_select(0, selected).tolist()
        # The scalar reference rounded the product to float32 before Python
        # sqrt/log. Keep that conversion and its deterministic row-major order.
        products = (starts.index_select(0, cell.pair_first.index_select(0, selected)) *
                    ends.index_select(0, cell.pair_last.index_select(0, selected))).to(
                        torch.float32).tolist()
        for first_index, last_index, product in zip(first_indices, last_indices, products):
            probability = math.sqrt(product)
            score = math.log(max(probability, 1e-8)) - math.log(max(1 - probability, 1e-8))
            key = cell.char_starts[first_index], cell.char_ends[last_index]
            old = compact.get(key)
            source = (window.window_id, score)
            if old is None:
                compact[key] = (score, window.window_id, {source})
            else:
                best_score, best_window, routes = old
                routes.add(source)
                if (-score, window.window_id) < (-best_score, best_window):
                    compact[key] = (score, window.window_id, routes)
        visited += len(first_indices)
    proposals = []
    for (start, end), (score, window_id, sources) in compact.items():
        provenance = tuple(sorted((RouteProvenance(
            "in_window", source_window, source_window, source_score,
            "V23_PARTICIPANT_B2") for source_window, source_score in sources),
            key=lambda row: row.order_key))
        proposals.append(RouteCandidate(
            "PARTICIPANT", start, end, provenance,
            (("in_window", score),), (("in_window", window_id, window_id),)))
    return proposals, visited, width_masked


def v23_participant_candidate_views(*, layout: SourceLayout,
                                    boundary: V23ParticipantBoundaryRows,
                                    endpoint_threshold: float | None
                                    ) -> dict[str, tuple[list[RouteCandidate], int, int]]:
    """Prepare three independent B2 role views over one Event's source geometry."""
    if boundary.layout_id != id(layout):
        raise ValueError("Participant boundary belongs to another source layout")
    compact = {role: {} for role in PARTICIPANT_ROLES}
    visits = {role: 0 for role in PARTICIPANT_ROLES}
    width_masked = {role: 0 for role in PARTICIPANT_ROLES}
    for local_row, window_row in enumerate(boundary.sentence_rows):
        window = layout.windows[window_row]
        cell = boundary.geometry[local_row]
        probabilities = torch.as_tensor(boundary.probabilities[local_row], dtype=torch.float64)
        starts = probabilities.index_select(0, cell.positions)[:, :, 0]
        ends = probabilities.index_select(0, cell.positions)[:, :, 1]
        accepted_starts = (starts >= endpoint_threshold if endpoint_threshold is not None
                           else torch.ones_like(starts, dtype=torch.bool))
        accepted_ends = (ends >= endpoint_threshold if endpoint_threshold is not None
                         else torch.ones_like(ends, dtype=torch.bool))
        eligible = (accepted_starts.index_select(0, cell.pair_first) &
                    accepted_ends.index_select(0, cell.pair_last))
        for role_index, role in enumerate(PARTICIPANT_ROLES):
            width_masked[role] += int((accepted_starts[:, role_index].to(torch.long) *
                                       cell.wide_per_start).sum())
            selected = torch.nonzero(eligible[:, role_index], as_tuple=False).flatten()
            first_indices = cell.pair_first.index_select(0, selected).tolist()
            last_indices = cell.pair_last.index_select(0, selected).tolist()
            products = (starts[:, role_index].index_select(0, cell.pair_first.index_select(0, selected)) *
                        ends[:, role_index].index_select(0, cell.pair_last.index_select(0, selected))).to(
                            torch.float32).tolist()
            role_compact = compact[role]
            for first_index, last_index, product in zip(first_indices, last_indices, products):
                probability = math.sqrt(product)
                score = math.log(max(probability, 1e-8)) - math.log(max(1 - probability, 1e-8))
                key = cell.char_starts[first_index], cell.char_ends[last_index]
                old = role_compact.get(key)
                source = (window.window_id, score)
                if old is None:
                    role_compact[key] = (score, window.window_id, {source})
                else:
                    best_score, best_window, routes = old
                    routes.add(source)
                    if (-score, window.window_id) < (-best_score, best_window):
                        role_compact[key] = (score, window.window_id, routes)
            visits[role] += len(first_indices)
    result = {}
    for role in PARTICIPANT_ROLES:
        proposals = []
        for (start, end), (score, window_id, sources) in compact[role].items():
            provenance = tuple(sorted((RouteProvenance(
                "in_window", source_window, source_window, source_score,
                "V23_PARTICIPANT_B2") for source_window, source_score in sources),
                key=lambda row: row.order_key))
            proposals.append(RouteCandidate(
                "PARTICIPANT", start, end, provenance,
                (("in_window", score),), (("in_window", window_id, window_id),)))
        result[role] = proposals, visits[role], width_masked[role]
    return result


def _propose_in_window(*, kind: str, layout: SourceLayout, shared: SharedForwardLease,
                       endpoints: torch.Tensor, task_boundary, channel: int,
                       retrieval: RetrievalBudget,
                       endpoint_threshold: float | None = None,
                       selection_only_threshold_free: bool = False,
                       structural_context: SourceDecodeContext | None = None
                       ) -> tuple[list[RouteCandidate | _V23RouteRecipe], int, int]:
    """window마다 후보를 확보한다. 기사 길이에 비례해 후보가 늘어난다.

    EVENT/STATEMENT는 이미 계산된 joint proposal 격자에서 직접 cell을 고른다.
    이 값은 정밀 span scoring이 쓰는 점수와 같은 producer이므로, 독립 endpoint
    순위만으로 정답을 먼저 버리는 구조가 사라진다.
    """
    proposals: list[RouteCandidate] = []
    visited = 0
    dropped_width = 0
    if retrieval.candidate_profile == "V23_BASELINE" and kind in ("ENTITY", "TIME"):
        structural, visited = _v23_bounded_span_candidates(
            kind=kind, layout=layout, retrieval=retrieval,
            context=structural_context, compact=structural_context is not None)
        return structural, visited, dropped_width
    if retrieval.candidate_profile == "V23_BASELINE" and kind == "TRIGGER":
        if endpoint_threshold is None and not selection_only_threshold_free:
            raise ValueError("v2.3 Trigger needs a calibrated endpoint gate")
        return _v23_trigger_candidates(layout=layout, task_boundary=task_boundary,
                                       endpoint_threshold=endpoint_threshold)
    joint_label = ("EVENT", "STATEMENT").index(kind) if kind in ("EVENT", "STATEMENT") else None
    semantic_by_sentence: dict[int, list[RouteCandidate]] = {}
    for row, tokens in _window_token_rows(layout):
        if not tokens:
            continue
        window = layout.windows[row]
        if (retrieval.candidate_profile == "V23_BASELINE" and
                joint_label is not None and window.view != "sentence"):
            continue
        positions = [position for position, _source in tokens]
        if joint_label is not None and shared.proposal_logits is not None:
            grid = shared.proposal_logits[0, row, :, :, joint_label]
            index = torch.tensor(positions, dtype=torch.long, device=grid.device)
            block = grid.index_select(0, index).index_select(1, index)
            offsets = torch.arange(len(positions), device=grid.device)
            width = offsets.unsqueeze(0) - offsets.unsqueeze(1)
            max_width = (96 if retrieval.candidate_profile == "V23_BASELINE"
                         else retrieval.max_span_tokens)
            eligible = (width >= 0) & (width < max_width)
            dropped_width += int((width >= max_width).sum())
            visited += int(eligible.sum())
            rows = _joint_window_candidates(
                kind=kind,
                window=window,
                block=block,
                eligible=eligible,
                limit=(32 if retrieval.candidate_profile == "V23_BASELINE"
                       else retrieval.proposal_top_k),
                producer=("V23_TOP32" if retrieval.candidate_profile == "V23_BASELINE"
                          else "V3_WINDOW"),
            )
            if retrieval.candidate_profile == "V23_BASELINE":
                semantic_by_sentence.setdefault(window.sentence_index, []).extend(rows)
            else:
                proposals.extend(rows)
            continue
        starts = []
        ends = []
        for position in positions:
            start_score = float(endpoints[0, row, position, channel, 0])
            end_score = float(endpoints[0, row, position, channel, 1])
            if task_boundary is not None:
                start_score += float(task_boundary.start_logits[0, row, position, 0])
                end_score += float(task_boundary.end_logits[0, row, position, 0])
            starts.append((start_score, position))
            ends.append((end_score, position))
        visited += 2 * len(positions)
        starts.sort(key=lambda value: (-value[0], value[1]))
        ends.sort(key=lambda value: (-value[0], value[1]))
        window_pairs = []
        for start_score, start_position in starts[:retrieval.per_window_starts]:
            for end_score, end_position in ends[:retrieval.per_window_ends]:
                if end_position < start_position:
                    continue
                if end_position - start_position >= retrieval.max_span_tokens:
                    dropped_width += 1
                    continue
                window_pairs.append((start_score + end_score, start_position, end_position))
        window_pairs.sort(key=lambda value: (-value[0], value[1], value[2]))
        for score, start_position, end_position in window_pairs[:retrieval.per_window_pairs]:
            start_token = next(token for token in layout.windows[row].tokens
                               if token.position == start_position)
            end_token = next(token for token in layout.windows[row].tokens
                             if token.position == end_position)
            proposals.append(_raw_route_candidate(
                kind=kind, start=start_token.start, end=end_token.end,
                route="in_window",
                start_window_id=layout.windows[row].window_id,
                end_window_id=layout.windows[row].window_id,
                score=score,
            ))
    if semantic_by_sentence:
        for rows in semantic_by_sentence.values():
            proposals.extend(sorted(rows, key=lambda candidate: (
                -candidate.rank_score("in_window"), candidate.start, candidate.end))[:32])
    return proposals, visited, dropped_width


def _propose_cross_window(*, kind: str, layout: SourceLayout,
                          token_start: list[tuple[float, int, str]],
                          token_end: list[tuple[float, int, str]],
                          retrieval: RetrievalBudget) -> list[RouteCandidate]:
    """window를 가로지르는 span만 별도 bounded 경로로 보존한다."""
    starts = sorted(token_start, key=lambda value: (-value[0], value[1], value[2]))[
        :retrieval.cross_window_starts]
    ends = sorted(token_end, key=lambda value: (-value[0], value[1], value[2]))[
        :retrieval.cross_window_ends]
    pairs = []
    for start_score, start_index, start_window_id in starts:
        for end_score, end_index, end_window_id in ends:
            if start_index > end_index:
                continue
            if start_window_id == end_window_id:
                continue
            first = layout.bridge_tokens[start_index]
            last = layout.bridge_tokens[end_index]
            pairs.append((start_score + end_score, first.start, last.end,
                          start_window_id, end_window_id))
    pairs.sort(key=lambda value: (-value[0], value[1], value[2], value[3], value[4]))
    return [
        _raw_route_candidate(
            kind=kind, start=start, end=end, route="cross_window",
            start_window_id=start_window_id, end_window_id=end_window_id,
            score=score,
            producer=("V23_EXACT_EXTENSION" if retrieval.candidate_profile == "V23_BASELINE"
                      else "V3_WINDOW"),
        )
        for score, start, end, start_window_id, end_window_id in (
            pairs[:retrieval.cross_window_pairs])
    ]


def _v23_needs_extension(kind: str, layout: SourceLayout,
                         candidate: RouteCandidate,
                         context: SourceDecodeContext | None = None) -> bool:
    """Keep v3 endpoint proposals outside the v2.3 local representation domain."""
    if kind == "PARTICIPANT" and context is not None:
        key = candidate.start, candidate.end
        if key not in context.participant_cells:
            context.participant_cells[key] = sentence_cell(layout, *key)
        cell = context.participant_cells[key]
    else:
        cell = sentence_cell(layout, candidate.start, candidate.end)
    if cell is None:
        return True
    if kind in ("EVENT", "STATEMENT", "TRIGGER", "PARTICIPANT"):
        return False
    token_limit, char_limit = ((20, 56) if kind == "ENTITY" else (21, 44))
    return (cell[2] - cell[1] > token_limit or
            candidate.end - candidate.start > char_limit)


def _route_candidate_alignment(layout: SourceLayout,
                               candidate: RouteCandidate) -> SpanAlignment:
    """Retrieval provenance와 무관하게 train과 같은 source-only rule을 쓴다."""
    return layout.align_runtime(candidate.start, candidate.end)


def _native_fallback_geometry(output, aligned: list[SpanAlignment],
                              prepared: NativeCandidateBatch | None) -> torch.Tensor:
    """Build fallback rows only when a native Entity/Time row cannot replace them."""
    if prepared is not None and all(cell is not None for cell in prepared.cells):
        return output.states.new_zeros((1, len(aligned), 4))
    return torch.cat((
        output.residuals,
        output.states.new_tensor([
            (min(row.end - row.start, 512) / 512, float(row.cross_window))
            for row in aligned])), dim=1).unsqueeze(0)


def _native_residuals(residuals: torch.Tensor,
                      native_used: tuple[bool, ...]) -> torch.Tensor:
    """Suppress native rows with one batch operation instead of row kernels."""
    if all(native_used):
        return residuals * 0
    mask = residuals.new_tensor([0 if used else 1 for used in native_used])
    return residuals * mask.unsqueeze(-1)


@torch.no_grad()
def decode_source_spans(*, kind: str, layout: SourceLayout, batch: ArticleBatch,
                        backbone: BackboneOutput, shared: SharedForwardLease,
                        core: V3Core, budget: DecodeBudget = DecodeBudget(),
                        event_alignment: SpanAlignment | None = None,
                        role: str | None = None,
                        context: SourceDecodeContext | None = None,
                        event_state: torch.Tensor | None = None,
                        retrieval: RetrievalBudget | None = None,
                        endpoint_threshold: float | None = None,
                        selection_only_threshold_free: bool = False,
                        participant_reservoir: int | None = None,
                        participant_boundary: V23ParticipantBoundaryRows | None = None,
                        participant_candidate_view: tuple[list[RouteCandidate], int, int] | None = None,
                        exact_feature_cache: RequestExactFeatureCache | None = None,
                        native_entity_retention_threshold: float | None = None,
                        native_time_retention_threshold: float | None = None,
                        v23_operational_expensive_cap: int | None = None
                        ) -> DecodeResult:
    """같은 backbone/DCE 출력만으로 cross-window 후보를 작은 chunk에서 평가한다."""
    if kind not in KIND_LAYER or shared.closed or shared.token_states is None:
        raise ValueError("known kind and live shared representation are required")
    if v23_operational_expensive_cap is not None and (
            type(v23_operational_expensive_cap) is not int or
            v23_operational_expensive_cap <= 0 or kind not in ("ENTITY", "TIME") or
            retrieval is None or retrieval.candidate_profile != "V23_BASELINE"):
        raise ValueError("operational expensive cap requires V23 Entity/Time")
    if native_entity_retention_threshold is not None and (
            kind != "ENTITY" or exact_feature_cache is None or
            retrieval is None or retrieval.candidate_profile != "V23_BASELINE" or
            not math.isfinite(native_entity_retention_threshold)):
        raise ValueError("native Entity state retention requires the V23 accepted source lane")
    if native_time_retention_threshold is not None and (
            kind != "TIME" or exact_feature_cache is None or
            retrieval is None or retrieval.candidate_profile != "V23_BASELINE" or
            not math.isfinite(native_time_retention_threshold)):
        raise ValueError("native Time state retention requires the V23 accepted source lane")
    if selection_only_threshold_free and (
            retrieval is None or retrieval.candidate_profile != "V23_BASELINE" or
            kind not in ("TRIGGER", "PARTICIPANT") or endpoint_threshold is not None):
        raise ValueError("threshold-free candidate path is Phase 1 V23 selection only")
    if participant_reservoir is not None and (
            retrieval is None or
            participant_reservoir != retrieval.max_scored_candidates or
            kind != "PARTICIPANT" or
            retrieval.candidate_profile != "V23_BASELINE" or
            selection_only_threshold_free):
        raise ValueError("bounded Participant fine scoring needs the V23 endpoint gate")
    if kind == "PARTICIPANT" and (event_alignment is None or role not in PARTICIPANT_ROLES):
        raise ValueError("Participant decoding requires an Event span and ACTOR/TARGET/PLACE role")
    v23_participant = (kind == "PARTICIPANT" and retrieval is not None and
                       retrieval.candidate_profile == "V23_BASELINE")
    v23_trigger = (kind == "TRIGGER" and retrieval is not None and
                   retrieval.candidate_profile == "V23_BASELINE")
    if participant_boundary is not None and (
            not v23_participant or participant_boundary.layout_id != id(layout) or
            participant_boundary.token_state_id != id(shared.token_states) or
            participant_boundary.event_start != event_alignment.start or
            participant_boundary.event_end != event_alignment.end):
        raise ValueError("precomputed B2 boundary belongs to another Event/profile")
    if participant_candidate_view is not None and (
            not v23_participant or participant_boundary is None):
        raise ValueError("precomputed B2 candidate view needs its Event boundary")
    if kind != "PARTICIPANT" and (event_alignment is not None or role is not None):
        raise ValueError("Event-conditioned role arguments belong only to Participant decoding")
    if kind != "PARTICIPANT" and event_state is not None:
        raise ValueError("reused Event representation belongs only to Participant decoding")
    if len(layout.windows) != batch.input_ids.shape[1] or batch.contents[0] != layout.article.content:
        raise ValueError("decoder source layout differs from model input")
    if context is not None and (context.closed or context.layout_id != id(layout) or
                                context.token_state_id != id(shared.token_states)):
        raise ValueError("source decode context belongs to a different request")
    endpoints = (context.generic_endpoints if context is not None else
                 core.exact_source_span.endpoint_logits(shared.token_states)) if kind != "PARTICIPANT" else None
    if kind != "PARTICIPANT" and endpoints is None:
        raise RuntimeError("generic source endpoints were already released")
    channel = list(KIND_LAYER).index(kind)
    task_boundary = None
    if kind in ("TRIGGER", "ENTITY", "TIME"):
        task_name, layer = {"TRIGGER": ("trigger", 8), "ENTITY": ("entity_mention", 12),
                            "TIME": ("time_mention", 10)}[kind]
        if task_name in core.task_modules:
            task_boundary = core.task_modules[task_name].boundary(
                backbone.layer(layer), batch.source_token_mask)
    window_index = (context.window_index if context is not None else
                    {window.window_id: row for row, window in enumerate(layout.windows)})
    if context is not None:
        bridge_positions = context.bridge_positions
    else:
        local_position = {(window.window_id, token.source_index): token.position
                          for window in layout.windows if window.view == "bridge"
                          for token in window.tokens}
        bridge_positions = tuple(tuple((window_index[window_id], local_position[window_id, token.source_index])
                                      for window_id in layout.bridge_windows_by_token[token.source_index])
                                 for token in layout.bridge_tokens)
    if v23_participant:
        # Release B2 consumes sentence-local logits only. Bridge-wide endpoint
        # rows must not run in this hot path.
        bridge_positions = ()
    role_logits = None
    bridge_row_index = None
    sentence_role_rows: list[int] = []
    sentence_role_logits = None
    sentence_role_probabilities = None
    if kind == "PARTICIPANT":
        if event_state is None:
            event_state = event_source_state(
                alignment=event_alignment, layout=layout, batch=batch, backbone=backbone,
                shared=shared, core=core)
        elif event_state.ndim != 1 or event_state.shape[0] != shared.token_states.shape[-1]:
            raise ValueError("reused Event representation has wrong shape")
        if not v23_participant:
            bridge_rows = [position for position, window in enumerate(layout.windows) if window.view == "bridge"]
            bridge_row_index = {row: index for index, row in enumerate(bridge_rows)}
            event_positions = [(position, event_alignment.start_ref.token_position,
                                event_alignment.end_ref.token_position + 1)
                               if event_alignment.canonical_window_id == layout.windows[position].window_id
                               else (position, 0, 0) for position in bridge_rows]
            role_logits = core.task_modules["participant"].boundary(
                event_state.unsqueeze(0).expand(len(bridge_rows), -1),
                shared.token_states[0, bridge_rows],
                torch.tensor(event_positions, dtype=torch.long, device=shared.token_states.device),
                batch.source_token_mask[0, bridge_rows])
        if v23_participant:
            if participant_boundary is not None:
                sentence_role_rows = list(participant_boundary.sentence_rows)
                sentence_role_probabilities = participant_boundary.probabilities
            else:
                sentence_role_rows = [position for position, window in enumerate(layout.windows)
                                  if window.view == "sentence" and
                                  any(token.start <= event_alignment.start < token.end
                                      for token in window.tokens)]
            if sentence_role_rows and participant_boundary is None:
                event_positions = []
                for position in sentence_role_rows:
                    cell = sentence_cell(layout, event_alignment.start,
                                         event_alignment.end,
                                         layout.windows[position].window_id)
                    event_positions.append((position, cell[1], cell[2]) if cell is not None
                                           else (position, 0, 0))
                sentence_role_logits = core.task_modules["participant"].boundary(
                    event_state.unsqueeze(0).expand(len(sentence_role_rows), -1),
                    shared.token_states[0, sentence_role_rows],
                    torch.tensor(event_positions, dtype=torch.long,
                                 device=shared.token_states.device),
                    batch.source_token_mask[0, sentence_role_rows])
    starts: list[tuple[float, int, str]] = []
    ends: list[tuple[float, int, str]] = []
    v23_native = (retrieval is not None and
                  retrieval.candidate_profile == "V23_BASELINE" and
                  kind in ("ENTITY", "TIME"))
    bridge_scores = (_bulk_v23_bridge_endpoints(
        endpoints=endpoints, task_boundary=task_boundary,
        bridge_positions=bridge_positions, channel=channel)
        if v23_native else None)
    bridge_offset = 0
    # V23 Trigger proposals are sentence-only; its bridge endpoint ranks have
    # no consumer in the generic cross-window branch below.
    for token in (() if v23_participant or v23_trigger else layout.bridge_tokens):
        start_scores: list[tuple[float, str]] = []
        end_scores: list[tuple[float, str]] = []
        for row, local in bridge_positions[token.source_index]:
            window_id = layout.windows[row].window_id
            if bridge_scores is not None:
                start_score, end_score = bridge_scores[bridge_offset]
                bridge_offset += 1
            elif kind == "PARTICIPANT":
                role_row = bridge_row_index[row]
                role_channel = PARTICIPANT_ROLES.index(role)
                start_score = float(role_logits[role_row, local, role_channel, 0])
                end_score = float(role_logits[role_row, local, role_channel, 1])
            else:
                start_score = float(endpoints[0, row, local, channel, 0])
                end_score = float(endpoints[0, row, local, channel, 1])
            if task_boundary is not None and bridge_scores is None:
                start_score += float(task_boundary.start_logits[0, row, local, 0])
                end_score += float(task_boundary.end_logits[0, row, local, 0])
            start_scores.append((start_score, window_id))
            end_scores.append((end_score, window_id))
        start_score, start_window_id = min(start_scores, key=lambda value: (-value[0], value[1]))
        end_score, end_window_id = min(end_scores, key=lambda value: (-value[0], value[1]))
        starts.append((start_score, token.source_index, start_window_id))
        ends.append((end_score, token.source_index, end_window_id))
    starts.sort(key=lambda value: (-value[0], value[1], value[2]))
    ends.sort(key=lambda value: (-value[0], value[1], value[2]))
    causes: dict[str, int] = {}
    if retrieval is None:
        # Legacy: 기사 전역 상위 K. pilot의 A/B 비교를 위해 보존한다.
        selected_starts, selected_ends = starts[:budget.max_starts], ends[:budget.max_ends]
        pairs = [(start_score + end_score, start_index, end_index)
                 for start_score, start_index, _start_window in selected_starts
                 for end_score, end_index, _end_window in selected_ends
                 if start_index <= end_index]
        pairs.sort(key=lambda value: (-value[0], value[1], value[2]))
        eligible = len(pairs)
        partial = (len(starts) > budget.max_starts or len(ends) > budget.max_ends
                   or eligible > budget.max_pairs)
        if len(starts) > budget.max_starts:
            causes["ARTICLE_GLOBAL_MAX_STARTS"] = len(starts) - budget.max_starts
        if len(ends) > budget.max_ends:
            causes["ARTICLE_GLOBAL_MAX_ENDS"] = len(ends) - budget.max_ends
        if eligible > budget.max_pairs:
            causes["ARTICLE_GLOBAL_MAX_PAIRS"] = eligible - budget.max_pairs
        selected = pairs[:budget.max_pairs]
        trace = RetrievalTrace(visited_cells=2 * len(layout.bridge_tokens),
                               in_window_proposed=0, cross_window_proposed=0,
                               unique_candidates=eligible, scored_candidates=len(selected))
        chunk_size = budget.chunk_size
    else:
        if (kind == "PARTICIPANT" and retrieval.candidate_profile == "V23_BASELINE"):
            if endpoint_threshold is None and not selection_only_threshold_free:
                raise ValueError("v2.3 Participant needs a calibrated endpoint gate")
            participant_args = dict(layout=layout, sentence_rows=sentence_role_rows,
                                    role_logits=sentence_role_logits, role=role,
                                    endpoint_threshold=endpoint_threshold)
            if sentence_role_probabilities is not None:
                participant_args["probabilities"] = sentence_role_probabilities
                participant_args["geometry"] = participant_boundary.geometry
            in_window, visited, dropped_width = (
                participant_candidate_view if participant_candidate_view is not None else
                _v23_participant_candidates(**participant_args))
        else:
            in_window, visited, dropped_width = _propose_in_window(
                kind=kind, layout=layout, shared=shared, endpoints=endpoints,
                task_boundary=task_boundary, channel=channel, retrieval=retrieval,
                endpoint_threshold=endpoint_threshold,
                selection_only_threshold_free=selection_only_threshold_free,
                structural_context=context)
        bounded_cross = []
        if retrieval.candidate_profile == "V23_BASELINE" and kind in ("ENTITY", "TIME"):
            bounded_cross = [row for row in in_window
                             if _v23_recipe(row).route == "cross_window"]
            in_window = [row for row in in_window
                         if _v23_recipe(row).route == "in_window"]
        generic_cross = (_propose_cross_window(
            kind=kind, layout=layout, token_start=starts, token_end=ends,
            retrieval=retrieval)
            if retrieval.candidate_profile != "V23_BASELINE" or
            kind in ("EVENT", "STATEMENT", "ENTITY", "TIME") else [])
        if retrieval.candidate_profile == "V23_BASELINE":
            generic_cross = [row for row in generic_cross
                             if _v23_needs_extension(kind, layout, row)]
        if retrieval.candidate_profile == "V23_BASELINE":
            # The v2.3 owner keeps every bounded or TOP32 candidate. The v3
            # bridge only adds spans absent from that owner's exact coordinates.
            if kind in V23_EXPENSIVE_ARTICLE_SAFETY_CEILING:
                emergency_ceiling = V23_EXPENSIVE_ARTICLE_SAFETY_CEILING[kind]
                selected, route_trace = _select_v23_candidates_capped(
                    local=in_window + bounded_cross, extension=generic_cross,
                    kind=kind, limit=min(
                        emergency_ceiling,
                        v23_operational_expensive_cap or emergency_ceiling))
                if route_trace.dropped_by_article_guard:
                    cause = ("ARTICLE_OPERATIONAL_SCORING_CAP"
                             if v23_operational_expensive_cap is not None and
                             v23_operational_expensive_cap < emergency_ceiling else
                             "ARTICLE_SCORING_GUARD")
                    causes[cause] = route_trace.dropped_by_article_guard
            else:
                selected, route_trace = select_v23_candidates(
                    local=in_window + bounded_cross, extension=generic_cross)
                if kind == "PARTICIPANT" and participant_reservoir is not None and \
                        len(selected) > participant_reservoir:
                    selected = _bound_v23_participant_fine_routes(
                        selected, participant_reservoir)
                    dropped = route_trace.union_deduplicated - len(selected)
                    causes["PARTICIPANT_FINE_ROUTING_CAP"] = dropped
                    route_trace = replace(
                        route_trace, scored_candidates=len(selected),
                        dropped_by_article_guard=dropped,
                        fine_scored_in_window=sum(any(
                            item.route == "in_window" for item in row.route_provenance)
                            for row in selected),
                        fine_scored_cross_window=sum(any(
                            item.route == "cross_window" for item in row.route_provenance)
                            for row in selected),
                        fine_scored_both_route=sum(len({
                            item.route for item in row.route_provenance}) == 2
                            for row in selected))
        elif bounded_cross and generic_cross:
            # The v2.3 structural rank and v3 endpoint rank have different
            # scales. Reserve each half of the cross route before union; never
            # compare the two raw scores to choose one producer over the other.
            half = retrieval.route_quota // 2
            cross = (sorted(bounded_cross,
                            key=lambda row: (-row.rank_score("cross_window"),
                                             row.start, row.end))[:half] +
                     sorted(generic_cross,
                            key=lambda row: (-row.rank_score("cross_window"),
                                             row.start, row.end))[:retrieval.route_quota - half])
        else:
            cross = bounded_cross or generic_cross
        if retrieval.candidate_profile != "V23_BASELINE":
            selected, route_trace = select_route_candidates(
                in_window=in_window, cross_window=cross, retrieval=retrieval)
        eligible = route_trace.union_deduplicated
        if retrieval.candidate_profile != "V23_BASELINE" and eligible > retrieval.max_scored_candidates:
            causes["ARTICLE_SCORING_GUARD"] = eligible - retrieval.max_scored_candidates
        # 폭 제한은 고정된 설계 경계이므로 partial 원인이 아니다. 실제로 후보를
        # 잃는 것은 article-level 정밀 평가 guard뿐이다.
        partial = bool(causes)
        trace = replace(
            route_trace,
            visited_cells=visited,
            in_window_proposed=(visited if v23_participant else
                                route_trace.in_window_proposed),
            dropped_by_article_guard=(causes.get("ARTICLE_SCORING_GUARD", 0) +
                                      causes.get("ARTICLE_OPERATIONAL_SCORING_CAP", 0)),
            width_masked_cells=dropped_width,
        )
        chunk_size = (V23_NATIVE_DECODE_CHUNK_SIZE.get(kind, retrieval.chunk_size)
                      if retrieval.candidate_profile == "V23_BASELINE"
                      else retrieval.chunk_size)
    retained: dict[tuple[str, int, int, str | None], DecodedSourceSpan] = {}
    char_extensions: list[DecodedSourceSpan] = []
    bounded = (_ParticipantExactClosure(participant_reservoir)
               if v23_participant else None)
    invalid = 0
    if retrieval is not None and retrieval.candidate_profile == "V23_BASELINE":
        local_rows, exact_rows = [], []
        for row in selected:
            (exact_rows if _v23_needs_extension(kind, layout, row, context)
             else local_rows).append(row)
        groups = ((local_rows, True), (exact_rows, False))
    else:
        groups = ((selected, False),)
    chunks = ((group[start:start + chunk_size], local)
              for group, local in groups
              for start in range(0, len(group), chunk_size))
    for chunk, local_chunk in chunks:
        aligned = []
        native_prepared = None
        if retrieval is None:
            for _, first, last in chunk:
                left, right = layout.bridge_tokens[first], layout.bridge_tokens[last]
                aligned.append(layout.align({"start": left.start, "end": right.end,
                                             "text": layout.article.content[left.start:right.end]}))
        else:
            if kind == "PARTICIPANT" and context is not None:
                aligned = []
                for row in chunk:
                    key = row.start, row.end
                    if key not in context.participant_alignments:
                        context.participant_alignments[key] = _route_candidate_alignment(
                            layout, row)
                    aligned.append(context.participant_alignments[key])
            else:
                aligned = [_route_candidate_alignment(layout, row) for row in chunk]
        if (retrieval is not None and
                retrieval.candidate_profile == "V23_BASELINE" and
                kind in ("ENTITY", "TIME")):
            native_preferred = [row.diagnostic_provenance.start_window_id
                                if "in_window" in {item.route for item in row.route_provenance}
                                else None for row in chunk]
            native_prepared = NativeCandidateBatch.from_rows(
                kind, layout, [(row.start, row.end, preferred)
                               for row, preferred in zip(chunk, native_preferred)])
        if local_chunk:
            if kind == "TRIGGER":
                output = exact_source_features(
                    layout=layout, batch=batch, backbone=backbone, shared=shared,
                    core=core, rows=[(row, kind) for row in aligned],
                    cache=exact_feature_cache)
            else:
                states = (local_source_states(
                    kind=kind, layout=layout, batch=batch, backbone=backbone,
                    shared=shared, core=core,
                    rows=[(row.start, row.end) for row in chunk])
                    if kind in ("EVENT", "STATEMENT") else
                    shared.document_state.new_zeros((len(chunk),
                                                     shared.document_state.shape[-1])))
                output = SimpleNamespace(
                    states=states, residuals=states.new_zeros((len(chunk), 2)),
                    local_mask=torch.ones(len(chunk), dtype=torch.bool, device=states.device),
                    link_logits=states.new_zeros(len(chunk)))
        else:
            output = exact_source_features(
                layout=layout, batch=batch, backbone=backbone, shared=shared, core=core,
                rows=[(row, kind) for row in aligned], cache=exact_feature_cache)
        char_residuals = None
        char_rows = None
        if local_chunk and kind in ("EVENT", "STATEMENT", "TRIGGER", "PARTICIPANT"):
            # Exact character correction is additive. The v2.3 cell keeps its
            # Canonical or endpoint decision, including Trigger's native cap 4.
            if kind == "PARTICIPANT" and context is not None and not core.training:
                char_rows = _cached_v23_participant_char_rows(
                    layout=layout, batch=batch, backbone=backbone, shared=shared,
                    core=core, context=context, chunk=chunk, aligned=aligned,
                    exact_feature_cache=exact_feature_cache)
            else:
                char_output = (output if kind == "TRIGGER" else exact_source_features(
                    layout=layout, batch=batch, backbone=backbone, shared=shared, core=core,
                    rows=[(row, kind) for row in aligned], cache=exact_feature_cache))
                char_residuals = (core.task_modules["semantic_boundary"](
                    char_output.states, char_output.residuals)
                    if kind in ("EVENT", "STATEMENT") else char_output.residuals)
        labels: list[str | None] = [kind] * len(chunk)
        decision_scores: list[float] | None = None
        boundary_fitness_scores: list[float | None] = [None] * len(chunk)
        decision_components: list[list[tuple[str, float]]] = [[] for _ in chunk]
        subtype_scores: list[tuple[tuple[str, float], ...]] = [()] * len(chunk)
        residuals = output.residuals
        baseline = retrieval is not None and retrieval.candidate_profile == "V23_BASELINE"
        if baseline and kind in ("EVENT", "STATEMENT"):
            preferred = [row.diagnostic_provenance.start_window_id
                         if "in_window" in {item.route for item in row.route_provenance}
                         else None for row in chunk]
            canonical = canonical_scores(
                layout=layout, batch=batch, backbone=backbone, shared=shared, core=core,
                rows=[(row.start, row.end, window) for row, window in zip(chunk, preferred)])
            fallback_residuals = core.task_modules["semantic_boundary"](
                output.states, output.residuals)
            fallback_fitness = core.task_modules["semantic_boundary"].fitness_score(output.states)
            fallback_validity = core.task_modules["semantic_validity"](output.states)
            needs_fallback = any(pair is None for pair in canonical)
            fallback_fitness_rows = (fallback_fitness.detach().cpu().tolist()
                                     if needs_fallback else None)
            fallback_validity_rows = (fallback_validity.detach().cpu().tolist()
                                      if needs_fallback else None)
            semantic_channel = ("EVENT", "STATEMENT").index(kind)
            decision_scores = [float(pair[0][semantic_channel]) if pair is not None
                               else fallback_validity_rows[index]
                               for index, pair in enumerate(canonical)]
            boundary_fitness_scores = [float(pair[1][semantic_channel]) if pair is not None
                                       else fallback_fitness_rows[index]
                                       for index, pair in enumerate(canonical)]
            decision_components = [[("canonical_v3_semantic" if pair is not None
                                    else "cross_window_exact_validity", score),
                                    ("canonical_v3_boundary" if pair is not None
                                     else "cross_window_exact_fitness",
                                     boundary_fitness_scores[index])]
                                   for index, (pair, score) in enumerate(zip(canonical, decision_scores))]
            residuals = torch.stack([
                output.residuals[index] * 0 if pair is not None else
                fallback_residuals[index]
                for index, pair in enumerate(canonical)])
        elif kind in ("EVENT", "STATEMENT") and all(
                name in core.task_modules for name in ("semantic_boundary", "semantic_validity")):
            residuals = core.task_modules["semantic_boundary"](output.states, output.residuals)
            fitness = core.task_modules["semantic_boundary"].fitness_score(output.states)
            validity = core.task_modules["semantic_validity"](output.states)
            decision_scores = [float(value) for value in validity]
            boundary_fitness_scores = [float(value) for value in fitness]
            for index, value in enumerate(decision_scores):
                decision_components[index].append(("semantic_validity_decision", value))
                decision_components[index].append(
                    ("boundary_fitness_decision", boundary_fitness_scores[index]))
        elif kind == "TRIGGER":
            logits = core.task_modules["trigger"].span_score(output.states).squeeze(-1)
            decision_scores = [float(value) for value in logits.detach().cpu().tolist()]
            decision_components = [[("trigger_span_decision", value)]
                                   for value in decision_scores]
            if baseline:
                native_trigger = ["in_window" in {item.route for item in row.route_provenance}
                                  for row in chunk]
                residuals = torch.stack([
                    output.residuals[index] * (0 if native_trigger[index] else 1)
                    for index in range(len(chunk))])
        entity_type_logits: list[tuple[float, ...]] | None = None
        if kind == "ENTITY":
            if "entity_mention" not in core.task_modules:
                raise ValueError("Entity type head is not registered")
            geometry = _native_fallback_geometry(output, aligned, native_prepared)
            states = output.states
            if baseline:
                preferred = native_preferred
                states, geometry_rows, native_used = native_states(
                    kind=kind, layout=layout, batch=batch, backbone=backbone,
                    shared=shared, core=core,
                    rows=[(row.start, row.end, window) for row, window in zip(chunk, preferred)],
                    fallback_states=states, fallback_geometry=geometry[0],
                    prepared=native_prepared,
                    sentence_cache=(exact_feature_cache.sentence_cache(
                        layout=layout, batch=batch, backbone=backbone,
                        shared=shared, core=core) if exact_feature_cache is not None else None))
                geometry = geometry_rows.unsqueeze(0)
                residuals = _native_residuals(output.residuals, native_used)
            logits = core.task_modules["entity_mention"].typing(
                states.unsqueeze(0), geometry,
                torch.ones((1, len(chunk)), dtype=torch.bool, device=output.states.device))[0]
            if baseline:
                entity_type_logits = [tuple(row) for row in logits.detach().cpu().tolist()]
                decision_scores = [max(row) for row in entity_type_logits]
                decision_components = [[("entity_native_multilabel", value)]
                                       for value in decision_scores]
                labels = [ENTITY_TYPES[max(range(len(row)), key=lambda index: row[index])]
                          for row in entity_type_logits]
            else:
                existence = core.task_modules["entity_mention"].existence(
                    states.unsqueeze(0), geometry,
                    torch.ones((1, len(chunk)), dtype=torch.bool,
                               device=output.states.device))[0, :, 0]
                decision_scores = existence.detach().cpu().tolist()
                decision_components = [[("entity_existence_decision", value)]
                                       for value in decision_scores]
                type_ids = logits.argmax(dim=-1)
                labels = [ENTITY_TYPES[int(value)] for value in type_ids.detach().cpu().tolist()]
            # 5-type 분류 logit은 type 책임이지 span 존재 책임이 아니다. 선택 점수에
            # 더하면 분류 confidence가 detection 순위를 움직인다. label만 쓴다.
            type_rows = entity_type_logits or logits.detach().cpu().tolist()
            subtype_scores = [tuple(zip(ENTITY_TYPES, row)) for row in type_rows]
        elif kind == "STATEMENT":
            if "statement_type" not in core.task_modules:
                raise ValueError("StatementType head is not registered")
            logits = core.task_modules["statement_type"](
                output.states.unsqueeze(0),
                torch.ones((1, len(chunk)), dtype=torch.bool, device=output.states.device)).logits[0]
            type_ids = logits.argmax(dim=-1)
            labels = [STATEMENT_TYPES[value] for value in type_ids.detach().cpu().tolist()]
            probabilities = logits.softmax(dim=-1)
            subtype_scores = [tuple(zip(STATEMENT_TYPES, row))
                              for row in probabilities.detach().cpu().tolist()]
        elif kind == "PARTICIPANT":
            labels = [role] * len(chunk)
            if baseline:
                local_role = ["in_window" in {item.route for item in row.route_provenance}
                              for row in chunk]
                role_logits = (core.task_modules["participant"].span_score(
                    torch.cat((event_state.unsqueeze(0).expand(len(chunk), -1),
                               output.states), dim=-1)) if not all(local_role) else None)
                role_rows = (role_logits[:, PARTICIPANT_ROLES.index(role)].detach().cpu().tolist()
                             if role_logits is not None else None)
                decision_scores = [row.rank_score("in_window") if local_role[index]
                                   else role_rows[index]
                                   for index, row in enumerate(chunk)]
                decision_components = [[("participant_b2_boundary" if local_role[index]
                                         else "cross_window_participant_span", value)]
                                       for index, value in enumerate(decision_scores)]
            else:
                role_logits = core.task_modules["participant"].span_score(
                    torch.cat((event_state.unsqueeze(0).expand(len(chunk), -1),
                               output.states), dim=-1))
                decision_scores = [float(role_logits[index, PARTICIPANT_ROLES.index(role)])
                                   for index in range(len(chunk))]
                decision_components = [[("participant_span_decision", value)]
                                       for value in decision_scores]
            if baseline:
                residuals = torch.stack([
                    output.residuals[index] * (0 if local_role[index] else 1)
                    for index in range(len(chunk))])
        elif kind == "TIME":
            geometry = _native_fallback_geometry(output, aligned, native_prepared)
            states = output.states
            if baseline:
                preferred = native_preferred
                states, geometry_rows, native_used = native_states(
                    kind=kind, layout=layout, batch=batch, backbone=backbone,
                    shared=shared, core=core,
                    rows=[(row.start, row.end, window) for row, window in zip(chunk, preferred)],
                    fallback_states=states, fallback_geometry=geometry[0],
                    prepared=native_prepared,
                    sentence_cache=(exact_feature_cache.sentence_cache(
                        layout=layout, batch=batch, backbone=backbone,
                        shared=shared, core=core) if exact_feature_cache is not None else None))
                geometry = geometry_rows.unsqueeze(0)
                residuals = _native_residuals(output.residuals, native_used)
            logits = core.task_modules["time_mention"].span(
                states.unsqueeze(0), geometry,
                torch.ones((1, len(chunk)), dtype=torch.bool, device=output.states.device))[0, :, 0]
            decision_scores = logits.detach().cpu().tolist()
            decision_components = [[("time_span_decision", value)]
                                   for value in decision_scores]
        if decision_scores is None:
            raise RuntimeError(f"{kind}: exact decision producer is not registered")
        # MPS scalar reads synchronize the device. Transfer each chunk once,
        # preserving the full bounded candidate stream and its original order.
        if local_chunk and kind in ("ENTITY", "TIME"):
            # Local native rows use the zero residual/link carrier created
            # above. Keep these constants in Python rather than copying three
            # zero tensors back from MPS for every scoring chunk.
            residual_rows = ((0.0, 0.0),) * len(chunk)
            local_rows = (True,) * len(chunk)
            link_rows = (0.0,) * len(chunk)
        else:
            residual_rows = residuals.detach().cpu().tolist()
            local_rows = (output.local_mask.detach().cpu().tolist()
                          if isinstance(output.local_mask, torch.Tensor)
                          else output.local_mask)
            link_rows = output.link_logits.detach().cpu().tolist()
        if char_residuals is not None:
            char_rows = char_residuals.detach().cpu().tolist()
        native_capture: list[NativeEntityStateRow] = []
        native_retention_threshold = (native_entity_retention_threshold
                                      if kind == "ENTITY" else
                                      native_time_retention_threshold)
        for offset, chunk_row in enumerate(chunk):
            if retrieval is None:
                pair_score = chunk_row[0]
                route_provenance: tuple[RouteProvenance, ...] = ()
            else:
                route_provenance = chunk_row.route_provenance
                pair_score = chunk_row.diagnostic_provenance.retrieval_score
            source = aligned[offset]
            start_char = source.start + round(residual_rows[offset][0])
            end_char = source.end + round(residual_rows[offset][1])
            if not (0 <= start_char < end_char <= len(layout.article.content)):
                invalid += 1
                continue
            # source_link는 cross-window 양 끝을 잇는 책임만 감독된다. in-window
            # 후보에 더하면 학습되지 않은 항이 선택 점수를 움직이므로 제외한다.
            cross_window = not local_rows[offset]
            link_score = link_rows[offset] if cross_window else 0.0
            # Retrieval 항은 candidate reachability/provenance만 맡는다. final rank와
            # 기존 raw-threshold consumer는 학습된 exact decision logit 하나를 쓴다.
            score = decision_scores[offset]
            boundary_fitness = boundary_fitness_scores[offset]
            components = (("retrieval_score", float(pair_score)),
                          ("source_link", link_score),
                          *decision_components[offset])
            if (not math.isfinite(score) or
                    (boundary_fitness is not None and not math.isfinite(boundary_fitness)) or
                    not all(math.isfinite(value) for _, value in components) or
                    not all(math.isfinite(value) for _, value in subtype_scores[offset])):
                invalid += 1
                continue
            if (kind in ("ENTITY", "TIME") and baseline and native_used[offset] and
                    native_retention_threshold is not None and
                    score >= native_retention_threshold and
                    (start_char, end_char) == (source.start, source.end)):
                cell = (native_prepared.cells[offset] if native_prepared is not None
                        else sentence_cell(layout, source.start, source.end,
                                           preferred[offset]))
                if (cell is not None and
                        source.canonical_window_id == layout.windows[cell[0]].window_id and
                        source.start_ref.window_id == source.canonical_window_id and
                        source.end_ref.window_id == source.canonical_window_id and
                        (source.start_ref.token_position,
                         source.end_ref.token_position + 1) == cell[1:3]):
                    native_capture.append(NativeEntityStateRow(
                        cell[0], cell[1], cell[2], start_char, end_char,
                        score, offset))
            source_windows = tuple(dict.fromkeys(
                ((source.start_ref.window_id, source.end_ref.window_id),) +
                tuple((row.start_window_id, row.end_window_id)
                      for row in route_provenance)
            ))
            if bounded is not None:
                recipe = (start_char, end_char, score, source.start_ref.window_id,
                          source.end_ref.window_id, tuple(components),
                          subtype_scores[offset], source_windows,
                          route_provenance, boundary_fitness)
                bounded.add_native(recipe)
            else:
                candidate = DecodedSourceSpan(kind, labels[offset], start_char, end_char,
                                              layout.article.content[start_char:end_char], score,
                                              source.start_ref.window_id,
                                              source.end_ref.window_id,
                                              tuple(components), subtype_scores[offset],
                                              source_windows,
                                              route_provenance,
                                              boundary_fitness)
                # V23 keeps all five type logits as evidence, but contributes
                # only the argmax typed mention at an exact source coordinate.
                key = layout.closure_key(
                    kind, start_char, end_char,
                    None if entity_type_logits is not None else candidate.label)
                old = retained.get(key)
                if old is None:
                    retained[key] = candidate
                elif candidate.score > old.score:
                    retained[key] = _merge_window_provenance(candidate, old)
                else:
                    retained[key] = _merge_window_provenance(old, candidate)
            if char_rows is not None:
                corrected_start = source.start + round(char_rows[offset][0])
                corrected_end = source.end + round(char_rows[offset][1])
                if kind == "PARTICIPANT" and context is not None:
                    def cached_cell(start: int, end: int):
                        if not 0 <= start < end <= len(layout.article.content):
                            return None
                        key = start, end
                        if key not in context.participant_cells:
                            context.participant_cells[key] = sentence_cell(layout, start, end)
                        return context.participant_cells[key]
                    original_cell = cached_cell(source.start, source.end)
                    corrected_cell = cached_cell(corrected_start, corrected_end)
                else:
                    original_cell = sentence_cell(layout, source.start, source.end)
                    corrected_cell = (sentence_cell(layout, corrected_start, corrected_end)
                                      if 0 <= corrected_start < corrected_end <= len(layout.article.content)
                                      else None)
                if (corrected_cell is not None and original_cell is not None and
                        corrected_cell[:3] == original_cell[:3] and
                        (corrected_start, corrected_end) != (start_char, end_char)):
                    extension_producer = {
                        "EVENT": "V23_CHAR_EXTENSION",
                        "STATEMENT": "V23_CHAR_EXTENSION",
                        "TRIGGER": "V23_TRIGGER_CHAR_EXTENSION",
                        "PARTICIPANT": "V23_PARTICIPANT_CHAR_EXTENSION",
                    }[kind]
                    extension_routes = tuple(replace(route, producer=extension_producer)
                                             for route in route_provenance)
                    extension_components = (*components,
                        ("char_extension_parent_start", float(source.start)),
                        ("char_extension_parent_end", float(source.end)),
                        ("exact_char_residual",
                         float(abs(corrected_start - source.start) +
                               abs(corrected_end - source.end))))
                    if bounded is not None:
                        bounded.add_extension((
                            corrected_start, corrected_end, score,
                            source.start_ref.window_id, source.end_ref.window_id,
                            extension_components, subtype_scores[offset],
                            source_windows, extension_routes, boundary_fitness))
                    else:
                        char_extensions.append(replace(
                            candidate, start=corrected_start, end=corrected_end,
                            text=layout.article.content[corrected_start:corrected_end],
                            route_provenance=extension_routes,
                            score_components=extension_components))
        if native_capture:
            exact_feature_cache.remember_native_states(
                kind=kind, layout=layout, batch=batch, backbone=backbone,
                shared=shared, core=core, rows=native_capture, states=states)
    if bounded is not None:
        spans, exact_count = bounded.finish(content=layout.article.content, role=role)
        if participant_reservoir is not None and not core.training and spans:
            # B2 supplies retrieval rank only. Fine-score exact survivor spans
            # after char correction and coordinate deduplication.
            fine_spans = []
            for start in range(0, len(spans), retrieval.chunk_size):
                chunk = spans[start:start + retrieval.chunk_size]
                alignments = [layout.align_runtime(row.start, row.end) for row in chunk]
                features = exact_source_features(
                    layout=layout, batch=batch, backbone=backbone,
                    shared=shared, core=core,
                    rows=[(row, "PARTICIPANT") for row in alignments],
                    cache=exact_feature_cache)
                logits = core.task_modules["participant"].span_score(
                    torch.cat((event_state.unsqueeze(0).expand(len(chunk), -1),
                               features.states), dim=-1))
                scores = logits[:, PARTICIPANT_ROLES.index(role)].detach().cpu().tolist()
                fine_spans.extend(replace(
                    row, score=float(score),
                    score_components=(*row.score_components,
                                      ("participant_span_decision", float(score))))
                    for row, score in zip(chunk, scores))
            spans = tuple(fine_spans)
        return DecodeResult(
            spans, eligible, len(selected), invalid, partial,
            retrieval.status, trace, tuple(sorted(causes.items())),
            (("raw_cartesian_observations", visited),
             ("route_candidate_objects", len(selected)),
             ("candidate_scores_evaluated", len(selected)),
             ("native_exact_observations", bounded.native_inputs),
             ("char_extension_observations", bounded.extension_inputs),
             ("deduplicated_exact_candidates", exact_count),
             ("decoded_source_span_objects", len(spans)),
             ("participant_fine_scored", len(spans))))
    if (kind == "TRIGGER" and retrieval is not None and
            retrieval.candidate_profile == "V23_BASELINE" and char_extensions):
        # A corrected character span is a new exact candidate. Score each new
        # coordinate once after native/extension dedup, using the same head.
        extension_coordinates = tuple(dict.fromkeys(
            (row.start, row.end) for row in char_extensions
            if layout.closure_key(kind, row.start, row.end, row.label) not in retained))
        exact_decisions: dict[tuple[int, int], float] = {}
        invalid_extensions: set[tuple[int, int]] = set()
        for offset in range(0, len(extension_coordinates), retrieval.chunk_size):
            coordinates = extension_coordinates[offset:offset + retrieval.chunk_size]
            alignments = [layout.align_runtime(start, end) for start, end in coordinates]
            features = exact_source_features(
                layout=layout, batch=batch, backbone=backbone, shared=shared,
                core=core, rows=[(row, "TRIGGER") for row in alignments],
                cache=exact_feature_cache)
            logits = core.task_modules["trigger"].span_score(features.states).squeeze(-1)
            for coordinate, score in zip(coordinates, logits.detach().cpu().tolist()):
                if math.isfinite(score):
                    exact_decisions[coordinate] = float(score)
                else:
                    invalid_extensions.add(coordinate)
                    invalid += 1
        char_extensions = [replace(
            row, score=float(exact_decisions[(row.start, row.end)]),
            score_components=tuple(
                ("char_extension_parent_trigger_span_decision" if name ==
                 "trigger_span_decision" else name, value)
                for name, value in row.score_components) +
                (("trigger_span_decision",
                  float(exact_decisions[(row.start, row.end)])),))
            if (row.start, row.end) in exact_decisions else row
            for row in char_extensions
            if (row.start, row.end) not in invalid_extensions]
    # Native TOP32 candidates own duplicate coordinates even if a character
    # correction has a higher score; the extension cannot displace that route.
    for extension in char_extensions:
        key = layout.closure_key(kind, extension.start, extension.end, extension.label)
        old = retained.get(key)
        retained[key] = (extension if old is None else
                         _merge_window_provenance(old, extension))
    ordered = tuple(sorted(retained.values(), key=lambda row: (row.start, row.end, row.kind)))
    status = budget.status if retrieval is None else retrieval.status
    return DecodeResult(ordered, eligible, len(selected), invalid, partial, status,
                        trace, tuple(sorted(causes.items())))
