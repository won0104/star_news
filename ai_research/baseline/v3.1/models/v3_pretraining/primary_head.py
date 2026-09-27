"""final EventCluster·Statement의 같은 score 축을 만드는 fresh Primary scorer.

member attention은 request-scoped final lease에서만 실행된다. importance rank나
relation label/degree는 feature가 아니며, 출력 개수 정책도 이 head 밖에 둔다.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Mapping

import torch
from torch import nn

from models.v3_pretraining.architecture import V3Core
from runtime.v3_pretraining.event_features import FinalClusterFeatureView


class PrimaryScorer(nn.Module):
    def __init__(self, hidden: int = 256, gate_hidden: int = 64) -> None:
        super().__init__()
        self.member_adapter = nn.Sequential(nn.LayerNorm(hidden), nn.Linear(hidden, hidden),
                                            nn.GELU())
        self.member_gate = nn.Linear(hidden, gate_hidden, bias=False)
        self.document_gate = nn.Linear(hidden, gate_hidden, bias=True)
        self.gate_scalar = nn.Linear(gate_hidden, 1, bias=False)
        # 3 unique role channels, trigger/Entity/Time, eight availability and two conflict masks.
        event_input = hidden * 9 + 10
        self.event_adapter = nn.Sequential(nn.LayerNorm(event_input),
                                           nn.Linear(event_input, hidden), nn.GELU())
        self.statement_adapter = nn.Sequential(nn.LayerNorm(hidden * 4 + 1),
                                               nn.Linear(hidden * 4 + 1, hidden), nn.GELU())
        self.shared_scalar = nn.Linear(hidden, 1)

    def event_embeddings(self, view: FinalClusterFeatureView) -> torch.Tensor:
        """final membership별 stable segmented attention과 unique role summary."""
        if (view.member_cluster_indices is None
                or view.role_unique_means is None or view.role_unique_mask is None):
            raise ValueError("Primary needs final member and unique-role feature lease")
        count = len(view.cluster_ids)
        hidden = view.document_state.shape[-1]
        if (len(set(view.member_ids)) != len(view.member_ids)
                or len(view.member_cluster_indices) != len(view.member_ids)
                or view.role_unique_means.shape != (count, 3, hidden)
                or view.role_unique_mask.shape != (count, 3)):
            raise ValueError("Primary final cluster member/role shape mismatch")
        if count == 0:
            if view.member_ids:
                raise ValueError("Primary final cluster member/role shape mismatch")
            return view.document_state.new_empty((0, hidden))
        if view.member_event_features is None:
            raise ValueError("Primary needs precomputed P5 Event features")
        if (view.member_event_features.shape != (len(view.member_ids), hidden)
                or view.member_event_features.device != view.document_state.device
                or view.member_event_features.dtype != view.document_state.dtype):
            raise ValueError("Primary precomputed Event feature shape mismatch")
        adapted = self.member_adapter(view.member_event_features)
        document_gate = self.document_gate(view.document_state)
        logits = self.gate_scalar(torch.tanh(self.member_gate(adapted) + document_gate)).squeeze(-1)
        if (len(view.member_cluster_indices) and
                (int(view.member_cluster_indices.min()) < 0 or
                 int(view.member_cluster_indices.max()) >= count)):
            raise ValueError("member references unknown final EventCluster")
        order = torch.argsort(view.member_cluster_indices, stable=True)
        ordered_states = adapted[order]
        ordered_logits = logits[order]
        segment_sizes = torch.bincount(view.member_cluster_indices, minlength=count).tolist()
        if any(size == 0 for size in segment_sizes):
            raise ValueError("final EventCluster has no retained member")
        pooled = []
        for segment, segment_logits in zip(torch.split(ordered_states, segment_sizes),
                                           torch.split(ordered_logits, segment_sizes)):
            weights = torch.softmax(segment_logits.float(), dim=0).to(adapted.dtype)
            pooled.append((weights.unsqueeze(-1) * segment).sum(dim=0))
        member_pool = torch.stack(pooled)
        summary = torch.cat((view.role_unique_means.flatten(1),
                             view.channel_means[:, [1, 5, 6], :].flatten(1),
                             view.channel_availability_mask.to(member_pool.dtype),
                             view.conflict_mask.to(member_pool.dtype)), dim=-1)
        document = view.document_state.unsqueeze(0).expand(count, -1)
        return self.event_adapter(torch.cat((member_pool, summary,
                                             member_pool * document, document), dim=-1))

    def statement_embedding(self, statement: torch.Tensor,
                            assertor: torch.Tensor | None,
                            document: torch.Tensor) -> torch.Tensor:
        if statement.shape != document.shape:
            raise ValueError("Statement and document representation shape mismatch")
        source = assertor if assertor is not None else torch.zeros_like(statement)
        if source.shape != statement.shape:
            raise ValueError("Assertor source representation shape mismatch")
        mask = statement.new_tensor((float(assertor is not None),))
        return self.statement_adapter(torch.cat((statement, source, statement * document,
                                                 document, mask)))

    def forward(self, view: FinalClusterFeatureView,
                statement_states: Mapping[str, torch.Tensor],
                assertor_states: Mapping[str, torch.Tensor],
                common_adapter: nn.Module) -> dict[str, torch.Tensor]:
        if not set(assertor_states) <= set(statement_states):
            raise ValueError("Assertor feature lacks owning Statement")
        event_vectors = self.event_embeddings(view)
        output = {"E:" + eid: self.shared_scalar(common_adapter(vector)).squeeze(-1)
                  for eid, vector in zip(view.cluster_ids, event_vectors)}
        for sid, state in statement_states.items():
            vector = self.statement_embedding(state, assertor_states.get(sid), view.document_state)
            output["S:" + sid] = self.shared_scalar(common_adapter(vector)).squeeze(-1)
        return output


def register_primary_head(core: V3Core) -> None:
    name = "primary"
    seed_offset = int(sha256(name.encode()).hexdigest()[:8], 16)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(core.config.seed + seed_offset)
        module = PrimaryScorer(core.config.context.hidden_size)
    core.register_task(name, module, source_run_id=core.config.run_id)
