"""Selected-pair Entity identity and post-closure ASSERTOR attribution.

Native and ROLE source mentions keep their source types and exact coordinates.
Only endpoints selected by the Gold-free coreference router receive expensive
pair representations. Participant identity is decided by this one closure;
ASSERTOR attribution remains a separate, later fine decision.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations
import math
from time import perf_counter
from typing import Mapping

import torch

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from runtime.v3_pretraining.attribution_features import (
    assertor_relation_left, build_assertor_entity_option_index,
    build_assertor_entity_options,
    assertor_option_routing_trace,
)
from runtime.v3_pretraining.entity_identity import (
    EntityClosure, RoleEndpoint, close_entity_identity,
)
from runtime.v3_pretraining.entity_pair_blocking import EntityPairPolicy
from runtime.v3_pretraining.entity_pair_features import (
    EntityPairContext, PreparedEntityPairMention, build_entity_pair_features,
    prepare_entity_pair_mentions,
)
from runtime.v3_pretraining.entity_union import EntityCandidateUniverse
from runtime.v3_pretraining.exact_feature_cache import (RequestExactFeatureCache,
                                                        exact_source_features)
from runtime.v3_pretraining.pair_routing import (
    RoutedPairs, inventory_lineage, route_entity_coreference,
)
from runtime.candidate_routing.integrated import IntegratedBoundedPolicies
from runtime.v3_pretraining.source_layout import SourceLayout


ENTITY_COREFERENCE_POLICIES = frozenset(("ARGMAX_CLASS_1", "MARGIN_GTE"))


@dataclass(frozen=True, slots=True)
class EntityResolutionDiagnostic:
    evidence_id: str
    role: str
    accepted: bool
    reason: str
    best_score: float | None = None
    selected_candidate_id: str | None = None
    option_count: int = 0
    threshold_passed_options: int = 0
    option_status: str | None = None


@dataclass(frozen=True, slots=True)
class EntityScoreResult:
    closure: EntityClosure
    mention_universe: EntityCandidateUniverse
    scored_coreference_pairs: int
    resolution_diagnostics: tuple[EntityResolutionDiagnostic, ...] = ()
    policy_status: str = "UNIFIED_MENTION_COREF_V1"
    accepted_coreference_pairs: int = 0
    rejected_coreference_pairs: int = 0
    scored_assertor_entity_pairs: int = 0
    entity_pair_route: RoutedPairs | None = None
    assertor_option_routes: tuple[dict[str, object], ...] = ()
    preliminary_closure: EntityClosure | None = None
    # Assertor evidence ID -> 선택된 Entity의 assertor_entity pair logit (PUBLIC confidence 원천).
    assertor_entity_logits: tuple[tuple[str, float], ...] = ()
    raw_pair_margins: tuple[tuple[str, str, float], ...] = ()


def _prepare_entity_pair_chunk(*, pair_chunk: torch.Tensor,
                               state_rows: torch.Tensor,
                               selected_position_index: torch.Tensor,
                               pair_sources: tuple[PreparedEntityPairMention, ...],
                               pair_context: EntityPairContext,
                               device: torch.device
                               ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Pack exact selected endpoints and shared source-only pair features."""
    local_ids, inverse = torch.unique(pair_chunk.reshape(-1), sorted=True,
                                      return_inverse=True)
    states = state_rows.index_select(
        0, selected_position_index.index_select(0, local_ids)).to(device)
    pair_indices = inverse.view(-1, 2).to(device)
    policy = torch.tensor([
        build_entity_pair_features(pair_sources[left], pair_sources[right], pair_context)
        for left, right in pair_chunk.tolist()], dtype=states.dtype, device=device)
    return states, pair_indices, policy


