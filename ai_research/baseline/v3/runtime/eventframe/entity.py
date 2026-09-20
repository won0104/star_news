"""Deterministic nested-capable Entity Mention candidate enumeration and inference."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from types import SimpleNamespace
import time

import torch

from models.contracts import SPAN_KINDS
from .candidate_iteration import (
    iter_bounded_span_candidates, iter_candidate_chunks, iter_span_candidates,
)
from .entity_consolidation import EntityBoundaryPolicy, close_entity_mentions
from ..candidate_routing.span_budget import (
    EntitySpanBoundedContract, Lane, selected_boundaries, token_pairs,
)
from ..candidate_routing.span_projection import (
    ChunkProjectionReuse, ProjectionIdentity,
)
from ..lifecycle import StageScope
from .models import ENTITY_TYPES


def enumerate_entity_candidates(
    prepared,
    *,
    max_token_width: int,
    max_character_width: int,
):
    """Enumerate contiguous character spans over deterministic covering tokens.

    Character starts/ends inside a tokenizer token are retained. This makes the
    universe strictly richer than token-boundary spans without changing tokenization.
    """

    return [
        {**row, "text": prepared.article.content[row["char_start"]:row["char_end"]]}
        for row in iter_span_candidates(
            prepared, max_token_width=max_token_width,
            max_character_width=max_character_width, character_boundaries=True,
        )
    ]


def pack_entity_candidates(rows, device):
    indices = [
        [row["sentence_index"], row["token_start"], row["token_end"]]
        for row in rows
    ]
    return (
        SimpleNamespace(
            span_indices=torch.tensor(indices, dtype=torch.long, device=device).reshape(1, -1, 3),
            span_kind_ids=torch.full(
                (1, len(rows)), SPAN_KINDS.index("ENTITY"), dtype=torch.long, device=device
            ),
            span_mask=torch.ones(1, len(rows), dtype=torch.bool, device=device),
        ),
        torch.tensor(
            [[row["boundary_features"] for row in rows]],
            dtype=torch.float32,
            device=device,
        ).reshape(1, len(rows), 4),
    )


def entity_prediction_id(article_id, char_start, char_end, entity_type):
    identity = f"{article_id}|{char_start}|{char_end}|{entity_type}".encode("utf-8")
    return "ENT-" + sha256(identity).hexdigest()[:20]


def _overlap(left, right) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])


def _strict_subspan(left, right) -> bool:
    return right[0] <= left[0] and left[1] <= right[1] and left != right


def _source_token_or_zero(states, mask, sentence_index: int, token_index: int):
    if token_index < 0 or token_index >= states.shape[2] or not bool(
        mask[0, sentence_index, token_index]
    ):
        return states.new_zeros(states.shape[-1])
    return states[0, sentence_index, token_index]


class FixedEntityMentionRuntime:
    """Inference-only stage ③ with optional non-destructive stage ⑦ metadata."""

    def __init__(
        self,
        model,
        config,
        checkpoint_sha,
        *,
        priority_model=None,
        priority_config=None,
        priority_checkpoint_sha=None,
        boundary_policy: EntityBoundaryPolicy | None = None,
    ):
        self.model = model
        self.config = config
        self.checkpoint_sha = checkpoint_sha
        self.priority_model = priority_model
        self.priority_config = priority_config or {}
        self.priority_checkpoint_sha = priority_checkpoint_sha
        self.boundary_policy = boundary_policy
        # Offline request-scoped observer only. The production result never owns accepted tensors.
        self.accepted_competition_audit = None

    def _priority_decisions(self, accepted):
        started = time.perf_counter()
        features = []
        for index, item in enumerate(accepted):
            mention = item["mention"]
            span = (mention["char_start"], mention["char_end"])
            same_sentence = [
                other
                for other_index, other in enumerate(accepted)
                if other_index != index
                and other["mention"]["sentence_index"] == mention["sentence_index"]
            ]
            same_type = [
                other
                for other in same_sentence
                if other["mention"]["entity_type"] == mention["entity_type"]
            ]

            def maximum(rows):
                return max((row["mention"]["score"] for row in rows), default=0.0)

            subspans = [
                other
                for other in same_type
                if _strict_subspan(
                    (other["mention"]["char_start"], other["mention"]["char_end"]),
                    span,
                )
            ]
            superspans = [
                other
                for other in same_type
                if _strict_subspan(
                    span,
                    (other["mention"]["char_start"], other["mention"]["char_end"]),
                )
            ]
            overlaps = [
                other
                for other in same_sentence
                if _overlap(
                    span,
                    (other["mention"]["char_start"], other["mention"]["char_end"]),
                )
                and (
                    other["mention"]["char_start"], other["mention"]["char_end"]
                )
                != span
            ]
            same_boundary_other = [
                other
                for other in same_sentence
                if (
                    other["mention"]["char_start"], other["mention"]["char_end"]
                )
                == span
                and other["mention"]["entity_type"] != mention["entity_type"]
            ]
            near = [
                other
                for other in same_sentence
                if (
                    other["mention"]["char_start"], other["mention"]["char_end"]
                )
                != span
                and (
                    abs(other["mention"]["char_start"] - span[0]) <= 2
                    or abs(other["mention"]["char_end"] - span[1]) <= 2
                )
            ]
            competition = item["base"].new_tensor(
                [
                    maximum(subspans),
                    maximum(superspans),
                    maximum(overlaps),
                    maximum(same_boundary_other),
                    maximum(near),
                ]
            )
            # Training cached detached features as float16. Reproduce that fixed
            # feature boundary before scoring with the float32 release verifier.
            features.append(torch.cat((item["base"], competition)).to(torch.float16).float())

        if not features:
            return (), {
                "stage": "⑦ 후보 제한부",
                "component": "Entity Candidate Soft Priority",
                "checkpoint_sha": self.priority_checkpoint_sha,
                "input_count": 0,
                "candidate_count": 0,
                "output_count": 0,
                "tier_counts": {"TIER1_PROMOTED": 0, "TIER2_EVIDENCE_ONLY": 0},
                "warnings": ["Priority metadata only; no Entity evidence was deleted."],
                "elapsed_seconds": time.perf_counter() - started,
            }

        matrix = torch.stack(features)
        scores = []
        batch_size = int(self.priority_config.get("verifier_batch_size", 2048))
        for offset in range(0, len(matrix), batch_size):
            scores.extend(
                torch.sigmoid(self.priority_model(matrix[offset : offset + batch_size]))
                .detach()
                .cpu()
                .tolist()
            )
        threshold = float(self.priority_config["threshold"])
        decisions = []
        tier_counts = {"TIER1_PROMOTED": 0, "TIER2_EVIDENCE_ONLY": 0}
        for item, score in zip(accepted, scores):
            tier = "TIER1_PROMOTED" if score >= threshold else "TIER2_EVIDENCE_ONLY"
            tier_counts[tier] += 1
            decisions.append(
                {
                    "entity_prediction_id": item["mention"]["prediction_id"],
                    "promotion_score": float(score),
                    "priority_tier": tier,
                    "verifier_checkpoint_sha": self.priority_checkpoint_sha,
                    "runtime_config_id": self.priority_config["runtime_config_id"],
                    "responsibility": "⑦ 후보 제한부",
                }
            )
        return tuple(decisions), {
            "stage": "⑦ 후보 제한부",
            "component": "Entity Candidate Soft Priority",
            "checkpoint_sha": self.priority_checkpoint_sha,
            "input_count": len(accepted),
            "candidate_count": len(accepted),
            "output_count": len(decisions),
            "tier_counts": tier_counts,
            "hard_deletion_authorized": False,
            "hard_identity_eligibility_gate_authorized": False,
            "warnings": [
                "TIER2 is preserved raw evidence, not a semantic negative or deletion.",
                "TIER2 rescue is deferred; no pair expansion was executed.",
            ],
            "elapsed_seconds": time.perf_counter() - started,
        }

    def _score_chunk(self, prepared, backbone, batch, context, layer12,
                     chunk, threshold, device, diagnostic_sink=None,
                     projection_identity: ProjectionIdentity | None = None):
        """scorer tensor의 참조는 호출 경계에서 끝내고 승인된 작은 값만 반환한다."""

        accepted = []
        priority_feature_seconds = 0.0
        projection_hits = projection_misses = 0
        with StageScope() as stage:
            packed, boundary = pack_entity_candidates(chunk, device)
            stage.own(packed)
            stage.own(boundary)
            if projection_identity is None:
                span_states = stage.own(
                    self.model.candidate_span_encoder.forward_runtime_direct(
                        backbone, context, packed, batch.source_token_mask
                    )[0]
                )
            else:
                cache = ChunkProjectionReuse(projection_identity)
                try:
                    unique, row_indices, projection_hits, projection_misses = (
                        cache.select_rows(chunk, projection_identity)
                    )
                    unique_packed, _ = pack_entity_candidates(unique, device)
                    stage.own(unique_packed)
                    projected = stage.own(
                        self.model.candidate_span_encoder.forward_runtime_direct(
                            backbone, context, unique_packed, batch.source_token_mask
                        )[0]
                    )
                    lookup = stage.own(torch.tensor(row_indices, dtype=torch.long,
                                                    device=device))
                    span_states = stage.own(projected.index_select(0, lookup))
                finally:
                    cache.close()
            logits = stage.own(self.model.head(
                span_states.unsqueeze(0), boundary, packed.span_mask
            )[0])
            scores = stage.own(torch.sigmoid(logits))
            for row_index, row in enumerate(chunk):
                if diagnostic_sink is not None and diagnostic_sink.level.value == "FULL":
                    diagnostic_sink.record("candidate", {
                        "component": "entity_mentions",
                        "article_version_id": prepared.article.article_version_id,
                        "sentence_index": row["sentence_index"],
                        "char_start": row["char_start"],
                        "char_end": row["char_end"],
                        "type_scores": [float(value) for value in scores[row_index]],
                    })
                for type_index, entity_type in enumerate(ENTITY_TYPES):
                    score = float(scores[row_index, type_index])
                    if score < threshold:
                        continue
                    base = None
                    if self.priority_model is not None:
                        feature_started = time.perf_counter()
                        other_score = max(
                            float(scores[row_index, other])
                            for other in range(len(ENTITY_TYPES)) if other != type_index
                        )
                        left = _source_token_or_zero(
                            layer12, batch.source_token_mask, row["sentence_index"],
                            row["token_start"] - 1,
                        )
                        right = _source_token_or_zero(
                            layer12, batch.source_token_mask, row["sentence_index"],
                            row["token_end"],
                        )
                        numeric = span_states.new_tensor([
                            float(logits[row_index, type_index]), score, other_score,
                            *row["boundary_features"],
                            (row["token_end"] - row["token_start"])
                            / float(self.config["max_span_width_tokens"]),
                            (row["char_end"] - row["char_start"])
                            / float(self.config["max_span_width_characters"]),
                        ])
                        # 원 accepted set의 priority 소비가 끝날 때까지 독립된 작은 tensor만 유지한다.
                        base = torch.cat((span_states[row_index], left, right, numeric)).detach()
                        priority_feature_seconds += time.perf_counter() - feature_started
                    mention = {
                        "prediction_id": entity_prediction_id(
                            prepared.article.article_id, row["char_start"],
                            row["char_end"], entity_type,
                        ),
                        "article_id": prepared.article.article_id,
                        "sentence_id": row["sentence_id"],
                        "sentence_index": row["sentence_index"],
                        "char_start": row["char_start"],
                        "char_end": row["char_end"],
                        "token_start": row["token_start"],
                        "token_end": row["token_end"],
                        "text": prepared.grounding_text(
                            row["char_start"], row["char_end"], row["sentence_index"],
                        ),
                        "entity_type": entity_type,
                        "score": score,
                        "source": "SPAN_NATIVE_MULTILABEL",
                        "checkpoint_sha": self.checkpoint_sha,
                        "runtime_config_id": self.config["runtime_config_id"],
                        "resolution_status": "NOT_RESOLVED",
                        "provenance": {
                            "responsibility": "③ 구간 추출부",
                            "representation_layer": 12,
                            "nested_capable": True,
                            "entity_coreference_executed": False,
                        },
                    }
                    accepted.append({"mention": mention, "base": base})
        return accepted, priority_feature_seconds, projection_hits, projection_misses

    @torch.inference_mode()
    def run(self, prepared, backbone, *, diagnostic_sink=None,
            application_profiler=None, routing_observer=None,
            bounded_policy: EntitySpanBoundedContract | None = None):
        started = time.perf_counter()
        if bounded_policy is not None:
            if not isinstance(bounded_policy, EntitySpanBoundedContract):
                raise TypeError("Entity span policy must be pinned T14/C6 contract")
            bounded_policy.validate()
            if (self.checkpoint_sha != bounded_policy.fine_checkpoint_sha256
                or self.priority_checkpoint_sha
                   != bounded_policy.priority_checkpoint_sha256
                or self.priority_model is None or self.boundary_policy is None
                or float(self.config["threshold"]) != 0.7
                or float(self.priority_config["threshold"]) != 0.3
                or int(self.config["max_span_width_tokens"]) != 20
                or int(self.config["max_span_width_characters"]) != 56
                or int(self.config["candidate_chunk_size"]) != 256
                or tuple(self.config.get("entity_types", ENTITY_TYPES))
                   != tuple(ENTITY_TYPES)):
                raise ValueError("bounded Entity requires frozen fine/priority contracts")
            if self.accepted_competition_audit is not None:
                raise ValueError("broad accepted competition hook is reference-only")
        device = next(self.model.parameters()).device
        batch = prepared.batch.to(device)
        context = self.model.encode_context(batch, backbone)
        context_seconds = time.perf_counter() - started
        cheap_seconds = 0.0
        budget_census = None
        projection_identity = None
        if bounded_policy is None:
            candidates = iter_span_candidates(
                prepared,
                max_token_width=int(self.config["max_span_width_tokens"]),
                max_character_width=int(self.config["max_span_width_characters"]),
                character_boundaries=True,
            )
        else:
            cheap_started = time.perf_counter()
            lane = Lane("ENTITY", int(self.config["max_span_width_tokens"]),
                        int(self.config["max_span_width_characters"]),
                        int(self.config["candidate_chunk_size"]), len(ENTITY_TYPES))
            pairs, broad = token_pairs(prepared, lane)
            boundaries, cheap = selected_boundaries(
                prepared, pairs, lane, bounded_policy.budget
            )
            if broad["candidate_count"] and not cheap.get("fine_candidate_rows", 0):
                raise RuntimeError("Entity bounded selector returned empty nonempty article")
            candidates = iter_bounded_span_candidates(
                prepared, boundaries, max_token_width=lane.max_tokens,
                max_character_width=lane.max_chars,
            )
            cheap_seconds = time.perf_counter() - cheap_started
            budget_census = {**cheap,
                "policy_id": bounded_policy.policy_id,
                "policy_config_sha256": bounded_policy.config_sha256,
                "selector_source_sha256": bounded_policy.selector_sha256,
                "broad_structural_candidate_count": broad["candidate_count"],
                "cheap_visited_count": (
                    cheap["token_span_cheaply_ranked"]
                    + cheap["cheap_boundary_position_visited"]
                    + cheap["cheap_character_cross_pair_visited"]),
                "boundary_candidate_retained_count": cheap.get("fine_candidate_rows", 0),
                "cheap_selection_seconds": cheap_seconds,
                "entity_context_encoding_seconds": context_seconds,
            }
            projection_identity = ProjectionIdentity(
                str(prepared.article.article_version_id),
                sha256(prepared.article.content.encode("utf-8")).hexdigest(),
                bounded_policy.policy_id, bounded_policy.config_sha256, 12,
                "ENTITY", id(backbone), id(context),
                id(self.model.candidate_span_encoder), self.checkpoint_sha,
                str(device), str(next(self.model.parameters()).dtype),
            )
            pairs.clear()  # cheap token/window rank arrays have no later consumer.
            boundaries = {}  # iterator owns selected options until scoring ends.
        scorer_started = time.perf_counter() if bounded_policy is not None else None
        threshold = float(self.config["threshold"])
        chunk_size = int(self.config.get("candidate_chunk_size", 4096))
        accepted = []
        candidate_count = 0
        width_census = Counter() if routing_observer is not None else None
        sentence_census = Counter() if routing_observer is not None else None
        character_variant_count = 0
        priority_feature_seconds = 0.0
        projection_hits = projection_misses = 0
        projected_keys = set() if bounded_policy is not None else None
        layer12 = backbone.layer(12)
        for chunk in iter_candidate_chunks(candidates, chunk_size):
            candidate_count += len(chunk)
            if projected_keys is not None:
                projected_keys.update(
                    (row["sentence_index"], row["token_start"], row["token_end"])
                    for row in chunk
                )
            if routing_observer is not None:
                for row in chunk:
                    width_census[int(row["token_end"]) - int(row["token_start"])] += 1
                    sentence_census[int(row["sentence_index"])] += 1
                    character_variant_count += int(
                        row["boundary_features"][0] != 0.0
                        or row["boundary_features"][1] != 1.0
                    )
            selected, feature_seconds, hits, misses = self._score_chunk(
                prepared, backbone, batch, context, layer12, chunk, threshold,
                device, diagnostic_sink, projection_identity,
            )
            accepted.extend(selected)
            priority_feature_seconds += feature_seconds
            projection_hits += hits
            projection_misses += misses
        if budget_census is not None:
            if candidate_count != budget_census["boundary_candidate_retained_count"]:
                raise RuntimeError("bounded selector rows differ from fine scorer input")
            budget_census.update({
                "fine_scored_candidate_count": candidate_count,
                "accepted_entity_count": len(accepted),
                "budget_exhaustion_count": (
                    budget_census["broad_structural_candidate_count"] - candidate_count),
                "unique_expensive_token_span_projection_count": len(projected_keys),
                "projection_reuse_hit_count": projection_hits,
                "projection_reuse_miss_count": projection_misses,
                "projection_cache_scope": "SELECTED_CHUNK_ONLY",
                "expensive_entity_representation_scoring_seconds": (
                    time.perf_counter() - scorer_started),
            })
            projected_keys.clear()
            # The selected generator owns boundary alternatives only through the
            # last fine chunk; its context/encoder inputs do not reach priority.
            del candidates, context, layer12, batch, projection_identity
        accepted.sort(
            key=lambda item: (
                item["mention"]["sentence_index"],
                item["mention"]["char_start"],
                item["mention"]["char_end"],
                item["mention"]["entity_type"],
            )
        )
        scoring_finished = (time.perf_counter() if application_profiler is not None
                            or bounded_policy is not None else None)
        raw_elapsed = time.perf_counter() - started - priority_feature_seconds
        priority_error = None
        priority_trace = None
        decisions = ()
        if self.priority_model is not None:
            try:
                decisions, priority_trace = self._priority_decisions(accepted)
                priority_trace = {
                    **priority_trace,
                    "input_feature_seconds": priority_feature_seconds,
                    "elapsed_seconds": (
                        priority_feature_seconds + priority_trace["elapsed_seconds"]
                    ),
                }
            except Exception as error:  # raw stage ③ must survive any stage ⑦ failure
                priority_error = str(error)
                priority_trace = {
                    "stage": "⑦ 후보 제한부",
                    "component": "Entity Candidate Soft Priority",
                    "checkpoint_sha": self.priority_checkpoint_sha,
                    "input_count": len(accepted),
                    "candidate_count": len(accepted),
                    "output_count": 0,
                    "tier_counts": {},
                    "hard_deletion_authorized": False,
                    "warnings": ["Priority scoring failed; all raw Entity evidence was preserved."],
                    "input_feature_seconds": priority_feature_seconds,
                    "elapsed_seconds": priority_feature_seconds,
                }
        if bounded_policy is not None and priority_error is not None:
            raise RuntimeError(f"bounded Entity priority failed: {priority_error}")
        if self.accepted_competition_audit is not None:
            if priority_error is not None or self.boundary_policy is None:
                raise RuntimeError("accepted competition audit requires frozen priority and closure")
            self.accepted_competition_audit(
                prepared, accepted, decisions, candidate_count, self
            )
        accepted_before_closure = len(accepted)
        mentions = tuple(item["mention"] for item in accepted)
        # priority는 원 accepted set 전체의 sub/super/overlap feature를 이미 소비했다.
        accepted.clear()  # 후보별 base tensor는 이 판단 이후 live inventory에 남지 않는다.
        rescue_only = ()
        closure_trace = None
        if self.boundary_policy is not None:
            mentions, decisions, rescue_only, closure_trace = close_entity_mentions(
                prepared.article.article_version_id, mentions, decisions,
                policy=self.boundary_policy, diagnostic_sink=diagnostic_sink,
            )
        if budget_census is not None:
            budget_census.update({
                "TIER1_count": priority_trace["tier_counts"].get("TIER1_PROMOTED", 0),
                "TIER2_count": priority_trace["tier_counts"].get("TIER2_EVIDENCE_ONLY", 0),
                "canonical_PRIMARY_count": len(mentions),
                "RESCUE_ONLY_count": len(rescue_only),
                "priority_closure_seconds": time.perf_counter() - scoring_finished,
            })
        if routing_observer is not None:
            census_record = {
                "lane": "ENTITY",
                "article_version_id": prepared.article.article_version_id,
                "candidate_count": candidate_count,
                "character_variant_count": character_variant_count,
                "token_width_counts": dict(sorted(width_census.items())),
                "sentence_count": len(sentence_census),
                "max_candidates_per_sentence": max(sentence_census.values(), default=0),
                "accepted_before_boundary_count": accepted_before_closure,
                "canonical_primary_count": len(mentions),
                "rescue_only_count": len(rescue_only),
                "canonical_type_counts": dict(sorted(Counter(
                    row["entity_type"] for row in mentions
                ).items())),
            }
            if bounded_policy is None:
                routing_observer.observe_reference_scalar("phase_b_census", census_record)
            else:
                routing_observer.observe_bounded_scalar("phase_b_bounded_census",
                                                        {**census_record, **budget_census})
        if application_profiler is not None:
            application_profiler.add_seconds(
                "entity_candidate_enumeration_scoring",
                scoring_finished - started - cheap_seconds,
            )
            if bounded_policy is not None:
                application_profiler.add_seconds("entity_cheap_selection", cheap_seconds)
            application_profiler.stop(
                "entity_priority_boundary_consolidation", scoring_finished
            )
        trace = {
            "stage": "③ 구간 추출부",
            "component": "Nested-capable Entity Mention span classifier",
            "checkpoint_sha": self.checkpoint_sha,
            "input_count": sum(len(sentence["tokens"]) for sentence in prepared.sentences),
            "candidate_count": candidate_count,
            "output_count": len(mentions),
            "drop_reason_counts": {
                "TYPE_SCORE_REJECT": candidate_count * len(ENTITY_TYPES)
                - (closure_trace["input_count"] if closure_trace else len(mentions)),
            },
            "warnings": ["Entity Coreference and Participant Resolution are NOT_RUN."],
            "elapsed_seconds": raw_elapsed,
        }
        if budget_census is not None:
            trace["entity_span_budget_census"] = budget_census
        if closure_trace is not None:
            trace["entity_boundary_closure"] = closure_trace
            if priority_trace is not None:
                priority_trace["live_primary_count"] = len(decisions)
                priority_trace["absorbed_priority_count"] = (
                    closure_trace["input_count"] - len(decisions)
                )
            return mentions, trace, decisions, priority_trace, priority_error, rescue_only
        return mentions, trace, decisions, priority_trace, priority_error
