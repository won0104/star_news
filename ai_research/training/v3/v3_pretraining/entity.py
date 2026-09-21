"""검증된 train Gold의 role-derived Entity oracle 구조와 6번 pair loss.

Gold Entity ID는 이 adapter의 학습 target일 뿐 runtime candidate/local ID가 아니다.
source representation은 5번과 같은 한 backbone·공유 DCE lease에서 직접 모은다.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
import random

import torch
from torch.nn import functional as F

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from models.v3_pretraining.extraction_heads import ENTITY_TYPES
from runtime.v3_pretraining.entity_identity import EntityClosure, close_entity_identity
from runtime.v3_pretraining.entity_union import (EntityCandidateUniverse, EntitySourceEvidence,
                                                build_entity_candidates)
from training.v3_pretraining.targets import ArticleTargets, ValidatedGoldArticle


@dataclass(frozen=True, slots=True)
class OracleEntityStructure:
    evidence: tuple[EntitySourceEvidence, ...]
    universe: EntityCandidateUniverse
    gold_entity_by_candidate: dict[str, str]
    closure: EntityClosure
    role_gold_entity: dict[str, str | None]


def build_oracle_entity_structure(article: ValidatedGoldArticle,
                                  target: ArticleTargets, *,
                                  include_assertors: bool = False) -> OracleEntityStructure:
    """Gold 주입 구조 검사; ACTOR/TARGET exact endpoint 누락은 즉시 실패한다."""
    if article.split != "train" or article.raw.article_version_id != target.article_version_id:
        raise ValueError("oracle Entity structure requires joined train target")
    gold = article.annotations
    mentions = {row["mention_id"]: row for row in gold["entity_mentions"]}
    member_to_entity = {mid: cluster["entity_id"] for cluster in gold["entity_clusters"]
                        for mid in cluster["mention_ids"]}
    cluster_to_mentions = {cluster["entity_id"]: tuple(mentions[mid] for mid in cluster["mention_ids"])
                           for cluster in gold["entity_clusters"]}
    evidence = []
    for mention in gold["entity_mentions"]:
        span = mention["span"]
        evidence.append(EntitySourceEvidence("NER:" + mention["mention_id"], "NER",
                                              span["start"], span["end"], span["text"],
                                              mention["type"], 1.0,
                                              referent_hint=member_to_entity[mention["mention_id"]]))
    role_gold_entity = {}
    for role in target.roles:
        endpoint = role.entity_id
        if role.role in ("ACTOR", "TARGET") and endpoint is None:
            raise ValueError("Gold ACTOR/TARGET lacks exact Entity endpoint")
        if endpoint is None:
            state, type_hint = "SPAN_ONLY", None
        else:
            state = "CONFIRMED"
            members = cluster_to_mentions[endpoint]
            exact_types = {mention["type"] for mention in members
                           if mention["span"]["start"] == role.alignment.start
                           and mention["span"]["end"] == role.alignment.end}
            known_types = exact_types or {mention["type"] for mention in members}
            concrete = known_types - {"GENERIC"}
            type_hint = (next(iter(concrete)) if len(concrete) == 1 else
                         "GENERIC" if not concrete and "GENERIC" in known_types else None)
        evidence.append(EntitySourceEvidence(role.role_id, "ROLE", role.alignment.start,
                                              role.alignment.end, role.alignment.text,
                                              type_hint, 1.0, owner_id=role.event_id,
                                              role=role.role, referential_state=state,
                                              referent_hint=endpoint))
        role_gold_entity[role.role_id] = endpoint
    if include_assertors:
        for assertor in target.assertors:
            if assertor.alignment is None:
                continue
            endpoint = assertor.entity_id
            if endpoint is None:
                state, type_hint = "SPAN_ONLY", None
            else:
                state = "CONFIRMED"
                members = cluster_to_mentions[endpoint]
                exact_types = {mention["type"] for mention in members
                               if mention["span"]["start"] == assertor.alignment.start
                               and mention["span"]["end"] == assertor.alignment.end}
                known_types = exact_types or {mention["type"] for mention in members}
                concrete = known_types - {"GENERIC"}
                type_hint = (next(iter(concrete)) if len(concrete) == 1 else
                             "GENERIC" if not concrete and "GENERIC" in known_types else None)
            evidence_id = "ASSERTOR:" + assertor.statement_id
            evidence.append(EntitySourceEvidence(evidence_id, "ASSERTOR", assertor.alignment.start,
                                                  assertor.alignment.end, assertor.alignment.text,
                                                  type_hint, 1.0, owner_id=assertor.statement_id,
                                                  role="ASSERTOR", referential_state=state,
                                                  referent_hint=endpoint))
            role_gold_entity[evidence_id] = endpoint
    universe = build_entity_candidates(article.raw, evidence, budget=None,
                                       source_mode="GOLD_ORACLE_STRUCTURE")
    gold_by_candidate = {}
    for candidate in universe.candidates:
        endpoints = set()
        for evidence_id in candidate.evidence_ids:
            if evidence_id.startswith("NER:"):
                endpoints.add(member_to_entity[evidence_id.removeprefix("NER:")])
            else:
                endpoints.add(role_gold_entity[evidence_id])
        endpoints.discard(None)
        if len(endpoints) != 1:
            raise ValueError("oracle union merged conflicting Gold Entity endpoints")
        gold_by_candidate[candidate.candidate_id] = next(iter(endpoints))
    positive = {(a.candidate_id, b.candidate_id): True
                for a, b in combinations(universe.candidates, 2)
                if gold_by_candidate[a.candidate_id] == gold_by_candidate[b.candidate_id]}
    resolution = {}
    for binding in universe.bindings:
        endpoint = role_gold_entity[binding.evidence_id]
        if endpoint is None:
            resolution[binding.evidence_id] = None
            continue
        local = [candidate_id for candidate_id in binding.candidate_ids
                 if gold_by_candidate[candidate_id] == endpoint]
        choices = local or [candidate_id for candidate_id, gold_id in gold_by_candidate.items()
                            if gold_id == endpoint]
        if not choices:
            raise ValueError("Gold role endpoint has no unified Entity candidate")
        resolution[binding.evidence_id] = sorted(choices)[0]
    closure = close_entity_identity(universe, merge_decisions=positive,
                                    resolution_decisions=resolution,
                                    strict_gold_endpoints=True)
    for role in target.roles:
        actual = next(row for row in closure.endpoints if row.evidence_id == role.role_id)
        if (actual.start, actual.end, actual.text) != (role.alignment.start, role.alignment.end,
                                                        role.alignment.text):
            raise AssertionError("role source grounding changed during Entity closure")
    if include_assertors:
        endpoints = {row.evidence_id: row for row in closure.endpoints}
        for assertor in target.assertors:
            if assertor.alignment is None:
                continue
            actual = endpoints["ASSERTOR:" + assertor.statement_id]
            if (actual.start, actual.end, actual.text) != (assertor.alignment.start,
                                                           assertor.alignment.end,
                                                           assertor.alignment.text):
                raise AssertionError("Assertor source grounding changed during Entity closure")
            if assertor.entity_id is None and (actual.local_entity_id is not None or actual.status != "SPAN_ONLY"):
                raise AssertionError("unresolved Gold Assertor created an Entity edge")
            if assertor.entity_id is not None and actual.local_entity_id is None:
                raise AssertionError("resolved Gold Assertor endpoint was lost")
    return OracleEntityStructure(tuple(evidence), universe, gold_by_candidate, closure,
                                 role_gold_entity)


def _coref_pairs(structure: OracleEntityStructure, *, negative_limit: int,
                 seed: int) -> tuple[tuple[tuple[int, int], int], ...]:
    candidates = structure.universe.candidates
    rng = random.Random(int(sha256(f"{seed}:{structure.universe.content_sha256}:entity_coref".encode()).hexdigest()[:16], 16))
    positives = []
    negatives = []
    seen = 0
    for left, right in combinations(range(len(candidates)), 2):
        same = (structure.gold_entity_by_candidate[candidates[left].candidate_id] ==
                structure.gold_entity_by_candidate[candidates[right].candidate_id])
        if same:
            positives.append(((left, right), 1))
        else:
            seen += 1
            pair = ((left, right), 0)
            if len(negatives) < negative_limit:
                negatives.append(pair)
            else:
                slot = rng.randrange(seen)
                if slot < negative_limit:
                    negatives[slot] = pair
    return tuple(positives + sorted(negatives))


@dataclass(frozen=True, slots=True)
class EntityLossResult:
    losses: dict[str, torch.Tensor]
    candidates: int
    origin_cohorts: dict[str, int]
    gold_role_endpoints: int
    resolved_role_endpoints: int
    span_only_roles: int
    coref_positive_pairs: int
    coref_sampled_negative_pairs: int
    role_positive_pairs: int
    role_sampled_negative_pairs: int


class EntityGoldAdapter:
    def __init__(self, core: V3Core, *, negative_limit: int = 128,
                 chunk_size: int = 128) -> None:
        if any(task in core.unimplemented_tasks for task in ("entity_priority", "role_entity", "entity_coreference")):
            raise ValueError("stage 6 Entity heads are not registered")
        if negative_limit <= 0 or chunk_size <= 0:
            raise ValueError("pair sample/chunk sizes must be positive")
        self.core = core
        self.negative_limit = negative_limit
        self.chunk_size = chunk_size

    def loss(self, article: ValidatedGoldArticle, target: ArticleTargets,
             batch: ArticleBatch, backbone: BackboneOutput,
             shared: SharedForwardLease) -> EntityLossResult:
        if shared.closed or shared.token_states is None or shared.sentence_states is None or shared.document_state is None:
            raise RuntimeError("Entity Gold loss needs a live shared DCE lease")
        structure = build_oracle_entity_structure(article, target)
        universe = structure.universe
        candidates = universe.candidates
        aligned = [(target.layout.align({"start": row.start, "end": row.end, "text": row.text}), "ENTITY")
                   for row in candidates]
        features = self.core.exact_source_span(
            layout=target.layout, batch=batch, backbone=backbone,
            token_states=shared.token_states, sentence_states=shared.sentence_states,
            document_state=shared.document_state, candidate_encoder=self.core.candidate_span,
            rows=aligned)
        states = features.states
        device = states.device
        origins = torch.tensor([[float(origin in row.origins) for origin in ("NER", "ROLE", "ASSERTOR")]
                                for row in candidates], dtype=states.dtype, device=device)
        priority_logits = self.core.task_modules["entity_priority"](states, origins)
        priority_loss = F.softplus(-priority_logits).mean() if len(candidates) else shared.token_states.sum() * 0
        typed = [(position, ENTITY_TYPES.index(row.entity_type)) for position, row in enumerate(candidates)
                 if row.entity_type in ENTITY_TYPES]
        if typed:
            positions = torch.tensor([position for position, _ in typed], dtype=torch.long, device=device)
            selected = states.index_select(0, positions).unsqueeze(0)
            geometry = torch.stack([
                torch.stack((features.residuals[position, 0], features.residuals[position, 1],
                             states.new_tensor(min(candidates[position].end - candidates[position].start, 512) / 512),
                             states.new_tensor(float(aligned[position][0].cross_window))))
                for position, _ in typed]).unsqueeze(0)
            logits = self.core.task_modules["entity_mention"].typing(
                selected, geometry, torch.ones((1, len(typed)), dtype=torch.bool, device=device))[0]
            labels = torch.tensor([label for _, label in typed], dtype=torch.long, device=device)
            typing_loss = F.cross_entropy(logits, labels)
        else:
            typing_loss = priority_loss * 0
        pair_rows = _coref_pairs(structure, negative_limit=self.negative_limit,
                                 seed=self.core.config.seed)
        coref_losses = []
        for start in range(0, len(pair_rows), self.chunk_size):
            chunk = pair_rows[start:start + self.chunk_size]
            indices = torch.tensor([pair for pair, _ in chunk], dtype=torch.long, device=device)
            labels = torch.tensor([label for _, label in chunk], dtype=torch.long, device=device)
            policy = torch.tensor([
                (float(candidates[a].entity_type == candidates[b].entity_type),
                 float("ROLE" in candidates[a].origins and "ROLE" in candidates[b].origins),
                 float(("ROLE" in candidates[a].origins) != ("ROLE" in candidates[b].origins)),
                 min(abs(candidates[a].start - candidates[b].start) / max(len(article.raw.content), 1), 1.0))
                for (a, b), _ in chunk], dtype=states.dtype, device=device)
            logits = self.core.task_modules["entity_coreference"](states, indices,
                                                                    shared.document_state[0], policy)
            coref_losses.append(F.cross_entropy(logits, labels, reduction="sum"))
        coref_loss = sum(coref_losses) / len(pair_rows) if pair_rows else priority_loss * 0
        gold_entities = sorted({row["entity_id"] for row in article.annotations["entity_clusters"]})
        entity_index = {gold_id: index for index, gold_id in enumerate(gold_entities)}
        entity_states = torch.stack([states[[position for position, candidate in enumerate(candidates)
                                              if structure.gold_entity_by_candidate[candidate.candidate_id] == gold_id]].mean(dim=0)
                                     for gold_id in gold_entities])
        resolved_roles = [role for role in target.roles if role.entity_id is not None]
        role_index = {role.role_id: position for position, role in enumerate(resolved_roles)}
        role_states = torch.stack([states[next(position for position, candidate in enumerate(candidates)
                                               if role.role_id in candidate.evidence_ids)]
                                   for role in resolved_roles]) if resolved_roles else states.new_empty((0, states.shape[-1]))
        universe_pairs = target.pairs["role_entity"]
        sampled = list(universe_pairs.positive_pairs) + [
            (row.left_id, row.right_id) for row in universe_pairs.sample_negatives(
                limit=self.negative_limit, seed=self.core.config.seed,
                content_sha256=target.content_sha256)]
        role_losses = []
        for start in range(0, len(sampled), self.chunk_size):
            chunk = sampled[start:start + self.chunk_size]
            indices = torch.tensor([(role_index[role_id], entity_index[entity_id])
                                    for role_id, entity_id in chunk], dtype=torch.long, device=device)
            labels = torch.tensor([float(pair in universe_pairs.positive_pairs) for pair in chunk],
                                  dtype=states.dtype, device=device)
            policy = torch.tensor([
                (float(resolved_roles[role_index[role_id]].role == "ACTOR"),
                 float(resolved_roles[role_index[role_id]].role == "TARGET"),
                 float(resolved_roles[role_index[role_id]].role == "PLACE"), 1.0)
                for role_id, _ in chunk], dtype=states.dtype, device=device)
            logits = self.core.task_modules["role_entity"](role_states, entity_states,
                                                            indices, shared.document_state[0], policy)
            role_losses.append(F.binary_cross_entropy_with_logits(logits, labels,
                                                                   reduction="sum"))
        role_loss = sum(role_losses) / len(sampled) if sampled else priority_loss * 0
        losses = {"entity_priority": priority_loss, "entity_typing_union": typing_loss,
                  "entity_coreference": coref_loss, "role_entity": role_loss}
        if any(not torch.isfinite(value) for value in losses.values()):
            raise ValueError("Entity union loss is non-finite")
        origin_cohorts = {name: sum(("NER" in row.origins, "ROLE" in row.origins) == flags
                                    for row in candidates) for name, flags in
                          (("NER_ONLY", (True, False)), ("ROLE_ONLY", (False, True)),
                           ("BOTH", (True, True)))}
        resolved = sum(row.status in ("RESOLVED", "RESOLVED_TYPE_CONFLICT")
                       for row in structure.closure.endpoints
                       if row.role in ("ACTOR", "TARGET"))
        required = sum(role.role in ("ACTOR", "TARGET") for role in target.roles)
        if resolved != required:
            raise AssertionError("Gold ACTOR/TARGET endpoint disappeared")
        return EntityLossResult(losses, len(candidates), origin_cohorts, required,
                                resolved, sum(row.status == "SPAN_ONLY" for row in structure.closure.endpoints),
                                sum(label == 1 for _, label in pair_rows),
                                sum(label == 0 for _, label in pair_rows),
                                len(universe_pairs.positive_pairs),
                                len(sampled) - len(universe_pairs.positive_pairs))