@torch.no_grad()
def score_and_close_entity(*, universe: EntityCandidateUniverse, layout: SourceLayout,
                           batch: ArticleBatch, backbone: BackboneOutput,
                           shared: SharedForwardLease, core: V3Core,
                           statement_states: Mapping[str, torch.Tensor] | None = None,
                           assertor_states: Mapping[str, torch.Tensor] | None = None,
                           assertor_resolution_threshold: float = 0.0,
                           entity_coreference_margin: float = 0.0,
                           entity_coreference_policy: str = "MARGIN_GTE",
                           pair_chunk_size: int = 128,
                           max_candidates: int | None = None,
                           pair_policies: IntegratedBoundedPolicies | None = None,
                           entity_pair_policy: EntityPairPolicy | None = None,
                           entity_all_pair_shadow_reference: bool = False,
                           identity_only: bool = False,
                           include_diagnostics: bool = True,
                           exact_feature_cache: RequestExactFeatureCache | None = None,
                           profile_sink: dict[str, float] | None = None
                           ) -> EntityScoreResult:
    """Score routed mention pairs, close identity once, then resolve Assertors.

    Pair routing is source-only. Missing pairs never enter the fine decision map;
    complete-link therefore cannot infer a merge from an unassessed pair.
    ``pair_chunk_size`` bounds execution memory and never deletes a candidate.
    """
    if (universe.identity_contract != "UNIFIED_MENTION_COREF_V1" or
            universe.source_mode != "PREDICTED" or
            universe.content_sha256 != layout.article.content_sha256 or
            universe.article_version_id != layout.article.article_version_id):
        raise ValueError("Entity scorer requires matching unified predicted mentions")
    if (shared.closed or shared.token_states is None or
            shared.sentence_states is None or shared.document_state is None):
        raise RuntimeError("Entity scorer needs one live shared representation")
    if (pair_chunk_size <= 0 or (max_candidates is not None and
                                 len(universe.candidates) > max_candidates)):
        raise ValueError("Entity scorer candidate/chunk contract differs")
    if (entity_coreference_policy not in ENTITY_COREFERENCE_POLICIES or
            not math.isfinite(entity_coreference_margin) or
            not math.isfinite(assertor_resolution_threshold)):
        raise ValueError("Entity decision policy or margin differs")
    if "entity_coreference" not in core.task_modules:
        raise ValueError("Entity coreference fine head is absent")
    assertors = tuple(binding for binding in universe.bindings
                      if binding.role == "ASSERTOR")
    if assertors and not identity_only and (
            "assertor_entity" not in core.task_modules or
            statement_states is None or assertor_states is None):
        raise ValueError("Assertor fine decision needs source and Statement states")

    profile_start = perf_counter() if profile_sink is not None else 0.0
    candidates = universe.candidates
    route = None
    if pair_policies is not None:
        source_lineage = inventory_lineage(
            layout.article,
            tuple((row.candidate_id, row.start, row.end) for row in candidates))
        route = route_entity_coreference(
            article=layout.article, candidates=candidates,
            source_lineage=source_lineage, policies=pair_policies,
            sentence_spans=layout.sentence_spans,
            entity_policy=entity_pair_policy,
            shadow_all_pairs=entity_all_pair_shadow_reference,
            materialize_records=include_diagnostics)
        pair_rows = route.pairs
    else:
        pair_rows = tuple(combinations(range(len(candidates)), 2))
    if profile_sink is not None:
        profile_sink["entity_pair_routing_ms"] = round(
            (perf_counter() - profile_start) * 1000, 3)
        profile_start = perf_counter()

    # Encode unique endpoints of selected pairs once in bounded chunks. CPU
    # storage avoids holding the full article candidate matrix on MPS; each
    # fine chunk moves only its needed rows back to the model device.
    needed = bytearray(len(candidates))
    for left, right in pair_rows:
        needed[left] = needed[right] = 1
    selected_indices = [index for index, present in enumerate(needed) if present]
    hidden = shared.document_state.shape[-1]
    state_rows = torch.empty((len(selected_indices), hidden),
                             dtype=shared.token_states.dtype, device="cpu")
    selected_positions = {index: pos for pos, index in enumerate(selected_indices)}
    selected_position_index = torch.full((len(candidates),), -1, dtype=torch.long)
    if selected_indices:
        selected_position_index[torch.tensor(selected_indices, dtype=torch.long)] = (
            torch.arange(len(selected_indices), dtype=torch.long))
    extra_states: dict[int, torch.Tensor] = {}

    def encode(indices: list[int]) -> torch.Tensor:
        aligned = [layout.align({"start": candidates[index].start,
                                 "end": candidates[index].end,
                                 "text": candidates[index].text})
                   for index in indices]
        features = exact_source_features(
            layout=layout, batch=batch, backbone=backbone, shared=shared, core=core,
            rows=[(row, "ENTITY") for row in aligned], cache=exact_feature_cache)
        return features.states.detach().to("cpu")

    for offset in range(0, len(selected_indices), pair_chunk_size):
        indices = selected_indices[offset:offset + pair_chunk_size]
        state_rows[offset:offset + len(indices)].copy_(encode(indices))
    if profile_sink is not None:
        profile_sink["entity_unique_endpoint_encoding_ms"] = round(
            (perf_counter() - profile_start) * 1000, 3)
        profile_start = perf_counter()

    def state_cpu(index: int) -> torch.Tensor:
        position = selected_positions.get(index)
        if position is not None:
            return state_rows[position]
        if index not in extra_states:
            extra_states[index] = encode([index])[0]
        return extra_states[index]

    device = shared.document_state.device
    document_state = shared.document_state[0]
    accepted_merge: dict[tuple[str, str], bool] = {}
    raw_pair_margins: list[tuple[str, str, float]] = []
    pair_indices_cpu = torch.tensor(pair_rows, dtype=torch.long).reshape(-1, 2)
    pair_context = (EntityPairContext(len(layout.article.content),
                                      tuple(layout.sentence_spans))
                    if pair_rows else None)
    pair_sources = (prepare_entity_pair_mentions(candidates, pair_context)
                    if pair_context is not None else ())
    for offset in range(0, len(pair_rows), pair_chunk_size):
        chunk = pair_rows[offset:offset + pair_chunk_size]
        pair_chunk = pair_indices_cpu[offset:offset + pair_chunk_size]
        states, pair_indices, policy = _prepare_entity_pair_chunk(
            pair_chunk=pair_chunk, state_rows=state_rows,
            selected_position_index=selected_position_index,
            pair_sources=pair_sources, pair_context=pair_context,
            device=device)
        logits = core.task_modules["entity_coreference"](
            states, pair_indices, document_state, policy)
        if not torch.isfinite(logits).all():
            raise ValueError("non-finite Entity coreference score")
        decisions = (logits.argmax(dim=-1) == 1 if
                     entity_coreference_policy == "ARGMAX_CLASS_1" else
                     logits[:, 1] - logits[:, 0] >= entity_coreference_margin)
        if include_diagnostics:
            margins = (logits[:, 1] - logits[:, 0]).detach().cpu().tolist()
            raw_pair_margins.extend(
                (candidates[left].candidate_id, candidates[right].candidate_id,
                 float(margin)) for (left, right), margin in zip(chunk, margins))
        for (left, right), keep in zip(chunk, decisions.tolist()):
            if keep:
                accepted_merge[(candidates[left].candidate_id,
                                candidates[right].candidate_id)] = True
    if profile_sink is not None:
        profile_sink["entity_coreference_fine_scoring_ms"] = round(
            (perf_counter() - profile_start) * 1000, 3)
        profile_start = perf_counter()

    preliminary = close_entity_identity(
        universe, merge_decisions=accepted_merge, resolution_decisions={})
    if profile_sink is not None:
        profile_sink["entity_complete_link_closure_ms"] = round(
            (perf_counter() - profile_start) * 1000, 3)
        profile_start = perf_counter()
    accepted_count = len(accepted_merge)
    if identity_only or not assertors:
        if profile_sink is not None:
            profile_sink["entity_assertor_resolution_ms"] = 0.0
        return EntityScoreResult(
            preliminary, universe, len(pair_rows),
            accepted_coreference_pairs=accepted_count,
            rejected_coreference_pairs=len(pair_rows) - accepted_count,
            entity_pair_route=route, preliminary_closure=preliminary,
            raw_pair_margins=tuple(raw_pair_margins))

    id_to_index = {row.candidate_id: index for index, row in enumerate(candidates)}
    entity_by_id = {row.local_id: row for row in preliminary.entities}
    entity_states: dict[str, torch.Tensor] = {}

    def entity_state(entity_id: str) -> torch.Tensor:
        if entity_id not in entity_states:
            entity = entity_by_id[entity_id]
            member_ids = sorted(entity.candidate_ids, key=lambda candidate_id: (
                candidates[id_to_index[candidate_id]].start,
                candidates[id_to_index[candidate_id]].end, candidate_id))
            total = torch.zeros(hidden, dtype=torch.float32)
            for candidate_id in member_ids:
                total += state_cpu(id_to_index[candidate_id]).float()
            entity_states[entity_id] = (total / len(member_ids)).to(device)
        return entity_states[entity_id]

    endpoint_by_evidence = {row.evidence_id: row for row in preliminary.endpoints}
    evidence_to_entity = dict(preliminary.evidence_to_entity)
    diagnostics: list[EntityResolutionDiagnostic] = []
    option_routes: list[dict[str, object]] = []
    chosen_logits: list[tuple[str, float]] = []
    scored_assertor = 0
    option_index = build_assertor_entity_option_index(
        layout=layout, universe=universe, preliminary=preliminary)
    for binding in assertors:
        owner = statement_states.get(binding.owner_id)
        source_exact = assertor_states.get(binding.owner_id)
        if owner is None or source_exact is None:
            raise ValueError("Assertor Statement/source representation missing")
        options = build_assertor_entity_options(
            layout=layout, universe=universe, preliminary=preliminary,
            binding=binding, index=option_index)
        trace = None
        if include_diagnostics:
            trace = assertor_option_routing_trace(
                layout=layout, universe=universe, preliminary=preliminary,
                binding=binding, options=options)
            option_routes.append(trace)
        entity_ids = options.entity_ids
        chosen = None
        best_score = None
        passed_count = 0
        if entity_ids:
            source = assertor_relation_left(owner, source_exact)
            right = torch.stack([entity_state(entity_id) for entity_id in entity_ids])
            logits = core.task_modules["assertor_entity"](
                source.unsqueeze(0).expand_as(right), right, document_state)
            if not torch.isfinite(logits).all():
                raise ValueError("non-finite Assertor Entity score")
            scored_assertor += len(entity_ids)
            if include_diagnostics:
                best_score = float(logits.max())
            passing = logits >= assertor_resolution_threshold
            passed_count = int(passing.sum())
            if passed_count:
                masked = logits.masked_fill(~passing, torch.finfo(logits.dtype).min)
                chosen_index = int(masked.argmax())
                chosen = entity_ids[chosen_index]
                chosen_logits.append((binding.evidence_id, float(logits[chosen_index])))
            if trace is not None:
                for record in trace["records"]:
                    record["fine_status"] = (
                        "FINE_ACCEPTED" if chosen is not None and
                        record["candidate_entity_local_id"] == chosen else "FINE_REJECTED")
        previous = endpoint_by_evidence[binding.evidence_id]
        endpoint_by_evidence[binding.evidence_id] = replace(
            previous, local_entity_id=chosen,
            status="RESOLVED" if chosen is not None else "SPAN_ONLY")
        if chosen is not None:
            evidence_to_entity[binding.evidence_id] = chosen
        if include_diagnostics:
            diagnostics.append(EntityResolutionDiagnostic(
                binding.evidence_id, "ASSERTOR", chosen is not None,
                "ASSERTOR_ENTITY_SELECTED" if chosen is not None else
                "NO_ENTITY_OPTIONS" if not entity_ids else "ASSERTOR_ENTITY_BELOW_THRESHOLD",
                best_score, (entity_by_id[chosen].representative_candidate_id
                             if chosen is not None else None),
                len(entity_ids), passed_count, options.status))
    closure = replace(
        preliminary, evidence_to_entity=evidence_to_entity,
        endpoints=tuple(endpoint_by_evidence[row.evidence_id]
                        for row in preliminary.endpoints),
        status=("PARTIAL_ENDPOINT" if any(
            row.local_entity_id is None for row in endpoint_by_evidence.values())
                else preliminary.status))
    if profile_sink is not None:
        profile_sink["entity_assertor_resolution_ms"] = round(
            (perf_counter() - profile_start) * 1000, 3)
    return EntityScoreResult(
        closure, universe, len(pair_rows), tuple(diagnostics),
        accepted_coreference_pairs=accepted_count,
        rejected_coreference_pairs=len(pair_rows) - accepted_count,
        scored_assertor_entity_pairs=scored_assertor,
        entity_pair_route=route, assertor_option_routes=tuple(option_routes),
        preliminary_closure=preliminary, assertor_entity_logits=tuple(chosen_logits),
        raw_pair_margins=tuple(raw_pair_margins))
