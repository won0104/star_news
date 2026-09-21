"""Stage ⑥ article-local Entity identity and Participant resolution.

Canonical Entity PRIMARY and B2 participant rows are current identity inputs.
RESCUE_ONLY is a distinct, bounded handoff for the step-7 failed-filler policy.
"""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from itertools import combinations
import struct
import time
from types import SimpleNamespace

import torch

from models.contracts import PairIndexBatch, SPAN_KINDS
from ..candidate_routing.participant_entity import (
    ParticipantEntityBoundedContract, ParticipantEntityBoundedSession,
)
from .resolution_handoff import (
    EntityRepresentationAggregate,
    IdentityResolutionHandoff,
    build_resolved_role_facts,
)


ENTITY_TYPES = ("PERSON", "ORGANIZATION", "LOCATION", "PRODUCT")
ROLES = ("ACTOR", "TARGET", "PLACE")

MEMORY_BOUNDED_EXECUTION_MODE = (
    "ENTITY_ONCE_PARTICIPANT_CHUNKED_STREAMING_ARGMAX_V1"
)
DEFAULT_ENTITY_STATE_CHUNK_SIZE = 64
DEFAULT_PARTICIPANT_STATE_CHUNK_SIZE = 64
DEFAULT_PARTICIPANT_PAIR_BATCH_SIZE = 4096


def _stable_id(prefix: str, *parts: object) -> str:
    material = "\u241f".join(str(part) for part in parts).encode("utf-8")
    return f"{prefix}-{sha256(material).hexdigest()[:24]}"


def _norm(text: str) -> str:
    return "".join(text.casefold().split())


def _overlap(left, right) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])


def _contains(left, right) -> bool:
    return left[0] <= right[0] and right[1] <= left[1]


def _entity_pair_eligible(left, right) -> bool:
    return (
        left["entity_type"] == right["entity_type"]
        and (
            left["priority_tier"] == "TIER1_PROMOTED"
            or right["priority_tier"] == "TIER1_PROMOTED"
        )
    )


def _participant_pair_eligible(filler, mention) -> bool:
    """Broad PRIMARY eligibility includes promoted tier or overlapping tier-2.

    Promotion tier and boundary-family canonical PRIMARY are separate axes.
    """
    return mention["priority_tier"] == "TIER1_PROMOTED" or _overlap(
        (int(filler["char_start"]), int(filler["char_end"])),
        (int(mention["char_start"]), int(mention["char_end"])),
    )


def _align(prepared, start: int, end: int):
    for sentence in prepared.sentences:
        if not (sentence["start"] <= start and end <= sentence["end"]):
            continue
        tokens = [
            token for token in sentence["tokens"]
            if int(token["end"]) > start and int(token["start"]) < end
        ]
        if tokens:
            return [
                int(sentence["sentence_index"]),
                int(tokens[0]["token_index"]),
                int(tokens[-1]["token_index"]) + 1,
            ]
    return None


def _entity_features(left, right):
    ls = (int(left["char_start"]), int(left["char_end"]))
    rs = (int(right["char_start"]), int(right["char_end"]))
    distance = abs(int(left["sentence_index"]) - int(right["sentence_index"]))
    char_gap = max(0, max(ls[0], rs[0]) - min(ls[1], rs[1]))
    tier_left = left.get("priority_tier") == "TIER1_PROMOTED"
    tier_right = right.get("priority_tier") == "TIER1_PROMOTED"
    scores = sorted((float(left.get("entity_score", left.get("score", 0.0))), float(right.get("entity_score", right.get("score", 0.0)))))
    priorities = sorted((float(left.get("promotion_score", 0.0)), float(right.get("promotion_score", 0.0))))
    return [
        float(left["entity_type"] == right["entity_type"]),
        float(_norm(left["text"]) == _norm(right["text"])),
        float(left["text"].strip().casefold() == right["text"].strip().casefold()),
        min(distance, 32) / 32.0,
        min(char_gap, 512) / 512.0,
        float(_overlap(ls, rs)),
        float((_contains(ls, rs) or _contains(rs, ls)) and ls != rs),
        float(tier_left and tier_right),
        float(tier_left or tier_right),
        scores[0], scores[1], priorities[0], priorities[1],
        float(distance == 0),
        float(min(len(left["text"]), len(right["text"])) <= 4 < max(len(left["text"]), len(right["text"]))),
        float(ls == rs),
    ]


def _participant_features(filler, mention):
    fs = (int(filler["char_start"]), int(filler["char_end"]))
    ms = (int(mention["char_start"]), int(mention["char_end"]))
    distance = int(mention["sentence_index"]) - int(filler["sentence_index"])
    char_gap = max(0, max(fs[0], ms[0]) - min(fs[1], ms[1]))
    return [
        *[float(filler["role"] == role) for role in ROLES],
        *[float(mention["entity_type"] == value) for value in ENTITY_TYPES],
        float(mention["priority_tier"] == "TIER1_PROMOTED"),
        float(mention["priority_tier"] == "TIER2_EVIDENCE_ONLY"),
        float(mention["promotion_score"]),
        float(mention.get("entity_score", mention.get("score", 0.0))),
        float(fs == ms), float(_contains(fs, ms)), float(_contains(ms, fs)),
        float(_overlap(fs, ms)), float(distance == 0),
        max(-32, min(32, distance)) / 32.0,
        min(char_gap, 512) / 512.0,
        float(_norm(filler["text"]) == _norm(mention["text"])),
        float(_norm(filler["text"]) in _norm(mention["text"]) or _norm(mention["text"]) in _norm(filler["text"])),
        float(filler.get("score", 1.0)),
    ]


def _pair_batch(source, target, features, device):
    count = len(source)
    return PairIndexBatch(
        source_indices=torch.tensor([source], dtype=torch.long, device=device).reshape(1, count),
        target_indices=torch.tensor([target], dtype=torch.long, device=device).reshape(1, count),
        mask=torch.ones(1, count, dtype=torch.bool, device=device),
        policy_features=torch.tensor([features], dtype=torch.float32, device=device).reshape(1, count, -1),
    )


def _span_batch(rows, kinds, device):
    """Build the existing candidate tensor contract for one bounded chunk."""

    return SimpleNamespace(
        span_indices=torch.tensor(
            [rows], dtype=torch.long, device=device
        ).reshape(1, -1, 3),
        span_kind_ids=torch.tensor(
            [kinds], dtype=torch.long, device=device
        ).reshape(1, -1),
        span_mask=torch.ones(1, len(rows), dtype=torch.bool, device=device),
    )


