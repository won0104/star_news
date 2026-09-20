"""최종 Event coreference 전용 fresh member encoder·대칭 pair scorer."""

from __future__ import annotations

from hashlib import sha256

import torch
from torch import nn

from models.v3_pretraining.architecture import V3Core


EVENT_CHANNELS = ("semantic", "trigger", "actor", "target", "place",
                  "entity", "time", "document")


class EventIdentityHead(nn.Module):
    """실제 Event/role/Entity/Time 채널을 모아 same-occurrence pair만 판정한다."""

    def __init__(self, hidden: int = 256) -> None:
        super().__init__()
        self.member_encoder = nn.Sequential(nn.LayerNorm(hidden * len(EVENT_CHANNELS) + len(EVENT_CHANNELS)),
                                            nn.Linear(hidden * len(EVENT_CHANNELS) + len(EVENT_CHANNELS), hidden),
                                            nn.GELU(), nn.LayerNorm(hidden))
        self.pair = nn.Sequential(nn.LayerNorm(hidden * 3 + 4),
                                  nn.Linear(hidden * 3 + 4, hidden), nn.GELU(), nn.Linear(hidden, 2))

    def encode_members(self, channel_sums: torch.Tensor, channel_counts: torch.Tensor) -> torch.Tensor:
        if (channel_sums.ndim != 3 or channel_sums.shape[1] != len(EVENT_CHANNELS) or
                channel_counts.shape != channel_sums.shape[:2]):
            raise ValueError("Event channels need [N,8,H] sums and [N,8] counts")
        means = channel_sums / channel_counts.clamp_min(1).unsqueeze(-1)
        masks = (channel_counts > 0).to(means.dtype)
        return self.member_encoder(torch.cat((means.flatten(1), masks), dim=-1))

    def forward(self, member_states: torch.Tensor, pair_indices: torch.Tensor,
                document_state: torch.Tensor, geometry: torch.Tensor) -> torch.Tensor:
        if pair_indices.ndim != 2 or pair_indices.shape[1] != 2 or geometry.shape != (len(pair_indices), 4):
            raise ValueError("Event pair/geometry shapes differ")
        if pair_indices.numel() == 0:
            return member_states.new_empty((0, 2))
        left, right = member_states[pair_indices[:, 0]], member_states[pair_indices[:, 1]]
        features = torch.cat((torch.abs(left - right), left * right,
                              document_state.unsqueeze(0).expand(len(pair_indices), -1),
                              geometry), dim=-1)
        return self.pair(features)


def register_event_heads(core: V3Core) -> None:
    name = "event_coreference"
    seed_offset = int(sha256(name.encode()).hexdigest()[:8], 16)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(core.config.seed + seed_offset)
        module = EventIdentityHead(core.config.context.hidden_size)
    core.register_task(name, module, source_run_id=core.config.run_id)
