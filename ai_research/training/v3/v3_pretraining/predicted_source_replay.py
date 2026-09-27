"""Gold-free predicted source replay and trainable coordinate re-gather.

Selection delegates to the serving worker's exact source funnel. The optional
re-gather starts a new trainable graph at DCE/encoders for downstream heads;
the discrete selection and scalar carrier remain detached from that graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import TYPE_CHECKING, Mapping, Sequence

import torch
from torch.nn import functional as F

from models.v3_pretraining.pair_context import original_sentence_states
from runtime.v3_pretraining.event_features import (
    EventFeatureProvenance, EventMemberFeatureLease,
    EventOptionalConfidenceEvidence, build_event_pair_feature_bundle,
    event_member_sentence_indices)
from runtime.v3_pretraining.event_identity import EventMember, MemberRoleFact
from runtime.v3_pretraining.event_pair_policy import event_pair_policy_features
from runtime.v3_pretraining.handoff import FrozenSourceViewKey
from runtime.v3_pretraining.serving import SourceFunnelResult, V3ServingWorker
from runtime.v3_pretraining.source_batch import source_windows_from_layout
from runtime.v3_pretraining.source_layout import RawArticle
from runtime.v3_pretraining.temporal import RelativeMonthContext, TemporalOccurrence

if TYPE_CHECKING:
    from training.v3_pretraining.harness import V3Trainer
    from training.v3_pretraining.targets import ValidatedGoldArticle


def assert_frozen_producer(trainer: V3Trainer, worker: V3ServingWorker) -> None:
    """The mutable student and checkpoint-bound producer must own disjoint tensors."""
    if worker.core is trainer.core or worker.backbone is trainer.backbone:
        raise ValueError("predicted replay requires an independent frozen producer")
    student = {id(parameter) for parameter in (*trainer.core.parameters(),
                                              *trainer.backbone.parameters())}
    producer = tuple((*worker.core.parameters(), *worker.backbone.parameters()))
    if student.intersection(id(parameter) for parameter in producer):
        raise ValueError("student and producer share parameter storage")
    if any(parameter.requires_grad or parameter.grad is not None for parameter in producer):
        raise ValueError("producer parameters must be frozen and gradient-free")
    if worker.source_policy is None or worker.source_policy.checkpoint_sha256 != worker.checkpoint_sha256:
        raise ValueError("producer checkpoint/source policy binding differs")
    worker.source_policy.validate_budget(worker.budget)


def build_predicted_source_replay(trainer: V3Trainer, worker: V3ServingWorker,
                                  raw: RawArticle) -> SourceFunnelResult:
    """Use one explicit checkpoint-bound source policy, without Gold or gradients."""
    assert_frozen_producer(trainer, worker)
    with torch.no_grad():
        result = worker.analyze_source_funnel(
            article_id=raw.article_id, content=raw.content,
            article_version_id=raw.article_version_id,
            published_at=raw.published_at)
    if (result.binding != worker.source_policy.binding() or
            result.article_version_id != raw.article_version_id or
            result.content_sha256 != raw.content_sha256):
        raise ValueError("predicted replay source/policy binding differs")
    return result


@dataclass(frozen=True, slots=True)
class ReplaySupervision:
    """Detached retrieval audit plus losses on real selected candidates only."""

    losses: dict[str, torch.Tensor]
    active: dict[str, bool]
    retrieval: dict[str, dict[str, int]]
    binding: dict[str, object]


def _gold_entity_coordinates(article: ValidatedGoldArticle) -> dict[tuple[int, int], str]:
    """Known unified mention identities; unresolved ROLE has no pair label."""
    mentions = {row["mention_id"]: row for row in article.annotations["entity_mentions"]}
    result: dict[tuple[int, int], str] = {}
    for cluster in article.annotations["entity_clusters"]:
        for mention_id in cluster["mention_ids"]:
            span = mentions[mention_id]["span"]
            key = (span["start"], span["end"])
            if key in result and result[key] != cluster["entity_id"]:
                raise ValueError("conflicting Gold Entity at one coordinate")
            result[key] = cluster["entity_id"]
    for event in article.annotations["events"]:
        for collection in ("actors", "targets", "places"):
            for role in event[collection]:
                if role["entity_id"] is None:
                    continue
                span = role["span"]
                key = (span["start"], span["end"])
                if key in result and result[key] != role["entity_id"]:
                    raise ValueError("conflicting grounded ROLE identity at one coordinate")
                result[key] = role["entity_id"]
    return result


def replay_entity_losses(trainer: V3Trainer, article: ValidatedGoldArticle,
                         replay: SourceFunnelResult, *, phase: str) -> ReplaySupervision:
    """Audit coreference on retrieved candidates with known Gold identity.

    Unknown predictions are ignored, not labelled negative. Gold coordinates
    absent from the runtime candidate universe count as retrieval misses.
    """
    if article.split not in ("train", "dev") or phase != "entity_identity":
        raise ValueError("replay Entity supervision needs train/dev article and Entity phase")
    if article.raw.article_version_id != replay.article_version_id or article.raw.content_sha256 != replay.content_sha256:
        raise ValueError("replay and Gold source versions differ")
    candidates = replay.entity_candidates_post_budget
    gold = _gold_entity_coordinates(article)
    retrieved = {(row["start"], row["end"]) for row in candidates}
    known = [gold.get((row["start"], row["end"])) for row in candidates]
    retrieval = {"ENTITY": {"gold": len(gold), "hit": len(set(gold) & retrieved),
                             "miss": len(set(gold) - retrieved),
                             "predicted": len(candidates),
                             "matched_candidates": sum(value is not None for value in known)}}
    losses: dict[str, torch.Tensor] = {}
    active: dict[str, bool] = {}
    if candidates:
        layout = trainer.compiler.layout_builder.build(article.raw)
        windows = source_windows_from_layout(layout, pad_token_id=trainer.collator.pad_token_id)
        key = FrozenSourceViewKey.from_config(
            article.raw, windows, backbone=trainer.core.config.backbone,
            tokenizer_sha256=trainer.tokenizer_sha256,
            dtype=trainer.core.config.dtype, source_view="all")
        batch = windows.article_view(article.raw, view="all").to(trainer.device)
        frozen = trainer.features.build(batch, cache_key=key, scope="predicted_regather")
        with trainer.core.forward_shared(batch, frozen) as shared:
            aligned = [(layout.align({"start": row["start"], "end": row["end"],
                                      "text": row["text"]}), "ENTITY") for row in candidates]
            features = trainer.core.exact_source_span(
                layout=layout, batch=batch, backbone=frozen,
                token_states=shared.token_states,
                sentence_states=shared.sentence_states,
                document_state=shared.document_state,
                candidate_encoder=trainer.core.candidate_span, rows=aligned)
            states = features.states
            pairs = [(a, b) for a, b in combinations(range(len(candidates)), 2)
                     if known[a] is not None and known[b] is not None]
            if pairs:
                indices = torch.tensor(pairs, dtype=torch.long, device=states.device)
                policy = states.new_tensor([
                    (float(candidates[a]["entity_type"] is not None and
                           candidates[a]["entity_type"] == candidates[b]["entity_type"]),
                     float("ROLE" in candidates[a]["origins"] and "ROLE" in candidates[b]["origins"]),
                     float(("ROLE" in candidates[a]["origins"]) != ("ROLE" in candidates[b]["origins"])),
                     min(abs(candidates[a]["start"] - candidates[b]["start"]) /
                         max(len(article.raw.content), 1), 1.0)) for a, b in pairs])
                logits = trainer.core.task_modules["entity_coreference"](
                    states, indices, shared.document_state[0], policy)
                labels = torch.tensor([int(known[a] == known[b]) for a, b in pairs],
                                      dtype=torch.long, device=states.device)
                losses["entity_coreference"] = F.cross_entropy(logits, labels)
                active["entity_coreference"] = True
    return ReplaySupervision(losses, active, retrieval, replay.binding)


def _replay_temporal_occurrences(structure: Mapping[str, object]
                                 ) -> tuple[TemporalOccurrence, ...]:
    """Rehydrate the producer's exact scalar Time carrier for source-only P5 policy."""
    required = ("local_id", "evidence_ids", "start", "end", "text",
                "normalized_value", "granularity", "normalization_status",
                "attached_event_ids", "attachment_status", "calendar_eligible",
                "public_calendar_candidate", "projection_safe", "projection_reason",
                "normalization_contexts", "normalization_reason")
    output = []
    for row in structure["times"]:
        if any(key not in row for key in required):
            raise ValueError("predicted replay Time carrier lacks source policy fields")
        output.append(TemporalOccurrence(
            row["local_id"], tuple(row["evidence_ids"]), row["start"], row["end"],
            row["text"], row["normalized_value"], row["granularity"],
            row["normalization_status"], tuple(row["attached_event_ids"]),
            row["attachment_status"], row["calendar_eligible"],
            row["public_calendar_candidate"], row["projection_safe"],
            row["projection_reason"],
            tuple(RelativeMonthContext(**context)
                  for context in row["normalization_contexts"]),
            row["normalization_reason"]))
    return tuple(output)