def _iter_candidate_state_chunks(
    span_model,
    backbone,
    context,
    source_token_mask,
    rows,
    kinds,
    *,
    device,
    chunk_size,
):
    """Encode candidates without constructing an article-wide ``[B,N,T,H]``.

    CandidateSpanEncoder is pointwise over the candidate dimension.  Reusing the
    same backbone/context while slicing only that dimension preserves its model
    contract and bounds the candidate-specific sentence-token allocation.  The
    runtime direct path gathers only the routed layer rows for the current chunk.
    """

    if chunk_size <= 0:
        raise ValueError("candidate state chunk_size must be positive")
    if len(rows) != len(kinds):
        raise ValueError("candidate rows and kinds must align")
    encoder = span_model.candidate_span_encoder
    for offset in range(0, len(rows), chunk_size):
        stop = min(offset + chunk_size, len(rows))
        packed = _span_batch(rows[offset:stop], kinds[offset:stop], device)
        states = encoder.forward_runtime_direct(
            backbone,
            context,
            packed,
            source_token_mask,
        )
        yield offset, stop, packed, states


def encode_candidate_states_bounded(
    span_model,
    backbone,
    context,
    source_token_mask,
    rows,
    kinds,
    *,
    device,
    chunk_size,
):
    """Encode and retain a bounded candidate collection such as Entity mentions."""

    pieces = [
        states
        for _offset, _stop, _packed, states in _iter_candidate_state_chunks(
            span_model,
            backbone,
            context,
            source_token_mask,
            rows,
            kinds,
            device=device,
            chunk_size=chunk_size,
        )
    ]
    if pieces:
        return torch.cat(pieces, dim=1)
    return context.document_state.new_zeros(
        (context.document_state.shape[0], 0, context.document_state.shape[-1])
    )


def _build_participant_eligibility_index(mentions):
    """Index the exact legacy TIER1-or-overlapping-TIER2 candidate universe."""

    tier1 = []
    tier2_by_sentence = defaultdict(list)
    for index, mention in enumerate(mentions):
        if mention["priority_tier"] == "TIER1_PROMOTED":
            tier1.append(index)
        else:
            tier2_by_sentence[int(mention["sentence_index"])].append(index)
    return {
        "tier1": tuple(tier1),
        "tier2_by_sentence": {
            sentence: tuple(indices)
            for sentence, indices in tier2_by_sentence.items()
        },
    }


def _indexed_participant_targets(filler, mentions, index):
    """Return the same mention indices and order as the legacy full scan."""

    filler_span = (int(filler["char_start"]), int(filler["char_end"]))
    overlapping_tier2 = [
        mention_index
        for mention_index in index["tier2_by_sentence"].get(
            int(filler["sentence_index"]), ()
        )
        if _overlap(
            filler_span,
            (
                int(mentions[mention_index]["char_start"]),
                int(mentions[mention_index]["char_end"]),
            ),
        )
    ]
    return tuple(sorted((*index["tier1"], *overlapping_tier2)))


def _rescue_targets_for_failed_filler(filler, rescue_index):
    """실패한 한 filler의 source sentence/overlap에 제한한 alternative만 조회한다."""
    filler_span = (int(filler["char_start"]), int(filler["char_end"]))
    return tuple(row for row in rescue_index.get(int(filler["sentence_index"]), ())
                 if _overlap(filler_span,
                             (int(row["char_start"]), int(row["char_end"]))))


def _complete_link_clusters(mention_ids, score_by_pair, threshold):
    """Score가 없거나 threshold 미달인 pair를 구분하며 complete-link한다."""
    clusters = [{index} for index in range(len(mention_ids))]
    for score, left, right in sorted(
        (
            (score, *pair)
            for pair, score in score_by_pair.items()
            if score >= threshold
        ),
        key=lambda row: (-row[0], mention_ids[row[1]], mention_ids[row[2]]),
    ):
        left_cluster = next(
            index for index, cluster in enumerate(clusters) if left in cluster
        )
        right_cluster = next(
            index for index, cluster in enumerate(clusters) if right in cluster
        )
        if left_cluster == right_cluster:
            continue
        if any(
            tuple(sorted((a, b))) not in score_by_pair
            or score_by_pair[tuple(sorted((a, b)))] < threshold
            for a in clusters[left_cluster] for b in clusters[right_cluster]
        ):
            continue
        clusters[left_cluster] |= clusters[right_cluster]
        del clusters[right_cluster]
    return clusters


