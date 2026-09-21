"""Event member→final cluster의 request-scoped typed tensor 소유 경계.

Event/Time은 7번 lease, Trigger/role/Entity는 같은 direct-gather pass의 transient
extra state만 소비한다. final scalar LocalEventState에는 tensor를 넣지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch

from models.v3_pretraining.event_heads import EVENT_CHANNELS, EventIdentityHead
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


class EventMemberFeatureLease:
    """coreference와 final aggregation까지 보유되는 member별 중간 tensor owner."""

    def __init__(self, *, article_version_id: str, content_sha256: str,
                 members: tuple[EventMember, ...], channel_sums: torch.Tensor,
                 channel_counts: torch.Tensor, member_states: torch.Tensor,
                 document_state: torch.Tensor, provenance: EventFeatureProvenance,
                 missing_entity_features: tuple[str, ...],
                 role_states: dict[str, torch.Tensor]) -> None:
        self.article_version_id = article_version_id
        self.content_sha256 = content_sha256
        self.members = members
        self.channel_sums: torch.Tensor | None = channel_sums
        self.channel_counts: torch.Tensor | None = channel_counts
        self.member_states: torch.Tensor | None = member_states
        self.role_states: dict[str, torch.Tensor] | None = role_states
        self.document_state: torch.Tensor | None = document_state
        self.provenance = provenance
        self.missing_entity_features = missing_entity_features
        self.closed = False

    def close(self) -> None:
        self.channel_sums = None
        self.channel_counts = None
        self.member_states = None
        self.role_states = None
        self.document_state = None
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
                                head: EventIdentityHead,
                                provenance: EventFeatureProvenance) -> EventMemberFeatureLease:
    """한 번 계산된 source state의 sum/count를 보존하며 역할 없는 zero를 평균하지 않는다."""
    if (time_lease.closed or time_lease.event_states is None or time_lease.time_states is None or
            time_lease.document_state is None or time_lease.extra_states is None):
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
        if trigger is None:
            raise ValueError("Event trigger feature missing from shared source pass")
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
    member_states = head.encode_members(channel_sums, channel_counts)
    return EventMemberFeatureLease(
        article_version_id=time_lease.article_version_id,
        content_sha256=time_lease.content_sha256,
        members=tuple(members), channel_sums=channel_sums,
        channel_counts=channel_counts, member_states=member_states,
        document_state=time_lease.document_state, provenance=provenance,
        missing_entity_features=tuple(sorted(missing_entity)),
        role_states={key.removeprefix("ROLE:"): value
                     for key, value in time_lease.extra_states.items()
                     if key.startswith("ROLE:")})


def event_pair_geometry(members: Sequence[EventMember], pairs: Sequence[tuple[int, int]],
                        *, content_length: int, reference: torch.Tensor) -> torch.Tensor:
    if content_length <= 0:
        raise ValueError("Event pair source length must be positive")
    return reference.new_tensor([
        (min(abs(members[a].start - members[b].start) / content_length, 1.0),
         float(members[a].trigger_text == members[b].trigger_text),
         float(bool(set(members[a].time_ids) & set(members[b].time_ids))),
         float(bool({role.entity_id for role in members[a].roles if role.entity_id} &
                    {role.entity_id for role in members[b].roles if role.entity_id})))
        for a, b in pairs])


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
    member_states: torch.Tensor | None
    member_cluster_indices: torch.Tensor | None
    role_unique_means: torch.Tensor | None
    role_unique_mask: torch.Tensor | None


class FinalClusterFeatureLease:
    """9번 관계와 10번 Primary가 모두 반환한 뒤에만 final tensor를 해제한다."""

    CONSUMERS = frozenset({"RELATION", "PRIMARY"})

    def __init__(self, *, cluster_ids: tuple[str, ...], channel_means: torch.Tensor,
                 channel_counts: torch.Tensor, conflict_mask: torch.Tensor,
                 mean_reference: torch.Tensor,
                 document_state: torch.Tensor, article_version_id: str,
                 content_sha256: str, member_ids: tuple[str, ...] = (),
                 member_states: torch.Tensor | None = None,
                 member_cluster_indices: torch.Tensor | None = None,
                 role_unique_means: torch.Tensor | None = None,
                 role_unique_mask: torch.Tensor | None = None,
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
        self.member_states: torch.Tensor | None = member_states
        self.member_cluster_indices: torch.Tensor | None = member_cluster_indices
        self.role_unique_means: torch.Tensor | None = role_unique_means
        self.role_unique_mask: torch.Tensor | None = role_unique_mask
        self.article_version_id = article_version_id
        self.content_sha256 = content_sha256
        self.source_mode = source_mode
        self.pending_consumers = set(self.CONSUMERS)
        self.closed = False

    def view_for(self, consumer: str) -> FinalClusterFeatureView:
        if (self.closed or consumer not in self.pending_consumers or self.channel_means is None or
                self.channel_counts is None or self.conflict_mask is None or
                self.mean_reference is None or self.document_state is None):
            raise RuntimeError("final Event feature consumer has been released or owner is closed")
        return FinalClusterFeatureView(self.cluster_ids, self.channel_means, self.channel_counts,
                                       self.channel_counts > 0, self.conflict_mask,
                                       self.mean_reference, self.document_state,
                                       self.member_ids, self.member_states,
                                       self.member_cluster_indices, self.role_unique_means,
                                       self.role_unique_mask)

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
        self.member_states = None
        self.member_cluster_indices = None
        self.role_unique_means = None
        self.role_unique_mask = None
        self.pending_consumers.clear()
        self.closed = True


def finalize_cluster_features(member_lease: EventMemberFeatureLease,
                              closure: EventClosure) -> FinalClusterFeatureLease:
    """membership 확정 직후 all-member sum/count로 parameter-free mean reference 생성."""
    if (member_lease.closed or member_lease.channel_sums is None or
            member_lease.channel_counts is None or member_lease.document_state is None
            or member_lease.member_states is None or member_lease.role_states is None):
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
    ordered_member_states = (member_lease.member_states[[member_index[mid] for mid in member_ids]]
                             if member_ids else member_lease.member_states.new_empty(
                                 (0, member_lease.member_states.shape[-1])))
    return FinalClusterFeatureLease(cluster_ids=tuple(row.local_id for row in closure.events),
                                    channel_means=means_tensor, channel_counts=counts_tensor,
                                    conflict_mask=conflict_tensor,
                                    mean_reference=reference_tensor,
                                    document_state=member_lease.document_state,
                                    article_version_id=member_lease.article_version_id,
                                    content_sha256=member_lease.content_sha256,
                                    member_ids=tuple(member_ids),
                                    member_states=ordered_member_states,
                                    member_cluster_indices=torch.tensor(member_cluster_indices,
                                                                        dtype=torch.long,
                                                                        device=ordered_member_states.device),
                                    role_unique_means=unique_role_tensor,
                                    role_unique_mask=unique_mask_tensor,
                                    source_mode=member_lease.provenance.membership_source)
