"""Gold-free v3 request orchestrator and strict diagnostic checkpoint startup.

The worker owns one frozen producer and one v3 core. Each request owns its source
layout and transient tensor leases; only scalar PUBLIC output crosses the boundary.
Selection budgets and checkpoint-bound acceptance are independent contracts. No
database writer or Gold reader is called by this module.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from hashlib import sha256
import heapq
from itertools import islice
import math
from pathlib import Path
from threading import BoundedSemaphore
from time import perf_counter
from typing import Any, Mapping, Sequence

import torch

from models.v3_pretraining.architecture import V3Core
from models.v3_pretraining.frozen_features import (FrozenBackboneFeatureBuilder,
                                                   RunLocalFrozenFeatureCache)
from runtime.v3_pretraining.acceptance import (SCORE_CONTRACT_VERSION, AcceptanceConfig,
                                               AcceptanceTrace,
                                               accept_decision_boundary_then_cap,
                                               accept_then_cap, cap_only)
from runtime.v3_pretraining.attribution_scoring import (asserted_by_facts, bridge_token_states,
                                                        decode_assertor_source,
                                                        decode_assertor_sources,
                                                        RelationDecode, score_final_relations)
from runtime.v3_pretraining.canonical_text import GroundedStatement, SourceGrounding
from runtime.v3_pretraining.entity_scoring import score_and_close_entity
from runtime.v3_pretraining.exact_feature_cache import RequestExactFeatureCache
from runtime.v3_pretraining.entity_union import (ENTITY_TYPES, build_unified_entity_mentions,
                                                cap_unified_entity_mentions,
                                                evidence_from_assertor_decode,
                                                evidence_from_entity_decode,
                                                evidence_from_role_decode)
from runtime.v3_pretraining.event_features import (EventFeatureProvenance,
                                                  EventOptionalConfidenceEvidence,
                                                  build_event_member_features,
                                                  build_event_pair_feature_bundle,
                                                  finalize_cluster_features)
from runtime.v3_pretraining.event_identity import EventMember, MemberRoleFact
from runtime.v3_pretraining.event_scoring import (EventIdentityDecodeConfig,
                                                 score_event_identity)
from runtime.v3_pretraining.extraction_decode import (DecodeBudget, DecodedSourceSpan,
                                                      RetrievalBudget,
                                                      V23_EXPENSIVE_ARTICLE_SAFETY_CEILING,
                                                      decode_source_spans,
                                                      event_source_state,
                                                      precompute_v23_event_states,
                                                      precompute_v23_participant_boundaries,
                                                      source_decode_context,
                                                      v23_participant_candidate_views)
from runtime.v3_pretraining.primary_scoring import (PrimaryTrainingProvenance,
                                                   score_final_primary)
from runtime.v3_pretraining.public_selection import (causes_discovery_pairs,
                                                     complete_public_selection,
                                                     PublicBaseSelection, PublicSelection,
                                                     public_relation_pairs,
                                                     select_public_base,
                                                     select_public_propositions)
from runtime.v3_pretraining.entity_pair_blocking import EntityPairPolicy
from runtime.v3_pretraining.public_confidence import (EdgeScore, PublicEdgeScores,
                                                     acceptance_edge_score)
from runtime.v3_pretraining.public_graph import (V3ConstructionResult,
                                                 compact_public_construction,
                                                 project_public)
from runtime.v3_pretraining.relation_routing import (
    PredictedRelationRoutingArtifact, full_relation_route, identity_policy_sha256, route_about,
    route_causes)
from runtime.v3_pretraining.pair_routing import (RoutedPairs, inventory_lineage,
                                                route_event_coreference,
                                                route_event_time)
from runtime.candidate_routing.integrated import IntegratedBoundedPolicies
from runtime.v3_pretraining.source_batch import source_windows_from_layout
from runtime.v3_pretraining.source_funnel import (SourceFunnelPolicy,
                                                  attach_optional_triggers,
                                                  contain_accepted_events)
from runtime.v3_pretraining.handoff import FrozenSourceViewKey
from runtime.v3_pretraining.source_layout import LayoutBuilder, RawArticle
from runtime.v3_pretraining.temporal import (RelativeMonthContextBinding,
                                             TimeMentionEvidence,
                                             close_time_occurrences,
                                             index_relative_month_context_bindings,
                                             infer_source_time)
from runtime.v3_pretraining.temporal_scoring import (EventTimeDecodeConfig,
                                                    encode_event_time_features,
                                                    score_event_time)
from runtime.v3_pretraining.tokenizer import load_pinned_fast_tokenizer


V23_PARTICIPANT_EVENT_CHUNK_SIZE = 16
V23_ACCEPTED_SAFETY_CAPS = {"EVENT": 128, "STATEMENT": 128,
                            "ENTITY": 256, "TIME": 256, "TRIGGER": 256}
V23_UNIFIED_ENTITY_SAFETY_CAP = 128


def _safety_budget_record(input_count: int, retained_count: int) -> dict[str, int | bool]:
    dropped = input_count - retained_count
    if dropped < 0:
        raise ValueError("safety budget cannot create candidates")
    return {"input_count": input_count, "retained_count": retained_count,
            "dropped_by_safety_budget": dropped, "budget_exhausted": dropped > 0}


def _operational_budget_record(input_count: int, retained_count: int,
                               cap: int | None) -> dict[str, int | bool | None]:
    dropped = input_count - retained_count
    if dropped < 0:
        raise ValueError("operational cap cannot create candidates")
    return {"cap": cap, "input_count": input_count,
            "retained_count": retained_count,
            "dropped_by_operational_cap": dropped, "budget_exhausted": dropped > 0}


@dataclass(frozen=True, slots=True)
class V23OperationalCaps:
    """Explicit V23 execution caps; None leaves the emergency defaults intact."""

    event_accepted: int | None = None
    time_accepted: int | None = None
    entity_expensive: int | None = None
    time_expensive: int | None = None

    def __post_init__(self) -> None:
        if any(value is not None and (type(value) is not int or value <= 0)
               for value in (self.event_accepted, self.time_accepted,
                             self.entity_expensive, self.time_expensive)):
            raise ValueError("V23 operational caps must be positive integers")

    def accepted_for(self, kind: str) -> int | None:
        return {"EVENT": self.event_accepted, "TIME": self.time_accepted}.get(kind)

    def expensive_for(self, kind: str) -> int | None:
        return {"ENTITY": self.entity_expensive, "TIME": self.time_expensive}.get(kind)


V23_DEFAULT_OPERATIONAL_CAPS = V23OperationalCaps(
    event_accepted=96, time_accepted=128,
    entity_expensive=20_480, time_expensive=24_576)


@dataclass(frozen=True, slots=True)
class ServingBudget:
    """Bound request work before calibrated extraction and selection exist."""

    source: DecodeBudget = field(default_factory=lambda: DecodeBudget(24, 24, 64, 32))
    participant: DecodeBudget = field(default_factory=lambda: DecodeBudget(12, 12, 24, 16))
    # generic 다섯 kind의 후보 검색. None이면 legacy 기사 전역 top-K로 되돌아간다.
    retrieval: RetrievalBudget | None = field(default_factory=RetrievalBudget)
    # kind별 검색 예산 재정의. ENGINEERING_CANDIDATE_BUDGET 비교용이며 production 값이 아니다.
    retrieval_by_kind: tuple[tuple[str, RetrievalBudget], ...] = ()
    max_events: int = 64
    max_statements: int = 64
    max_entities: int = 64
    max_times: int = 64
    max_triggers: int = 64
    max_entity_candidates: int = 128
    max_role_fillers_per_event_role: int = 2
    pair_chunk_size: int = 64
    max_event_time_pairs: int = 4096
    max_event_coreference_pairs: int = 4096
    max_relation_pairs: int = 4096
    v23_operational_caps: V23OperationalCaps | None = None

    def __post_init__(self) -> None:
        if min(self.max_events, self.max_statements, self.max_entities,
               self.max_times, self.max_triggers, self.max_entity_candidates,
               self.max_role_fillers_per_event_role,
               self.pair_chunk_size, self.max_event_time_pairs,
               self.max_event_coreference_pairs, self.max_relation_pairs) <= 0:
            raise ValueError("serving engineering budgets must be positive")
        if any(kind not in ("EVENT", "STATEMENT", "ENTITY", "TIME", "TRIGGER")
               for kind, _budget in self.retrieval_by_kind):
            raise ValueError("retrieval override needs one of the five generic source kinds")
        if self.v23_operational_caps is not None and not isinstance(
                self.v23_operational_caps, V23OperationalCaps):
            raise ValueError("V23 operational caps need the declared contract")

    def retrieval_for(self, kind: str) -> RetrievalBudget | None:
        for name, budget in self.retrieval_by_kind:
            if name == kind:
                return budget
        return self.retrieval

    def operational_caps_for_v23(self) -> V23OperationalCaps:
        return self.v23_operational_caps or V23_DEFAULT_OPERATIONAL_CAPS


@dataclass(frozen=True, slots=True)
class ServingResult:
    public: dict[str, Any]
    audit: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PhasePrefixResult:
    """Gold-free scalar snapshot at an actual serving execution boundary."""

    phase: str
    structure: dict[str, Any]
    checkpoint_sha256: str


@dataclass(frozen=True, slots=True)
class SourceFunnelResult:
    """Scalar-only source carrier; downstream training must re-gather trainable states."""

    article_id: str
    article_version_id: str
    content_sha256: str
    binding: dict[str, Any]
    selected: dict[str, tuple[dict[str, Any], ...]]
    candidate_trace: dict[str, tuple[dict[str, Any], ...]]
    stage_counts: dict[str, dict[str, int]]
    event_owners: tuple[str, ...]
    participant_evidence: tuple[dict[str, Any], ...]
    assertor_sources: tuple[dict[str, Any], ...]
    entity_evidence: tuple[dict[str, Any], ...]
    entity_pre_budget: tuple[str, ...]
    entity_post_budget: tuple[str, ...]
    entity_candidates_pre_budget: tuple[dict[str, Any], ...]
    entity_candidates_post_budget: tuple[dict[str, Any], ...]
    partial_stages: tuple[str, ...]
    backbone_calls: int
    dce_calls: int

    def as_dict(self, *, include_candidates: bool = False) -> dict[str, Any]:
        candidate_summary = {
            kind: {"candidate_count": len(rows),
                   "rejection_reasons": dict(sorted(Counter(
                       row["reason"] for row in rows
                       if row.get("reason") not in (None, "SELECTED")).items()))}
            for kind, rows in self.candidate_trace.items()}
        return {"article_id": self.article_id,
                "article_version_id": self.article_version_id,
                "content_sha256": self.content_sha256,
                "binding": self.binding,
                "selected": self.selected,
                "candidate_trace": (self.candidate_trace if include_candidates
                                    else candidate_summary),
                "stage_counts": self.stage_counts, "event_owners": self.event_owners,
                "participant_evidence": self.participant_evidence,
                "assertor_sources": self.assertor_sources,
                "entity_evidence": self.entity_evidence,
                "entity_pre_budget": self.entity_pre_budget,
                "entity_post_budget": self.entity_post_budget,
                "entity_candidates_pre_budget": self.entity_candidates_pre_budget,
                "entity_candidates_post_budget": self.entity_candidates_post_budget,
                "partial_stages": self.partial_stages,
                "backbone_calls": self.backbone_calls, "dce_calls": self.dce_calls}


def _source_span_record(span: DecodedSourceSpan) -> dict[str, Any]:
    return {"kind": span.kind, "start": span.start, "end": span.end,
            "label": span.label, "text": span.text,
            "decision_score": span.extraction_score,
            "boundary_score": span.boundary_fitness_score,
            "route_provenance": [
                {"route": row.route, "start_window_id": row.start_window_id,
                 "end_window_id": row.end_window_id,
                 **({"producer": row.producer} if row.producer != "V3_WINDOW" else {})}
                for row in span.route_provenance],
            "source_windows": [list(pair) for pair in span.provenance_windows]}


def _native_decision_probability(span: DecodedSourceSpan,
                                 producer: str) -> float | None:
    """검증된 동일 decision logit만 Event confidence로 변환한다."""
    scores = [score for name, score in span.score_components if name == producer]
    if (len(scores) != 1 or not math.isfinite(scores[0]) or
            not math.isclose(scores[0], span.extraction_score, rel_tol=0, abs_tol=1e-6)):
        return None
    return 1.0 / (1.0 + math.exp(-max(-80.0, min(80.0, scores[0]))))


def _entity_candidate_record(row: Any) -> dict[str, Any]:
    return {"candidate_id": row.candidate_id, "start": row.start,
            "end": row.end, "text": row.text, "entity_type": row.entity_type,
            "origins": list(row.origins), "evidence_ids": list(row.evidence_ids),
            "score": row.score, "referential_state": row.referential_state,
            "referent_hint": row.referent_hint}


def _source_candidate_records(spans: tuple[DecodedSourceSpan, ...],
                              selected: tuple[DecodedSourceSpan, ...], *,
                              kind: str, policy: SourceFunnelPolicy | None) -> tuple[dict[str, Any], ...]:
    selected_keys = {(row.start, row.end, row.label) for row in selected}
    ranked = sorted(spans, key=lambda row: (-row.extraction_score, row.start,
                                          row.end, row.label or ""))
    records = []
    for rank, row in enumerate(ranked, 1):
        record = _source_span_record(row)
        survived = (row.start, row.end, row.label) in selected_keys
        reason = "SELECTED" if survived else "BUDGET_TRUNCATION"
        if policy is not None and not (kind == "TRIGGER" and
                policy.retrieval.candidate_profile == "V23_BASELINE"):
            decision_ok = row.extraction_score >= policy.threshold(kind)
            boundary_ok = (kind not in ("EVENT", "STATEMENT") or
                           row.boundary_fitness_score is not None and
                           row.boundary_fitness_score >= policy.boundary_threshold(kind))
            if not decision_ok and not boundary_ok:
                reason = "DECISION_AND_BOUNDARY_BELOW_THRESHOLD"
            elif not decision_ok:
                reason = "DECISION_BELOW_THRESHOLD"
            elif not boundary_ok:
                reason = ("BOUNDARY_SCORE_MISSING" if row.boundary_fitness_score is None else
                          "BOUNDARY_BELOW_THRESHOLD")
        record.update({"rank": rank, "accepted": reason in ("SELECTED", "BUDGET_TRUNCATION"),
                       "cap_survived": survived, "reason": reason})
        records.append(record)
    return tuple(records)


def _accepted_spans(spans: tuple[DecodedSourceSpan, ...], *, kind: str, limit: int,
                    acceptance: AcceptanceConfig,
                    source_policy: SourceFunnelPolicy | None = None,
                    v23_operational_cap: int | None = None
                    ) -> tuple[tuple[DecodedSourceSpan, ...], AcceptanceTrace]:
    if v23_operational_cap is not None and (
            type(v23_operational_cap) is not int or v23_operational_cap <= 0 or
            kind not in ("EVENT", "TIME") or source_policy is None or
            source_policy.retrieval.candidate_profile != "V23_BASELINE"):
        raise ValueError("operational accepted cap requires V23 Event/Time")
    if source_policy is not None:
        baseline = source_policy.retrieval.candidate_profile == "V23_BASELINE"
        if not baseline and limit != source_policy.cap(kind):
            raise ValueError("source policy cap differs from runtime cap")
        if baseline and kind == "TRIGGER":
            safety_limit = V23_ACCEPTED_SAFETY_CAPS[kind]
            selected = (tuple(sorted(spans, key=lambda row: (row.start, row.end,
                                                             row.label or "")))
                        if len(spans) <= safety_limit else
                        cap_only(spans, limit=safety_limit,
                                 rank_key=lambda row: (-row.extraction_score, row.start,
                                                       row.end, row.label or ""),
                                 output_key=lambda row: (row.start, row.end,
                                                         row.label or "")))
            return selected, AcceptanceTrace(
                kind, len(spans), len(spans), len(selected), 0,
                len(spans) - len(selected), budget_reason="SAFETY_BUDGET_EXHAUSTED")
        if baseline:
            limit = min(V23_ACCEPTED_SAFETY_CAPS[kind],
                        v23_operational_cap or V23_ACCEPTED_SAFETY_CAPS[kind])
        if kind in ("EVENT", "STATEMENT"):
            selected, trace = accept_decision_boundary_then_cap(
                spans, kind=kind, decision_threshold=source_policy.threshold(kind),
                boundary_threshold=source_policy.boundary_threshold(kind), limit=limit,
                decision_score=lambda row: row.extraction_score,
                boundary_score=lambda row: row.boundary_fitness_score,
                rank_key=lambda row: (-row.extraction_score, row.start, row.end, row.label or ""),
                output_key=lambda row: (row.start, row.end, row.label or ""))
            return selected, (replace(trace, budget_reason=(
                "OPERATIONAL_CAP_EXHAUSTED" if v23_operational_cap is not None and
                v23_operational_cap < V23_ACCEPTED_SAFETY_CAPS[kind] else
                "SAFETY_BUDGET_EXHAUSTED"))
                              if baseline else trace)
        selected, trace = accept_then_cap(
            spans, lane=kind, threshold=source_policy.threshold(kind), limit=limit,
            score=lambda row: row.extraction_score,
            rank_key=lambda row: (-row.extraction_score, row.start, row.end, row.label or ""),
            output_key=lambda row: (row.start, row.end, row.label or ""))
        return selected, (replace(trace, budget_reason=(
            "OPERATIONAL_CAP_EXHAUSTED" if v23_operational_cap is not None and
            v23_operational_cap < V23_ACCEPTED_SAFETY_CAPS[kind] else
            "SAFETY_BUDGET_EXHAUSTED"))
                          if baseline else trace)
    if acceptance.mode == "LEGACY_DIAGNOSTIC":
        selected = _bounded(spans, limit)
        return selected, AcceptanceTrace(
            kind, len(spans), len(spans), len(selected), 0, len(spans) - len(selected),
            rejection_reason="LEGACY_CAP_ONLY")
    if kind in ("EVENT", "STATEMENT"):
        return accept_decision_boundary_then_cap(
            spans, kind=kind, decision_threshold=acceptance.threshold(kind),
            boundary_threshold=acceptance.boundary_threshold(kind), limit=limit,
            decision_score=lambda row: row.extraction_score,
            boundary_score=lambda row: row.boundary_fitness_score,
            rank_key=lambda row: (-row.extraction_score, row.start, row.end, row.label or ""),
            output_key=lambda row: (row.start, row.end, row.label or ""))
    return accept_then_cap(
        spans, lane=kind, threshold=acceptance.threshold(kind), limit=limit,
        score=lambda row: row.extraction_score,
        rank_key=lambda row: (-row.extraction_score, row.start, row.end, row.label or ""),
        output_key=lambda row: (row.start, row.end, row.label or ""))


def _bounded(spans: tuple[DecodedSourceSpan, ...], limit: int) -> tuple[DecodedSourceSpan, ...]:
    """Compatibility helper for the pre-D4 generic source cap-only contract.

    Service/calibration paths call :func:`_accepted_spans` and cannot reach this
    helper without first selecting the explicit LEGACY_DIAGNOSTIC mode.
    """
    return cap_only(
        spans, limit=limit,
        rank_key=lambda row: (-row.score, row.start, row.end, row.label or ""),
        output_key=lambda row: (row.start, row.end, row.label or ""))


def _legacy_or_config_threshold(acceptance: AcceptanceConfig, lane: str) -> float:
    """Return the historical raw-zero gate only for lanes that had one pre-D4."""
    return 0.0 if acceptance.mode == "LEGACY_DIAGNOSTIC" else acceptance.threshold(lane)


@dataclass(frozen=True, slots=True)
class RoleCandidateSelection:
    spans: tuple[DecodedSourceSpan, ...]
    input_count: int
    valid_count: int
    invalid_count: int
    duplicates_removed: int
    dropped_below_threshold: int
    dropped_by_k: int
    overlap_ambiguous_pairs: int


def _overlap_pair_count(rows: Sequence[DecodedSourceSpan]) -> int:
    """Count exact interval overlaps without materializing every pair."""
    active_ends: list[int] = []
    count = 0
    for row in sorted(rows, key=lambda item: (item.start, item.end)):
        while active_ends and active_ends[0] <= row.start:
            heapq.heappop(active_ends)
        count += len(active_ends)
        heapq.heappush(active_ends, row.end)
    return count


def _pair_route_record(route: RoutedPairs, *, fine_scored: int) -> dict[str, Any]:
    """Keep retrieval provenance separate from fine acceptance diagnostics."""
    if (len(route.pairs) != fine_scored or not route.records_materialized):
        raise ValueError("V23 selected pair count differs from fine scorer input")
    return {"policy_id": route.policy_id, "policy_sha256": route.policy_sha256,
            "source_inventory_lineage": route.source_inventory_lineage,
            "visited": route.visited, "selected": len(route.pairs),
            "fine_scored": fine_scored,
            "query_count": route.query_count,
            "retrieved_candidate_mentions": route.retrieved_candidate_mentions,
            "primary_candidate_mentions": route.primary_candidate_mentions,
            "naive_pairs": route.naive_pair_count,
            "budget_exhausted_queries": route.budget_exhausted_queries,
            "missing_pair_status": route.missing_pair_status,
            "rescue_status": route.rescue_status,
            "shadow_reference_policy_id": route.shadow_reference_policy_id,
            "selected_pairs": route.records}


def _select_role_fillers(spans: tuple[DecodedSourceSpan, ...], *, role: str,
                         content: str, limit: int | None,
                         accept_threshold: float | None = 0.0,
                         include_diagnostics: bool = True) -> RoleCandidateSelection:
    """Validate, deduplicate, accept, then cap one Event×role by raw extraction score."""
    if role not in ("ACTOR", "TARGET", "PLACE") or (limit is not None and limit <= 0):
        raise ValueError("known participant role and positive forwarding bound are required")
    if accept_threshold is not None and not math.isfinite(accept_threshold):
        raise ValueError("participant raw-score acceptance threshold must be finite")
    valid = [row for row in spans
             if row.kind == "PARTICIPANT" and row.label == role and
             math.isfinite(row.extraction_score) and
             0 <= row.start < row.end <= len(content) and
             content[row.start:row.end] == row.text]
    deduplicated: dict[tuple[int, int], DecodedSourceSpan] = {}
    for row in valid:
        key = (row.start, row.end)
        old = deduplicated.get(key)
        if old is None:
            deduplicated[key] = row
            continue
        winner, other = (row, old) if row.extraction_score > old.extraction_score else (old, row)
        provenance = tuple(dict.fromkeys(
            (winner.provenance_windows or ((winner.start_window_id, winner.end_window_id),)) +
            (other.provenance_windows or ((other.start_window_id, other.end_window_id),))))
        deduplicated[key] = replace(winner, provenance_windows=provenance)
    candidates = tuple(deduplicated.values())
    overlap_pairs = _overlap_pair_count(candidates) if include_diagnostics else 0
    accepted = tuple(row for row in candidates
                     if accept_threshold is None or row.extraction_score >= accept_threshold)
    ranked = sorted(accepted, key=lambda row: (-row.extraction_score, row.start, row.end))
    forwarded = tuple(sorted(ranked if limit is None else ranked[:limit],
                             key=lambda row: (row.start, row.end)))
    return RoleCandidateSelection(
        forwarded, len(spans), len(valid), len(spans) - len(valid),
        len(valid) - len(candidates), len(candidates) - len(accepted),
        max(0, len(accepted) - (limit if limit is not None else len(accepted))), overlap_pairs)


def _span_id(prefix: str, span: DecodedSourceSpan) -> str:
    return f"{prefix}:{span.start}:{span.end}:{span.label or ''}"


def _storage_census(*tensors: torch.Tensor | None) -> dict[str, int]:
    """Count unique backing storage in one live owner without exporting pointers."""
    live = [row for row in tensors if row is not None]
    storage = {row.untyped_storage().data_ptr(): row.untyped_storage().nbytes()
               for row in live if row.numel()}
    return {"tensor_views": len(live), "unique_storage_count": len(storage),
            "unique_storage_bytes": sum(storage.values())}


def _stage_latency_ms(points: Sequence[float], *, primary_before_relation: bool = False
                      ) -> dict[str, float]:
    """Name stage boundaries in their actual execution order."""
    names = ("source_backbone_shared", "source_extraction", "entity_resolution",
             "time_attachment", "event_identity") + (
                 ("primary", "relations") if primary_before_relation else
                 ("relations", "primary")) + ("public_projection",)
    if len(points) != len(names) + 1:
        raise ValueError("runtime stage timing boundaries differ")
    return {name: round((end - start) * 1000, 3)
            for name, start, end in zip(names, points, points[1:])}


def _score_public_relevant_relations(*, core, final, closure,
                                     statement_states, statement_spans,
                                     base: PublicBaseSelection,
                                     about_route, causes_route,
                                     max_pairs: int, chunk_size: int,
                                     about_threshold: float, causes_threshold: float,
                                     legacy_prefix_fallback: bool
                                     ) -> tuple[RelationDecode, PublicSelection]:
    """Score CAUSES discovery, then only relations surviving final PUBLIC selection.

    Both passes intersect the original route inside score_final_relations. Discovery
    pairs already scored are reused when they survive; the fine head sees each pair
    at most once in this PUBLIC-only path. Full offscreen relation diagnostics remain
    in analyze(); PUBLIC projection only sees materialized accepted facts.
    """
    shared = dict(core=core, final=final, closure=closure,
                  statement_states=statement_states, statement_spans=statement_spans,
                  max_pairs=max_pairs, chunk_size=chunk_size, score_threshold=None,
                  about_threshold=about_threshold, causes_threshold=causes_threshold,
                  about_route=about_route, causes_route=causes_route,
                  legacy_prefix_fallback=legacy_prefix_fallback,
                  include_diagnostics=False)
    discovery_pairs = causes_discovery_pairs(base)
    discovery = score_final_relations(
        **shared, allowed_about_pairs=frozenset(),
        allowed_causes_pairs=discovery_pairs)
    selection = complete_public_selection(
        base=base, accepted_relations=discovery.facts)
    about_pairs, causes_pairs = public_relation_pairs(selection)
    materialized = score_final_relations(
        **shared, allowed_about_pairs=about_pairs,
        allowed_causes_pairs=causes_pairs - discovery_pairs)
    accepted_causes = [row for row in discovery.facts
                       if (row.source_id, row.target_id) in causes_pairs]
    accepted_causes.extend(row for row in materialized.facts
                           if row.relation == "CAUSES")
    if causes_route is not None:
        original_order = {pair: index for index, pair in enumerate(causes_route.pairs)}
        accepted_causes.sort(key=lambda row: original_order[(row.source_id, row.target_id)])
    else:
        cluster_order = {row.local_id: index for index, row in enumerate(closure.events)}
        n = len(cluster_order)
        accepted_causes.sort(key=lambda row: (
            cluster_order[row.source_id] * (n - 1) + cluster_order[row.target_id]
            - (cluster_order[row.target_id] > cluster_order[row.source_id])))
    facts = tuple(row for row in materialized.facts if row.relation == "ABOUT") + tuple(accepted_causes)
    scored_about = materialized.scored_about
    scored_causes = discovery.scored_causes + materialized.scored_causes
    return RelationDecode(
        facts, materialized.eligible_about, materialized.eligible_causes,
        scored_about, scored_causes,
        scored_about < materialized.eligible_about or
        scored_causes < materialized.eligible_causes), selection


def _entity_identity_prefix(result) -> dict[str, Any]:
    """Project the closure before Role/ASSERTOR decisions alter its members."""
    closure = result.preliminary_closure
    if closure is None:
        raise RuntimeError("Entity identity prefix was not captured")
    candidates = result.mention_universe.candidates
    pair_indices = (result.entity_pair_route.pairs if result.entity_pair_route is not None
                    else tuple((left, right) for left in range(len(candidates))
                               for right in range(left + 1, len(candidates))))
    return {
        "candidates": [{"id": row.candidate_id, "start": row.start,
                        "end": row.end, "text": row.text,
                        "entity_type": row.entity_type} for row in candidates],
        "pairs": [[candidates[left].candidate_id, candidates[right].candidate_id]
                  for left, right in pair_indices],
        "candidate_to_entity": dict(closure.candidate_to_entity),
        "entities": [{"id": row.local_id,
                      "representative_id": row.representative_candidate_id,
                      "members": list(row.candidate_ids), "start": row.start,
                      "end": row.end, "entity_type": row.entity_type}
                     for row in closure.entities],
        "accepted_pairs": result.accepted_coreference_pairs,
        "rejected_pairs": result.rejected_coreference_pairs,
    }


def _entity_resolution_prefix(result) -> dict[str, Any]:
    closure = result.closure
    return {
        "identity": _entity_identity_prefix(result),
        "candidate_to_entity": dict(closure.candidate_to_entity),
        "entities": [{"id": row.local_id,
                      "representative_id": row.representative_candidate_id,
                      "members": list(row.candidate_ids), "start": row.start,
                      "end": row.end, "entity_type": row.entity_type}
                     for row in closure.entities],
        "endpoints": [{"id": row.evidence_id, "role": row.role,
                       "owner_id": row.owner_id, "entity_id": row.local_entity_id,
                       "start": row.start, "end": row.end, "status": row.status}
                      for row in closure.endpoints],
        "assertor_options": list(result.assertor_option_routes),
    }


class V3ServingWorker:
    """One eval worker; a semaphore keeps request leases from overlapping on shared modules."""

    def __init__(self, core: V3Core, backbone: torch.nn.Module, tokenizer: Any,
                 tokenizer_sha256: str, *, budget: ServingBudget = ServingBudget(),
                 acceptance: AcceptanceConfig | None = None,
                 source_policy: SourceFunnelPolicy | None = None,
                 checkpoint_sha256: str = "0" * 64,
                 calibration_artifact: Mapping[str, Any] | None = None,
                 producer_version: str = "V3_FRESH_SMOKE_DIAGNOSTIC",
                 frozen_feature_cache: RunLocalFrozenFeatureCache | None = None,
                 frozen_feature_cache_scope: str = "serving",
                 entity_pair_policy: EntityPairPolicy | None = None,
                 participant_salience_mode: str = "SOURCE_SCORE",
                 relation_routing_artifact: PredictedRelationRoutingArtifact | None = None,
                 allow_all_pair_shadow_reference: bool = False,
                 primary_training_provenance: PrimaryTrainingProvenance | None = None) -> None:
        core.require_full_model()
        if tokenizer_sha256 != core.config.tokenizer_sha256 or any(
                parameter.requires_grad for parameter in backbone.parameters()):
            raise ValueError("serving requires pinned tokenizer and frozen backbone")
        self.core = core.eval()
        self.backbone = backbone.eval()
        core_devices = {parameter.device for parameter in core.parameters()}
        backbone_devices = {parameter.device for parameter in backbone.parameters()}
        if len(core_devices) != 1 or len(backbone_devices) != 1 or core_devices != backbone_devices:
            raise ValueError("serving core and backbone must share one execution device")
        self.device = next(iter(core_devices))
        self.layout_builder = LayoutBuilder(tokenizer, tokenizer_sha256=tokenizer_sha256)
        if not isinstance(frozen_feature_cache_scope, str) or not frozen_feature_cache_scope:
            raise ValueError("frozen feature cache scope must be non-empty")
        self.tokenizer_sha256 = tokenizer_sha256
        self.frozen_feature_cache = frozen_feature_cache
        self.frozen_feature_cache_scope = frozen_feature_cache_scope
        self.frozen_features = FrozenBackboneFeatureBuilder(
            self.backbone, cache=frozen_feature_cache)
        self.pad_token_id = tokenizer.pad_token_id
        self.budget = budget
        if budget.v23_operational_caps is not None and (
                source_policy is None or
                source_policy.retrieval.candidate_profile != "V23_BASELINE"):
            raise ValueError("V23 operational caps require a V23 source policy")
        if source_policy is not None:
            if acceptance is None:
                raise ValueError("source-policy caller must choose downstream acceptance explicitly")
            if source_policy.checkpoint_sha256 != checkpoint_sha256:
                raise ValueError("source-policy checkpoint SHA mismatch")
            source_policy.validate_budget(budget)
        self.source_policy = source_policy
        self.v23_pair_policies = (IntegratedBoundedPolicies.from_root()
                                  if source_policy is not None and
                                  source_policy.retrieval.candidate_profile == "V23_BASELINE"
                                  else None)
        if entity_pair_policy is not None and self.v23_pair_policies is None:
            raise ValueError("Entity blocking policy requires V23_BASELINE source profile")
        if self.v23_pair_policies is not None and (
                (entity_pair_policy is None) != allow_all_pair_shadow_reference):
            raise ValueError("V23 Entity identity requires a policy or explicit all-pair shadow")
        if participant_salience_mode != "SOURCE_SCORE":
            raise ValueError("Participant salience mode was retired with role_entity resolution")
        self.v23_entity_pair_policy = entity_pair_policy
        self.v23_all_pair_shadow_reference = allow_all_pair_shadow_reference
        if relation_routing_artifact is not None:
            if (self.v23_pair_policies is None or entity_pair_policy is None or
                    source_policy is None or
                    relation_routing_artifact.checkpoint_sha256 != checkpoint_sha256 or
                    relation_routing_artifact.source_policy_sha256 != source_policy.policy_sha256 or
                    relation_routing_artifact.source_acceptance_sha256 !=
                    source_policy.acceptance_sha256 or
                    relation_routing_artifact.entity_identity_policy_sha256 !=
                    identity_policy_sha256("ENTITY", entity_pair_policy.sha256) or
                    relation_routing_artifact.event_identity_policy_sha256 !=
                    identity_policy_sha256(
                        "EVENT", self.v23_pair_policies.config_sha256)):
                raise ValueError("V23 relation routing artifact/source identity binding differs")
        self.v23_relation_routing_artifact = relation_routing_artifact
        self.acceptance = acceptance or AcceptanceConfig.legacy_diagnostic(checkpoint_sha256)
        self.acceptance.validate_runtime(
            checkpoint_sha256=checkpoint_sha256,
            score_contract_version=SCORE_CONTRACT_VERSION,
            calibration_artifact=calibration_artifact)
        if (primary_training_provenance is not None and
                primary_training_provenance.checkpoint_sha256 != checkpoint_sha256):
            raise ValueError("Primary training provenance/checkpoint SHA mismatch")
        self.primary_training_provenance = primary_training_provenance
        self.checkpoint_sha256 = checkpoint_sha256
        self.producer_version = producer_version
        self._request_slot = BoundedSemaphore(1)

    @torch.no_grad()
    def analyze(self, *, article_id: str, content: str, title: str = "",
                article_version_id: str | None = None,
                published_at: str | None = None,
                enable_primary: bool = True,
                relative_month_contexts: Sequence[RelativeMonthContextBinding] = ()) -> ServingResult:
        """Run one predicted request, then return only scalar PUBLIC graph and audit."""
        digest = sha256(content.encode("utf-8")).hexdigest()
        raw = RawArticle(article_id, article_version_id or f"{article_id}:{digest[:16]}",
                         content, digest, published_at)
        with self._request_slot:
            return self._analyze_owned(
                raw, title=title, enable_primary=enable_primary,
                relative_month_contexts=relative_month_contexts)

    @torch.no_grad()
    def analyze_public(self, *, article_id: str, content: str, title: str = "",
                       article_version_id: str | None = None,
                       published_at: str | None = None,
                       enable_primary: bool = True,
                       relative_month_contexts: Sequence[RelativeMonthContextBinding] = ()
                       ) -> dict[str, Any]:
        """Run the validated predicted graph without diagnostic carriers."""
        digest = sha256(content.encode("utf-8")).hexdigest()
        raw = RawArticle(article_id, article_version_id or f"{article_id}:{digest[:16]}",
                         content, digest, published_at)
        with self._request_slot:
            result = self._analyze_owned(
                raw, title=title, enable_primary=enable_primary,
                relative_month_contexts=relative_month_contexts,
                audit_enabled=False)
        if not isinstance(result, dict):
            raise AssertionError("PUBLIC-only execution returned diagnostics")
        return result

    @torch.no_grad()
    def analyze_public_profiled(self, *, article_id: str, content: str,
                                title: str = "", article_version_id: str | None = None,
                                published_at: str | None = None,
                                enable_primary: bool = True,
                                relative_month_contexts: Sequence[RelativeMonthContextBinding] = ()
                                ) -> tuple[dict[str, Any], dict[str, float]]:
        """Explicit diagnostic timing of the actual PUBLIC-only path.

        The timing map is returned separately and never projected into PUBLIC.
        This method does not select thresholds or evaluate Gold.
        """
        digest = sha256(content.encode("utf-8")).hexdigest()
        raw = RawArticle(article_id,
                         article_version_id or f"{article_id}:{digest[:16]}",
                         content, digest, published_at)
        timing: dict[str, float] = {}
        with self._request_slot:
            result = self._analyze_owned(raw, title=title,
                                         enable_primary=enable_primary,
                                         relative_month_contexts=relative_month_contexts,
                                         audit_enabled=False, profile_sink=timing)
        if not isinstance(result, dict) or "elapsed_ms" not in timing:
            raise AssertionError("PUBLIC-only profile did not complete")
        return result, timing

    @torch.no_grad()
    def analyze_source_funnel(self, *, article_id: str, content: str,
                              article_version_id: str | None = None,
                              published_at: str | None = None,
                              include_candidate_diagnostics: bool = False) -> SourceFunnelResult:
        """Run the same source path as ``analyze`` and stop before downstream scoring."""
        if self.source_policy is None:
            raise ValueError("predicted source replay requires an explicit source policy")
        digest = sha256(content.encode("utf-8")).hexdigest()
        raw = RawArticle(article_id, article_version_id or f"{article_id}:{digest[:16]}",
                         content, digest, published_at)
        with self._request_slot:
            result = self._analyze_owned(raw, title="", enable_primary=False,
                                         source_only=True,
                                         include_candidate_diagnostics=
                                         include_candidate_diagnostics)
        if not isinstance(result, SourceFunnelResult):
            raise AssertionError("source-only execution returned a full serving result")
        return result

    @torch.no_grad()
    def analyze_until(self, *, phase: str, article_id: str, content: str,
                      title: str = "", article_version_id: str | None = None,
                      published_at: str | None = None,
                      relative_month_contexts: Sequence[RelativeMonthContextBinding] = ()) -> PhasePrefixResult:
        """Stop at a real predicted stage; Phase 2 exposes source only for now."""
        if phase not in ("entity_role_time_attribution_sources", "entity_identity",
                         "entity_role_time_attribution", "event_identity"):
            raise ValueError("unknown or full-graph phase prefix")
        digest = sha256(content.encode("utf-8")).hexdigest()
        raw = RawArticle(article_id, article_version_id or f"{article_id}:{digest[:16]}",
                         content, digest, published_at)
        with self._request_slot:
            result = self._analyze_owned(
                raw, title=title, enable_primary=False,
                relative_month_contexts=relative_month_contexts,
                source_only=(phase == "entity_role_time_attribution_sources"),
                until_phase=phase)
        if isinstance(result, SourceFunnelResult):
            return PhasePrefixResult(phase, {
                "source": result.as_dict(),
                "complete_for_phase": False,
                "missing_consumers": ["ENTITY_COREFERENCE", "EVENT_TIME"],
            }, self.checkpoint_sha256)
        if not isinstance(result, PhasePrefixResult):
            raise AssertionError("phase prefix executed past its boundary")
        return result

    @torch.no_grad()
    def analyze_with_prefix_trace(self, *, article_id: str, content: str,
                                  title: str = "", article_version_id: str | None = None,
                                  published_at: str | None = None,
                                  relative_month_contexts: Sequence[RelativeMonthContextBinding] = ()) -> ServingResult:
        """Diagnostic full run with scalar snapshots; ordinary serving is unchanged."""
        digest = sha256(content.encode("utf-8")).hexdigest()
        raw = RawArticle(article_id, article_version_id or f"{article_id}:{digest[:16]}",
                         content, digest, published_at)
        prefixes: dict[str, dict[str, Any]] = {}
        with self._request_slot:
            result = self._analyze_owned(
                raw, title=title, enable_primary=True,
                relative_month_contexts=relative_month_contexts,
                prefix_trace=prefixes)
        if not isinstance(result, ServingResult):
            raise AssertionError("full prefix trace stopped early")
        return ServingResult(result.public, {**result.audit, "phase_prefixes": prefixes})

    def _analyze_owned(self, raw: RawArticle, *, title: str,
                       enable_primary: bool,
                       relative_month_contexts: Sequence[RelativeMonthContextBinding] = (),
                       source_only: bool = False,
                       until_phase: str | None = None,
                       prefix_trace: dict[str, dict[str, Any]] | None = None,
                       include_candidate_diagnostics: bool = False,
                       audit_enabled: bool = True,
                       profile_sink: dict[str, float] | None = None
                       ) -> ServingResult | SourceFunnelResult | PhasePrefixResult | dict[str, Any]:
        collect_diagnostics = (audit_enabled or source_only or until_phase is not None or
                               prefix_trace is not None)
        relative_month_context_by_span = index_relative_month_context_bindings(
            raw, relative_month_contexts)
        consumed_relative_month_contexts: set[tuple[int, int, str]] = set()
        start_clock = perf_counter()
        counts = {"backbone": 0, "dce": 0}
        handles = [self.backbone.register_forward_hook(
            lambda *_: counts.__setitem__("backbone", counts["backbone"] + 1)),
            self.core.document_context.register_forward_hook(
                lambda *_: counts.__setitem__("dce", counts["dce"] + 1))]
        shared = time_lease = member_lease = final = source_context = exact_feature_cache = None
        participant_stream = None
        stages: dict[str, int] = {}
        source_pairs: dict[str, dict[str, int]] = {}
        acceptance_trace: dict[str, dict[str, Any]] = {}
        pair_routing_audit: dict[str, dict[str, Any]] = {}
        source_candidates: dict[str, tuple[dict[str, Any], ...]] = {}
        source_selected: dict[str, tuple[dict[str, Any], ...]] = {}
        partial: list[str] = []
        storage: dict[str, dict[str, int]] = {}
        baseline = (self.source_policy is not None and
                    self.source_policy.retrieval.candidate_profile == "V23_BASELINE")
        try:
            layout = self.layout_builder.build(raw)
            windows = source_windows_from_layout(layout, pad_token_id=self.pad_token_id)
            cache_key = (None if self.frozen_feature_cache is None else
                         FrozenSourceViewKey.from_config(
                             raw, windows, backbone=self.core.config.backbone,
                             tokenizer_sha256=self.tokenizer_sha256,
                             dtype=self.core.config.dtype, source_view="all"))
            batch = windows.article_view(raw, view="all").to(self.device)
            backbone_output = self.frozen_features.build(
                batch, cache_key=cache_key, scope=self.frozen_feature_cache_scope)
            downstream_started = perf_counter()
            if set(backbone_output.hidden_by_layer) != {8, 10, 12}:
                raise ValueError("serving backbone captured nonselective layer set")
            capture = getattr(self.backbone, "required_layer_capture", None)
            if capture is not None and (capture.capture_hook_count != 3 or
                                        capture.current_context_tensor_count != 0):
                raise RuntimeError("pinned selective capture hooks or cleanup regressed")
            shared = self.core.forward_shared(batch, backbone_output)
            after_shared = perf_counter()
            if collect_diagnostics:
                storage["backbone_shared"] = _storage_census(
                    *(backbone_output.layer(layer) for layer in (8, 10, 12)),
                    shared.token_states, shared.sentence_states,
                    shared.document_state, shared.proposal_logits)
            shared_source = id(shared.token_states)
            source_context = source_decode_context(layout, shared, self.core)
            if baseline and not source_only and until_phase not in (
                    "entity_identity", "entity_role_time_attribution"):
                exact_feature_cache = RequestExactFeatureCache(
                    layout=layout, batch=batch, backbone=backbone_output,
                    shared=shared, core=self.core)
            operational = self.budget.operational_caps_for_v23() if baseline else None
            for kind, limit in (("EVENT", self.budget.max_events),
                                ("STATEMENT", self.budget.max_statements),
                                ("ENTITY", self.budget.max_entities),
                                ("TIME", self.budget.max_times),
                                ("TRIGGER", self.budget.max_triggers)):
                decoded = decode_source_spans(kind=kind, layout=layout, batch=batch,
                                              backbone=backbone_output, shared=shared,
                                              core=self.core, budget=self.budget.source,
                                              context=source_context,
                                              exact_feature_cache=exact_feature_cache,
                                              native_entity_retention_threshold=(
                                                  self.source_policy.threshold("ENTITY")
                                                  if baseline and kind == "ENTITY" and
                                                  exact_feature_cache is not None else None),
                                              native_time_retention_threshold=(
                                                  self.source_policy.threshold("TIME")
                                                  if baseline and kind == "TIME" and
                                                  exact_feature_cache is not None else None),
                                              retrieval=self.budget.retrieval_for(kind),
                                              endpoint_threshold=(self.source_policy.trigger_endpoint_threshold
                                                                  if self.source_policy is not None and
                                                                  kind == "TRIGGER" else None),
                                              v23_operational_expensive_cap=(
                                                  operational.expensive_for(kind)
                                                  if operational is not None else None))
                stages[kind] = shared_source
                selected_spans, gate = _accepted_spans(
                    decoded.spans, kind=kind, limit=limit, acceptance=self.acceptance,
                    source_policy=self.source_policy,
                    v23_operational_cap=(operational.accepted_for(kind)
                                         if operational is not None else None))
                if collect_diagnostics:
                    accepted_emergency_retained = min(
                        gate.accepted_before_budget, V23_ACCEPTED_SAFETY_CAPS[kind])
                    expensive_emergency_retained = min(
                        decoded.retrieval.union_deduplicated,
                        V23_EXPENSIVE_ARTICLE_SAFETY_CEILING.get(
                            kind, decoded.retrieval.union_deduplicated))
                    source_candidates[kind] = _source_candidate_records(
                        decoded.spans, selected_spans, kind=kind, policy=self.source_policy)
                    source_selected[kind] = tuple(_source_span_record(row) for row in selected_spans)
                    acceptance_trace[kind] = gate.as_dict()
                    source_pairs[kind] = {"eligible": decoded.eligible_pairs,
                                          "scored": decoded.scored_pairs,
                                          "retained": len(selected_spans),
                                          **({"accepted_safety_budget": _safety_budget_record(
                                                  gate.accepted_before_budget,
                                                  accepted_emergency_retained),
                                              "accepted_operational_budget": _operational_budget_record(
                                                  accepted_emergency_retained,
                                                  gate.accepted_count,
                                                  operational.accepted_for(kind)
                                                  if operational is not None else None)}
                                             if baseline else {}),
                                          **({"expensive_safety_budget": _safety_budget_record(
                                                  decoded.retrieval.union_deduplicated,
                                                  expensive_emergency_retained),
                                              "expensive_operational_budget": _operational_budget_record(
                                                  expensive_emergency_retained,
                                                  decoded.retrieval.scored_candidates,
                                                  operational.expensive_for(kind)
                                                  if operational is not None else None)}
                                             if baseline and kind in ("ENTITY", "TIME") else {}),
                                          **decoded.retrieval.as_dict(
                                              final_cap_count=len(selected_spans)),
                                          **{f"partial:{cause}": value
                                             for cause, value in decoded.partial_causes}}
                if decoded.partial or gate.budget_truncated_count:
                    partial.append(kind)
                if kind == "EVENT":
                    event_spans = selected_spans
                elif kind == "STATEMENT":
                    statement_spans = selected_spans
                elif kind == "ENTITY":
                    entity_spans = selected_spans
                    if exact_feature_cache is not None:
                        exact_feature_cache.retain_native_entity_coordinates(
                            {(row.start, row.end) for row in selected_spans})
                elif kind == "TIME":
                    time_spans = selected_spans
                    if exact_feature_cache is not None:
                        exact_feature_cache.retain_native_coordinates(
                            "TIME", {(row.start, row.end) for row in selected_spans})
                else:
                    trigger_spans = selected_spans
            source_context.release_generic_endpoints()

            contained = (attach_optional_triggers(event_spans, trigger_spans) if baseline else
                         contain_accepted_events(event_spans, trigger_spans))
            events: dict[str, tuple[DecodedSourceSpan, DecodedSourceSpan | None]] = {
                _span_id("EM", span): (span, trigger) for span, trigger in contained}
            if not baseline and len(contained) != len(event_spans):
                partial.append("EVENT_TRIGGER_MISSING")
            statements = {_span_id("ST", span): span for span in statement_spans}

            statement_states: dict[str, torch.Tensor] = {}
            if statements:
                aligned = [layout.align({"start": span.start, "end": span.end, "text": span.text})
                           for span in statements.values()]
                features = self.core.exact_source_span(
                    layout=layout, batch=batch, backbone=backbone_output,
                    token_states=shared.token_states, sentence_states=shared.sentence_states,
                    document_state=shared.document_state, candidate_encoder=self.core.candidate_span,
                    rows=[(row, "STATEMENT") for row in aligned])
                statement_states = {sid: features.states[index]
                                    for index, sid in enumerate(statements)}
                features = None
                stages["STATEMENT_FEATURE"] = shared_source

            assertors: dict[str, DecodedSourceSpan] = {}
            assertor_reasons: dict[str, int] = {}
            assertor_source_proposed = 0
            assertor_source_pairs_scored = 0
            assertor_bridge_states = (bridge_token_states(
                layout, shared, bridge_positions=source_context.bridge_positions)
                if statements else None)
            if baseline and statements:
                assertor_outcomes = decode_assertor_sources(
                    statements=[(sid, layout.align({
                        "start": span.start, "end": span.end, "text": span.text}),
                        statement_states[sid]) for sid, span in statements.items()],
                    layout=layout, batch=batch, backbone=backbone_output,
                    shared=shared, core=self.core,
                    bridge_states=assertor_bridge_states,
                    score_threshold=_legacy_or_config_threshold(
                        self.acceptance, "ASSERTOR_SOURCE"))
            else:
                assertor_outcomes = tuple(decode_assertor_source(
                    statement_id=sid, statement_alignment=layout.align({
                        "start": span.start, "end": span.end, "text": span.text}),
                    layout=layout, batch=batch, backbone=backbone_output, shared=shared,
                    core=self.core, statement_state=statement_states[sid],
                    bridge_states=assertor_bridge_states,
                    score_threshold=_legacy_or_config_threshold(
                        self.acceptance, "ASSERTOR_SOURCE"))
                    for sid, span in statements.items())
            assertor_winner_states = {}
            for outcome in assertor_outcomes:
                sid = outcome.statement_id
                if outcome.span is not None:
                    assertors[sid] = outcome.span
                    if (baseline and shared.token_states.device.type != "mps" and
                            outcome.winner_state is not None):
                        assertor_winner_states[sid] = outcome.winner_state
                elif collect_diagnostics and outcome.rejection_reason is not None:
                    assertor_reasons[outcome.rejection_reason] = (
                        assertor_reasons.get(outcome.rejection_reason, 0) + 1)
                if outcome.partial:
                    partial.append("ASSERTOR")
                if collect_diagnostics:
                    assertor_source_proposed += int(outcome.scored_pairs > 0)
                    assertor_source_pairs_scored += outcome.scored_pairs
            if collect_diagnostics:
                acceptance_trace["ASSERTOR_SOURCE"] = {
                    **AcceptanceTrace("ASSERTOR_SOURCE", len(statements), len(assertors),
                                      len(assertors), len(statements) - len(assertors), 0).as_dict(),
                    "rejection_reasons": assertor_reasons,
                }
            assertor_bridge_states = None
            stages["ASSERTOR"] = shared_source
            assertor_states: dict[str, torch.Tensor] = {}
            missing_assertor_states = [sid for sid in assertors
                                       if sid not in assertor_winner_states]
            if missing_assertor_states:
                aligned = [layout.align({"start": assertors[sid].start,
                                         "end": assertors[sid].end,
                                         "text": assertors[sid].text})
                           for sid in missing_assertor_states]
                features = self.core.exact_source_span(
                    layout=layout, batch=batch, backbone=backbone_output,
                    token_states=shared.token_states, sentence_states=shared.sentence_states,
                    document_state=shared.document_state, candidate_encoder=self.core.candidate_span,
                    rows=[(row, "STATEMENT") for row in aligned])
                assertor_states = {sid: features.states[index]
                                   for index, sid in enumerate(missing_assertor_states)}
                features = None
            assertor_states.update(assertor_winner_states)
            if collect_diagnostics:
                storage["statement_assertor"] = _storage_census(
                    *statement_states.values(), *assertor_states.values())

            role_evidence = []
            role_decision_confidence: dict[str, float] = {}
            participant_pairs = {"eligible": 0, "scored": 0, "retained": 0,
                                 "valid": 0, "invalid": 0, "duplicates_removed": 0,
                                 "dropped_below_threshold": 0, "dropped_by_k": 0,
                                 "overlap_ambiguous_pairs": 0}
            def participant_event_inputs():
                if not baseline:
                    for member_id, (event_span, _trigger) in events.items():
                        alignment = layout.align({"start": event_span.start,
                                                  "end": event_span.end,
                                                  "text": event_span.text})
                        state = event_source_state(
                            alignment=alignment, layout=layout, batch=batch,
                            backbone=backbone_output, shared=shared, core=self.core,
                            profile=(self.budget.retrieval.candidate_profile
                                     if self.budget.retrieval is not None else "V3_WINDOW"))
                        yield member_id, alignment, state, None
                    return
                event_iter = iter(events.items())
                while event_chunk := list(islice(event_iter, V23_PARTICIPANT_EVENT_CHUNK_SIZE)):
                    aligned = [(member_id, layout.align({
                        "start": event_span.start, "end": event_span.end,
                        "text": event_span.text}))
                        for member_id, (event_span, _trigger) in event_chunk]
                    states = precompute_v23_event_states(
                        layout=layout, batch=batch, backbone=backbone_output,
                        shared=shared, core=self.core, events=aligned,
                        event_chunk_size=V23_PARTICIPANT_EVENT_CHUNK_SIZE,
                        exact_feature_cache=exact_feature_cache)
                    inputs = [(member_id, alignment, states[member_id])
                              for member_id, alignment in aligned]
                    boundaries = precompute_v23_participant_boundaries(
                        layout=layout, batch=batch, shared=shared, core=self.core,
                        events=inputs,
                        event_chunk_size=V23_PARTICIPANT_EVENT_CHUNK_SIZE)
                    try:
                        for member_id, alignment, state in inputs:
                            yield member_id, alignment, state, boundaries[member_id]
                    finally:
                        # The next chunk must never retain this chunk's Event
                        # states, B2 endpoint rows, or alignment references.
                        inputs.clear()
                        boundaries.clear()
                        states.clear()
                        aligned.clear()
                        event_chunk.clear()
                        state = None
                        alignment = None

            participant_stream = participant_event_inputs()
            for member_id, alignment, event_state, participant_boundary in participant_stream:
                participant_views = (v23_participant_candidate_views(
                    layout=layout, boundary=participant_boundary,
                    endpoint_threshold=self.source_policy.participant_endpoint_threshold)
                    if baseline else None)
                for role in ("ACTOR", "TARGET", "PLACE"):
                    outcome = decode_source_spans(
                        kind="PARTICIPANT", layout=layout, batch=batch,
                        backbone=backbone_output, shared=shared, core=self.core,
                        budget=self.budget.participant, event_alignment=alignment, role=role,
                        context=source_context, event_state=event_state,
                        participant_boundary=participant_boundary,
                        participant_candidate_view=(participant_views[role]
                                                    if participant_views is not None else None),
                        exact_feature_cache=exact_feature_cache,
                        retrieval=(self.budget.retrieval
                                   if self.budget.retrieval is not None and
                                   self.budget.retrieval.candidate_profile == "V23_BASELINE"
                                   else None),
                        endpoint_threshold=(self.source_policy.participant_endpoint_threshold
                                            if self.source_policy is not None else None))
                    stages["PARTICIPANT"] = shared_source
                    participant_pairs["eligible"] += outcome.eligible_pairs
                    participant_pairs["scored"] += outcome.scored_pairs
                    if outcome.partial:
                        partial.append("PARTICIPANT")
                    selected = _select_role_fillers(
                        outcome.spans, role=role, content=raw.content,
                        limit=(self.source_policy.participant_role_forwarding_limit
                               if baseline else self.budget.max_role_fillers_per_event_role),
                        accept_threshold=(None if baseline else
                                          self.source_policy.participant_threshold
                                          if self.source_policy is not None else
                                          _legacy_or_config_threshold(
                                              self.acceptance, "PARTICIPANT")),
                        include_diagnostics=collect_diagnostics)
                    participant_key = f"{member_id}:{role}"
                    participant_threshold = (None if baseline else
                                             self.source_policy.participant_threshold
                                             if self.source_policy is not None else
                                             _legacy_or_config_threshold(
                                                 self.acceptance, "PARTICIPANT"))
                    if collect_diagnostics and include_candidate_diagnostics:
                        selected_keys = {(row.start, row.end) for row in selected.spans}
                        source_candidates[participant_key] = tuple({
                            **_source_span_record(row), "owner_event_id": member_id,
                            "role": role, "rank": rank,
                            "cap_survived": (row.start, row.end) in selected_keys,
                            "accepted": (participant_threshold is None or
                                         row.extraction_score >= participant_threshold),
                            "reason": ("SELECTED" if (row.start, row.end) in selected_keys else
                                       "BELOW_THRESHOLD" if participant_threshold is not None and
                                       row.extraction_score < participant_threshold
                                       else "BUDGET_OR_DUPLICATE_TRUNCATION"),
                        } for rank, row in enumerate(sorted(
                            outcome.spans,
                            key=lambda row: (-row.extraction_score, row.start, row.end)), 1))
                    selected_role_evidence = tuple(evidence_from_role_decode(
                        member_id, span, referential_state="PROPOSED")
                        for span in selected.spans)
                    for evidence_row, span in zip(selected_role_evidence, selected.spans):
                        probability = _native_decision_probability(
                            span, "participant_b2_boundary")
                        if probability is not None:
                            role_decision_confidence[evidence_row.evidence_id] = probability
                    if collect_diagnostics and baseline:
                        # Source replay needs coordinates and score, not the
                        # decoder's RouteCandidate/provenance object graph.
                        source_selected[participant_key] = tuple({
                            "kind": "PARTICIPANT", "label": row.role,
                            "start": row.start, "end": row.end, "text": row.text,
                            "decision_score": row.score,
                            "boundary_score": span.boundary_fitness_score,
                            "source_windows": [list(pair) for pair in row.source_windows],
                            "owner_event_id": row.owner_id, "role": row.role,
                        } for row, span in zip(selected_role_evidence, selected.spans))
                    elif collect_diagnostics:
                        source_selected[participant_key] = tuple(
                            {**_source_span_record(row), "owner_event_id": member_id,
                             "role": role} for row in selected.spans)
                    participant_pairs["retained"] += len(selected.spans)
                    participant_pairs["valid"] += selected.valid_count
                    participant_pairs["invalid"] += selected.invalid_count
                    participant_pairs["duplicates_removed"] += selected.duplicates_removed
                    participant_pairs["dropped_below_threshold"] += selected.dropped_below_threshold
                    participant_pairs["dropped_by_k"] += selected.dropped_by_k
                    participant_pairs["overlap_ambiguous_pairs"] += selected.overlap_ambiguous_pairs
                    if selected.invalid_count:
                        partial.append("PARTICIPANT_SOURCE_INVALID")
                    if selected.dropped_by_k:
                        partial.append("PARTICIPANT_ROLE_K")
                    role_evidence.extend(selected_role_evidence)
                if baseline:
                    # All three role decoders have consumed this Event's exact
                    # alignments. Keep the cache bounded by one Event, not the
                    # full article's Cartesian B2 inventory.
                    source_context.participant_alignments.clear()
                    source_context.participant_cells.clear()
                event_state = None
                participant_boundary = None
                outcome = None
                selected = None
            if collect_diagnostics:
                acceptance_trace["PARTICIPANT"] = AcceptanceTrace(
                    "PARTICIPANT", participant_pairs["valid"] - participant_pairs["duplicates_removed"],
                    participant_pairs["retained"] + participant_pairs["dropped_by_k"],
                    participant_pairs["retained"], participant_pairs["dropped_below_threshold"],
                    participant_pairs["dropped_by_k"]).as_dict()
            source_context.close()
            after_extraction = perf_counter()

            evidence = list(evidence_from_entity_decode(entity_spans)) + role_evidence + [
                evidence_from_assertor_decode(sid, span) for sid, span in assertors.items()]
            universe = build_unified_entity_mentions(raw, evidence)
            pre_budget_universe = universe
            if baseline:
                universe = cap_unified_entity_mentions(
                    universe, limit=V23_UNIFIED_ENTITY_SAFETY_CAP)
                if universe.status == "BOUNDED_PARTIAL":
                    partial.append("UNIFIED_ENTITY_SAFETY_BUDGET")
            source_funnel_result = None
            if collect_diagnostics:
                pre_budget_records = tuple(_entity_candidate_record(row)
                                           for row in pre_budget_universe.candidates)
                post_budget_records = tuple(_entity_candidate_record(row)
                                            for row in universe.candidates)
                source_funnel_result = SourceFunnelResult(
                    raw.article_id, raw.article_version_id, raw.content_sha256,
                    (self.source_policy.binding() if self.source_policy is not None else
                     {"mode": "LEGACY_OR_FULL_ACCEPTANCE", "checkpoint_sha256": self.checkpoint_sha256}),
                    source_selected, source_candidates,
                    {**source_pairs, "PARTICIPANT": participant_pairs,
                     "ASSERTOR_SOURCE": {"owner_count": len(statements),
                                          "proposed": assertor_source_proposed,
                                          "accepted": len(assertors),
                                          "scored_pairs": assertor_source_pairs_scored},
                     "UNIFIED_ENTITY_MENTIONS": {
                         "evidence": len(evidence),
                         "native": sum("NER" in row.origins for row in universe.candidates),
                         "role_only": sum(row.origins == ("ROLE",) for row in universe.candidates),
                         "mentions": len(universe.candidates),
                         "safety_budget": _safety_budget_record(
                             len(pre_budget_universe.candidates), len(universe.candidates))}},
                    tuple(events),
                    tuple({"evidence_id": row.evidence_id, "owner_id": row.owner_id,
                           "role": row.role, "start": row.start, "end": row.end,
                           "text": row.text} for row in role_evidence),
                    tuple({"statement_id": sid, **_source_span_record(span)}
                          for sid, span in assertors.items()),
                    tuple({"evidence_id": row.evidence_id, "origin": row.origin,
                           "owner_id": row.owner_id, "role": row.role,
                           "start": row.start, "end": row.end, "text": row.text,
                           "entity_type": row.entity_type,
                           "referential_state": row.referential_state,
                           "source_windows": [list(pair) for pair in row.source_windows]}
                          for row in evidence),
                    tuple(row.candidate_id for row in pre_budget_universe.candidates),
                    tuple(row.candidate_id for row in universe.candidates),
                    pre_budget_records, post_budget_records,
                    tuple(sorted(set(partial))), counts["backbone"], counts["dce"])
            source_prefix = (source_funnel_result.as_dict()
                             if source_funnel_result is not None and
                             (prefix_trace is not None or
                              until_phase in ("entity_identity",
                                              "entity_role_time_attribution",
                                              "event_identity")) else None)
            if prefix_trace is not None:
                prefix_trace["entity_role_time_attribution_sources"] = {
                    "source": source_prefix, "complete_for_phase": False,
                    "missing_consumers": ["ENTITY_COREFERENCE", "EVENT_TIME"]}
            if source_only:
                if source_funnel_result is None:
                    raise AssertionError("source replay lost its diagnostic carrier")
                if counts["backbone"] not in ({1} if self.frozen_feature_cache is None else {0, 1}) or counts["dce"] != 1:
                    raise RuntimeError("source replay duplicated backbone/DCE")
                return source_funnel_result
            legacy_entity_policy = self.acceptance.mode == "LEGACY_DIAGNOSTIC"
            entity_result = score_and_close_entity(
                universe=universe, layout=layout, batch=batch, backbone=backbone_output,
                shared=shared, core=self.core,
                statement_states=statement_states,
                assertor_states=assertor_states,
                assertor_resolution_threshold=_legacy_or_config_threshold(
                    self.acceptance, "ASSERTOR_ENTITY"),
                entity_coreference_margin=_legacy_or_config_threshold(
                    self.acceptance, "ENTITY_COREFERENCE"),
                entity_coreference_policy=("ARGMAX_CLASS_1" if legacy_entity_policy else
                                           "MARGIN_GTE"),
                pair_chunk_size=self.budget.pair_chunk_size,
                max_candidates=(V23_UNIFIED_ENTITY_SAFETY_CAP if baseline else
                                self.budget.max_entity_candidates),
                pair_policies=self.v23_pair_policies if baseline else None,
                entity_pair_policy=self.v23_entity_pair_policy if baseline else None,
                entity_all_pair_shadow_reference=(self.v23_all_pair_shadow_reference
                                                  if baseline else False),
                identity_only=(until_phase == "entity_identity"),
                include_diagnostics=collect_diagnostics,
                exact_feature_cache=exact_feature_cache,
                profile_sink=profile_sink)
            identity_prefix = ({"source": source_prefix,
                                "identity": _entity_identity_prefix(entity_result)}
                               if source_prefix is not None else None)
            if prefix_trace is not None:
                prefix_trace["entity_identity"] = identity_prefix
            if until_phase == "entity_identity":
                return PhasePrefixResult(until_phase, identity_prefix,
                                         self.checkpoint_sha256)
            resolution_prefix = ({**identity_prefix,
                                  "resolution": _entity_resolution_prefix(entity_result)}
                                 if identity_prefix is not None else None)
            if prefix_trace is not None:
                prefix_trace["entity_role_time_attribution"] = resolution_prefix
            if until_phase == "entity_role_time_attribution":
                return PhasePrefixResult(until_phase, resolution_prefix,
                                         self.checkpoint_sha256)
            if collect_diagnostics and baseline:
                if entity_result.entity_pair_route is not None:
                    pair_routing_audit["ENTITY_COREFERENCE"] = _pair_route_record(
                        entity_result.entity_pair_route,
                        fine_scored=entity_result.scored_coreference_pairs)
            entity_closure = entity_result.closure
            if any(row.entity_type not in ENTITY_TYPES for row in entity_closure.entities):
                raise ValueError("predicted LocalEntity lacks one canonical five-type value")
            stages["ENTITY_RESOLUTION"] = shared_source
            assertor_diagnostics = entity_result.resolution_diagnostics
            if collect_diagnostics:
                acceptance_trace["ASSERTOR_ENTITY"] = AcceptanceTrace(
                    "ASSERTOR_ENTITY", len(assertor_diagnostics),
                    sum(row.accepted for row in assertor_diagnostics),
                    sum(row.accepted for row in assertor_diagnostics),
                    sum(not row.accepted for row in assertor_diagnostics), 0).as_dict()
                acceptance_trace["ENTITY_COREFERENCE"] = AcceptanceTrace(
                    "ENTITY_COREFERENCE", entity_result.scored_coreference_pairs,
                    entity_result.accepted_coreference_pairs,
                    entity_result.accepted_coreference_pairs,
                    entity_result.rejected_coreference_pairs, 0).as_dict()
            after_entity = perf_counter()

            time_mentions = []
            routed_time_spans = []
            unresolved_time_dropped = 0
            for span in time_spans:
                context_key = (span.start, span.end, span.text)
                relative_month_context = relative_month_context_by_span.get(context_key)
                if relative_month_context is not None:
                    consumed_relative_month_contexts.add(context_key)
                value, normalization_reason = infer_source_time(
                    span.text, raw.published_at,
                    relative_month_context=relative_month_context)
                if baseline and value is None:
                    # V23 runtime keeps the accepted source trace, but an
                    # unresolved Time is not an Event-Time or PUBLIC candidate.
                    unresolved_time_dropped += 1
                    continue
                routed_time_spans.append(span)
                time_mentions.append(TimeMentionEvidence(
                    _span_id("TM", span), span.start, span.end, span.text, value,
                    "SOURCE_RULE" if value is not None else "UNRESOLVED",
                    relative_month_context=relative_month_context,
                    normalization_reason=normalization_reason))
            if baseline:
                time_spans = tuple(routed_time_spans)
            extra_rows = []
            def time_source_alignment(start: int, end: int, text: str):
                if raw.content[start:end] != text:
                    raise ValueError("Event-Time source text differs from exact coordinate")
                return layout.align_runtime(start, end)
            for mid, (_event, trigger) in events.items():
                if trigger is not None:
                    extra_rows.append(("TRIGGER:" + mid,
                                       time_source_alignment(trigger.start, trigger.end,
                                                             trigger.text),
                                       "TRIGGER"))
            for role in entity_closure.endpoints:
                if role.role != "ASSERTOR" and role.owner_id in events:
                    extra_rows.append(("ROLE:" + role.evidence_id,
                                       time_source_alignment(role.start, role.end,
                                                             role.text),
                                       "PARTICIPANT"))
            referenced_entity_ids = {
                role.local_entity_id for role in entity_closure.endpoints
                if role.role != "ASSERTOR" and role.owner_id in events
                and role.local_entity_id is not None
            }
            for entity in entity_closure.entities:
                if entity.local_id in referenced_entity_ids:
                    extra_rows.append(("ENTITY:" + entity.local_id,
                                       time_source_alignment(entity.start, entity.end,
                                                             entity.text),
                                       "ENTITY"))
            time_event_rows = [(mid, time_source_alignment(span.start, span.end,
                                                           span.text))
                               for mid, (span, _trigger) in events.items()]
            time_mention_rows = [(row.time_id, time_source_alignment(
                row.start, row.end, row.text))
                                 for row in time_mentions]
            direct_time_features = {}
            if exact_feature_cache is not None:
                for alignment, kind in (
                        [(alignment, "EVENT") for _, alignment in time_event_rows] +
                        [(alignment, "TIME") for _, alignment in time_mention_rows] +
                        [(alignment, kind) for _, alignment, kind in extra_rows]):
                    handoff = exact_feature_cache.direct_handoff(
                        layout=layout, batch=batch, backbone=backbone_output,
                        shared=shared, core=self.core,
                        alignment=alignment, kind=kind)
                    if handoff is not None:
                        direct_time_features[(kind, alignment.start, alignment.end)] = handoff
            time_lease = encode_event_time_features(
                layout=layout, batch=batch, backbone=backbone_output, shared=shared, core=self.core,
                events=time_event_rows,
                times=time_mention_rows,
                extra_rows=extra_rows, source_mode="PREDICTED",
                exact_feature_cache=exact_feature_cache,
                direct_features=direct_time_features)
            direct_time_features.clear()
            if collect_diagnostics:
                storage["event_time"] = _storage_census(
                    time_lease.event_states, time_lease.time_states, time_lease.document_state,
                    time_lease.original_sentence_states,
                    *(time_lease.extra_states or {}).values(),
                    *(time_lease.extra_residuals or {}).values(),
                    *(time_lease.extra_link_logits or {}).values())
            stages["EVENT_TIME_FEATURE"] = shared_source
            if exact_feature_cache is not None:
                exact_feature_cache.close()
            shared.close()
            if not shared.closed or time_lease.closed or time_lease.event_states is None:
                raise RuntimeError("source feature handoff released Event/Time before attachment")
            backbone_output = None
            batch = None
            # Source-valid normalization is the only emitted value. The untrained format/character
            # head is executed for diagnosis, but cannot invent precision or overwrite the source.
            normalization_checked = 0
            if collect_diagnostics and time_mentions:
                states = time_lease.time_states
                for index, row in enumerate(time_mentions):
                    if row.normalized_value is None:
                        continue
                    fmt, chars = self.core.task_modules["time_normalization"](
                        states[index:index + 1], length=len(row.normalized_value))
                    if not torch.isfinite(fmt).all() or not torch.isfinite(chars).all():
                        raise ValueError("nonfinite Time normalization prediction")
                    normalization_checked += 1
                    fmt = chars = None
                states = None
            time_route = None
            if baseline:
                if self.v23_pair_policies is None:
                    raise RuntimeError("v2.3 pair policy is absent")
                time_rows = (tuple((key, *span) for key, span in zip(
                    time_lease.event_ids, time_lease.event_spans)) +
                    tuple((key, *span) for key, span in zip(
                        time_lease.time_ids, time_lease.time_spans)))
                time_route = route_event_time(
                    article=raw, lease=time_lease,
                    sentence_spans=layout.sentence_spans,
                    time_scores={_span_id("TM", span): 1.0 / (
                        1.0 + math.exp(-max(-80.0, min(80.0, span.score))))
                        for span in time_spans},
                    policies=self.v23_pair_policies,
                    source_lineage=inventory_lineage(raw, time_rows),
                    include_diagnostics=collect_diagnostics)
            attachments = score_event_time(
                time_lease, core=self.core, content_length=len(raw.content),
                config=EventTimeDecodeConfig(max_pairs=self.budget.max_event_time_pairs,
                                             chunk_size=self.budget.pair_chunk_size,
                                             score_threshold=_legacy_or_config_threshold(
                                                 self.acceptance, "EVENT_TIME"),
                                             status=self.acceptance.mode),
                routed_pairs=time_route)
            if collect_diagnostics and time_route is not None:
                pair_routing_audit["EVENT_TIME"] = _pair_route_record(
                    time_route, fine_scored=attachments.scored_pairs)
            if collect_diagnostics:
                acceptance_trace["EVENT_TIME"] = AcceptanceTrace(
                    "EVENT_TIME", attachments.scored_pairs, len(attachments.attached_pairs),
                    len(attachments.attached_pairs),
                    attachments.scored_pairs - len(attachments.attached_pairs),
                    attachments.eligible_pairs - attachments.scored_pairs).as_dict()
            occurrences = close_time_occurrences(raw, time_mentions, attachments.attached_pairs)
            after_time = perf_counter()
            if attachments.partial:
                partial.append("EVENT_TIME")
            occurrence_by_evidence = {eid: row.local_id for row in occurrences
                                      for eid in row.evidence_ids}
            endpoints_by_owner: dict[str, list] = {}
            for endpoint in entity_closure.endpoints:
                if endpoint.role != "ASSERTOR":
                    endpoints_by_owner.setdefault(endpoint.owner_id, []).append(endpoint)
            members = []
            for mid, (span, trigger) in events.items():
                roles = tuple(MemberRoleFact(row.evidence_id, row.role, row.start, row.end,
                                             row.text, row.local_entity_id, row.status,
                                             row.source_score, row.source_windows)
                              for row in endpoints_by_owner.get(mid, ()))
                time_ids = tuple(sorted({occurrence_by_evidence[tid] for eid, tid in attachments.attached_pairs
                                         if eid == mid}))
                members.append(EventMember(mid, span.start, span.end, span.text,
                                           trigger.start if trigger is not None else None,
                                           trigger.end if trigger is not None else None,
                                           trigger.text if trigger is not None else None,
                                           roles, time_ids))
            member_lease = build_event_member_features(
                time_lease, members=members, occurrences=occurrences,
                provenance=EventFeatureProvenance("PREDICTED", "PREDICTED"))
            confidence_evidence = []
            for member_id, (_span, trigger) in events.items():
                if trigger is None:
                    continue
                probability = _native_decision_probability(trigger, "trigger_greedy_boundary")
                if probability is not None:
                    confidence_evidence.append(EventOptionalConfidenceEvidence(
                        member_id, "trigger", "TRIGGER:" + member_id, probability,
                        "V23_TRIGGER_GREEDY_BOUNDARY"))
            for member in members:
                for role in member.roles:
                    probability = role_decision_confidence.get(role.evidence_id)
                    if probability is not None:
                        confidence_evidence.append(EventOptionalConfidenceEvidence(
                            member.member_id, role.role.lower(), role.evidence_id,
                            probability, "V23_PARTICIPANT_B2_BOUNDARY"))
            candidates_by_id = universe.candidate_by_id()
            entity_type_probability: dict[str, float] = {}
            entity_native_member_count: dict[str, int] = {}
            for entity in entity_closure.entities:
                entity_native_member_count[entity.local_id] = sum(
                    "NER" in candidates_by_id[candidate_id].origins
                    for candidate_id in entity.candidate_ids)
                native_logits = [max(candidate.type_evidence)
                                 for candidate_id in entity.candidate_ids
                                 if (candidate := candidates_by_id.get(candidate_id)) is not None
                                 and "NER" in candidate.origins
                                 and len(candidate.type_evidence) == len(ENTITY_TYPES)]
                if native_logits:
                    score = max(native_logits)
                    if not math.isfinite(score):
                        raise ValueError("Native Entity type confidence is non-finite")
                    entity_type_probability[entity.local_id] = 1.0 / (
                        1.0 + math.exp(-max(-80.0, min(80.0, score))))
            for member in members:
                for entity_id in sorted({role.entity_id for role in member.roles
                                         if role.entity_id is not None}):
                    probability = entity_type_probability.get(entity_id)
                    if probability is not None:
                        confidence_evidence.append(EventOptionalConfidenceEvidence(
                            member.member_id, "entity", entity_id, probability,
                            "V23_ENTITY_NATIVE_TYPE"))
            time_attachment_logits: dict[tuple[str, str], float] = {}
            for member_id, evidence_id, logit in attachments.attached_pair_logits:
                occurrence_id = occurrence_by_evidence[evidence_id]
                key = member_id, occurrence_id
                time_attachment_logits[key] = max(
                    logit, time_attachment_logits.get(key, float("-inf")))
            for (member_id, occurrence_id), logit in time_attachment_logits.items():
                confidence_evidence.append(EventOptionalConfidenceEvidence(
                    member_id, "time", occurrence_id,
                    1.0 / (1.0 + math.exp(-max(-80.0, min(80.0, logit)))),
                    "V23_EVENT_TIME_ATTACHMENT"))
            occurrences_by_id = {row.local_id: row for row in occurrences}
            event_optional_source_counts = tuple(
                (int(member.trigger_text is not None),
                 *(sum(row.role == role for row in member.roles)
                   for role in ("ACTOR", "TARGET", "PLACE")),
                 sum(entity_native_member_count.get(entity_id, 0)
                     for entity_id in {row.entity_id for row in member.roles
                                       if row.entity_id is not None}),
                 sum(len(occurrences_by_id[time_id].evidence_ids)
                     for time_id in member.time_ids))
                for member in members)
            event_bundle = build_event_pair_feature_bundle(
                member_lease, confidence_evidence=tuple(confidence_evidence),
                optional_source_counts=event_optional_source_counts)
            member_lease.set_encoded_event_features(
                self.core.task_modules["event_coreference"].encode_events(event_bundle),
                member_ids=tuple(member.member_id for member in members))
            if collect_diagnostics:
                storage["event_member"] = _storage_census(
                    member_lease.channel_sums, member_lease.channel_counts,
                    member_lease.document_state,
                    member_lease.original_sentence_states,
                    *(member_lease.role_states or {}).values())
            time_lease.close()
            if not time_lease.closed or member_lease.closed or member_lease.channel_sums is None:
                raise RuntimeError("Event member feature handoff released before coreference")
            event_route = None
            if baseline:
                event_route = route_event_coreference(
                    article=raw, members=members, occurrences=occurrences,
                    sentence_spans=layout.sentence_spans,
                    policies=self.v23_pair_policies,
                    source_lineage=inventory_lineage(
                        raw, tuple((row.member_id, row.start, row.end)
                                   for row in members)))
            identity = score_event_identity(
                raw, member_lease, core=self.core,
                config=EventIdentityDecodeConfig(
                    max_pairs=self.budget.max_event_coreference_pairs,
                    chunk_size=self.budget.pair_chunk_size,
                    margin_threshold=_legacy_or_config_threshold(
                        self.acceptance, "EVENT_COREFERENCE"),
                    status=self.acceptance.mode),
                routed_pairs=event_route, occurrences=occurrences,
                sentence_spans=layout.sentence_spans, pair_bundle=event_bundle,
                collect_raw_pair_margins=collect_diagnostics)
            # Pair-only means and sentence context are no longer needed by the
            # final cluster consumers; the lease retains only the encoded rows.
            del event_bundle
            if collect_diagnostics and event_route is not None:
                pair_routing_audit["EVENT_COREFERENCE"] = _pair_route_record(
                    event_route, fine_scored=identity.scored_pairs)
            if identity.partial:
                partial.append("EVENT_IDENTITY")
            if resolution_prefix is not None:
                event_pair_indices = (event_route.pairs if event_route is not None else
                                      tuple((left, right) for left in range(len(members))
                                            for right in range(left + 1, len(members))))
                event_prefix = {**resolution_prefix,
                            "time": {
                                "mentions": [{"id": row.time_id, "start": row.start,
                                              "end": row.end, "value": row.normalized_value}
                                             for row in time_mentions],
                                "attached_pairs": [list(pair)
                                                   for pair in attachments.attached_pairs],
                                "occurrences": [{"id": row.local_id,
                                                 "evidence_ids": list(row.evidence_ids),
                                                 "start": row.start, "end": row.end}
                                                for row in occurrences]},
                            "event_identity": {
                                "members": [{"id": row.member_id, "start": row.start,
                                             "end": row.end,
                                             "role_ids": [role.evidence_id for role in row.roles],
                                             "time_ids": list(row.time_ids)}
                                            for row in members],
                                "pairs": [[members[left].member_id,
                                           members[right].member_id]
                                          for left, right in event_pair_indices],
                                "member_to_cluster": dict(identity.closure.member_to_cluster),
                                "clusters": [{"id": row.local_id,
                                              "members": list(row.member_ids),
                                              "representative_id": row.representative_member_id}
                                             for row in identity.closure.events],
                                "accepted_pairs": identity.accepted_pairs,
                                "rejected_pairs": identity.rejected_pairs,
                                "raw_pair_margins": [
                                    {"left_id": left, "right_id": right,
                                     "margin": margin}
                                    for left, right, margin in identity.raw_pair_margins]}}
                if prefix_trace is not None:
                    prefix_trace["event_identity"] = event_prefix
                if until_phase == "event_identity":
                    return PhasePrefixResult(until_phase, event_prefix,
                                             self.checkpoint_sha256)
            final = finalize_cluster_features(
                member_lease, identity.closure,
                include_member_channel_diagnostics=collect_diagnostics)
            if collect_diagnostics:
                acceptance_trace["EVENT_COREFERENCE"] = AcceptanceTrace(
                    "EVENT_COREFERENCE", identity.scored_pairs, identity.accepted_pairs,
                    identity.accepted_pairs, identity.rejected_pairs,
                    identity.eligible_pairs - identity.scored_pairs).as_dict()
                storage["final_cluster"] = _storage_census(
                    final.channel_means, final.channel_counts, final.conflict_mask,
                    final.mean_reference, final.document_state,
                    final.member_channel_sums, final.member_channel_counts,
                    final.member_cluster_indices, final.role_unique_means, final.role_unique_mask)
                storage["relation_context"] = _storage_census(
                    final.original_sentence_states,
                    *(summary.context for summary in final.event_sentence_summaries))
            member_lease.close()
            if not member_lease.closed or final.closed or final.pending_consumers != {"RELATION", "PRIMARY"}:
                raise RuntimeError("final cluster feature handoff lost relation/Primary consumer")
            after_identity = perf_counter()
            statement_geometry = {statement_id: (span.start, span.end)
                                  for statement_id, span in statements.items()}
            public_only_relations = (not collect_diagnostics and
                                     self.acceptance.mode != "LEGACY_DIAGNOSTIC")
            selection = None
            if public_only_relations:
                scores = (score_final_primary(core=self.core, final=final,
                                              closure=identity.closure,
                                              statement_states=statement_states,
                                              assertor_states=assertor_states,
                                              training_provenance=self.primary_training_provenance)
                          if enable_primary else ())
                accepted_scores = tuple(row for row in scores
                                        if row.primary_score >= self.acceptance.threshold("PRIMARY"))
                base_selection = select_public_base(
                    accepted_scores=accepted_scores,
                    event_spans={row.local_id: (row.start, row.end)
                                 for row in identity.closure.events},
                    statement_spans=statement_geometry)
                final.release("PRIMARY")
                if final.closed or final.pending_consumers != {"RELATION"}:
                    raise RuntimeError("final cluster feature released before Relation consumer")
                after_primary = perf_counter()
            about_route = causes_route = None
            if baseline:
                event_count = len(identity.closure.events)
                relation_policy = self.v23_relation_routing_artifact
                full_limit = min(self.budget.max_relation_pairs,
                                 relation_policy.full_score_limit
                                 if relation_policy is not None else
                                 self.budget.max_relation_pairs)
                if len(statements) * event_count <= full_limit:
                    about_route = full_relation_route(
                        lane="ABOUT", article=raw, statements=statement_geometry,
                        events=identity.closure.events,
                        sentence_spans=layout.sentence_spans)
                elif relation_policy is not None:
                    entity_spans: dict[str, list[tuple[int, int]]] = {}
                    for candidate in universe.candidates:
                        eid = entity_closure.candidate_to_entity.get(candidate.candidate_id)
                        if eid is not None:
                            entity_spans.setdefault(eid, []).append(
                                (candidate.start, candidate.end))
                    about_route = route_about(
                        article=raw, statements=statement_geometry,
                        events=identity.closure.events,
                        sentence_spans=layout.sentence_spans,
                        entity_spans=entity_spans,
                        assertor_entities={row.owner_id: row.local_entity_id
                                           for row in entity_closure.endpoints
                                           if row.role == "ASSERTOR" and
                                           row.local_entity_id is not None},
                        policy=relation_policy.about)
                if event_count * (event_count - 1) <= full_limit:
                    causes_route = full_relation_route(
                        lane="CAUSES", article=raw, statements=statement_geometry,
                        events=identity.closure.events,
                        sentence_spans=layout.sentence_spans)
                elif relation_policy is not None:
                    causes_route = route_causes(
                        article=raw, events=identity.closure.events,
                        sentence_spans=layout.sentence_spans,
                        time_values={row.local_id: row.normalized_value
                                     for row in occurrences},
                        policy=relation_policy.causes)
            if public_only_relations:
                relation, selection = _score_public_relevant_relations(
                    core=self.core, final=final, closure=identity.closure,
                    statement_states=statement_states,
                    statement_spans=statement_geometry, base=base_selection,
                    about_route=about_route, causes_route=causes_route,
                    max_pairs=self.budget.max_relation_pairs,
                    chunk_size=self.budget.pair_chunk_size,
                    about_threshold=_legacy_or_config_threshold(self.acceptance, "ABOUT"),
                    causes_threshold=_legacy_or_config_threshold(self.acceptance, "CAUSES"),
                    legacy_prefix_fallback=not baseline)
                final.release("RELATION")
                after_relation = perf_counter()
            else:
                # Diagnostic analyze() retains the full routed relation universe.
                relation = score_final_relations(
                    core=self.core, final=final, closure=identity.closure,
                    statement_states=statement_states,
                    statement_spans=statement_geometry,
                    max_pairs=self.budget.max_relation_pairs,
                    chunk_size=self.budget.pair_chunk_size, score_threshold=None,
                    about_threshold=_legacy_or_config_threshold(self.acceptance, "ABOUT"),
                    causes_threshold=_legacy_or_config_threshold(self.acceptance, "CAUSES"),
                    about_route=about_route, causes_route=causes_route,
                    legacy_prefix_fallback=not baseline,
                    include_diagnostics=collect_diagnostics)
                if collect_diagnostics:
                    about_accepted = sum(row.relation == "ABOUT" for row in relation.facts)
                    causes_accepted = sum(row.relation == "CAUSES" for row in relation.facts)
                    acceptance_trace["ABOUT"] = AcceptanceTrace(
                        "ABOUT", relation.scored_about, about_accepted, about_accepted,
                        relation.scored_about - about_accepted,
                        relation.eligible_about - relation.scored_about).as_dict()
                    acceptance_trace["CAUSES"] = AcceptanceTrace(
                        "CAUSES", relation.scored_causes, causes_accepted, causes_accepted,
                        relation.scored_causes - causes_accepted,
                        relation.eligible_causes - relation.scored_causes).as_dict()
                final.release("RELATION")
                if final.closed or final.pending_consumers != {"PRIMARY"}:
                    raise RuntimeError("final cluster feature released before Primary consumer")
                after_relation = perf_counter()
                scores = (score_final_primary(core=self.core, final=final,
                                              closure=identity.closure,
                                              statement_states=statement_states,
                                              assertor_states=assertor_states,
                                              training_provenance=self.primary_training_provenance)
                          if enable_primary else ())
                accepted_scores = (tuple(scores) if self.acceptance.mode == "LEGACY_DIAGNOSTIC" else
                                   tuple(row for row in scores
                                         if row.primary_score >= self.acceptance.threshold("PRIMARY")))
                if collect_diagnostics:
                    acceptance_trace["PRIMARY"] = AcceptanceTrace(
                        "PRIMARY", len(scores), len(accepted_scores), len(accepted_scores),
                        len(scores) - len(accepted_scores), 0).as_dict()
                final.release("PRIMARY")
                after_primary = perf_counter()
            if not final.closed:
                raise RuntimeError("final cluster feature survived last consumer")
            if relation.partial:
                partial.append("RELATION")
            grounded = tuple(GroundedStatement(
                sid, span.label, SourceGrounding(sid, span.start, span.end, span.text),
                SourceGrounding("ASSERTOR:" + sid, assertors[sid].start,
                                assertors[sid].end, assertors[sid].text)
                if sid in assertors else None) for sid, span in statements.items())
            asserted_facts = asserted_by_facts(entity_closure)
            if self.acceptance.mode == "LEGACY_DIAGNOSTIC":
                selected_event_ids = frozenset(row.local_id for row in identity.closure.events)
                selected_statement_ids = frozenset(statements)
                public_selection_trace = None
            else:
                if selection is None:
                    selection = select_public_propositions(
                        accepted_scores=accepted_scores,
                        accepted_relations=relation.facts,
                        event_spans={row.local_id: (row.start, row.end)
                                     for row in identity.closure.events},
                        statement_spans=statement_geometry)
                selected_event_ids = selection.event_ids
                selected_statement_ids = selection.statement_ids
                public_selection_trace = {
                    "primary_threshold_accepted": len(accepted_scores),
                    "public_selected": len(selected_event_ids) + len(selected_statement_ids),
                    "event_selected": len(selected_event_ids),
                    "statement_selected": len(selected_statement_ids),
                    "causes_completion_event_id": selection.causes_completion_event_id,
                } if collect_diagnostics else None
            # Carrier가 싣지 않는 edge 판단 logit을 해제(del) 전에 stable key로 모은다.
            assertor_entities = dict(entity_result.assertor_entity_logits)
            if len(assertor_entities) != len(entity_result.assertor_entity_logits):
                raise ValueError("duplicate Assertor evidence in Entity resolution scores")
            edge_scores = PublicEdgeScores(
                event_members={member_id: acceptance_edge_score(span)
                               for member_id, (span, _trigger) in events.items()},
                statements={sid: acceptance_edge_score(span)
                            for sid, span in statements.items()},
                entity_candidates={
                    row.candidate_id: EdgeScore(row.score, "ENTITY_CANDIDATE:" + "+".join(row.origins))
                    for row in entity_result.mention_universe.candidates},
                time_attachments={key: EdgeScore(logit, "EVENT_TIME_ATTACHMENT")
                                  for key, logit in time_attachment_logits.items()},
                assertor_entities={evidence_id: EdgeScore(logit, "ASSERTOR_ENTITY_PAIR")
                                   for evidence_id, logit in assertor_entities.items()})
            construction = V3ConstructionResult(
                raw, title, identity.closure, entity_closure, grounded, occurrences,
                asserted_facts, relation.facts, scores,
                self.producer_version, edge_scores)
            if not collect_diagnostics:
                # P5/P6 have consumed the complete scalar Event inventory.
                # PUBLIC only needs the selected clusters in the compact view.
                construction = compact_public_construction(
                    construction, selected_event_ids)
                del identity, members, event_route
                del role_evidence, confidence_evidence, event_optional_source_counts
                del evidence, universe, events
            public = project_public(
                construction, selected_event_ids=selected_event_ids,
                selected_statement_ids=selected_statement_ids,
                diagnostic_unfiltered=self.acceptance.mode == "LEGACY_DIAGNOSTIC")
            statement_states.clear()
            assertor_states.clear()
            after_public = perf_counter()
            if (counts["backbone"] not in ({1} if self.frozen_feature_cache is None else {0, 1})
                    or counts["dce"] != 1 or len(set(stages.values())) != 1):
                raise RuntimeError("serving duplicated frozen producer/DCE or source representation")
            if not all(lease is None or lease.closed for lease in
                       (shared, time_lease, member_lease, final)):
                raise RuntimeError("request tensor lease escaped last consumer")
            self.frozen_features.record_downstream(
                self.frozen_feature_cache_scope,
                (perf_counter() - downstream_started) * 1000)
            if profile_sink is not None:
                profile_sink.update(_stage_latency_ms((
                    start_clock, after_shared, after_extraction, after_entity,
                    after_time, after_identity,
                    *((after_primary, after_relation) if public_only_relations else
                      (after_relation, after_primary)), after_public),
                    primary_before_relation=public_only_relations))
                profile_sink["elapsed_ms"] = round((after_public - start_clock) * 1000, 3)
            if not audit_enabled:
                return public
            if source_funnel_result is None:
                raise AssertionError("diagnostic serving lost its source carrier")
            assertor_resolved_endpoints = sum(
                row.role == "ASSERTOR" and row.local_entity_id is not None
                for row in entity_closure.endpoints)
            assertor_funnel = {
                "statement_accepted": len(statements),
                "assertor_source_proposed": assertor_source_proposed,
                "assertor_source_pairs_scored": assertor_source_pairs_scored,
                "assertor_source_accepted": len(assertors),
                "entity_option_generated": sum(row.option_count > 0
                                               for row in assertor_diagnostics),
                "target_option_present": "NOT_MEASURED_GOLD_FREE_RUNTIME",
                "option_miss": "NOT_MEASURED_GOLD_FREE_RUNTIME",
                "option_pairs_scored": entity_result.scored_assertor_entity_pairs,
                "absolute_threshold_accepted": sum(row.accepted
                                                   for row in assertor_diagnostics),
                "argmax_selected": sum(row.selected_candidate_id is not None
                                       for row in assertor_diagnostics),
                "entity_closure": assertor_resolved_endpoints,
                "asserted_by_fact": sum(row.entity_id is not None for row in asserted_facts),
                "public_survived": sum(row["edge_type"] == "ASSERTED_BY"
                                       for row in public["edges"]),
                "gold_proxy_used": False,
            }
            audit = {"mode": self.acceptance.mode,
                     "source_funnel": source_funnel_result.as_dict(),
                     "predicted_structure": {
                         "candidate_to_entity": dict(entity_closure.candidate_to_entity),
                         "entity_representatives": {
                             row.local_id: row.representative_candidate_id
                             for row in entity_closure.entities},
                         "members": [
                             {"member_id": row.member_id, "start": row.start,
                              "end": row.end, "text": row.text,
                              "trigger_start": row.trigger_start,
                              "trigger_end": row.trigger_end,
                              "trigger_text": row.trigger_text,
                              "roles": [{"evidence_id": role.evidence_id,
                                         "role": role.role, "start": role.start,
                                         "end": role.end, "text": role.text,
                                         "entity_id": role.entity_id,
                                         "endpoint_status": role.endpoint_status}
                                        for role in row.roles],
                              "time_ids": list(row.time_ids)} for row in members],
                         "member_to_cluster": dict(identity.closure.member_to_cluster),
                         "event_confidence_evidence": [
                             {"member_id": row.member_id, "channel": row.channel,
                              "source_id": row.source_id,
                              "probability": row.probability,
                              "producer": row.producer}
                             for row in confidence_evidence],
                         "event_optional_source_counts": [
                             list(row) for row in event_optional_source_counts],
                         "times": [
                             {"local_id": row.local_id, "start": row.start,
                              "end": row.end, "text": row.text,
                              "evidence_ids": list(row.evidence_ids),
                              "normalized_value": row.normalized_value,
                              "granularity": row.granularity,
                              "normalization_status": row.normalization_status,
                              "attached_event_ids": list(row.attached_event_ids),
                              "attachment_status": row.attachment_status,
                              "calendar_eligible": row.calendar_eligible,
                              "public_calendar_candidate": row.public_calendar_candidate,
                              "projection_safe": row.projection_safe,
                              "projection_reason": row.projection_reason,
                              "normalization_contexts": [
                                  {"year": context.year, "month": context.month,
                                   "provenance": context.provenance,
                                   "evidence_id": context.evidence_id,
                                   "evidence_start": context.evidence_start,
                                   "evidence_end": context.evidence_end,
                                   "evidence_text": context.evidence_text}
                                  for context in row.normalization_contexts],
                              "normalization_reason": row.normalization_reason}
                             for row in occurrences],
                         "time_evidence": [
                             {"time_id": row.time_id, "start": row.start,
                              "end": row.end, "text": row.text,
                              "normalized_value": row.normalized_value,
                              "normalization_status": row.normalization_status,
                              "normalization_reason": row.normalization_reason}
                             for row in time_mentions],
                     },
                     "policy_status": ("SERVICE_READY" if self.acceptance.service_ready
                                       else "SERVICE_READY_FALSE"),
                     "score_contract_version": SCORE_CONTRACT_VERSION,
                     "checkpoint_sha256": self.checkpoint_sha256,
                     "acceptance_config": self.acceptance.as_dict(),
                     "acceptance_trace": acceptance_trace,
                     "public_selection": public_selection_trace,
                     "pair_routing": pair_routing_audit,
                     "raw_score_audit": {
                         "EVENT_COREFERENCE": [
                             {"left_id": left, "right_id": right,
                              "margin": margin}
                             for left, right, margin in identity.raw_pair_margins],
                         "ABOUT": [
                             {"left_id": left, "right_id": right, "score": score}
                             for left, right, score in
                             (relation.raw_score_rows or {}).get("ABOUT", ())],
                         "CAUSES": [
                             {"left_id": left, "right_id": right, "score": score}
                             for left, right, score in
                             (relation.raw_score_rows or {}).get("CAUSES", ())],
                         "PRIMARY": [
                             {"local_id": row.local_id, "kind": row.kind,
                              "score": row.primary_score} for row in scores],
                     },
                     "assertor_funnel": assertor_funnel,
                     "semantic_status_trace": {
                         "unresolved_time_mentions": sum(
                             row.normalized_value is None for row in time_mentions),
                         "unresolved_time_mentions_dropped": unresolved_time_dropped,
                         "span_only_place": sum(
                             row.role == "PLACE" and row.status == "SPAN_ONLY"
                             for row in entity_closure.endpoints),
                         "unresolved_place": sum(
                             row.role == "PLACE" and row.status == "UNRESOLVED_REFERENTIAL"
                             for row in entity_closure.endpoints),
                         "span_only_assertor": sum(
                             row.role == "ASSERTOR" and row.status == "SPAN_ONLY"
                             for row in entity_closure.endpoints),
                     },
                     "downstream_counts": {
                         "event_owners": len(events),
                         "participant_owner_role_calls": len(events) * 3,
                         "assertor_owner_calls": len(statements),
                         "entity_candidates": len(universe.candidates),
                         "time_mentions": len(time_mentions),
                         "relation_pairs_scored": relation.scored_about + relation.scored_causes,
                     },
                     "partial_stages": sorted(set(partial)),
                     "backbone_calls": counts["backbone"], "dce_calls": counts["dce"],
                     "frozen_feature_cache": {
                         "enabled": self.frozen_feature_cache is not None,
                         "scope": self.frozen_feature_cache_scope,
                         "hit": self.frozen_feature_cache is not None
                         and counts["backbone"] == 0,
                     },
                     "captured_layers": [8, 10, 12],
                     "capture_hook_count": capture.capture_hook_count if capture is not None else None,
                     "source_representation_reused": len(set(stages.values())) == 1,
                     "source_consumers": sorted(stages),
                     "source_candidate_pairs": source_pairs,
                     "participant_candidate_pairs": participant_pairs,
                     "role_forwarding_policy": {
                         "max_fillers_per_event_role": (
                             self.source_policy.participant_role_forwarding_limit
                             if baseline else self.budget.max_role_fillers_per_event_role),
                         "selection_score": ("V23_B2_ENDPOINT" if baseline else
                                             "DecodedSourceSpan.extraction_score"),
                         "accept_threshold": (None if baseline else
                                              self.source_policy.participant_threshold
                                              if self.source_policy is not None else
                                              _legacy_or_config_threshold(
                                                  self.acceptance, "PARTICIPANT")),
                         "accept_condition": ("ENDPOINT_GATE_ALREADY_APPLIED"
                                              if baseline else
                                              "extraction_score >= accept_threshold"),
                         "score_semantics": SCORE_CONTRACT_VERSION,
                         "identity_owner": "ENTITY_COREFERENCE_ONLY",
                         "status": (self.source_policy.participant_mode
                                    if self.source_policy is not None else self.acceptance.mode)},
                     "role_source_provenance": [
                         {"evidence_id": row.evidence_id, "owner_id": row.owner_id,
                          "role": row.role, "start": row.start, "end": row.end,
                          "source_windows": [list(pair) for pair in row.source_windows]}
                         for row in role_evidence],
                     "entity_candidates": len(universe.candidates),
                     "entity_clusters": len(entity_closure.entities),
                     "all_entities_canonical_type": True,
                     "entity_candidates_dropped_ner": universe.dropped_ner,
                     "entity_candidates_dropped_role": universe.dropped_role,
                     "entity_coreference_pairs_scored": entity_result.scored_coreference_pairs,
                     "entity_coreference_decision_policy": (
                         "ARGMAX_CLASS_1" if legacy_entity_policy else "MARGIN_GTE"),
                     "entity_coreference_margin": (
                         0.0 if legacy_entity_policy else
                         self.acceptance.threshold("ENTITY_COREFERENCE")),
                     "entity_resolution_policy_status": entity_result.policy_status,
                     "entity_resolution_diagnostics": [
                         {"evidence_id": row.evidence_id, "role": row.role,
                          "accepted": row.accepted, "reason": row.reason,
                          "best_score": row.best_score,
                          "selected_candidate_id": row.selected_candidate_id,
                          "option_count": row.option_count,
                          "threshold_passed_options": row.threshold_passed_options,
                          "option_status": row.option_status}
                         for row in entity_result.resolution_diagnostics],
                     "asserted_by_option_routing": entity_result.assertor_option_routes,
                     "event_time_pairs_eligible": attachments.eligible_pairs,
                     "event_time_pairs_scored": attachments.scored_pairs,
                     "event_coreference_pairs_eligible": identity.eligible_pairs,
                     "event_coreference_pairs_scored": identity.scored_pairs,
                     "about_pairs_eligible": relation.eligible_about,
                     "about_pairs_scored": relation.scored_about,
                     "causes_pairs_eligible": relation.eligible_causes,
                     "causes_pairs_scored": relation.scored_causes,
                     "storage_census": storage,
                     "event_members": len(events), "final_event_clusters": len(identity.closure.events),
                     "statements": len(statements), "time_mentions": len(time_mentions),
                     "time_normalization_checked": normalization_checked,
                     "unresolved_time_mentions": sum(row.normalized_value is None for row in time_mentions),
                     "unresolved_time_mentions_dropped": unresolved_time_dropped,
                     "relative_month_context_trace": {
                         "provided": len(relative_month_context_by_span),
                         "consumed": len(consumed_relative_month_contexts),
                         "unused": (len(relative_month_context_by_span) -
                                    len(consumed_relative_month_contexts)),
                         "auto_published_contexts_created": 0,
                         "bindings": [
                             {"time_start": key[0], "time_end": key[1],
                              "time_text": key[2],
                              "evidence_id": context.evidence_id,
                              "provenance": context.provenance,
                              "consumed": key in consumed_relative_month_contexts}
                             for key, context in sorted(
                                 relative_month_context_by_span.items(),
                                 key=lambda item: item[0])],
                     },
                     "noncalendar_time_occurrences": sum(not row.calendar_eligible for row in occurrences),
                     "time_semantics": [
                         {"local_id": row.local_id, "start": row.start, "end": row.end,
                          "text": row.text, "normalized_value": row.normalized_value,
                          "granularity": row.granularity,
                          "normalization_status": row.normalization_status,
                          "normalization_reason": row.normalization_reason,
                          "attachment_status": row.attachment_status,
                          "calendar_eligible": row.calendar_eligible,
                          "projection_safe": row.projection_safe,
                          "projection_reason": row.projection_reason,
                          "public_calendar_candidate": row.public_calendar_candidate,
                          "normalization_context_ids": list(row.normalization_context_ids),
                          "normalization_context_provenance": list(
                              row.normalization_context_provenance),
                          "normalization_contexts": [
                              {"year": context.year, "month": context.month,
                               "provenance": context.provenance,
                               "evidence_id": context.evidence_id,
                               "evidence_start": context.evidence_start,
                               "evidence_end": context.evidence_end,
                               "evidence_text": context.evidence_text}
                              for context in row.normalization_contexts]}
                         for row in occurrences],
                     "span_only_place": sum(row.role == "PLACE" and row.status == "SPAN_ONLY"
                                            for row in entity_closure.endpoints),
                     "unresolved_place": sum(row.role == "PLACE" and
                                               row.status == "UNRESOLVED_REFERENTIAL"
                                               for row in entity_closure.endpoints),
                     "span_only_assertor": sum(row.role == "ASSERTOR" and row.status == "SPAN_ONLY"
                                               for row in entity_closure.endpoints),
                     "role_derived_entities": sum(any(eid.startswith("ROLE-PRED:")
                                                      for eid in row.evidence_ids)
                                                  for row in entity_closure.entities),
                     "assertor_derived_entities": sum(any(eid.startswith("ASSERTOR-PRED:")
                                                          for eid in row.evidence_ids)
                                                      for row in entity_closure.entities),
                     "entity_type_conflicts": [
                         {"local_id": row.local_id, "canonical_type": row.entity_type,
                          "observed_types": list(row.observed_types),
                          "member_type_evidence": [
                              {"candidate_id": cid, "predicted_type": kind,
                               "log_probabilities": list(values)}
                              for cid, kind, values in row.member_type_evidence]}
                         for row in entity_closure.entities if row.status == "TYPE_CONFLICT"],
                     "relation_scored_pairs": relation.scored_about + relation.scored_causes,
                     "pair_context_census": relation.pair_context_census,
                     "relation_routing": relation.routing_trace,
                     "stage_latency_ms": _stage_latency_ms((
                         start_clock, after_shared, after_extraction, after_entity,
                         after_time, after_identity, after_relation, after_primary,
                         after_public)),
                     "elapsed_ms": round((perf_counter() - start_clock) * 1000, 3),
                     "all_tensor_leases_closed": all(
                         lease is None or lease.closed for lease in
                         (shared, time_lease, member_lease, final))}
            if not audit["all_tensor_leases_closed"]:
                raise RuntimeError("request tensor lease escaped last consumer")
            return ServingResult(public, audit)
        finally:
            if participant_stream is not None:
                participant_stream.close()
            if source_context is not None and not source_context.closed:
                source_context.close()
            if exact_feature_cache is not None and not exact_feature_cache.closed:
                exact_feature_cache.close()
            for lease in (final, member_lease, time_lease, shared):
                if lease is not None and not lease.closed:
                    lease.close()
            for handle in handles:
                handle.remove()


def _file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_diagnostic_worker(checkpoint_path: str | Path, *,
                           budget: ServingBudget = ServingBudget(),
                           acceptance: AcceptanceConfig | None = None,
                           source_policy: SourceFunnelPolicy | None = None,
                           calibration_artifact: Mapping[str, Any] | None = None,
                           entity_pair_policy: EntityPairPolicy | None = None,
                           allow_all_pair_shadow_reference: bool = False) -> V3ServingWorker:
    """Strictly load a stage-13 smoke core at startup without reading Gold articles.

    The returned worker remains diagnostic: smoke weights and Primary scores are
    never promoted to a trained or persistence-ready service model.
    """
    from models.v3_pretraining.task_contract import HEAD_TASKS
    from training.v3_pretraining.checkpoint import (
        ENGINEERING_CHECKPOINT_REQUIRED_FIELDS, FORMAT_VERSION, _json_digest,
        label_mappings, producer_hashes, relation_policy_from_config)
    from training.v3_pretraining.harness import (HarnessConfig, fresh_full_core,
                                                 load_pinned_backbone, parameter_manifest)
    from training.v3_pretraining.relation_sampling import validate_relation_training_metadata
    from training.v3_pretraining.selection_contract import validate_checkpoint_selection_contract

    checkpoint_sha256 = _file_sha256(checkpoint_path)
    if source_policy is not None and acceptance is None:
        raise ValueError("source-policy startup requires explicit downstream acceptance")
    acceptance = acceptance or AcceptanceConfig.legacy_diagnostic(checkpoint_sha256)
    acceptance.validate_runtime(
        checkpoint_sha256=checkpoint_sha256,
        score_contract_version=SCORE_CONTRACT_VERSION,
        calibration_artifact=calibration_artifact)
    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if (not isinstance(payload, dict)
            or set(payload) != ENGINEERING_CHECKPOINT_REQUIRED_FIELDS
            or payload.get("format_version") != FORMAT_VERSION
            or payload.get("mode") != "ENGINEERING_SMOKE_ONLY"):
        raise ValueError("incomplete or foreign diagnostic v3 checkpoint")
    config_data = payload["harness_config"]
    if (set(config_data) != set(HarnessConfig.__dataclass_fields__) or
            _json_digest(config_data) != payload["harness_config_sha256"] or
            payload["run_id"] != config_data["run_id"] or
            payload["seed"] != config_data["seed"]):
        raise ValueError("serving checkpoint run/config identity differs")
    config = HarnessConfig(**config_data)
    config.validate()
    validate_relation_training_metadata(
        payload["relation_training_metadata"],
        expected_policy=relation_policy_from_config(config))
    validate_checkpoint_selection_contract(payload["selection_contract"])
    core = fresh_full_core(config)
    if (payload["architecture_config_sha256"] != core.config.fingerprint() or
            _json_digest(payload["architecture_config"]) != core.config.fingerprint() or
            payload["task_registry"] != list(HEAD_TASKS) or
            payload["label_mappings"] != label_mappings() or
            payload["producer_hashes"] != producer_hashes() or
            payload["parameter_manifest"] != list(parameter_manifest(core)) or
            set(payload["model_state"]) != set(core.state_dict())):
        raise ValueError("serving checkpoint architecture/producer/parameter manifest differs")
    snapshot = payload["source_snapshot"]
    if (not isinstance(snapshot, dict) or
            set(snapshot) != {"source_join_sha256", "split_sha256", "exposure"} or
            any(not isinstance(snapshot[key], str) or len(snapshot[key]) != 64
                for key in ("source_join_sha256", "split_sha256")) or
            not isinstance(snapshot["exposure"], list) or not snapshot["exposure"] or
            any(not isinstance(row, dict) or
                set(row) != {"article_id", "gold_file", "gold_sha256", "source_sha256", "split"}
                or row["split"] != "train" or
                any(not isinstance(row[key], str) or len(row[key]) != 64
                    for key in ("gold_sha256", "source_sha256"))
                for row in snapshot["exposure"]) or
            len({row["article_id"] for row in snapshot["exposure"]}) != len(snapshot["exposure"]) or
            payload["sampler_state"].get("article_ids") != [row["article_id"]
                                                            for row in snapshot["exposure"]] or
            payload["sampler_state"].get("cursor") != payload["training_state"].get("articles_seen") or
            payload["training_state"].get("optimizer_steps", -1) < 0):
        raise ValueError("serving checkpoint train-only provenance/resume metadata differs")
    tokenizer, digest, revision = load_pinned_fast_tokenizer()
    if (payload["backbone"] != {"model_id": core.config.backbone.model_id,
                                  "revision": core.config.backbone.revision,
                                  "weights_sha256": core.config.backbone.expected_weights_sha256,
                                  "stored_in_checkpoint": False} or
            payload["tokenizer"] != {"revision": revision, "sha256": digest}):
        raise ValueError("serving checkpoint pinned backbone/tokenizer differs")
    core.load_state_dict(payload["model_state"], strict=True)
    return V3ServingWorker(core, load_pinned_backbone(core), tokenizer, digest,
                           budget=budget, acceptance=acceptance,
                           source_policy=source_policy,
                           checkpoint_sha256=checkpoint_sha256,
                           calibration_artifact=calibration_artifact,
                           producer_version="V3_STEP13_SMOKE_DIAGNOSTIC",
                           entity_pair_policy=entity_pair_policy,
                           allow_all_pair_shadow_reference=allow_all_pair_shadow_reference)