def replay_event_identity_loss(trainer: V3Trainer, worker: V3ServingWorker,
                               article: ValidatedGoldArticle,
                               replay: SourceFunnelResult) -> ReplaySupervision:
    """Score retrieved Event pairs with producer-resolved Entity/Time channels.

    The producer runs its full runtime closure once. The student re-gathers only
    those detached coordinates, so the producer's discrete decisions stay fixed.
    """
    assert_frozen_producer(trainer, worker)
    raw = article.raw
    if article.split not in ("train", "dev") or raw.content_sha256 != replay.content_sha256:
        raise ValueError("Event replay requires matching train/dev Gold")
    full = worker.analyze(article_id=raw.article_id, content=raw.content,
                          article_version_id=raw.article_version_id,
                          published_at=raw.published_at, enable_primary=False)
    if (full.audit["source_funnel"]["selected"] != replay.selected or
            full.audit["source_funnel"]["binding"] != replay.binding):
        raise ValueError("full runtime and source replay selected different candidates")
    structure = full.audit["predicted_structure"]
    occurrences = _replay_temporal_occurrences(structure)
    confidence = tuple(EventOptionalConfidenceEvidence(**row)
                       for row in structure["event_confidence_evidence"])
    optional_counts = structure["event_optional_source_counts"]
    if (len(optional_counts) != len(structure["members"]) or
            any(len(row) != 6 for row in optional_counts)):
        raise ValueError("predicted replay Event optional source counts differ")
    member_rows = structure["members"]
    gold_events_by_span: dict[tuple[int, int], list[str]] = {}
    for row in article.annotations["events"]:
        key = (row["span"]["start"], row["span"]["end"])
        gold_events_by_span.setdefault(key, []).append(row["event_id"])
    gold_event = {key: ids[0] for key, ids in gold_events_by_span.items()
                  if len(ids) == 1}
    gold_cluster = {event_id: cluster["cluster_id"]
                    for cluster in article.annotations["event_clusters"]
                    for event_id in cluster["event_ids"]}
    matched = [gold_event.get((row["start"], row["end"])) for row in member_rows]
    predicted_keys = {(row["start"], row["end"]) for row in member_rows}
    retrieval = {"EVENT": {"gold": len(article.annotations["events"]),
                            "hit": len(set(gold_event) & predicted_keys),
                            "miss": len(article.annotations["events"]) -
                                    len(set(gold_event) & predicted_keys),
                            "predicted": len(member_rows),
                            "matched_candidates": sum(value is not None for value in matched)}}
    pairs = [(a, b) for a, b in combinations(range(len(member_rows)), 2)
             if matched[a] is not None and matched[b] is not None]
    if not pairs:
        return ReplaySupervision({}, {}, retrieval, replay.binding)
    layout = trainer.compiler.layout_builder.build(raw)
    windows = source_windows_from_layout(layout, pad_token_id=trainer.collator.pad_token_id)
    key = FrozenSourceViewKey.from_config(
        raw, windows, backbone=trainer.core.config.backbone,
        tokenizer_sha256=trainer.tokenizer_sha256,
        dtype=trainer.core.config.dtype, source_view="all")
    batch = windows.article_view(raw, view="all").to(trainer.device)
    frozen = trainer.features.build(batch, cache_key=key, scope="predicted_regather")
    # Only the runtime carrier supplies candidates and closure membership.
    sources = []
    for row in member_rows:
        sources.append((row["start"], row["end"], row["text"], "EVENT"))
        if row["trigger_start"] is not None:
            sources.append((row["trigger_start"], row["trigger_end"],
                            row["trigger_text"], "TRIGGER"))
        sources.extend((role["start"], role["end"], role["text"], "PARTICIPANT")
                       for role in row["roles"])
    representative_ids = set(structure["entity_representatives"].values())
    sources.extend((row["start"], row["end"], row["text"], "ENTITY")
                   for row in replay.entity_candidates_post_budget
                   if row["candidate_id"] in representative_ids)
    sources.extend((row["start"], row["end"], row["text"], "TIME")
                   for row in structure["time_evidence"])
    unique = tuple(dict.fromkeys(sources))
    with trainer.core.forward_shared(batch, frozen) as shared:
        aligned = [(layout.align({"start": start, "end": end, "text": value}), kind)
                   for start, end, value, kind in unique]
        features = trainer.core.exact_source_span(
            layout=layout, batch=batch, backbone=frozen,
            token_states=shared.token_states,
            sentence_states=shared.sentence_states,
            document_state=shared.document_state,
            candidate_encoder=trainer.core.candidate_span, rows=aligned)
        states = dict(zip(unique, features.states))
        sums, counts, members = replay_event_member_channels(
            structure, replay.entity_candidates_post_budget, states,
            shared.document_state[0])
        head = trainer.core.task_modules["event_coreference"]
        entity_representatives = set(structure["entity_representatives"])
        missing_entities = tuple(sorted({role.entity_id for member in members
                                         for role in member.roles if role.entity_id is not None
                                         and role.entity_id not in entity_representatives}))
        lease = EventMemberFeatureLease(
            article_version_id=raw.article_version_id,
            content_sha256=raw.content_sha256, members=members,
            channel_sums=sums, channel_counts=counts,
            document_state=shared.document_state[0],
            provenance=EventFeatureProvenance("PREDICTED", "PREDICTED"),
            original_sentence_states=original_sentence_states(
                layout, shared.sentence_states[0]),
            original_sentence_spans=layout.sentence_spans,
            missing_entity_features=missing_entities, role_states={})
        try:
            bundle = build_event_pair_feature_bundle(
                lease, confidence_evidence=confidence,
                optional_source_counts=optional_counts)
            # The whole retained inventory is encoded, including Events with no
            # selected supervised pair in this replay batch.
            encoded = head.encode_events(bundle)
            lease.set_encoded_event_features(
                encoded, member_ids=tuple(member.member_id for member in members))
            sentence_indices = event_member_sentence_indices(lease)
            canonical = tuple(sorted({(min(a, b), max(a, b)) for a, b in pairs}))
            policy = event_pair_policy_features(
                article=raw, members=members, occurrences=occurrences,
                sentence_spans=layout.sentence_spans, pairs=canonical,
                reference=encoded)
            positions = {pair: index for index, pair in enumerate(canonical)}
            policy_indices = torch.tensor(
                [positions[(min(a, b), max(a, b))] for a, b in pairs],
                dtype=torch.long, device=encoded.device)
            indices = torch.tensor(pairs, dtype=torch.long,
                                   device=encoded.device)
            logits = head(bundle, encoded, sentence_indices, indices,
                          policy[policy_indices])
        finally:
            lease.close()
        labels = torch.tensor([int(gold_cluster[matched[a]] == gold_cluster[matched[b]])
                               for a, b in pairs], dtype=torch.long, device=encoded.device)
        loss = F.cross_entropy(logits, labels)
    return ReplaySupervision({"event_coreference": loss},
                             {"event_coreference": True}, retrieval, replay.binding)


