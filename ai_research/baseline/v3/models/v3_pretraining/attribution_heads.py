"""Statement source와 세 방향 관계의 fresh task weight.

Assertor source는 Entity 후보와 독립적으로 찾는다. 관계의 입력은 final local
identity가 확정된 뒤의 request-scoped feature이며 Gold ID는 입력되지 않는다.
"""

from __future__ import annotations

from hashlib import sha256

import torch
from torch import nn

from models.v3_pretraining.architecture import V3Core


class AssertorSourceHead(nn.Module):
    def __init__(self, hidden: int = 256) -> None:
        super().__init__()
        self.token = nn.Sequential(nn.LayerNorm(hidden * 3), nn.Linear(hidden * 3, hidden),
                                   nn.GELU(), nn.Linear(hidden, 2))
        self.exists = nn.Linear(hidden, 1)
        self.span = nn.Sequential(nn.LayerNorm(hidden * 3), nn.Linear(hidden * 3, hidden),
                                  nn.GELU(), nn.Linear(hidden, 1))
        self.residual = nn.Sequential(nn.LayerNorm(hidden * 2 + 2),
                                      nn.Linear(hidden * 2 + 2, hidden), nn.GELU(),
                                      nn.Linear(hidden, 2))

    def token_logits(self, statement: torch.Tensor, tokens: torch.Tensor) -> torch.Tensor:
        owner = statement.unsqueeze(0).expand_as(tokens)
        return self.token(torch.cat((owner, tokens, owner * tokens), dim=-1))

    def existence_logit(self, statement: torch.Tensor) -> torch.Tensor:
        return self.exists(statement).squeeze(-1)

    def span_logit(self, statement: torch.Tensor, source: torch.Tensor) -> torch.Tensor:
        return self.span(torch.cat((statement, source, statement * source), dim=-1)).squeeze(-1)

    def residual_delta(self, statement: torch.Tensor, source: torch.Tensor,
                       bridge_residual: torch.Tensor) -> torch.Tensor:
        return self.residual(torch.cat((statement, source, bridge_residual), dim=-1))


class DirectedRelationHead(nn.Module):
    """순서가 보존되는 source/target pair 점수; symmetric coreference와 무관하다."""

    def __init__(self, hidden: int = 256) -> None:
        super().__init__()
        self.scorer = nn.Sequential(nn.LayerNorm(hidden * 5),
                                    nn.Linear(hidden * 5, hidden), nn.GELU(),
                                    nn.Linear(hidden, 1))

    def forward(self, left: torch.Tensor, right: torch.Tensor,
                document: torch.Tensor) -> torch.Tensor:
        if left.shape != right.shape or left.ndim != 2 or document.shape != left.shape[1:]:
            raise ValueError("directed pair feature shapes differ")
        common = document.unsqueeze(0).expand_as(left)
        return self.scorer(torch.cat((left, right, left - right, left * right, common),
                                     dim=-1)).squeeze(-1)


def register_attribution_heads(core: V3Core) -> None:
    for name, factory in (("assertor_source", AssertorSourceHead),
                          ("assertor_entity", DirectedRelationHead),
                          ("about", DirectedRelationHead),
                          ("causes", DirectedRelationHead)):
        seed_offset = int(sha256(name.encode()).hexdigest()[:8], 16)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(core.config.seed + seed_offset)
            module = factory(core.config.context.hidden_size)
        core.register_task(name, module, source_run_id=core.config.run_id)
