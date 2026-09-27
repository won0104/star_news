"""검증된 Gold의 Native typing과 unified mention identity supervision.

Gold Entity ID는 이 adapter의 학습 target일 뿐 runtime candidate/local ID가 아니다.
source representation은 5번과 같은 한 backbone·공유 DCE lease에서 직접 모은다.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import torch
from torch.nn import functional as F

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from models.v3_pretraining.extraction_heads import ENTITY_TYPES
from runtime.v3_pretraining.v23_features import native_states
from runtime.v3_pretraining.entity_identity import EntityClosure, close_entity_identity
from runtime.v3_pretraining.entity_union import (EntityCandidate, EntityCandidateUniverse,
                                                EntitySourceEvidence, RoleBinding)
from training.v3_pretraining.relation_evaluation import score_full_universe
from training.v3_pretraining.targets import ArticleTargets, ValidatedGoldArticle


@dataclass(frozen=True, slots=True)
class OracleEntityStructure:
    evidence: tuple[EntitySourceEvidence, ...]
    universe: EntityCandidateUniverse
    gold_entity_by_candidate: dict[str, str | None]
    closure: EntityClosure
    role_gold_entity: dict[str, str | None]


def build_oracle_entity_structure(article: ValidatedGoldArticle,
                                  target: ArticleTargets, *,
                                  include_assertors: bool = False) -> OracleEntityStructure:
    """Build the same unified mention identity as P3, with Gold labels only in oracle closure."""
    if (article.split not in ("train", "dev", "test") or
            article.raw.article_version_id != target.article_version_id):
        raise ValueError("oracle Entity structure requires a joined validated target")
    evidence: list[EntitySourceEvidence] = []
    role_to_mention = {role_id: row.mention_id for row in target.entity_mentions
                       for role_id in row.role_use_ids}
    if len(role_to_mention) != len(target.roles):
        raise ValueError("Gold ROLE use inventory differs from unified mentions")
    for mention in target.entity_mentions:
        if "NATIVE" in mention.origins:
            evidence.append(EntitySourceEvidence(
                "NER:" + mention.mention_id, "NER", mention.alignment.start,
                mention.alignment.end, mention.alignment.text, mention.entity_type,
                1.0, referent_hint=mention.gold_entity_id))
    role_gold_entity = {}
    role_bindings = []
    for role in target.roles:
        state = "CONFIRMED" if role.entity_id is not None else "SPAN_ONLY"
        evidence.append(EntitySourceEvidence(
            role.role_id, "ROLE", role.alignment.start, role.alignment.end,
            role.alignment.text, None, 1.0, owner_id=role.event_id,
            role=role.role, referential_state=state, referent_hint=role.entity_id))
        role_gold_entity[role.role_id] = role.entity_id
        role_bindings.append(RoleBinding(
            role.role_id, role.event_id, role.role, role.alignment.start,
            role.alignment.end, role.alignment.text,
            (role_to_mention[role.role_id],), state,
            "CANDIDATE" if role.entity_id is not None else "SPAN_ONLY"))
    assertor_bindings = []
    if include_assertors:
        for assertor in target.assertors:
            if assertor.alignment is None:
                continue
            evidence_id = "ASSERTOR:" + assertor.statement_id
            state = "CONFIRMED" if assertor.entity_id is not None else "SPAN_ONLY"
            evidence.append(EntitySourceEvidence(
                evidence_id, "ASSERTOR", assertor.alignment.start,
                assertor.alignment.end, assertor.alignment.text, None, 1.0,
                owner_id=assertor.statement_id, role="ASSERTOR",
                referential_state=state, referent_hint=assertor.entity_id))
            role_gold_entity[evidence_id] = assertor.entity_id
            assertor_bindings.append(RoleBinding(
                evidence_id, assertor.statement_id, "ASSERTOR",
                assertor.alignment.start, assertor.alignment.end,
                assertor.alignment.text, (), state,
                "CANDIDATE" if assertor.entity_id is not None else "SPAN_ONLY"))
    candidates = tuple(EntityCandidate(
        mention.mention_id, mention.alignment.start, mention.alignment.end,
        mention.alignment.text, mention.entity_type,
        tuple("NER" if origin == "NATIVE" else origin for origin in mention.origins),
        tuple(("NER:" + mention.mention_id,) if "NATIVE" in mention.origins else ()) +
        mention.role_use_ids, 1.0,
        "CONFIRMED" if mention.gold_entity_id is not None else "SPAN_ONLY",
        mention.gold_entity_id)
        for mention in target.entity_mentions)
    universe = EntityCandidateUniverse(
        article.raw.article_version_id, article.raw.content_sha256,
        candidates, tuple((*role_bindings, *assertor_bindings)), "READY", 0, 0, 0,
        "GOLD_ORACLE_STRUCTURE", "UNIFIED_MENTION_COREF_V1")
    gold_by_candidate = {row.mention_id: row.gold_entity_id
                         for row in target.entity_mentions}
    positive = {pair: True for pair in target.pairs["entity_coreference"].positive_pairs}
    resolution = {}
    for assertor in target.assertors if include_assertors else ():
        if assertor.alignment is None:
            continue
        evidence_id = "ASSERTOR:" + assertor.statement_id
        if assertor.entity_id is None:
            resolution[evidence_id] = None
            continue
        choices = [row for row in candidates
                   if gold_by_candidate[row.candidate_id] == assertor.entity_id]
        if not choices:
            raise ValueError("Gold Assertor endpoint has no unified Entity mention")
        resolution[evidence_id] = min(choices, key=lambda row: (
            (row.start, row.end) != (assertor.alignment.start,
                                      assertor.alignment.end),
            row.start, row.end, row.candidate_id)).candidate_id
    closure = close_entity_identity(
        universe, merge_decisions=positive, resolution_decisions=resolution,
        strict_gold_endpoints=True)
    endpoints = {row.evidence_id: row for row in closure.endpoints}
    for role in target.roles:
        actual = endpoints[role.role_id]
        if ((actual.start, actual.end, actual.text) !=
                (role.alignment.start, role.alignment.end, role.alignment.text) or
                actual.local_entity_id is None):
            raise AssertionError("ROLE mention or exact source coordinate was lost")
    if include_assertors:
        for assertor in target.assertors:
            if assertor.alignment is None:
                continue
            actual = endpoints["ASSERTOR:" + assertor.statement_id]
            if (actual.start, actual.end, actual.text) != (
                    assertor.alignment.start, assertor.alignment.end,
                    assertor.alignment.text):
                raise AssertionError("Assertor source grounding changed")
            if (assertor.entity_id is None and actual.local_entity_id is not None or
                    assertor.entity_id is not None and actual.local_entity_id is None):
                raise AssertionError("Gold Assertor resolution differs")
    return OracleEntityStructure(tuple(evidence), universe, gold_by_candidate,
                                 closure, role_gold_entity)


def _coref_pairs(target: ArticleTargets, *, negative_limit: int,
                 seed: int) -> tuple[tuple[tuple[int, int], int], ...]:
    """Gold pair labels: same known cluster MERGE, distinct known KEEP, unknown IGNORE."""
    universe = target.pairs["entity_coreference"]
    index = {mention.mention_id: position for position, mention in enumerate(target.entity_mentions)}
    if tuple(index) != universe.left_ids or universe.negative_authority != "DISTINCT_KNOWN_GOLD_ENTITY_IDS_V1":
        raise ValueError("unified Entity mention and supervised pair authority differ")
    positives = [((index[a], index[b]), 1) for a, b in sorted(universe.positive_pairs)]
    negatives = [((index[row.left_id], index[row.right_id]), 0)
                 for row in universe.sample_negatives(
                     limit=negative_limit, seed=seed,
                     content_sha256=target.content_sha256)]
    return tuple(positives + negatives)


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


class EntityGoldAdapter:
    """Native typing and P3 unified mention coreference share one Gold encoding."""

    def __init__(self, core: V3Core, *, negative_limit: int = 128,
                 chunk_size: int = 128, extraction_profile: str = "V3_WINDOW") -> None:
        if "entity_coreference" in core.unimplemented_tasks:
            raise ValueError("Entity heads are not registered")
        if negative_limit <= 0 or chunk_size <= 0:
            raise ValueError("pair sample/chunk sizes must be positive")
        if extraction_profile not in ("V3_WINDOW", "V23_BASELINE"):
            raise ValueError("unknown Entity typing source profile")
        self.core = core
        self.negative_limit = negative_limit
        self.chunk_size = chunk_size
        self.extraction_profile = extraction_profile

    def _encode(self, target: ArticleTargets, batch: ArticleBatch,
                backbone: BackboneOutput, shared: SharedForwardLease,
                mentions):
        aligned = [(row.alignment, "ENTITY") for row in mentions]
        features = self.core.exact_source_span(
            layout=target.layout, batch=batch, backbone=backbone,
            token_states=shared.token_states, sentence_states=shared.sentence_states,
            document_state=shared.document_state,
            candidate_encoder=self.core.candidate_span, rows=aligned)
        return aligned, features

    def phase1_typing_union_loss(self, article: ValidatedGoldArticle,
                                 target: ArticleTargets, batch: ArticleBatch,
                                 backbone: BackboneOutput,
                                 shared: SharedForwardLease) -> tuple[torch.Tensor, int]:
        """Phase 1 types only exact Native Entity mentions, never an UNKNOWN ROLE."""
        if shared.closed or shared.token_states is None:
            raise RuntimeError("Entity typing needs a live shared DCE lease")
        mentions = tuple(row for row in target.entity_mentions if "NATIVE" in row.origins)
        if not mentions:
            return shared.token_states.sum() * 0, 0
        aligned, features = self._encode(target, batch, backbone, shared, mentions)
        return self._typing_loss(mentions, aligned, features, features.states,
                                 shared, batch, backbone, target), len(mentions)

    def _typing_loss(self, mentions, aligned, features, states,
                     shared, batch, backbone, target) -> torch.Tensor:
        typed = [(position, ENTITY_TYPES.index(row.entity_type))
                 for position, row in enumerate(mentions)
                 if "NATIVE" in row.origins and row.entity_type in ENTITY_TYPES]
        if not typed:
            return shared.token_states.sum() * 0
        device = states.device
        positions = torch.tensor([position for position, _ in typed],
                                 dtype=torch.long, device=device)
        selected = states.index_select(0, positions).unsqueeze(0)
        geometry = torch.stack([
            torch.stack((features.residuals[position, 0], features.residuals[position, 1],
                         states.new_tensor(min(mentions[position].alignment.end -
                                               mentions[position].alignment.start, 512) / 512),
                         states.new_tensor(float(aligned[position][0].cross_window))))
            for position, _ in typed]).unsqueeze(0)
        if self.extraction_profile == "V23_BASELINE":
            native, native_geometry, _ = native_states(
                kind="ENTITY", layout=target.layout, batch=batch,
                backbone=backbone, shared=shared, core=self.core,
                rows=[(mentions[position].alignment.start,
                       mentions[position].alignment.end, None)
                      for position, _ in typed],
                fallback_states=selected[0], fallback_geometry=geometry[0])
            selected, geometry = native.unsqueeze(0), native_geometry.unsqueeze(0)
        logits = self.core.task_modules["entity_mention"].typing(
            selected, geometry,
            torch.ones((1, len(typed)), dtype=torch.bool, device=device))[0]
        labels = torch.tensor([label for _, label in typed], dtype=torch.long,
                              device=device)
        return (F.softplus(-logits.gather(1, labels[:, None]).squeeze(1)).mean()
                if self.extraction_profile == "V23_BASELINE" else
                F.cross_entropy(logits, labels))

    @staticmethod
    def _pair_policy(mentions, pairs, *, text_length: int, states: torch.Tensor):
        return torch.tensor([
            (float(mentions[a].entity_type is not None and
                   mentions[a].entity_type == mentions[b].entity_type),
             float("ROLE" in mentions[a].origins and "ROLE" in mentions[b].origins),
             float(("ROLE" in mentions[a].origins) != ("ROLE" in mentions[b].origins)),
             min(abs(mentions[a].alignment.start - mentions[b].alignment.start) /
                 max(text_length, 1), 1.0))
            for a, b in pairs], dtype=states.dtype, device=states.device)

    def loss(self, article: ValidatedGoldArticle, target: ArticleTargets,
             batch: ArticleBatch, backbone: BackboneOutput,
             shared: SharedForwardLease, *,
             channels: frozenset[str] | None = None) -> EntityLossResult:
        """Run only requested heads; UNKNOWN ROLE pairs contribute no implicit negative."""
        allowed = frozenset(("entity_typing_union", "entity_coreference"))
        requested = allowed if channels is None else channels
        if not requested or not requested <= allowed:
            raise ValueError("unknown Entity Gold loss channel")
        if (shared.closed or shared.token_states is None or
                shared.sentence_states is None or shared.document_state is None):
            raise RuntimeError("Entity Gold loss needs a live shared DCE lease")
        mentions = target.entity_mentions
        native_mentions = tuple(row for row in mentions if "NATIVE" in row.origins)
        zero = shared.token_states.sum() * 0
        losses = {name: zero for name in allowed}
        pair_rows = ()
        encoded_mentions = mentions if "entity_coreference" in requested else native_mentions
        if encoded_mentions:
            aligned, features = self._encode(target, batch, backbone, shared, encoded_mentions)
            states = features.states
            native_indices = [index for index, row in enumerate(encoded_mentions)
                              if "NATIVE" in row.origins]
            native_states_encoded = states[native_indices]
            if "entity_typing_union" in requested and native_indices:
                native_rows = tuple(encoded_mentions[index] for index in native_indices)
                native_aligned = [aligned[index] for index in native_indices]
                native_features = SimpleNamespace(residuals=features.residuals[native_indices])
                losses["entity_typing_union"] = self._typing_loss(
                    native_rows, native_aligned, native_features, native_states_encoded,
                    shared, batch, backbone, target)
            if "entity_coreference" in requested:
                pair_rows = _coref_pairs(target, negative_limit=self.negative_limit,
                                         seed=self.core.config.seed)
                total = zero
                for start in range(0, len(pair_rows), self.chunk_size):
                    chunk = pair_rows[start:start + self.chunk_size]
                    indices = torch.tensor([pair for pair, _ in chunk],
                                           dtype=torch.long, device=states.device)
                    labels = torch.tensor([label for _, label in chunk],
                                          dtype=torch.long, device=states.device)
                    policy = self._pair_policy(mentions, [pair for pair, _ in chunk],
                                               text_length=len(article.raw.content), states=states)
                    logits = self.core.task_modules["entity_coreference"](
                        states, indices, shared.document_state[0], policy)
                    total = total + F.cross_entropy(logits, labels, reduction="sum")
                losses["entity_coreference"] = total / len(pair_rows) if pair_rows else zero
        required = sum(role.role in ("ACTOR", "TARGET") for role in target.roles)
        attached = {role_id for mention in mentions for role_id in mention.role_use_ids}
        if any(role.role in ("ACTOR", "TARGET") and role.role_id not in attached
               for role in target.roles):
            raise AssertionError("Gold ACTOR/TARGET endpoint disappeared")
        cohorts = {
            "NER_ONLY": sum(row.origins == ("NATIVE",) for row in mentions),
            "ROLE_ONLY": sum(row.origins == ("ROLE",) for row in mentions),
            "BOTH": sum(row.origins == ("NATIVE", "ROLE") for row in mentions),
        }
        if any(not torch.isfinite(value) for value in losses.values()):
            raise ValueError("Entity loss is non-finite")
        return EntityLossResult(losses, len(mentions), cohorts, required, required,
                                sum(role.entity_id is None for role in target.roles),
                                sum(label == 1 for _, label in pair_rows),
                                sum(label == 0 for _, label in pair_rows))

    @torch.no_grad()
    def evaluate_full_universe(self, article: ValidatedGoldArticle,
                               target: ArticleTargets, batch: ArticleBatch,
                               backbone: BackboneOutput,
                               shared: SharedForwardLease) -> dict[str, object]:
        """Score supervised unified Entity pairs; unresolved pair labels stay IGNORE."""
        if article.split not in ("dev", "test") or self.core.training:
            raise ValueError("Entity selection evaluation requires eval-mode dev/test Gold")
        mentions = target.entity_mentions
        if not mentions:
            return {"entity_coreference": score_full_universe(
                article_id=article.raw.article_id,
                universe=target.pairs["entity_coreference"],
                chunk_size=self.chunk_size,
                score_chunk=lambda _chunk: shared.token_states.new_empty((0,)))}
        _, features = self._encode(target, batch, backbone, shared, mentions)
        states = features.states
        index = {row.mention_id: position for position, row in enumerate(mentions)}

        def score_coref(chunk):
            pairs = [(index[row.left_id], index[row.right_id]) for row in chunk]
            indices = torch.tensor(pairs, dtype=torch.long, device=states.device)
            policy = self._pair_policy(mentions, pairs,
                                       text_length=len(article.raw.content), states=states)
            logits = self.core.task_modules["entity_coreference"](
                states, indices, shared.document_state[0], policy)
            return logits[:, 1] - logits[:, 0]

        return {"entity_coreference": score_full_universe(
            article_id=article.raw.article_id,
            universe=target.pairs["entity_coreference"], chunk_size=self.chunk_size,
            score_chunk=score_coref)}
