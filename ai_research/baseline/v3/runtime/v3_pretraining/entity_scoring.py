"""Gold 없는 Entity union의 request-local typing·identity·role 점수화.

하나의 live backbone/DCE lease를 소비하고 scalar closure만 반환한다. 이 단계의
argmax는 engineering decision이며 서비스 threshold·checkpoint 정책이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations
from typing import Mapping

import torch

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from models.v3_pretraining.extraction_heads import ENTITY_TYPES
from runtime.v3_pretraining.entity_identity import EntityClosure, close_entity_identity
from runtime.v3_pretraining.entity_union import EntityCandidateUniverse
from runtime.v3_pretraining.source_layout import SourceLayout


@dataclass(frozen=True, slots=True)
class EntityScoreResult:
    closure: EntityClosure
    typed_universe: EntityCandidateUniverse
    scored_coreference_pairs: int
    scored_role_entity_pairs: int
    policy_status: str = "PROVISIONAL_ARGMAX_NO_SERVICE_THRESHOLD"


@torch.no_grad()
def score_and_close_entity(*, universe: EntityCandidateUniverse, layout: SourceLayout,
                           batch: ArticleBatch, backbone: BackboneOutput,
                           shared: SharedForwardLease, core: V3Core,
                           accepted_role_evidence: frozenset[str] = frozenset(),
                           statement_states: Mapping[str, torch.Tensor] | None = None,
                           assertor_resolution_threshold: float = 0.0,
                           pair_chunk_size: int = 128,
                           max_candidates: int = 128) -> EntityScoreResult:
    """role span을 유지한 bounded pair 점수와 최종 article-local remap을 생성한다."""
    if (universe.source_mode != "PREDICTED" or universe.content_sha256 != layout.article.content_sha256
            or universe.article_version_id != layout.article.article_version_id):
        raise ValueError("runtime Entity scoring needs matching predicted source")
    if (shared.closed or shared.token_states is None or shared.sentence_states is None
            or shared.document_state is None):
        raise RuntimeError("Entity scoring needs a live shared representation")
    if pair_chunk_size <= 0 or max_candidates <= 0 or len(universe.candidates) > max_candidates:
        raise ValueError("Entity pair scoring must stay within explicit candidate/chunk bounds")
    if any(name not in core.task_modules for name in ("entity_mention", "entity_coreference",
                                                       "role_entity", "entity_priority")):
        raise ValueError("Entity score heads must be registered")
    if any(row.role == "ASSERTOR" for row in universe.bindings) and (
            "assertor_entity" not in core.task_modules or statement_states is None):
        raise ValueError("Assertor resolution needs its fresh head and Statement representations")
    bindings = {row.evidence_id: row for row in universe.bindings}
    if not accepted_role_evidence <= bindings.keys():
        raise ValueError("unknown accepted role evidence")
    accepted_sources = accepted_role_evidence | frozenset(
        row.evidence_id for row in universe.bindings
        if row.role == "ASSERTOR" and row.status == "CANDIDATE")
    candidates = universe.candidates
    if not candidates:
        closure = close_entity_identity(universe, merge_decisions={}, resolution_decisions={})
        return EntityScoreResult(closure, universe, 0, 0)
    aligned = [layout.align({"start": row.start, "end": row.end, "text": row.text})
               for row in candidates]
    features = core.exact_source_span(
        layout=layout, batch=batch, backbone=backbone,
        token_states=shared.token_states, sentence_states=shared.sentence_states,
        document_state=shared.document_state, candidate_encoder=core.candidate_span,
        rows=[(row, "ENTITY") for row in aligned])
    states = features.states
    device = states.device
    geometry = torch.stack([
        torch.stack((features.residuals[index, 0], features.residuals[index, 1],
                     states.new_tensor(min(row.end - row.start, 512) / 512),
                     states.new_tensor(float(row.cross_window))))
        for index, row in enumerate(aligned)]).unsqueeze(0)
    type_logits = core.task_modules["entity_mention"].typing(
        states.unsqueeze(0), geometry,
        torch.ones((1, len(candidates)), dtype=torch.bool, device=device))[0]
    type_log_probabilities = type_logits.log_softmax(dim=-1)
    typed = tuple(replace(candidate, entity_type=ENTITY_TYPES[int(type_logits[index].argmax())],
                          type_evidence=tuple(float(value) for value in type_log_probabilities[index]))
                  for index, candidate in enumerate(candidates))
    typed_universe = replace(universe, candidates=typed)
    origins = torch.tensor([[float(origin in row.origins) for origin in ("NER", "ROLE", "ASSERTOR")]
                            for row in typed], dtype=states.dtype, device=device)
    # Priority is scored for diagnostics; mandatory role reservation already happened before this head.
    priority = core.task_modules["entity_priority"](states, origins)
    if not torch.isfinite(priority).all():
        raise ValueError("non-finite Entity priority")
    pair_rows = tuple(combinations(range(len(typed)), 2))
    merge = {}
    document_state = shared.document_state[0]
    for start in range(0, len(pair_rows), pair_chunk_size):
        chunk = pair_rows[start:start + pair_chunk_size]
        indices = torch.tensor(chunk, dtype=torch.long, device=device)
        policy = torch.tensor([
            (float(typed[a].entity_type == typed[b].entity_type),
             float("ROLE" in typed[a].origins and "ROLE" in typed[b].origins),
             float(("ROLE" in typed[a].origins) != ("ROLE" in typed[b].origins)),
             min(abs(typed[a].start - typed[b].start) / max(len(layout.article.content), 1), 1.0))
            for a, b in chunk], dtype=states.dtype, device=device)
        logits = core.task_modules["entity_coreference"](states, indices, document_state, policy)
        if not torch.isfinite(logits).all():
            raise ValueError("non-finite Entity coreference score")
        merge.update({(typed[a].candidate_id, typed[b].candidate_id): bool(logits[index].argmax() == 1)
                      for index, (a, b) in enumerate(chunk)})
    preliminary = close_entity_identity(typed_universe, merge_decisions=merge,
                                        resolution_decisions={},
                                        accepted_evidence_ids=accepted_sources)
    id_to_index = {candidate.candidate_id: index for index, candidate in enumerate(typed)}
    entities = preliminary.entities
    entity_states = (torch.stack([states[[id_to_index[cid] for cid in row.candidate_ids]].mean(dim=0)
                                  for row in entities]) if entities else states.new_empty((0, states.shape[-1])))
    decisions: dict[str, str | None] = {}
    scored_role_pairs = 0
    for binding in universe.bindings:
        if (binding.status != "CANDIDATE" or
                (binding.evidence_id not in accepted_role_evidence and
                 binding.referential_state != "CONFIRMED" and binding.role != "ASSERTOR")):
            decisions[binding.evidence_id] = None
            continue
        # role의 exact source에서 생성된 후보만 endpoint가 될 수 있다. 이후 동일성으로
        # 확장된 alias는 같은 local Entity ID를 공유한다.
        candidate_ids = binding.candidate_ids
        entity_options = tuple(sorted({preliminary.candidate_to_entity[cid] for cid in candidate_ids}))
        entity_lookup = {row.local_id: index for index, row in enumerate(entities)}
        role_index = id_to_index[candidate_ids[0]]
        indices = torch.tensor([(0, entity_lookup[eid]) for eid in entity_options],
                               dtype=torch.long, device=device)
        if binding.role == "ASSERTOR":
            owner = statement_states.get(binding.owner_id)
            if owner is None:
                raise ValueError("Assertor owner Statement representation missing")
            source = states[role_index] + owner
            right = entity_states[indices[:, 1]]
            logits = core.task_modules["assertor_entity"](
                source.unsqueeze(0).expand_as(right), right, document_state)
        else:
            policy = torch.tensor([(float(binding.role == "ACTOR"), float(binding.role == "TARGET"),
                                    float(binding.role == "PLACE"), 1.0)
                                   for _ in entity_options], dtype=states.dtype, device=device)
            logits = core.task_modules["role_entity"](
                states[role_index].unsqueeze(0), entity_states, indices, document_state, policy)
        if not torch.isfinite(logits).all():
            raise ValueError("non-finite role Entity score")
        scored_role_pairs += len(entity_options)
        if binding.role == "ASSERTOR" and float(logits.max()) < assertor_resolution_threshold:
            decisions[binding.evidence_id] = None
            continue
        selected_entity = entity_options[int(logits.argmax())]
        decisions[binding.evidence_id] = next(cid for cid in candidate_ids
                                              if preliminary.candidate_to_entity[cid] == selected_entity)
    accepted_final = accepted_role_evidence | frozenset(
        evidence_id for evidence_id, choice in decisions.items()
        if choice is not None and bindings[evidence_id].role == "ASSERTOR")
    closure = close_entity_identity(typed_universe, merge_decisions=merge,
                                    resolution_decisions=decisions,
                                    accepted_evidence_ids=accepted_final)
    return EntityScoreResult(closure, typed_universe, len(pair_rows), scored_role_pairs)