class FixedEntityIdentityParticipantResolutionRuntime:
    """Inference-only stage ⑥ over frozen stage-③/⑦ evidence."""

    def __init__(
        self,
        span_model,
        coreference_model,
        participant_model,
        config,
        coreference_sha,
        participant_sha,
    ) -> None:
        self.span_model = span_model
        self.coreference_model = coreference_model
        self.participant_model = participant_model
        self.config = config
        self.coreference_sha = coreference_sha
        self.participant_sha = participant_sha

    def _score_rescue_targets(
        self, backbone, context, batch, filler, filler_state, targets,
        *, device, state_chunk_size, pair_batch_size,
    ):
        """한 실패 filler의 허용 alternative만 bounded directed pair로 점수화한다."""
        if not targets:
            return None, 0, 0
        aligned_rows = [row["aligned"] for row in targets]
        entity_kinds = [SPAN_KINDS.index("ENTITY")] * len(targets)
        winner = None
        evaluated = 0
        pair_batches = 0
        for start, stop, _packed, states in _iter_candidate_state_chunks(
            self.span_model, backbone, context, batch.source_token_mask,
            aligned_rows, entity_kinds, device=device, chunk_size=state_chunk_size,
        ):
            candidates = targets[start:stop]
            chunk_rows = aligned_rows[start:stop]
            combined_rows = [*chunk_rows, filler["aligned"]]
            combined_kinds = [
                *([SPAN_KINDS.index("ENTITY")] * len(candidates)),
                SPAN_KINDS.index("EVIDENCE"),
            ]
            combined_packed = _span_batch(combined_rows, combined_kinds, device)
            combined_states = torch.cat((states, filler_state.reshape(1, 1, -1)), dim=1)
            for offset in range(0, len(candidates), pair_batch_size):
                stop_offset = min(offset + pair_batch_size, len(candidates))
                subset = candidates[offset:stop_offset]
                pairs = _pair_batch(
                    [len(candidates)] * len(subset),
                    list(range(offset, stop_offset)),
                    [_participant_features(filler, row) for row in subset], device,
                )
                logits = self.participant_model(
                    combined_states, combined_packed.span_indices,
                    combined_packed.span_kind_ids, combined_packed.span_mask,
                    pairs, context.document_state,
                ).logits[0, :, 0]
                for score, row in zip(torch.sigmoid(logits).cpu().tolist(), subset):
                    key = (float(score), str(row["prediction_id"]))
                    if winner is None or key > winner[0]:
                        winner = (key, row)
                evaluated += len(subset)
                pair_batches += 1
            del combined_states, states
        return winner, evaluated, pair_batches

    @torch.inference_mode()
    def run(self, prepared, backbone, entity_mentions, priorities, participants,
            *, rescue_only=(), two_pass=False, compact_handoff=False,
            diagnostic_sink=None, application_profiler=None,
            routing_observer=None, bounded_policy=None,
            entity_inventory_lineage=None):
        started = time.perf_counter()
        if bounded_policy is not None and not isinstance(
            bounded_policy, ParticipantEntityBoundedContract
        ):
            raise TypeError("bounded Participant policy must be the selected r2 K16 contract")
        if rescue_only and not two_pass:
            raise ValueError("RESCUE_ONLY requires explicit PRIMARY-then-rescue policy")
        primary_by_id = {row["prediction_id"]: row for row in entity_mentions}
        primary_ids = set(primary_by_id)
        rescue_ids = [row["prediction_id"] for row in rescue_only]
        if len(rescue_ids) != len(set(rescue_ids)) or primary_ids.intersection(rescue_ids):
            raise ValueError("RESCUE_ONLY must be unique and absent from PRIMARY identity input")
        family_by_primary = {}
        for row in rescue_only:
            if (row["canonical_entity_prediction_id"] not in primary_ids
                or row["article_version_id"] != prepared.article.article_version_id
                or row["consumer"] != "FAILED_FILLER_OVERLAP_ONLY"
                or row["lifetime"] != "RESOLUTION_ONLY"):
                raise ValueError("invalid Entity RESCUE_ONLY handoff")
            canonical = primary_by_id[row["canonical_entity_prediction_id"]]
            family = str(row["source_family_id"])
            previous_family = family_by_primary.setdefault(
                row["canonical_entity_prediction_id"], family,
            )
            if (family != previous_family
                or row["entity_type"] != canonical["entity_type"]
                or int(row["sentence_index"]) != int(canonical["sentence_index"])
                or prepared.article.content[
                    int(row["char_start"]):int(row["char_end"])
                ] != row["text"]
                or not _overlap(
                    (int(row["char_start"]), int(row["char_end"])),
                    (int(canonical["char_start"]), int(canonical["char_end"])),
                )):
                raise ValueError("RESCUE_ONLY escaped its canonical Entity family")
        device = next(self.coreference_model.parameters()).device
        priority_by_id = {row["entity_prediction_id"]: row for row in priorities}
        mentions = []
        entity_rows = []
        alignment_failures = 0
        for mention in entity_mentions:
            aligned = _align(prepared, int(mention["char_start"]), int(mention["char_end"]))
            if aligned is None:
                alignment_failures += 1
                continue
            priority = priority_by_id[mention["prediction_id"]]
            state_index = len(entity_rows)
            entity_rows.append(aligned)
            mentions.append({
                **mention,
                "state_index": state_index,
                "aligned": aligned,
                "entity_score": float(mention["score"]),
                "promotion_score": float(priority["promotion_score"]),
                "priority_tier": priority["priority_tier"],
            })
        canonical_index_by_id = {
            row["prediction_id"]: index for index, row in enumerate(mentions)
        }
        rescue_index = defaultdict(list)
        rescue_alignment_failures = 0
        if two_pass:
            for candidate in rescue_only:
                if candidate["canonical_entity_prediction_id"] not in canonical_index_by_id:
                    rescue_alignment_failures += 1
                    continue
                aligned = _align(
                    prepared, int(candidate["char_start"]), int(candidate["char_end"]),
                )
                if aligned is None:
                    rescue_alignment_failures += 1
                    continue
                rescue_index[aligned[0]].append({**candidate, "aligned": aligned})
            for rows in rescue_index.values():
                rows.sort(key=lambda row: (
                    int(row["char_start"]), int(row["char_end"]),
                    str(row["source_family_id"]), str(row["prediction_id"]),
                ))
        fillers = []
        for event_id in sorted(participants):
            eventframe_id = "EFR-" + event_id.split("-", 1)[1]
            for role in ROLES:
                for ordinal, filler in enumerate(participants[event_id][role]):
                    aligned = _align(prepared, int(filler["char_start"]), int(filler["char_end"]))
                    if aligned is None:
                        alignment_failures += 1
                        continue
                    fillers.append({
                        **filler,
                        "role": role,
                        "sentence_index": aligned[0],
                        "aligned": aligned,
                        "ordinal": ordinal,
                        "participant_evidence_id": _stable_id(
                            "RAW", eventframe_id, role,
                            filler["char_start"], filler["char_end"], ordinal,
                        ),
                    })
        if not entity_rows and not fillers:
            empty = ((), (), (), {
                "stage": "⑥ 동일성 판정부",
                "candidate_count": 0,
                "output_count": 0,
                "elapsed_seconds": time.perf_counter() - started,
            })
            if compact_handoff:
                return (*empty, IdentityResolutionHandoff({}, (), {}))
            return empty
        batch = prepared.batch.to(device)
        context = self.span_model.encode_context(batch, backbone)
        entity_chunk_size = max(
            1,
            int(
                self.config.get(
                    "entity_candidate_state_chunk_size",
                    DEFAULT_ENTITY_STATE_CHUNK_SIZE,
                )
            ),
        )
        participant_chunk_size = max(
            1,
            int(
                self.config.get(
                    "participant_candidate_state_chunk_size",
                    DEFAULT_PARTICIPANT_STATE_CHUNK_SIZE,
                )
            ),
        )
        entity_pair_batch_size = max(
            1, int(self.config.get("pair_batch_size", 4096))
        )
        participant_pair_batch_size = max(
            1,
            int(
                self.config.get(
                    "participant_pair_batch_size",
                    DEFAULT_PARTICIPANT_PAIR_BATCH_SIZE,
                )
            ),
        )
        entity_kinds = [SPAN_KINDS.index("ENTITY")] * len(entity_rows)
        entity_packed = _span_batch(entity_rows, entity_kinds, device)
        entity_states = encode_candidate_states_bounded(
            self.span_model,
            backbone,
            context,
            batch.source_token_mask,
            entity_rows,
            entity_kinds,
            device=device,
            chunk_size=entity_chunk_size,
        )
        if routing_observer is not None and bounded_policy is None:
            article_hash = sha256(prepared.article.content.encode("utf-8")).hexdigest()
            context_hash = sha256(
                context.document_state.detach().cpu().contiguous().numpy().tobytes()
            ).hexdigest()
            entity_state_hash = sha256(
                entity_states.detach().cpu().contiguous().numpy().tobytes()
            ).hexdigest()

        coreference_started = time.perf_counter()
        pair_source, pair_target, pair_features = [], [], []
        pair_mentions = []
        for left_index, right_index in combinations(range(len(mentions)), 2):
            left, right = mentions[left_index], mentions[right_index]
            if not _entity_pair_eligible(left, right):
                continue
            pair_source.append(left["state_index"]); pair_target.append(right["state_index"])
            pair_features.append(_entity_features(left, right)); pair_mentions.append((left_index, right_index))
        pair_scores = []
        for offset in range(0, len(pair_source), entity_pair_batch_size):
            stop = offset + entity_pair_batch_size
            pairs = _pair_batch(pair_source[offset:stop], pair_target[offset:stop], pair_features[offset:stop], device)
            output = self.coreference_model(
                entity_states,
                entity_packed.span_indices,
                entity_packed.span_mask,
                pairs,
                context.document_state,
            ).logits[0]
            pair_scores.extend(torch.sigmoid(output[:, 1] - output[:, 0]).cpu().tolist())
        score_by_pair = {
            tuple(sorted(pair)): score for pair, score in zip(pair_mentions, pair_scores)
        }
        clustering_started = time.perf_counter()
        threshold = float(self.config["entity_coreference_threshold"])
        clusters = _complete_link_clusters(
            [row["prediction_id"] for row in mentions],
            score_by_pair,
            threshold,
        )

        materialized_indices = {
            index for index, cluster in enumerate(clusters)
            if any(mentions[item]["priority_tier"] == "TIER1_PROMOTED" for item in cluster)
        }
        mention_cluster = {
            member: cluster_index for cluster_index, cluster in enumerate(clusters) for member in cluster
        }
        if routing_observer is not None and bounded_policy is None:
            # Query×mention negative universe 대신 article당 M개의 scalar catalog만 남긴다.
            for offset in range(0, max(len(mentions), 1), 64):
                routing_observer.observe_reference_scalar("primary_catalog", {
                    "article_version_id": prepared.article.article_version_id,
                    "content_sha256": article_hash,
                    "feature_contract": "PARTICIPANT_RESOLUTION_FINE_INPUT_V22_V1",
                    "context_document_sha256": context_hash,
                    "entity_states_sha256": entity_state_hash,
                    "candidate_count": len(mentions),
                    "alignment_failure_count": alignment_failures,
                    "chunk_start": offset,
                    "candidates": [
                        {
                            "prediction_id": row["prediction_id"],
                            "char_start": int(row["char_start"]),
                            "char_end": int(row["char_end"]),
                            "sentence_index": int(row["sentence_index"]),
                            "aligned": [int(value) for value in row["aligned"]],
                            "entity_type": row["entity_type"],
                            "priority_tier": row["priority_tier"],
                            "promotion_score": float(row["promotion_score"]),
                            "entity_score": float(row["entity_score"]),
                            "text_norm": _norm(row["text"]),
                            "cluster_index": mention_cluster[index],
                        }
                        for index, row in enumerate(mentions[offset:offset + 64], offset)
                    ],
                })

        bounded_session = None
        if bounded_policy is not None:
            # Scalar index는 scorer 입력을 만들기 전 canonical PRIMARY M개로 한 번 만든다.
            catalog = [
                {
                    "prediction_id": row["prediction_id"],
                    "char_start": int(row["char_start"]),
                    "char_end": int(row["char_end"]),
                    "sentence_index": int(row["sentence_index"]),
                    "entity_type": row["entity_type"],
                    "priority_tier": row["priority_tier"],
                    "promotion_score": float(row["promotion_score"]),
                    "entity_score": float(row["entity_score"]),
                    "text_norm": _norm(row["text"]),
                    "cluster_index": mention_cluster[index],
                }
                for index, row in enumerate(mentions)
            ]
            bounded_session = ParticipantEntityBoundedSession(
                bounded_policy, catalog, prepared.article.article_version_id,
                sha256(prepared.article.content.encode("utf-8")).hexdigest(),
                len(fillers), rescue_index=rescue_index,
                entity_inventory_lineage=entity_inventory_lineage,
            )
            del catalog

        participant_started = time.perf_counter()
        resolution_rows = []
        participant_candidate_count = 0
        rescue_candidate_count = 0
        rescue_pair_batch_count = 0
        rescue_not_evaluated_count = 0
        rescue_success_count = 0
        primary_success_count = 0
        rescue_seconds = 0.0
        participant_pair_batch_count = 0
        participant_state_chunk_count = 0
        participant_threshold = float(self.config["participant_resolution_threshold"])
        eligibility_index = (
            _build_participant_eligibility_index(mentions)
            if bounded_session is None else None
        )
        bounded_census = defaultdict(int)
        filler_rows = [filler["aligned"] for filler in fillers]
        filler_kinds = [SPAN_KINDS.index("EVIDENCE")] * len(fillers)
        for chunk_start, chunk_stop, _filler_packed, filler_states in (
            _iter_candidate_state_chunks(
                self.span_model,
                backbone,
                context,
                batch.source_token_mask,
                filler_rows,
                filler_kinds,
                device=device,
                chunk_size=participant_chunk_size,
            )
        ):
            participant_state_chunk_count += 1
            chunk_fillers = fillers[chunk_start:chunk_stop]
            chunk_rows = filler_rows[chunk_start:chunk_stop]
            combined_rows = [*entity_rows, *chunk_rows]
            combined_kinds = [
                *entity_kinds,
                *([SPAN_KINDS.index("EVIDENCE")] * len(chunk_rows)),
            ]
            combined_packed = _span_batch(combined_rows, combined_kinds, device)
            combined_states = torch.cat((entity_states, filler_states), dim=1)
            best_by_filler = [None] * len(chunk_fillers)
            target_count_by_filler = [0] * len(chunk_fillers)
            if routing_observer is not None and bounded_session is None:
                positive_count_by_filler = [0] * len(chunk_fillers)
                positive_top_by_filler = [[] for _ in chunk_fillers]
                pair_input_hashers = [sha256() for _ in chunk_fillers]
            route_by_filler = [None] * len(chunk_fillers)
            pending_source = []
            pending_target = []
            pending_features = []
            pending_owner = []

            def flush_participant_pairs():
                nonlocal participant_pair_batch_count
                if not pending_source:
                    return
                pairs = _pair_batch(
                    pending_source,
                    pending_target,
                    pending_features,
                    device,
                )
                logits = self.participant_model(
                    combined_states,
                    combined_packed.span_indices,
                    combined_packed.span_kind_ids,
                    combined_packed.span_mask,
                    pairs,
                    context.document_state,
                ).logits[0, :, 0]
                scores = torch.sigmoid(logits).cpu().tolist()
                for score, owner, mention_index in zip(
                    scores, pending_owner, pending_target
                ):
                    key = (float(score), mentions[mention_index]["prediction_id"])
                    current = best_by_filler[owner]
                    if current is None or key > current[0]:
                        best_by_filler[owner] = (key, mention_index)
                    if (routing_observer is not None and bounded_session is None
                        and score >= participant_threshold):
                        positive_count_by_filler[owner] += 1
                        top = positive_top_by_filler[owner]
                        top.append(key)
                        if len(top) > 64:
                            top.sort(reverse=True)
                            del top[64:]
                participant_pair_batch_count += 1
                pending_source.clear()
                pending_target.clear()
                pending_features.clear()
                pending_owner.clear()

            for filler_local_index, filler in enumerate(chunk_fillers):
                if bounded_session is None:
                    targets = _indexed_participant_targets(
                        filler, mentions, eligibility_index
                    )
                else:
                    selection = bounded_session.route(filler, _participant_pair_eligible)
                    route_by_filler[filler_local_index] = selection
                    targets = tuple(
                        canonical_index_by_id[candidate_id]
                        for candidate_id in selection.selected_candidate_ids
                    )
                    bounded_census["query_count"] += 1
                    bounded_census["visited"] += selection.decision.visited
                    bounded_census["cheaply_ranked"] += selection.decision.cheaply_ranked
                    bounded_census["selected_primary_pair_count"] += len(targets)
                    bounded_census["skipped_by_budget"] += selection.decision.skipped_by_budget
                    bounded_census["primary_budget_exhausted_query_count"] += int(
                        selection.decision.budget_exhausted
                    )
                target_count_by_filler[filler_local_index] = len(targets)
                participant_candidate_count += len(targets)
                filler_state_index = len(mentions) + filler_local_index
                for mention_index in targets:
                    features = _participant_features(filler, mentions[mention_index])
                    pending_source.append(filler_state_index)
                    pending_target.append(mention_index)
                    pending_features.append(features)
                    pending_owner.append(filler_local_index)
                    if routing_observer is not None and bounded_session is None:
                        pair_input_hashers[filler_local_index].update(
                            mentions[mention_index]["prediction_id"].encode("utf-8") + b"\x00"
                        )
                        pair_input_hashers[filler_local_index].update(
                            struct.pack("<" + "f" * len(features), *features)
                        )
                    if len(pending_source) >= participant_pair_batch_size:
                        flush_participant_pairs()
            flush_participant_pairs()

            for filler_local_index, filler in enumerate(chunk_fillers):
                primary_count = target_count_by_filler[filler_local_index]
                primary_winner = best_by_filler[filler_local_index]
                selection = route_by_filler[filler_local_index]
                route_summary = (
                    bounded_session.record_and_release(
                        filler["participant_evidence_id"], primary_count,
                    ) if bounded_session is not None else None
                )
                if primary_count and primary_winner is None:
                    raise RuntimeError("participant pair streaming lost an eligible PRIMARY filler")
                primary_score = primary_winner[0][0] if primary_winner else None
                rescue_universe = "NOT_EVALUATED"
                rescue_score = None
                rescue_count = 0
                rescue_available_count = 0
                rescue_visited = 0
                rescue_budget_exhausted = False
                rescue_winner = None
                chosen_pass = None
                chosen_index = None
                rescue_row = None
                if primary_winner is not None and primary_score >= participant_threshold:
                    chosen_pass = "PRIMARY"
                    chosen_index = primary_winner[1]
                    primary_success_count += 1
                    rescue_not_evaluated_count += int(two_pass)
                elif two_pass:
                    rescue_started = (
                        time.perf_counter() if application_profiler is not None else None
                    )
                    if bounded_session is None:
                        allowed = _rescue_targets_for_failed_filler(filler, rescue_index)
                        rescue_visited = len(allowed)
                        rescue_retrieval_exhausted = False
                    else:
                        allowed, rescue_visited, rescue_retrieval_exhausted = (
                            bounded_session.retrieve_rescue(filler)
                        )
                        bounded_census["rescue_retrieval_visited"] += rescue_visited
                        bounded_census["rescue_retrieval_exhausted_query_count"] += int(
                            rescue_retrieval_exhausted
                        )
                    rescue_available_count = len(allowed)
                    if bounded_session is not None:
                        selected_rescue_count, rescue_fine_budget_exhausted = (
                            bounded_session.reserve_rescue(rescue_available_count)
                        )
                        rescue_budget_exhausted = (
                            rescue_retrieval_exhausted or rescue_fine_budget_exhausted
                        )
                        allowed = allowed[:selected_rescue_count]
                        bounded_census["rescue_available_candidate_count"] += (
                            rescue_available_count
                        )
                        bounded_census["rescue_budget_exhausted_query_count"] += int(
                            rescue_budget_exhausted
                        )
                    rescue_count = len(allowed)
                    rescue_universe = (
                        "SEARCH_BUDGET_EXHAUSTED" if rescue_budget_exhausted and not allowed
                        else "SCORED_BOUNDED" if bounded_session is not None and allowed
                        else "SCORED" if allowed else "EMPTY"
                    )
                    rescue_winner, evaluated, pair_batches = self._score_rescue_targets(
                        backbone, context, batch, filler,
                        filler_states[0, filler_local_index], allowed,
                        device=device, state_chunk_size=entity_chunk_size,
                        pair_batch_size=participant_pair_batch_size,
                    )
                    rescue_candidate_count += evaluated
                    rescue_pair_batch_count += pair_batches
                    rescue_score = rescue_winner[0][0] if rescue_winner else None
                    if rescue_winner is not None and rescue_score >= participant_threshold:
                        chosen_pass = "RESCUE_ONLY"
                        rescue_row = rescue_winner[1]
                        chosen_index = canonical_index_by_id[
                            rescue_row["canonical_entity_prediction_id"]
                        ]
                        rescue_success_count += 1
                    if application_profiler is not None:
                        rescue_seconds += time.perf_counter() - rescue_started
                fine_threshold_rejected = bool(
                    (primary_winner is not None and primary_score < participant_threshold)
                    or (rescue_winner is not None and rescue_score < participant_threshold)
                )
                search_budget_exhausted = bool(
                    (selection is not None and selection.decision.budget_exhausted)
                    or rescue_budget_exhausted
                )
                if bounded_session is not None:
                    bounded_census["fine_threshold_reject_query_count"] += int(
                        fine_threshold_rejected
                    )
                    bounded_census["search_budget_exhausted_query_count"] += int(
                        search_budget_exhausted
                    )
                if chosen_index is not None:
                    materialized_indices.add(mention_cluster[chosen_index])
                    resolved = {
                        "participant_evidence_id": filler["participant_evidence_id"],
                        "source_event_prediction_id": filler["source_event_prediction_id"],
                        "role": filler["role"],
                        "char_start": filler["char_start"],
                        "char_end": filler["char_end"],
                        "resolution_status": "ENTITY_RESOLVED",
                        "target_entity_prediction_id": mentions[chosen_index]["prediction_id"],
                        "target_cluster_index": mention_cluster[chosen_index],
                        "resolution_score": primary_score if chosen_pass == "PRIMARY" else rescue_score,
                        "checkpoint_sha": self.participant_sha,
                        "responsibility": "⑥ 동일성 판정부",
                    }
                    if two_pass:
                        resolved["candidate_pass"] = chosen_pass
                        if bounded_session is not None:
                            resolved["routing_policy_id"] = bounded_policy.policy_id
                            resolved["search_budget_exhausted"] = search_budget_exhausted
                            resolved["fine_threshold_rejected"] = fine_threshold_rejected
                        resolved["scored_entity_prediction_id"] = (
                            rescue_row["prediction_id"] if rescue_row is not None
                            else mentions[chosen_index]["prediction_id"]
                        )
                        if rescue_row is not None:
                            resolved["rescue_grounding"] = {
                                "article_version_id": prepared.article.article_version_id,
                                "sentence_index": rescue_row["sentence_index"],
                                "char_start": rescue_row["char_start"],
                                "char_end": rescue_row["char_end"],
                                "text": rescue_row["text"],
                                "source_family_id": rescue_row["source_family_id"],
                            }
                    resolution_rows.append(resolved)
                else:
                    reason = (
                        "SEARCH_BUDGET_EXHAUSTED" if search_budget_exhausted
                        else "NO_ENTITY_CANDIDATE" if not primary_count and not rescue_count
                        else "RESOLUTION_SCORE_REJECT"
                    )
                    unresolved = self._unresolved(
                        filler, reason,
                        rescue_score if rescue_score is not None else primary_score,
                    )
                    if two_pass:
                        unresolved["candidate_pass"] = "NONE"
                        if bounded_session is not None:
                            unresolved["routing_policy_id"] = bounded_policy.policy_id
                            unresolved["search_budget_exhausted"] = search_budget_exhausted
                            unresolved["fine_threshold_rejected"] = fine_threshold_rejected
                    resolution_rows.append(unresolved)
                if two_pass and diagnostic_sink is not None:
                    decision_payload = {
                        "component": "participant_entity_resolution_two_pass",
                        "participant_evidence_id": filler["participant_evidence_id"],
                        "canonical_event_mention_id": filler["source_event_prediction_id"],
                        "article_version_id": prepared.article.article_version_id,
                        "filler_char_start": int(filler["char_start"]),
                        "filler_char_end": int(filler["char_end"]),
                        "role": filler["role"],
                        "primary_candidate_carrier": "CANONICAL_PRIMARY_ENTITY_MENTION",
                        "primary_universe": "SCORED" if primary_count else "EMPTY",
                        "primary_candidate_count": primary_count,
                        "primary_best_score": primary_score,
                        "rescue_candidate_carrier": "RESCUE_ONLY_BOUNDARY_ALTERNATIVE",
                        "rescue_universe": rescue_universe,
                        "rescue_candidate_count": rescue_count,
                        "rescue_best_score": rescue_score,
                        "result": chosen_pass or "UNRESOLVED",
                        "canonical_target_entity_prediction_id": (
                            mentions[chosen_index]["prediction_id"]
                            if chosen_index is not None else None
                        ),
                        "scored_rescue_prediction_id": (
                            rescue_row["prediction_id"] if rescue_row else None
                        ),
                        "threshold": participant_threshold,
                        "not_evaluated_is_negative": False,
                    }
                    if bounded_session is not None:
                        decision_payload.update({
                            "routing_policy_id": bounded_policy.policy_id,
                            "shared_retrieval_policy_id": bounded_policy.retrieval_policy_id,
                            "routing_mode": "BOUNDED_EXPLICIT_ANALYSIS",
                            "primary_selected_candidate_ids": list(
                                selection.selected_candidate_ids
                            ),
                            "shared_k64_tier_retained_counts": dict(
                                selection.decision.route_counts
                            ),
                            "selected_k16_tier_counts": {
                                tier: len(ids) for tier, ids in
                                selection.tier_selected_ids.items()
                            },
                            "retrieval_visited": route_summary.visited,
                            "cheaply_ranked": route_summary.cheaply_ranked,
                            "fine_scored": route_summary.fine_scored,
                            "retained_shared_k64": route_summary.retained,
                            "skipped_by_budget": route_summary.skipped_by_budget,
                            "request_used": bounded_session.router.request.used_units,
                            "search_budget_exhausted": search_budget_exhausted,
                            "fine_threshold_rejected": fine_threshold_rejected,
                            "rescue_available_candidate_count": rescue_available_count,
                            "rescue_retrieval_visited": rescue_visited,
                            "rescue_budget_exhausted": rescue_budget_exhausted,
                        })
                    diagnostic_sink.record("decision", decision_payload)
                if routing_observer is not None and bounded_session is None:
                    top = sorted(positive_top_by_filler[filler_local_index], reverse=True)
                    routing_observer.observe_reference_scalar("participant_query", {
                        "article_version_id": prepared.article.article_version_id,
                        "content_sha256": article_hash,
                        "query_key": filler["participant_evidence_id"],
                        "source_event_prediction_id": filler["source_event_prediction_id"],
                        "role": filler["role"],
                        "sentence_index": int(filler["sentence_index"]),
                        "aligned": [int(value) for value in filler["aligned"]],
                        "char_start": int(filler["char_start"]),
                        "char_end": int(filler["char_end"]),
                        "text_norm": _norm(filler["text"]),
                        "filler_score": float(filler.get("score", 1.0)),
                        "feature_contract": "PARTICIPANT_RESOLUTION_FINE_INPUT_V22_V1",
                        "filler_state_sha256": sha256(
                            filler_states[0, filler_local_index].detach().cpu()
                            .contiguous().numpy().tobytes()
                        ).hexdigest(),
                        "pair_policy_input_sha256": pair_input_hashers[
                            filler_local_index
                        ].hexdigest(),
                        "context_document_sha256": context_hash,
                        "entity_states_sha256": entity_state_hash,
                        "participant_checkpoint_sha256": self.participant_sha,
                        "eligible_primary_count": primary_count,
                        "primary_winner_id": (
                            mentions[primary_winner[1]]["prediction_id"]
                            if primary_winner else None
                        ),
                        "primary_winner_score": primary_score,
                        "primary_threshold": participant_threshold,
                        "fine_tie_break": "SCORE_DESC_PREDICTION_ID_DESC",
                        "baseline_positive_count": positive_count_by_filler[filler_local_index],
                        "baseline_positive_top": [
                            {"prediction_id": candidate_id, "score": score}
                            for score, candidate_id in top
                        ],
                        "rescue_candidate_count": rescue_count,
                        "rescue_winner_id": (
                            rescue_winner[1]["prediction_id"] if rescue_winner else None
                        ),
                        "rescue_canonical_id": (
                            rescue_winner[1]["canonical_entity_prediction_id"]
                            if rescue_winner else None
                        ),
                        "result": chosen_pass or "UNRESOLVED",
                    })
            del combined_states, filler_states

        local_entities = []
        local_id_by_cluster = {}
        entity_aggregate_by_local_id = {}
        for cluster_index in sorted(materialized_indices):
            members = sorted(
                (mentions[index] for index in clusters[cluster_index]),
                key=lambda row: row["prediction_id"],
            )
            local_id = _stable_id(
                "LENT", prepared.article.article_id,
                *[row["prediction_id"] for row in members],
            )
            local_id_by_cluster[cluster_index] = local_id
            if compact_handoff:
                member_indices = sorted(clusters[cluster_index])
                entity_aggregate_by_local_id[local_id] = EntityRepresentationAggregate(
                    torch.stack([entity_states[0, index] for index in member_indices]).sum(0).detach(),
                    len(member_indices),
                    max(float(mentions[index]["score"]) for index in member_indices),
                )
            representative = max(
                members,
                key=lambda row: (
                    row["priority_tier"] == "TIER1_PROMOTED",
                    row["promotion_score"], row["score"],
                    len(row["text"]), -int(row["char_start"]),
                    row["prediction_id"],
                ),
            )
            internal_scores = [
                score_by_pair[tuple(sorted((left, right)))]
                for left, right in combinations(
                    [mentions.index(member) for member in members], 2
                )
                if tuple(sorted((left, right))) in score_by_pair
            ]
            local_entity = {
                "local_entity_id": local_id,
                "article_id": prepared.article.article_id,
                "entity_type": representative["entity_type"],
                "canonical_name": representative["text"],
                "representative_entity_prediction_id": representative["prediction_id"],
                "member_entity_prediction_ids": [row["prediction_id"] for row in members],
                "confidence": min(internal_scores) if internal_scores else float(representative["promotion_score"]),
                "materialization_source": (
                    "TIER1_PRIMARY" if any(row["priority_tier"] == "TIER1_PROMOTED" for row in members)
                    else "PARTICIPANT_TIER2_RESCUE"
                ),
                "coreference_checkpoint_sha": self.coreference_sha,
                "runtime_config_id": self.config["runtime_config_id"],
                "responsibility": "⑥ 동일성 판정부",
            }
            if compact_handoff:
                local_entity["identity_confidence_source"] = (
                    "ENTITY_COMPLETE_LINK_MIN_PAIR_SCORE" if internal_scores
                    else "ENTITY_PRIMARY_PROMOTION_SCORE"
                )
                local_entity["representative_grounding"] = {
                    "article_version_id": prepared.article.article_version_id,
                    "sentence_index": representative["sentence_index"],
                    "char_start": representative["char_start"],
                    "char_end": representative["char_end"],
                    "text": representative["text"],
                }
            local_entities.append(local_entity)
        for row in resolution_rows:
            cluster_index = row.pop("target_cluster_index", None)
            if cluster_index is not None:
                row["target_local_entity_id"] = local_id_by_cluster[cluster_index]
        coreference_rows = [
            {
                "left_entity_prediction_id": mentions[left]["prediction_id"],
                "right_entity_prediction_id": mentions[right]["prediction_id"],
                "decision": "MERGE",
                "score": float(score),
                "checkpoint_sha": self.coreference_sha,
                "responsibility": "⑥ 동일성 판정부",
            }
            for (left, right), score in sorted(score_by_pair.items())
            if score >= threshold and mention_cluster[left] == mention_cluster[right]
        ]
        identity_handoff = None
        compact_handoff_seconds = 0.0
        if compact_handoff:
            handoff_started = (
                time.perf_counter() if application_profiler is not None else None
            )
            facts, feature_sets = build_resolved_role_facts(
                prepared.article.article_version_id, tuple(resolution_rows),
                {row["participant_evidence_id"]: row for row in fillers},
                {row["prediction_id"]: row for row in mentions},
                tuple(local_entities),
                tuple(coreference_rows),
            )
            identity_handoff = IdentityResolutionHandoff(
                entity_aggregate_by_local_id, facts, feature_sets,
                {
                    str(member_id): str(row["local_entity_id"])
                    for row in local_entities
                    for member_id in row["member_entity_prediction_ids"]
                },
            )
            if application_profiler is not None:
                compact_handoff_seconds = time.perf_counter() - handoff_started
        if bounded_session is not None:
            bounded_census["request_used"] = bounded_session.router.request.used_units
            bounded_census["request_budget"] = bounded_session.router.request.total_units
            bounded_census["entity_inventory_cache_key"] = bounded_session.cache_key
            bounded_census["entity_inventory_policy_id"] = (
                entity_inventory_lineage[0] if entity_inventory_lineage
                else "BCR_REFERENCE_V22_V1"
            )
            if bounded_session.remaining_queries:
                raise RuntimeError("bounded session did not consume every aligned filler")
            bounded_session.close()
            rescue_index.clear()
        finished = time.perf_counter()
        if application_profiler is not None:
            application_profiler.add_seconds(
                "entity_coreference", participant_started - started
            )
            application_profiler.add_seconds("rescue_only_resolution", rescue_seconds)
            application_profiler.add_seconds(
                "participant_entity_primary_resolution",
                max(0.0, finished - participant_started - rescue_seconds
                    - compact_handoff_seconds),
            )
            application_profiler.add_seconds(
                "role_entity_compact_handoff", compact_handoff_seconds
            )
            for name, value in (
                ("entity_count", len(mentions)),
                ("eligible_pair_count", len(pair_source)),
                ("scored_pair_count", len(pair_scores)),
                ("accepted_pair_count", len(coreference_rows)),
                ("cluster_count", len(clusters)),
            ):
                application_profiler.count("entity_coreference", name, int(value))
            failed_primary_count = len(fillers) - primary_success_count
            for name, value in (
                ("primary_pair_count", participant_candidate_count),
                ("primary_success_count", primary_success_count),
                ("rescue_pair_count", rescue_candidate_count),
                ("rescue_success_count", rescue_success_count),
                ("primary_failure_filler_count", failed_primary_count),
            ):
                application_profiler.count("participant_resolution", name, int(value))
            application_profiler.count(
                "participant_resolution", "rescue_fallback_rate",
                rescue_success_count / failed_primary_count if failed_primary_count else 0.0,
            )
        trace = {
            "stage": "⑥ 동일성 판정부",
            "component": "Entity identity + Participant resolution",
            "checkpoint_sha": {
                "entity_coreference": self.coreference_sha,
                "participant_entity_resolution": self.participant_sha,
            },
            "input_count": len(mentions) + len(fillers),
            "resolution_execution_mode": (
                "ENTITY_ONCE_PARTICIPANT_R2_SELECTED_STREAMING_ARGMAX_V1"
                if bounded_policy is not None else MEMORY_BOUNDED_EXECUTION_MODE
            ),
            "execution_parameters": {
                "entity_candidate_state_chunk_size": entity_chunk_size,
                "participant_candidate_state_chunk_size": participant_chunk_size,
                "entity_pair_batch_size": entity_pair_batch_size,
                "participant_pair_batch_size": participant_pair_batch_size,
                "entity_states_retained": len(mentions),
                "participant_states_retained_article_wide": 0,
                "participant_state_chunk_count": participant_state_chunk_count,
                "participant_pair_batch_count": participant_pair_batch_count,
                "max_candidate_span_encoder_batch": max(
                    min(entity_chunk_size, len(mentions)),
                    min(participant_chunk_size, len(fillers)),
                ),
                "max_pair_model_candidate_states": len(mentions)
                + min(participant_chunk_size, len(fillers)),
            },
            "candidate_count": {
                "entity_mentions": len(mentions),
                "rescue_only_handoff": len(rescue_only),
                "participant_fillers": len(fillers),
                "entity_pairs": len(pair_source),
                "participant_entity_pairs": participant_candidate_count,
                "primary_pass_pairs": participant_candidate_count,
                "rescue_pass_pairs": rescue_candidate_count,
                "unscored_tier2_tier2_pairs": sum(
                    mentions[left]["priority_tier"] == "TIER2_EVIDENCE_ONLY"
                    and mentions[right]["priority_tier"] == "TIER2_EVIDENCE_ONLY"
                    for left, right in combinations(range(len(mentions)), 2)
                ),
            },
            "output_count": {
                "local_entities": len(local_entities),
                "entity_merge_decisions": len(coreference_rows),
                "participant_resolutions": sum(row["resolution_status"] == "ENTITY_RESOLVED" for row in resolution_rows),
                "primary_resolutions": primary_success_count,
                "rescue_resolutions": rescue_success_count,
                "resolved_role_facts": len(identity_handoff.resolved_role_facts) if identity_handoff else 0,
            },
            "drop_reason_counts": {
                "ALIGNMENT_FAILURE": alignment_failures,
                "PARTICIPANT_UNRESOLVED": sum(row["resolution_status"] != "ENTITY_RESOLVED" for row in resolution_rows),
                "RESCUE_ALIGNMENT_FAILURE": rescue_alignment_failures,
                "RESCUE_NOT_EVALUATED_AFTER_PRIMARY_SUCCESS": rescue_not_evaluated_count,
            },
            "warnings": [
                "Unscored TIER2-TIER2 pairs are unavailable, not confident negatives.",
                "RESCUE_ONLY is scored only after PRIMARY failure and remaps to canonical Entity identity.",
                "NOT_EVALUATED rescue/pair availability is not a negative label.",
            ],
            "span_encoding_seconds": coreference_started - started,
            "entity_coreference_seconds": clustering_started - coreference_started,
            "clustering_seconds": participant_started - clustering_started,
            "participant_resolution_seconds": finished - participant_started,
            "elapsed_seconds": finished - started,
        }
        if bounded_policy is not None:
            trace["participant_bounded_routing"] = {
                "policy_id": bounded_policy.policy_id,
                "revision": bounded_policy.revision,
                "shared_retrieval_policy_id": bounded_policy.retrieval_policy_id,
                "manifest_sha256": bounded_policy.manifest_sha256,
            "selected_tier_quota": {
                "LOCAL": bounded_policy.selected_tiers.local,
                "NEAR": bounded_policy.selected_tiers.near,
                "GLOBAL": bounded_policy.selected_tiers.global_,
            },
                "coarse_score_is_final_confidence": False,
                "query_cache_active": False,
                "rescue_representation_cache_active": False,
                "reference_fallback_active": False,
                "index_released_after_handoff": True,
                "rescue_pool_released_after_handoff": True,
                "counts": dict(sorted(bounded_census.items())),
            }
        result = (tuple(local_entities), tuple(coreference_rows), tuple(resolution_rows), trace)
        if compact_handoff:
            return (*result, identity_handoff)
        return result

    def _unresolved(self, filler, reason, score=None):
        return {
            "participant_evidence_id": filler["participant_evidence_id"],
            "source_event_prediction_id": filler["source_event_prediction_id"],
            "role": filler["role"],
            "char_start": filler["char_start"],
            "char_end": filler["char_end"],
            "resolution_status": "UNRESOLVED",
            "target_entity_prediction_id": None,
            "target_local_entity_id": None,
            "resolution_score": score,
            "first_loss": reason,
            "checkpoint_sha": self.participant_sha,
            "responsibility": "⑥ 동일성 판정부",
        }
