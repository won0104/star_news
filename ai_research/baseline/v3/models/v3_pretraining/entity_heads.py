"""동일 source representation 위의 대칭 Entity 동일성 head."""

from __future__ import annotations

from hashlib import sha256

import torch
from torch import nn

from models.v3_pretraining.architecture import V3Core


class EntityIdentityHead(nn.Module):
    """후보 pair만 점수화하는 대칭 KEEP/MERGE scorer; full N×N×H 생성 없음."""

    def __init__(self, hidden: int = 256) -> None:
        super().__init__()
        self.classifier = nn.Sequential(nn.LayerNorm(hidden * 3 + 4),
                                        nn.Linear(hidden * 3 + 4, hidden), nn.GELU(),
                                        nn.Linear(hidden, 2))

    def forward(self, states: torch.Tensor, pair_indices: torch.Tensor,
                document_state: torch.Tensor, policy: torch.Tensor) -> torch.Tensor:
        if pair_indices.ndim != 2 or pair_indices.shape[1] != 2 or policy.shape != (len(pair_indices), 4):
            raise ValueError("Entity identity pair/policy shapes differ")
        if pair_indices.numel() == 0:
            return states.new_empty((0, 2))
        left, right = states[pair_indices[:, 0]], states[pair_indices[:, 1]]
        features = torch.cat((torch.abs(left - right), left * right,
                              document_state.unsqueeze(0).expand(len(pair_indices), -1), policy), dim=-1)
        return self.classifier(features)


def register_entity_heads(core: V3Core) -> None:
    factories = (("entity_coreference", EntityIdentityHead),)
    for name, factory in factories:
        seed_offset = int(sha256(name.encode()).hexdigest()[:8], 16)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(core.config.seed + seed_offset)
            module = factory(core.config.context.hidden_size)
        core.register_task(name, module, source_run_id=core.config.run_id)