@dataclass(frozen=True, slots=True)
class PredictedReplayAudit:
    """Scalar-only dev diagnostic; no optimizer graph or training authority."""

    phase: str
    loss_values: dict[str, float]
    retrieval: dict[str, dict[str, int]]
    binding: dict[str, object]
    producer_full_analyze: bool


@torch.no_grad()
def audit_predicted_replay(trainer: V3Trainer, worker: V3ServingWorker,
                           article: ValidatedGoldArticle, *, phase: str
                           ) -> PredictedReplayAudit:
    """Retain historical replay as a dev audit without backward edges.

    P5/P6 still call the historical full producer and therefore do not replace
    the stage-limited phase evaluator.
    """
    if article.split != "dev" or phase not in (
            "entity_role_time_attribution_sources", "entity_identity",
            "entity_role_time_attribution", "event_identity", "cluster_consumers"):
        raise ValueError("predicted replay audit requires dev and a downstream phase")
    replay = build_predicted_source_replay(trainer, worker, article.raw)
    if phase == "entity_identity":
        scored = replay_entity_losses(trainer, article, replay, phase=phase)
    elif phase == "event_identity":
        scored = replay_event_identity_loss(trainer, worker, article, replay)
    elif phase == "cluster_consumers":
        full = worker.analyze(
            article_id=article.raw.article_id, content=article.raw.content,
            article_version_id=article.raw.article_version_id,
            published_at=article.raw.published_at, enable_primary=False)
        if (full.audit["source_funnel"]["selected"] != replay.selected or
                full.audit["source_funnel"]["binding"] != replay.binding):
            raise ValueError("cluster replay source and full runtime differ")
        clusters = set(full.audit["predicted_structure"]["member_to_cluster"].values())
        scored = ReplaySupervision({}, {}, {"EVENT_CLUSTER": {
            "predicted": len(clusters), "gold": len(article.annotations["event_clusters"])}},
            replay.binding)
    else:
        scored = ReplaySupervision({}, {}, {}, replay.binding)
    if any(value.requires_grad for value in scored.losses.values()):
        raise RuntimeError("predicted dev diagnostic retained an optimizer graph")
    return PredictedReplayAudit(
        phase, {name: float(value) for name, value in scored.losses.items()},
        scored.retrieval, scored.binding,
        phase in ("event_identity", "cluster_consumers"))


