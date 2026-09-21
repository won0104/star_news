"""Gold 없는 Event pair 점수→complete-link final identity; relation/Primary는 미구현."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import torch

from models.v3_pretraining.architecture import V3Core
from runtime.v3_pretraining.event_features import EventMemberFeatureLease, event_pair_geometry
from runtime.v3_pretraining.event_identity import EventClosure, close_event_identity
from runtime.v3_pretraining.source_layout import RawArticle


@dataclass(frozen=True, slots=True)
class EventIdentityDecodeConfig:
    max_pairs: int = 4096
    chunk_size: int = 128
    margin_threshold: float = 0.0
    status: str = "PROVISIONAL_ENGINEERING_ONLY"

    def __post_init__(self) -> None:
        if self.max_pairs <= 0 or self.chunk_size <= 0:
            raise ValueError("Event pair budget/chunk must be positive")


@dataclass(frozen=True, slots=True)
class EventIdentityDecodeResult:
    closure: EventClosure
    scored_pairs: int
    eligible_pairs: int
    partial: bool
    policy_status: str


@torch.no_grad()
def score_event_identity(article: RawArticle, lease: EventMemberFeatureLease, *,
                         core: V3Core,
                         config: EventIdentityDecodeConfig = EventIdentityDecodeConfig(),
                         strict_equivalence_pairs: frozenset[tuple[str, str]] = frozenset()) -> EventIdentityDecodeResult:
    """학습된 symmetric score 외의 관련성/시간 선후 관계를 merge 근거로 쓰지 않는다."""
    if (lease.closed or lease.member_states is None or lease.document_state is None or
            lease.provenance.membership_source != "PREDICTED" or
            lease.provenance.role_source != "PREDICTED" or
            lease.article_version_id != article.article_version_id or
            lease.content_sha256 != article.content_sha256):
        raise ValueError("predicted Event scorer needs live matching source features")
    if "event_coreference" not in core.task_modules:
        raise ValueError("Event coreference head is not registered")
    eligible = [(a, b) for a, b in combinations(range(len(lease.members)), 2)
                if lease.members[a].aligned and lease.members[b].aligned]
    selected = eligible[:config.max_pairs]
    decisions = {}
    for start in range(0, len(selected), config.chunk_size):
        chunk = selected[start:start + config.chunk_size]
        indices = torch.tensor(chunk, dtype=torch.long, device=lease.member_states.device)
        logits = core.task_modules["event_coreference"](
            lease.member_states, indices, lease.document_state,
            event_pair_geometry(lease.members, chunk, content_length=len(article.content),
                                reference=lease.member_states))
        if not torch.isfinite(logits).all():
            raise ValueError("Event pair scorer returned non-finite logits")
        decisions.update({(lease.members[a].member_id, lease.members[b].member_id):
                          bool(float(logits[index, 1] - logits[index, 0]) >= config.margin_threshold)
                          for index, (a, b) in enumerate(chunk)})
    closure = close_event_identity(article, lease.members, pair_decisions=decisions,
                                   strict_equivalence_pairs=strict_equivalence_pairs,
                                   source_mode="PREDICTED")
    return EventIdentityDecodeResult(closure, len(selected), len(eligible),
                                     len(selected) < len(eligible) or closure.status in (
                                         "BOUNDED_PARTIAL", "PARTIAL_ALIGNMENT"), config.status)
