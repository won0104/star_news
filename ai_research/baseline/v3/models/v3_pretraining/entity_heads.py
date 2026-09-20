"""동일 source representation 위의 bounded Entity 우선순위·대칭 동일성·방향 해소 head."""

from __future__ import annotations

from hashlib import sha256

import torch
from torch import nn

from models.v3_pretraining.architecture import V3Core


class EntityPriorityHead(nn.Module):
    """NER-only 점수 때문에 필수 role 후보가 삭제되지 않도록 union 뒤에 점수를 낸다."""

    def __init__(self, hidden: int = 256) -> None:
        super().__init__()
        self.classifier = nn.Sequential(nn.LayerNorm(hidden + 3), nn.Linear(hidden + 3, hidden),
                                        nn.GELU(), nn.Linear(hidden, 1))

    def forward(self, states: torch.Tensor, origins: torch.Tensor) -> torch.Tensor:
        if states.ndim != 2 or origins.shape != (states.shape[0], 3):
            raise ValueError("Entity priority expects [N,H] and [N,3] origins")
        return self.classifier(torch.cat((states, origins), dim=-1)).squeeze(-1)


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


class RoleEntityHead(nn.Module):
    """role span→Entity cluster의 방향 pair만 점수화한다."""

    def __init__(self, hidden: int = 256) -> None:
        super().__init__()
        self.classifier = nn.Sequential(nn.LayerNorm(hidden * 5 + 4),
                                        nn.Linear(hidden * 5 + 4, hidden), nn.GELU(),
                                        nn.Linear(hidden, 1))

    def forward(self, role_states: torch.Tensor, entity_states: torch.Tensor,
                pair_indices: torch.Tensor, document_state: torch.Tensor,
                policy: torch.Tensor) -> torch.Tensor:
        if pair_indices.ndim != 2 or pair_indices.shape[1] != 2 or policy.shape != (len(pair_indices), 4):
            raise ValueError("role/entity pair/policy shapes differ")
        if pair_indices.numel() == 0:
            return role_states.new_empty((0,))
        role, entity = role_states[pair_indices[:, 0]], entity_states[pair_indices[:, 1]]
        features = torch.cat((role, entity, role * entity, role - entity,
                              document_state.unsqueeze(0).expand(len(pair_indices), -1), policy), dim=-1)
        return self.classifier(features).squeeze(-1)


def register_entity_heads(core: V3Core) -> None:
    factories = (("entity_priority", EntityPriorityHead),
                 ("role_entity", RoleEntityHead),
                 ("entity_coreference", EntityIdentityHead))
    for name, factory in factories:
        seed_offset = int(sha256(name.encode()).hexdigest()[:8], 16)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(core.config.seed + seed_offset)
            module = factory(core.config.context.hidden_size)
        core.register_task(name, module, source_run_id=core.config.run_id)
