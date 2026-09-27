"""Time value의 Gold-only 문자 감독과 Event→Time 방향 attachment fresh heads."""

from __future__ import annotations

from hashlib import sha256
import math

import torch
from torch import nn

from models.v3_pretraining.architecture import V3Core


TIME_FORMATS = ("YEAR", "MONTH", "DAY", "FISCAL_YEAR",
                "INTERVAL_YEAR", "INTERVAL_MONTH", "INTERVAL_DAY")
TIME_CHARS = "0123456789FY-/"


def time_format(kind: str, granularity: str) -> str:
    return f"INTERVAL_{granularity}" if kind == "INTERVAL" else granularity


class TimeNormalizationHead(nn.Module):
    """Gold normalized_value가 있을 때만 format+전체 문자열에 gradient를 보낸다."""

    def __init__(self, hidden: int = 256) -> None:
        super().__init__()
        self.format = nn.Sequential(nn.LayerNorm(hidden), nn.Linear(hidden, hidden),
                                    nn.GELU(), nn.Linear(hidden, len(TIME_FORMATS)))
        self.character = nn.Sequential(nn.LayerNorm(hidden + 32), nn.Linear(hidden + 32, hidden),
                                       nn.GELU(), nn.Linear(hidden, len(TIME_CHARS)))

    def forward(self, states: torch.Tensor, *, length: int) -> tuple[torch.Tensor, torch.Tensor]:
        if states.ndim != 2 or length < 0:
            raise ValueError("Time normalization expects [N,H] and nonnegative full Gold length")
        positions = torch.arange(length, dtype=states.dtype, device=states.device)
        frequencies = torch.exp(torch.arange(16, dtype=states.dtype, device=states.device) *
                                (-math.log(10000.0) / 15))
        phase = positions[:, None] * frequencies[None, :]
        positional = torch.cat((phase.sin(), phase.cos()), dim=-1)
        expanded = states[:, None, :].expand(-1, length, -1)
        features = torch.cat((expanded, positional[None].expand(len(states), -1, -1)), dim=-1)
        return self.format(states), self.character(features)


class EventTimeHead(nn.Module):
    """실제 Event occurrence와 textual Time 후보의 directed attachment scorer."""

    def __init__(self, hidden: int = 256) -> None:
        super().__init__()
        self.classifier = nn.Sequential(nn.LayerNorm(hidden * 5 + 4),
                                        nn.Linear(hidden * 5 + 4, hidden), nn.GELU(),
                                        nn.Linear(hidden, 1))

    def forward(self, event_states: torch.Tensor, time_states: torch.Tensor,
                pair_indices: torch.Tensor, document_state: torch.Tensor,
                geometry: torch.Tensor) -> torch.Tensor:
        if pair_indices.ndim != 2 or pair_indices.shape[1] != 2 or geometry.shape != (len(pair_indices), 4):
            raise ValueError("Event-Time pair/geometry shapes differ")
        if pair_indices.numel() == 0:
            return event_states.new_empty((0,))
        event, time = event_states[pair_indices[:, 0]], time_states[pair_indices[:, 1]]
        features = torch.cat((event, time, event * time, event - time,
                              document_state.unsqueeze(0).expand(len(pair_indices), -1),
                              geometry), dim=-1)
        return self.classifier(features).squeeze(-1)


def register_time_heads(core: V3Core) -> None:
    for name, factory in (("event_time", EventTimeHead),
                          ("time_normalization", TimeNormalizationHead)):
        seed_offset = int(sha256(name.encode()).hexdigest()[:8], 16)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(core.config.seed + seed_offset)
            module = factory(core.config.context.hidden_size)
        core.register_task(name, module, source_run_id=core.config.run_id)