def replay_event_member_channels(
        structure: Mapping[str, object], entity_candidates: Sequence[dict],
        states: Mapping[tuple[int, int, str, str], torch.Tensor],
        document_state: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, tuple[EventMember, ...]]:
    """Compose student Event channels at the frozen runtime's scalar coordinates."""
    candidates = {row["candidate_id"]: row for row in entity_candidates}
    entity_states = {}
    for entity_id, candidate_id in structure["entity_representatives"].items():
        row = candidates.get(candidate_id)
        if row is None or structure["candidate_to_entity"].get(candidate_id) != entity_id:
            raise ValueError("Event representative is absent from frozen Entity candidates")
        entity_states[entity_id] = states[(row["start"], row["end"], row["text"], "ENTITY")]
    evidence = {row["time_id"]: row for row in structure["time_evidence"]}
    if len(evidence) != len(structure["time_evidence"]):
        raise ValueError("duplicate frozen Time evidence ID")
    time_states = {}
    for row in structure["times"]:
        ids = row["evidence_ids"]
        if not ids or any(time_id not in evidence for time_id in ids):
            raise ValueError("Time occurrence lacks frozen source evidence")
        time_states[row["local_id"]] = torch.stack([
            states[(evidence[time_id]["start"], evidence[time_id]["end"],
                    evidence[time_id]["text"], "TIME")] for time_id in ids]).mean(dim=0)
    zero = document_state.new_zeros(document_state.shape)
    channel_sums = []
    channel_counts = []
    members = []
    for row in structure["members"]:
        channels: list[list[torch.Tensor]] = [[] for _ in range(8)]
        channels[0].append(states[(row["start"], row["end"], row["text"], "EVENT")])
        if row["trigger_start"] is not None:
            channels[1].append(states[(row["trigger_start"], row["trigger_end"],
                                       row["trigger_text"], "TRIGGER")])
        roles = tuple(MemberRoleFact(**role) for role in row["roles"])
        for role in roles:
            channels[2 + ("ACTOR", "TARGET", "PLACE").index(role.role)].append(
                states[(role.start, role.end, role.text, "PARTICIPANT")])
        for entity_id in sorted({role.entity_id for role in roles if role.entity_id}):
            if entity_id in entity_states:
                channels[5].append(entity_states[entity_id])
        for time_id in row["time_ids"]:
            if time_id not in time_states:
                raise ValueError("Event attachment lacks frozen Time occurrence")
            channels[6].append(time_states[time_id])
        channels[7].append(document_state)
        channel_sums.append(torch.stack([torch.stack(values).sum(dim=0)
                                         if values else zero for values in channels]))
        channel_counts.append([len(values) for values in channels])
        members.append(EventMember(row["member_id"], row["start"], row["end"],
                                   row["text"], row["trigger_start"], row["trigger_end"],
                                   row["trigger_text"], roles, tuple(row["time_ids"])))
    sums = torch.stack(channel_sums)
    return sums, sums.new_tensor(channel_counts), tuple(members)


