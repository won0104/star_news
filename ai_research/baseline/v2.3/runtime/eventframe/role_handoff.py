"""raw B2 filler의 마지막 feature 소비를 compact role aggregate로 이관한다.

resolved/unresolved filler 모두 같은 Participant span model L8/context로 인코딩한다.
role sum/count/confidence와 literal grounding을 보존하고 raw dict는 보유하지 않는다.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Mapping

import torch

from models.contracts import SPAN_KINDS
from .resolution import DEFAULT_PARTICIPANT_STATE_CHUNK_SIZE, _align, encode_candidate_states_bounded


ROLES = ("ACTOR", "TARGET", "PLACE")


@dataclass(slots=True)
class RoleRepresentationAggregate:
    representation_sum: torch.Tensor | None
    member_count: int
    confidence_sum: float
    literal_texts: tuple[str, ...]
    groundings: tuple[dict[str, Any], ...]

    @property
    def confidence_mean(self) -> float:
        return self.confidence_sum / self.member_count if self.member_count else 0.0

    def release(self) -> None:
        self.representation_sum = None


@dataclass(slots=True)
class EventRoleFeatureHandoff:
    by_event: dict[str, dict[str, RoleRepresentationAggregate]]
    source_model: str = "PARTICIPANT_B2_CANDIDATE_SPAN_ENCODER_L8"

    def aggregate(self, event_id: str, role: str) -> RoleRepresentationAggregate | None:
        return self.by_event.get(event_id, {}).get(role)

    def release(self) -> None:
        for roles in self.by_event.values():
            for aggregate in roles.values():
                aggregate.release()
        self.by_event.clear()


@torch.inference_mode()
def build_event_role_feature_handoff(
    prepared, backbone, canonical_events,
    participants: Mapping[str, Mapping[str, list[Mapping[str, Any]]]],
    participant_span_model,
) -> EventRoleFeatureHandoff:
    """B2 이후 한 번만 raw filler를 읽고 같은 model의 sum/count로 닫는다."""
    event_sentence_by_id = {
        str(row["prediction_id"]): int(row["sentence_index"])
        for row in canonical_events
    }
    event_ids = set(event_sentence_by_id)
    if set(participants) - event_ids:
        raise ValueError("role handoff contains a noncanonical Event")
    device = next(participant_span_model.parameters()).device
    batch = prepared.batch.to(device)
    context = participant_span_model.document_context(
        backbone.layer(8), batch.source_token_mask,
        batch.sentence_mask, batch.sentence_positions,
    )
    specs = []
    grouped: dict[tuple[str, str], list[tuple[int, Mapping[str, Any]]]] = defaultdict(list)
    for event_id in sorted(event_ids):
        for role in ROLES:
            for filler in participants.get(event_id, {}).get(role, ()):
                aligned = _align(
                    prepared, int(filler["char_start"]), int(filler["char_end"]),
                )
                if aligned is None:
                    continue  # 기존 EventFeatureBundle도 alignment 실패 filler는 쓰지 않았다.
                index = len(specs)
                specs.append(aligned)
                grouped[(event_id, role)].append((index, filler))
    kinds = [SPAN_KINDS.index("EVIDENCE")] * len(specs)
    states = encode_candidate_states_bounded(
        participant_span_model, backbone, context, batch.source_token_mask,
        specs, kinds, device=device,
        chunk_size=DEFAULT_PARTICIPANT_STATE_CHUNK_SIZE,
    )[0]
    by_event = {}
    for event_id in sorted(event_ids):
        roles = {}
        for role in ROLES:
            members = grouped.get((event_id, role), ())
            representation_sum = (
                torch.stack([states[index] for index, _ in members]).sum(0).detach()
                if members else None
            )
            groundings = []
            for filler in participants.get(event_id, {}).get(role, ()):
                aligned = _align(
                    prepared, int(filler["char_start"]), int(filler["char_end"]),
                )
                groundings.append({
                    "article_version_id": prepared.article.article_version_id,
                    "sentence_index": (
                        aligned[0] if aligned is not None else
                        event_sentence_by_id[event_id]
                    ),
                    "char_start": int(filler["char_start"]),
                    "char_end": int(filler["char_end"]),
                    "text": str(filler["text"]),
                    "score": float(filler.get("score", 1.0)),
                    "representation_contributed": aligned is not None,
                })
            roles[role] = RoleRepresentationAggregate(
                representation_sum, len(members),
                sum(float(filler.get("score", 1.0)) for _index, filler in members),
                tuple(str(filler["text"]) for filler in
                      participants.get(event_id, {}).get(role, ())),
                tuple(groundings),
            )
        by_event[event_id] = roles
    return EventRoleFeatureHandoff(by_event)
