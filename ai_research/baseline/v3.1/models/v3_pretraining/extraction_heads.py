"""기존 추출 topology를 v3 fresh registry에 등록하는 작은 task별 모듈."""

from __future__ import annotations

from hashlib import sha256

import torch
from torch import nn

from models.attributes.statement_type import StatementTypeHead
from models.spans.entity import EntitySpanNativeHead
from models.spans.time import TimeExpressionSpanNativeHead
from models.spans.trigger import TriggerBoundaryHead
from runtime.eventframe.models import ParticipantBoundaryHead
from models.v3_pretraining.architecture import V3Core


ENTITY_TYPES = ("PERSON", "ORGANIZATION", "LOCATION", "PRODUCT", "GENERIC")
STATEMENT_TYPES = ("FORECAST", "CLAIM", "EVALUATION")
PARTICIPANT_ROLES = ("ACTOR", "TARGET", "PLACE")


class ExactSemanticBoundaryHead(nn.Module):
    """좌표 residual과 N1 exact-boundary fitness를 서로 다른 출력으로 만든다."""

    def __init__(self, hidden: int = 256) -> None:
        super().__init__()
        self.delta = nn.Sequential(nn.LayerNorm(hidden + 2), nn.Linear(hidden + 2, hidden),
                                   nn.GELU(), nn.Linear(hidden, 2))
        self.fitness = nn.Sequential(nn.LayerNorm(hidden), nn.Linear(hidden, hidden),
                                     nn.GELU(), nn.Linear(hidden, 1))

    def forward(self, states: torch.Tensor, bridge_residuals: torch.Tensor) -> torch.Tensor:
        return bridge_residuals + self.delta(torch.cat((states, bridge_residuals), dim=-1))

    def fitness_score(self, states: torch.Tensor) -> torch.Tensor:
        """Score whether each exact candidate has the reviewed Gold boundary (N1)."""
        return self.fitness(states).squeeze(-1)


class ExactSemanticValidityHead(nn.Module):
    """canonical-window 밖의 의미 span도 endpoint feature로 적격성을 평가한다."""

    def __init__(self, hidden: int = 256) -> None:
        super().__init__()
        self.classifier = nn.Sequential(nn.LayerNorm(hidden), nn.Linear(hidden, hidden),
                                        nn.GELU(), nn.Linear(hidden, 1))

    def forward(self, states: torch.Tensor) -> torch.Tensor:
        return self.classifier(states).squeeze(-1)


class TriggerExtractionHead(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.boundary = TriggerBoundaryHead(768, 256, 0.1)
        self.span_score = nn.Linear(256, 1)


class ParticipantExtractionHead(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.boundary = ParticipantBoundaryHead(256, 0.1)
        self.span_score = nn.Sequential(nn.Linear(512, 256), nn.GELU(), nn.Linear(256, 3))


class EntityExtractionHead(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.boundary = TriggerBoundaryHead(768, 256, 0.1)
        # ENTITY type confidence와 독립된 exact mention existence decision.
        self.existence = EntitySpanNativeHead(256, 128, 1, 0.1)
        self.typing = EntitySpanNativeHead(256, 128, len(ENTITY_TYPES), 0.1)


class TimeExtractionHead(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.boundary = TriggerBoundaryHead(768, 256, 0.1)
        self.span = TimeExpressionSpanNativeHead(256, 128, 0.1)


def register_extraction_heads(core: V3Core) -> None:
    """task별 독립 seed와 한 v3 run owner로 5번 head를 fresh 등록한다."""
    factories = (
        ("semantic_boundary", ExactSemanticBoundaryHead),
        ("semantic_validity", ExactSemanticValidityHead),
        ("trigger", TriggerExtractionHead),
        ("participant", ParticipantExtractionHead),
        ("entity_mention", EntityExtractionHead),
        ("time_mention", TimeExtractionHead),
        ("statement_type", lambda: StatementTypeHead(256, len(STATEMENT_TYPES), 0.1)),
    )
    for name, factory in factories:
        seed_offset = int(sha256(name.encode()).hexdigest()[:8], 16)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(core.config.seed + seed_offset)
            module = factory()
        core.register_task(name, module, source_run_id=core.config.run_id)
