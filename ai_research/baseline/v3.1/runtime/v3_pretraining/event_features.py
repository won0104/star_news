"""Event member→final cluster의 request-scoped typed tensor 소유 경계.

Event/Time은 7번 lease, Trigger/role/Entity는 같은 direct-gather pass의 transient
extra state만 소비한다. final scalar LocalEventState에는 tensor를 넣지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import torch

from models.v3_pretraining.event_heads import (EVENT_CHANNELS,
                                               OPTIONAL_CHANNEL_INDICES,
                                               EventPairFeatureBundle)
from models.v3_pretraining.pair_context import (EndpointSentenceSummary,
                                                summarize_event_members)
from runtime.v3_pretraining.event_identity import EventClosure, EventMember
from runtime.v3_pretraining.temporal import TemporalOccurrence
from runtime.v3_pretraining.temporal_scoring import EventTimeFeatureLease


@dataclass(frozen=True, slots=True)
class EventFeatureProvenance:
    membership_source: str  # GOLD_ORACLE or PREDICTED
    role_source: str  # GOLD_ORACLE or PREDICTED

    def __post_init__(self) -> None:
        if self.membership_source not in ("GOLD_ORACLE", "PREDICTED") or self.role_source not in (
                "GOLD_ORACLE", "PREDICTED"):
            raise ValueError("Event feature provenance is diagnostic only but must be declared")


@dataclass(frozen=True, slots=True)
class EventOptionalConfidenceEvidence:
    """한 optional Event 채널의 기존 source decision 확률과 producer."""

    member_id: str
    channel: str  # trigger, actor, target, place, entity, time
    source_id: str
    probability: float
    producer: str


_CONFIDENCE_PRODUCERS = {
    "trigger": "TRIGGER_SPAN_DECISION",
    "actor": "PARTICIPANT_SPAN_DECISION",
    "target": "PARTICIPANT_SPAN_DECISION",
    "place": "PARTICIPANT_SPAN_DECISION",
    "entity": "V23_ENTITY_NATIVE_TYPE",
    "time": "V23_EVENT_TIME_ATTACHMENT",
}
_OPTIONAL_CHANNELS = tuple(EVENT_CHANNELS[index] for index in OPTIONAL_CHANNEL_INDICES)


class EventMemberFeatureLease:
    """coreference와 final aggregation까지 보유되는 member별 중간 tensor owner."""

    def __init__(self, *, article_version_id: str, content_sha256: str,
                 members: tuple[EventMember, ...], channel_sums: torch.Tensor,
                 channel_counts: torch.Tensor,
                 document_state: torch.Tensor, provenance: EventFeatureProvenance,
                 original_sentence_states: torch.Tensor,
                 original_sentence_spans: tuple[tuple[int, int], ...],
                 missing_entity_features: tuple[str, ...],
                 role_states: dict[str, torch.Tensor]) -> None:
        self.article_version_id = article_version_id
        self.content_sha256 = content_sha256
        self.members = members
        self.channel_sums: torch.Tensor | None = channel_sums
        self.channel_counts: torch.Tensor | None = channel_counts
        self.encoded_event_features: torch.Tensor | None = None
        self.role_states: dict[str, torch.Tensor] | None = role_states
        self.document_state: torch.Tensor | None = document_state
        self.original_sentence_states: torch.Tensor | None = original_sentence_states
        self.original_sentence_spans = original_sentence_spans
        self.provenance = provenance
        self.missing_entity_features = missing_entity_features
        self.closed = False

    def set_encoded_event_features(self, features: torch.Tensor, *,
                                   member_ids: Sequence[str]) -> None:
        """P5가 전체 retained Event에 대해 계산한 벡터를 원래 member 순서로 보관한다."""
        if self.closed or self.channel_sums is None or self.document_state is None:
            raise RuntimeError("Event member feature lease already closed")
        if self.encoded_event_features is not None:
            raise ValueError("Event features already encoded for this request")
        if tuple(member_ids) != tuple(member.member_id for member in self.members):
            raise ValueError("encoded Event feature order differs from retained members")
        if (features.ndim != 2 or features.shape !=
                (len(self.members), self.document_state.shape[-1]) or
                features.device != self.document_state.device or
                features.dtype != self.document_state.dtype or
                not bool(torch.isfinite(features).all())):
            raise ValueError("encoded Event features need finite [member,H] source states")
        self.encoded_event_features = features

    def close(self) -> None:
        # Scalar members are needed through final aggregation, but retaining
        # them in a closed lease extends every role fact into PUBLIC projection.
        self.members = ()
        self.channel_sums = None
        self.channel_counts = None
        self.encoded_event_features = None
        self.role_states = None
        self.document_state = None
        self.original_sentence_states = None
        self.original_sentence_spans = ()
        self.closed = True

    def __enter__(self) -> "EventMemberFeatureLease":
        if self.closed:
            raise RuntimeError("Event member feature lease already closed")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def build_event_member_features(time_lease: EventTimeFeatureLease, *,
                                members: Sequence[EventMember],
                                occurrences: Sequence[TemporalOccurrence],
                                provenance: EventFeatureProvenance) -> EventMemberFeatureLease:
    """한 번 계산된 source state의 sum/count를 보존하며 역할 없는 zero를 평균하지 않는다."""
    if (time_lease.closed or time_lease.event_states is None or time_lease.time_states is None or
            time_lease.document_state is None or time_lease.extra_states is None
            or time_lease.original_sentence_states is None):
        raise RuntimeError("Event feature construction needs live upstream source lease")
    if time_lease.source_mode != provenance.role_source:
        raise ValueError("Event role feature provenance and upstream producer differ")
    if tuple(row.member_id for row in members) != time_lease.event_ids:
        raise ValueError("Event member order differs from upstream source representation")
    if len({row.local_id for row in occurrences}) != len(occurrences):
        raise ValueError("duplicate Time occurrence ID")
    time_index = {tid: index for index, tid in enumerate(time_lease.time_ids)}
    occurrence_states = {}
    for row in occurrences:
        indices = [time_index[tid] for tid in row.evidence_ids if tid in time_index]
        if not indices:
            raise ValueError("Time occurrence lacks shared source representation")
        occurrence_states[row.local_id] = time_lease.time_states[indices].mean(dim=0)
    zero = time_lease.document_state.new_zeros(time_lease.document_state.shape)
    sums = []
    counts = []
    missing_entity: set[str] = set()
    for index, member in enumerate(members):
        channels: list[list[torch.Tensor]] = [[] for _ in EVENT_CHANNELS]
        channels[0].append(time_lease.event_states[index])
        trigger = time_lease.extra_states.get("TRIGGER:" + member.member_id)
        if member.trigger_start is not None and trigger is None:
            raise ValueError("Event trigger feature missing from shared source pass")
        if trigger is not None:
            channels[1].append(trigger)
        unique_entities = set()
        for role in member.roles:
            state = time_lease.extra_states.get("ROLE:" + role.evidence_id)
            if state is None:
                raise ValueError("Event role feature missing from shared source pass")
            channels[2 + ("ACTOR", "TARGET", "PLACE").index(role.role)].append(state)
            if role.entity_id is not None:
                unique_entities.add(role.entity_id)
        for entity_id in sorted(unique_entities):
            state = time_lease.extra_states.get("ENTITY:" + entity_id)
            if state is None:
                missing_entity.add(entity_id)
            else:
                channels[5].append(state)
        for time_id in member.time_ids:
            state = occurrence_states.get(time_id)
            if state is None:
                raise ValueError("Event attachment lacks Time occurrence feature")
            channels[6].append(state)
        channels[7].append(time_lease.document_state)
        sums.append(torch.stack([torch.stack(values).sum(dim=0) if values else zero
                                 for values in channels]))
        counts.append([len(values) for values in channels])
    if sums:
        channel_sums = torch.stack(sums)
        channel_counts = time_lease.document_state.new_tensor(counts)
    else:
        channel_sums = time_lease.document_state.new_empty((0, len(EVENT_CHANNELS), len(zero)))
        channel_counts = time_lease.document_state.new_empty((0, len(EVENT_CHANNELS)))
    return EventMemberFeatureLease(
        article_version_id=time_lease.article_version_id,
        content_sha256=time_lease.content_sha256,
        members=tuple(members), channel_sums=channel_sums,
        channel_counts=channel_counts,
        document_state=time_lease.document_state, provenance=provenance,
        original_sentence_states=time_lease.original_sentence_states,
        original_sentence_spans=time_lease.original_sentence_spans,
        missing_entity_features=tuple(sorted(missing_entity)),
        role_states={key.removeprefix("ROLE:"): value
                     for key, value in time_lease.extra_states.items()
                     if key.startswith("ROLE:")})


def _member_optional_sources(lease: EventMemberFeatureLease,
                             member: EventMember) -> tuple[tuple[str, ...], ...]:
    trigger = (("TRIGGER:" + member.member_id,) if member.trigger_text is not None else ())
    roles = tuple(tuple(row.evidence_id for row in member.roles if row.role == role)
                  for role in ("ACTOR", "TARGET", "PLACE"))
    entities = tuple(sorted({row.entity_id for row in member.roles
                             if row.entity_id is not None and
                             row.entity_id not in lease.missing_entity_features}))
    return (trigger, *roles, entities, member.time_ids)


def event_member_sentence_indices(lease: EventMemberFeatureLease) -> torch.LongTensor:
    """Event별 원문 문장 anchor를 source 좌표에서 결정한다."""
    if lease.closed or lease.document_state is None or lease.original_sentence_states is None:
        raise RuntimeError("Event sentence indices need live member features")
    indices = []
    for member in lease.members:
        summary = summarize_event_members(
            lease.original_sentence_states, lease.original_sentence_spans,
            ((member.member_id, member.start, member.end),))
        indices.append(summary.anchor_index)
    return torch.tensor(indices, dtype=torch.long, device=lease.document_state.device)


def build_event_pair_feature_bundle(
        lease: EventMemberFeatureLease, *,
        confidence_evidence: Sequence[EventOptionalConfidenceEvidence] = (),
        optional_source_counts: Sequence[Sequence[int]] | None = None,
) -> EventPairFeatureBundle:
    """P5의 모든 retained Event를 pair routing 이전에 인코딩할 source bundle."""
    if (lease.closed or lease.channel_sums is None or lease.channel_counts is None or
            lease.document_state is None or lease.original_sentence_states is None):
        raise RuntimeError("Event bundle needs live member source features")
    count = len(lease.members)
    if (lease.channel_sums.shape != (count, len(EVENT_CHANNELS),
                                     lease.document_state.numel()) or
            lease.channel_counts.shape != (count, len(EVENT_CHANNELS))):
        raise ValueError("Event source channels differ from retained members")
    means = lease.channel_sums / lease.channel_counts.clamp_min(1).unsqueeze(-1)
    if count:
        contexts = torch.stack(tuple(summarize_event_members(
            lease.original_sentence_states, lease.original_sentence_spans,
            ((member.member_id, member.start, member.end),)).context
            for member in lease.members))
    else:
        contexts = lease.document_state.new_empty((0, lease.document_state.numel()))
    member_index = {row.member_id: index for index, row in enumerate(lease.members)}
    if len(member_index) != count:
        raise ValueError("duplicate Event member ID")
    expected = {row.member_id: _member_optional_sources(lease, row)
                for row in lease.members}
    expected_counts = lease.channel_counts.new_tensor(
        [[len(sources) for sources in expected[row.member_id]] for row in lease.members]
    ).reshape(count, len(OPTIONAL_CHANNEL_INDICES))
    if not torch.equal(lease.channel_counts[:, OPTIONAL_CHANNEL_INDICES], expected_counts):
        raise ValueError("Event optional channel counts differ from exact source facts")
    if optional_source_counts is None:
        source_counts = expected_counts
    else:
        if (len(optional_source_counts) != count or any(
                len(row) != len(OPTIONAL_CHANNEL_INDICES) or
                any(not isinstance(value, int) or isinstance(value, bool) or value < 0
                    for value in row) for row in optional_source_counts)):
            raise ValueError("Event optional source counts need nonnegative [member,6] rows")
        source_counts = lease.channel_counts.new_tensor(optional_source_counts).reshape(
            count, len(OPTIONAL_CHANNEL_INDICES))
    counts = source_counts.clamp(max=8) / 8
    confidence = counts.new_zeros(counts.shape)
    known = torch.zeros(counts.shape, dtype=torch.bool, device=counts.device)
    evidence_index: dict[tuple[str, str, str], float] = {}
    for row in confidence_evidence:
        member_sources = expected.get(row.member_id)
        if member_sources is None or row.channel not in _CONFIDENCE_PRODUCERS:
            raise ValueError("Event confidence references unknown member/channel")
        channel_index = _OPTIONAL_CHANNELS.index(row.channel)
        if row.source_id not in member_sources[channel_index]:
            raise ValueError("Event confidence source does not belong to channel")
        expected_producer = ("GOLD_ORACLE" if lease.provenance.role_source == "GOLD_ORACLE"
                             else _CONFIDENCE_PRODUCERS[row.channel])
        if (row.producer != expected_producer or
                not math.isfinite(row.probability) or
                not 0 <= row.probability <= 1):
            raise ValueError("Event confidence lacks same-decision producer/probability")
        key = row.member_id, row.channel, row.source_id
        if key in evidence_index:
            raise ValueError("duplicate Event confidence source")
        evidence_index[key] = row.probability
    for member_id, sources_by_channel in expected.items():
        index = member_index[member_id]
        for channel_index, sources in enumerate(sources_by_channel):
            if not sources:
                continue
            channel = _OPTIONAL_CHANNELS[channel_index]
            values = [evidence_index.get((member_id, channel, source)) for source in sources]
            if all(value is not None for value in values):
                # v2.3 role confidence averaged member scores; other optional
                # channels used the strongest source decision.
                aggregate = (sum(values) / len(values) if channel in
                             ("actor", "target", "place") else max(values))
                confidence[index, channel_index] = aggregate
                known[index, channel_index] = True
    bundle = EventPairFeatureBundle(
        means, lease.channel_counts, contexts, lease.document_state,
        counts, confidence, known)
    bundle.validate()
    return bundle


@dataclass(frozen=True, slots=True)
class FinalClusterFeatureView:
    cluster_ids: tuple[str, ...]
    channel_means: torch.Tensor
    channel_counts: torch.Tensor
    channel_availability_mask: torch.Tensor
    conflict_mask: torch.Tensor  # ROLE_ENDPOINT_CONFLICT, PARTIAL_ALIGNMENT
    mean_reference: torch.Tensor
    document_state: torch.Tensor
    member_ids: tuple[str, ...]
    member_channel_sums: torch.Tensor | None
    member_channel_counts: torch.Tensor | None
    member_cluster_indices: torch.Tensor | None
    role_unique_means: torch.Tensor | None
    role_unique_mask: torch.Tensor | None
    original_sentence_states: torch.Tensor | None
    original_sentence_spans: tuple[tuple[int, int], ...]
    event_sentence_summaries: tuple[EndpointSentenceSummary, ...]
    member_event_features: torch.Tensor | None = None


class FinalClusterFeatureLease:
    """Relation과 Primary가 모두 반환한 뒤에만 final tensor를 해제한다."""

    CONSUMERS = frozenset({"RELATION", "PRIMARY"})

    def __init__(self, *, cluster_ids: tuple[str, ...], channel_means: torch.Tensor,
                 channel_counts: torch.Tensor, conflict_mask: torch.Tensor,
                 mean_reference: torch.Tensor,
                 document_state: torch.Tensor, article_version_id: str,
                 content_sha256: str, member_ids: tuple[str, ...] = (),
                 member_channel_sums: torch.Tensor | None = None,
                 member_channel_counts: torch.Tensor | None = None,
                 member_cluster_indices: torch.Tensor | None = None,
                 role_unique_means: torch.Tensor | None = None,
                 role_unique_mask: torch.Tensor | None = None,
                 original_sentence_states: torch.Tensor | None = None,
                 original_sentence_spans: tuple[tuple[int, int], ...] = (),
                 event_sentence_summaries: tuple[EndpointSentenceSummary, ...] = (),
                 member_event_features: torch.Tensor | None = None,
                 source_mode: str = "PREDICTED") -> None:
        if source_mode not in ("PREDICTED", "GOLD_ORACLE"):
            raise ValueError("unknown final Event feature provenance")
        self.cluster_ids = cluster_ids
        self.channel_means: torch.Tensor | None = channel_means
        self.channel_counts: torch.Tensor | None = channel_counts
        self.conflict_mask: torch.Tensor | None = conflict_mask
        self.mean_reference: torch.Tensor | None = mean_reference
        self.document_state: torch.Tensor | None = document_state
        self.member_ids = member_ids
        self.member_channel_sums: torch.Tensor | None = member_channel_sums
        self.member_channel_counts: torch.Tensor | None = member_channel_counts
        self.member_event_features: torch.Tensor | None = member_event_features
        self.member_cluster_indices: torch.Tensor | None = member_cluster_indices
        self.role_unique_means: torch.Tensor | None = role_unique_means
        self.role_unique_mask: torch.Tensor | None = role_unique_mask
        self.original_sentence_states: torch.Tensor | None = original_sentence_states
        self.original_sentence_spans = original_sentence_spans
        self.event_sentence_summaries = event_sentence_summaries
        self.article_version_id = article_version_id
        self.content_sha256 = content_sha256
        self.source_mode = source_mode
        self.pending_consumers = set(self.CONSUMERS)
        self.closed = False

    def view_for(self, consumer: str) -> FinalClusterFeatureView:
        if (self.closed or consumer not in self.pending_consumers or self.channel_means is None or
                self.channel_counts is None or self.conflict_mask is None or
                self.mean_reference is None or self.document_state is None
                or (consumer == "RELATION" and (
                    self.original_sentence_states is None
                    or len(self.event_sentence_summaries) != len(self.cluster_ids)))):
            raise RuntimeError("final Event feature consumer has been released or owner is closed")
        return FinalClusterFeatureView(self.cluster_ids, self.channel_means, self.channel_counts,
                                       self.channel_counts > 0, self.conflict_mask,
                                       self.mean_reference, self.document_state,
                                       self.member_ids, self.member_channel_sums,
                                       self.member_channel_counts,
                                       self.member_cluster_indices, self.role_unique_means,
                                       self.role_unique_mask, self.original_sentence_states,
                                       self.original_sentence_spans,
                                       self.event_sentence_summaries,
                                       self.member_event_features)

    def release(self, consumer: str) -> None:
        if consumer not in self.pending_consumers:
            raise ValueError("unknown or already released Event cluster consumer")
        self.pending_consumers.remove(consumer)
        if not self.pending_consumers:
            self.close()

    def close(self) -> None:
        self.channel_means = None
        self.channel_counts = None
        self.conflict_mask = None
        self.mean_reference = None
        self.document_state = None
        self.member_channel_sums = None
        self.member_channel_counts = None
        self.member_event_features = None
        self.member_cluster_indices = None
        self.role_unique_means = None
        self.role_unique_mask = None
        self.original_sentence_states = None
        self.original_sentence_spans = ()
        self.event_sentence_summaries = ()
        self.pending_consumers.clear()
        self.closed = True


def finalize_cluster_features(member_lease: EventMemberFeatureLease,
                              closure: EventClosure, *,
                              include_member_channel_diagnostics: bool = False
                              ) -> FinalClusterFeatureLease:
    """membership 확정 직후 all-member sum/count로 parameter-free mean reference 생성."""
    if (member_lease.closed or member_lease.channel_sums is None or
            member_lease.channel_counts is None or member_lease.document_state is None
            or member_lease.role_states is None
            or member_lease.original_sentence_states is None):
        raise RuntimeError("final cluster aggregation needs live member features")
    if (member_lease.article_version_id != closure.article_version_id or
            member_lease.content_sha256 != closure.content_sha256):
        raise ValueError("final Event feature source differs from closure source")
    if member_lease.provenance.membership_source != closure.source_mode:
        raise ValueError("final membership provenance differs from feature producer")
    member_index = {member.member_id: index for index, member in enumerate(member_lease.members)}
    if len(member_index) != len(member_lease.members) or set(member_index) != set(closure.member_to_cluster):
        raise ValueError("final Event membership omits upstream feature member")
    channel_means = []
    channel_counts = []
    mean_reference = []
    conflicts = []
    member_ids = []
    member_cluster_indices = []
    unique_roles = []
    unique_masks = []
    zero = member_lease.document_state.new_zeros(member_lease.document_state.shape)
    for cluster_index, cluster in enumerate(closure.events):
        indices = [member_index[mid] for mid in cluster.member_ids]
        member_ids.extend(cluster.member_ids)
        member_cluster_indices.extend([cluster_index] * len(indices))
        sums = member_lease.channel_sums[indices].sum(dim=0)
        counts = member_lease.channel_counts[indices].sum(dim=0)
        means = sums / counts.clamp_min(1).unsqueeze(-1)
        mask = (counts > 0).to(means.dtype)
        reference = (means * mask.unsqueeze(-1)).sum(dim=0) / mask.sum().clamp_min(1)
        channel_means.append(means)
        channel_counts.append(counts)
        mean_reference.append(reference)
        conflicts.append(("ROLE_ENDPOINT_CONFLICT" in cluster.conflict_flags,
                          cluster.status == "PARTIAL_ALIGNMENT"))
        role_means = []
        role_masks = []
        for role_name in ("ACTOR", "TARGET", "PLACE"):
            seen = set()
            states = []
            for role in cluster.roles:
                if role.role != role_name:
                    continue
                key = role.entity_id if role.entity_id is not None else (role.start, role.end, role.text)
                if key in seen:
                    continue
                seen.add(key)
                evidence_id = next((eid for eid in role.evidence_ids
                                    if eid in member_lease.role_states), None)
                if evidence_id is None:
                    raise ValueError("final role summary lost grounded source feature")
                states.append(member_lease.role_states[evidence_id])
            role_means.append(torch.stack(states).mean(dim=0) if states else zero)
            role_masks.append(bool(states))
        unique_roles.append(torch.stack(role_means))
        unique_masks.append(role_masks)
    if closure.events:
        means_tensor = torch.stack(channel_means)
        counts_tensor = torch.stack(channel_counts)
        reference_tensor = torch.stack(mean_reference)
        conflict_tensor = torch.tensor(conflicts, dtype=torch.bool, device=means_tensor.device)
        unique_role_tensor = torch.stack(unique_roles)
        unique_mask_tensor = torch.tensor(unique_masks, dtype=torch.bool, device=means_tensor.device)
    else:
        hidden = member_lease.document_state.shape[-1]
        means_tensor = member_lease.document_state.new_empty((0, len(EVENT_CHANNELS), hidden))
        counts_tensor = member_lease.document_state.new_empty((0, len(EVENT_CHANNELS)))
        reference_tensor = member_lease.document_state.new_empty((0, hidden))
        conflict_tensor = torch.empty((0, 2), dtype=torch.bool, device=reference_tensor.device)
        unique_role_tensor = member_lease.document_state.new_empty((0, 3, hidden))
        unique_mask_tensor = torch.empty((0, 3), dtype=torch.bool, device=reference_tensor.device)
    ordered_indices = [member_index[mid] for mid in member_ids]
    identity_order = ordered_indices == list(range(len(member_lease.members)))
    ordered_member_sums = (member_lease.channel_sums if identity_order else
                           member_lease.channel_sums[ordered_indices]
                           ) if include_member_channel_diagnostics else None
    ordered_member_counts = (member_lease.channel_counts if identity_order else
                             member_lease.channel_counts[ordered_indices]
                             ) if include_member_channel_diagnostics else None
    ordered_event_features = (
        (member_lease.encoded_event_features if identity_order else
         member_lease.encoded_event_features[ordered_indices])
        if member_lease.encoded_event_features is not None else None)
    event_sentence_summaries = tuple(
        summarize_event_members(
            member_lease.original_sentence_states,
            member_lease.original_sentence_spans,
            tuple((member_id, member_lease.members[member_index[member_id]].start,
                   member_lease.members[member_index[member_id]].end)
                  for member_id in cluster.member_ids))
        for cluster in closure.events)
    return FinalClusterFeatureLease(cluster_ids=tuple(row.local_id for row in closure.events),
                                    channel_means=means_tensor, channel_counts=counts_tensor,
                                    conflict_mask=conflict_tensor,
                                    mean_reference=reference_tensor,
                                    document_state=member_lease.document_state,
                                    article_version_id=member_lease.article_version_id,
                                    content_sha256=member_lease.content_sha256,
                                    member_ids=tuple(member_ids),
                                    member_channel_sums=ordered_member_sums,
                                    member_channel_counts=ordered_member_counts,
                                    member_event_features=ordered_event_features,
                                    member_cluster_indices=torch.tensor(member_cluster_indices,
                                                                        dtype=torch.long,
                                                                        device=member_lease.document_state.device),
                                    role_unique_means=unique_role_tensor,
                                    role_unique_mask=unique_mask_tensor,
                                    original_sentence_states=member_lease.original_sentence_states,
                                    original_sentence_spans=member_lease.original_sentence_spans,
                                    event_sentence_summaries=event_sentence_summaries,
                                    source_mode=member_lease.provenance.membership_source)