def regather_predicted_source_states(trainer: V3Trainer, raw: RawArticle,
                                     replay: SourceFunnelResult) -> tuple[torch.Tensor, ...]:
    """Re-encode selected source coordinates with current trainable DCE/bridge.

    This does not run a loss or backward. Callers retain the returned tensor
    graph for future downstream objectives; no Gold identity enters the rows.
    """
    if (raw.article_id != replay.article_id or
            raw.article_version_id != replay.article_version_id or
            raw.content_sha256 != replay.content_sha256):
        raise ValueError("re-gather article differs from detached source replay")
    rows = []
    for kind in ("EVENT", "STATEMENT", "ENTITY", "TIME", "TRIGGER"):
        rows.extend((row, kind) for row in replay.selected[kind])
    for key, selected in replay.selected.items():
        if key not in ("EVENT", "STATEMENT", "ENTITY", "TIME", "TRIGGER"):
            rows.extend((row, "PARTICIPANT") for row in selected)
    rows.extend((row, "STATEMENT") for row in replay.assertor_sources)
    if not rows:
        return ()
    layout = trainer.compiler.layout_builder.build(raw)
    windows = source_windows_from_layout(layout, pad_token_id=trainer.collator.pad_token_id)
    key = FrozenSourceViewKey.from_config(
        raw, windows, backbone=trainer.core.config.backbone,
        tokenizer_sha256=trainer.tokenizer_sha256,
        dtype=trainer.core.config.dtype, source_view="all")
    batch = windows.article_view(raw, view="all").to(trainer.device)
    frozen = trainer.features.build(batch, cache_key=key, scope="predicted_regather")
    with trainer.core.forward_shared(batch, frozen) as shared:
        aligned = [(layout.align({"start": row["start"], "end": row["end"],
                                  "text": row["text"]}), kind) for row, kind in rows]
        features = trainer.core.exact_source_span(
            layout=layout, batch=batch, backbone=frozen,
            token_states=shared.token_states,
            sentence_states=shared.sentence_states,
            document_state=shared.document_state,
            candidate_encoder=trainer.core.candidate_span,
            rows=aligned)
        return tuple(features.states[index] for index in range(len(aligned)))
