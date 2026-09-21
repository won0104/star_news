"""검증된 train Gold의 exact span을 5번 fresh head loss로 연결한다.

Gold ID와 label은 이 adapter 밖으로 전달하지 않는다. 공유 core는 한 번 계산된
backbone/DCE를 소비하며, loss에는 반올림한 token span이나 truncation mask가 없다.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch.nn import functional as F

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from models.v3_pretraining.extraction_heads import ENTITY_TYPES, PARTICIPANT_ROLES, STATEMENT_TYPES
from models.v3_pretraining.exact_span import KIND_LAYER
from training.v3_pretraining.targets import ArticleTargets, SpanTarget


TASKS = ("semantic_proposer", "semantic_boundary", "semantic_validity", "trigger",
         "participant", "entity_mention", "time_mention", "statement_type")


def _kind(row: SpanTarget) -> str:
    return {"semantic_proposer": row.label, "trigger": "TRIGGER",
            "participant": "PARTICIPANT", "entity_mention": "ENTITY",
            "time_mention": "TIME"}[row.task]


def _key(kind: str, row: SpanTarget) -> tuple[str, int, int]:
    return kind, row.alignment.start, row.alignment.end


def _positive(logits: list[torch.Tensor], zero: torch.Tensor) -> torch.Tensor:
    return torch.stack([F.softplus(-value) for value in logits]).mean() if logits else zero


def _residual(predictions: list[torch.Tensor], targets: list[torch.Tensor],
              zero: torch.Tensor) -> torch.Tensor:
    return F.smooth_l1_loss(torch.stack(predictions), torch.stack(targets)) if predictions else zero


@dataclass(frozen=True, slots=True)
class ExtractionLossResult:
    losses: dict[str, torch.Tensor]
    target_count: dict[str, int]
    scored_count: dict[str, int]
    cross_window_count: dict[str, int]

    def validate(self) -> None:
        if set(self.losses) != set(TASKS):
            raise ValueError("extraction loss task set differs")
        for task in TASKS:
            if self.scored_count[task] != self.target_count[task]:
                raise ValueError(f"{task}: exact Gold target was dropped")
            if not torch.isfinite(self.losses[task]):
                raise ValueError(f"{task}: loss is non-finite")


class ExtractionGoldAdapter:
    """Gold-positive loss와 문자 residual을 task별로 분리한 teacher-forced 학습 경계."""

    def __init__(self, core: V3Core) -> None:
        missing = set(TASKS) & set(core.unimplemented_tasks)
        if missing:
            raise ValueError(f"extraction heads not registered: {sorted(missing)}")
        self.core = core

    def loss(self, target: ArticleTargets, batch: ArticleBatch,
             backbone: BackboneOutput, shared: SharedForwardLease) -> ExtractionLossResult:
        if shared.closed or shared.token_states is None or shared.sentence_states is None or shared.document_state is None:
            raise RuntimeError("shared DCE lease has ended")
        if target.layout.article.content != batch.contents[0] or target.article_version_id != target.layout.article.article_version_id:
            raise ValueError("Gold/source article mismatch")
        if len(target.layout.windows) != batch.input_ids.shape[1]:
            raise ValueError("training loss needs the all-window source view")
        if target.layout.tokenizer_sha256 != self.core.config.tokenizer_sha256:
            raise ValueError("Gold target and trainable core tokenizer differ")
        window_index = {window.window_id: index for index, window in enumerate(target.layout.windows)}
        unique: dict[tuple[str, int, int], tuple] = {}
        for task in ("semantic_proposer", "trigger", "participant", "entity_mention", "time_mention"):
            for row in target.spans[task]:
                unique.setdefault(_key(_kind(row), row), (row.alignment, _kind(row)))
        rows = list(unique.values())
        index = {key: offset for offset, key in enumerate(unique)}
        bridge = self.core.exact_source_span(
            layout=target.layout, batch=batch, backbone=backbone,
            token_states=shared.token_states, sentence_states=shared.sentence_states,
            document_state=shared.document_state, candidate_encoder=self.core.candidate_span,
            rows=rows)
        source_endpoints = self.core.exact_source_span.endpoint_logits(shared.token_states)
        def source_boundary(row: SpanTarget, kind: str) -> tuple[torch.Tensor, torch.Tensor]:
            alignment = row.alignment
            start = window_index[alignment.start_ref.window_id]
            end = window_index[alignment.end_ref.window_id]
            channel = list(KIND_LAYER).index(kind)
            return (source_endpoints[0, start, alignment.start_ref.token_position, channel, 0],
                    source_endpoints[0, end, alignment.end_ref.token_position, channel, 1])
        zero = shared.token_states.sum() * 0.0
        losses: dict[str, torch.Tensor] = {}
        counts = {task: len(target.spans[task]) if task in target.spans else 0 for task in TASKS}
        counts["statement_type"] = sum(row.task == "statement_type" for row in target.classes)
        cross = {task: sum(row.alignment.cross_window for row in target.spans[task])
                 if task in target.spans else 0 for task in TASKS}
        scores = {task: 0 for task in TASKS}
        semantic = target.spans["semantic_proposer"]
        semantic_keys = tuple((row.owner_id, row.label, row.alignment.start, row.alignment.end)
                              for row in semantic)
        for task in ("semantic_boundary", "semantic_validity"):
            if semantic_keys != tuple((row.owner_id, row.label, row.alignment.start, row.alignment.end)
                                      for row in target.spans[task]):
                raise ValueError(f"{task}: Gold target differs from semantic proposer source")
        semantic_index = [index[_key(row.label, row)] for row in semantic]
        proposer_logits: list[torch.Tensor] = []
        local_semantic = []
        local_semantic_rows = []
        for row, feature_index in zip(semantic, semantic_index):
            alignment = row.alignment
            proposer_logits.extend(source_boundary(row, row.label))
            if alignment.canonical_window_id is None:
                proposer_logits.append(bridge.link_logits[feature_index])
            else:
                window = window_index[alignment.canonical_window_id]
                label = ("EVENT", "STATEMENT").index(row.label)
                proposer_logits.append(shared.proposal_logits[0, window,
                                                               alignment.start_ref.token_position,
                                                               alignment.end_ref.token_position, label])
                local_semantic.append((window, alignment.start_ref.token_position,
                                       alignment.end_ref.token_position + 1))
                local_semantic_rows.append(row)
            scores["semantic_proposer"] += 1
        losses["semantic_proposer"] = _positive(proposer_logits, zero)
        if local_semantic:
            proposals = torch.tensor([local_semantic], dtype=torch.long, device=shared.token_states.device)
            mask = torch.ones((1, len(local_semantic)), dtype=torch.bool, device=proposals.device)
            canonical = self.core.canonical_span(backbone.layer(8), shared.token_states,
                                                 proposals, mask, batch.source_token_mask)
            local_boundary = [canonical.boundary_logits[0, pos, ("EVENT", "STATEMENT").index(row.label)]
                              for pos, row in enumerate(local_semantic_rows)]
            local_validity = [canonical.semantic_logits[0, pos, ("EVENT", "STATEMENT").index(row.label)]
                              for pos, row in enumerate(local_semantic_rows)]
        else:
            local_boundary = local_validity = []
        boundary_head = self.core.task_modules["semantic_boundary"]
        validity_head = self.core.task_modules["semantic_validity"]
        residual = boundary_head(bridge.states[semantic_index], bridge.residuals[semantic_index]) if semantic else bridge.residuals
        residual_truth = [shared.token_states.new_tensor((row.alignment.start_ref.char_delta,
                                                          row.alignment.end_ref.char_delta)) for row in semantic]
        losses["semantic_boundary"] = (_residual(list(residual), residual_truth, zero)
                                         + _positive(local_boundary, zero))
        scores["semantic_boundary"] = len(residual_truth)
        all_validity = [validity_head(bridge.states[feature_index:feature_index + 1])[0]
                        for feature_index in semantic_index]
        losses["semantic_validity"] = _positive(all_validity + local_validity, zero)
        scores["semantic_validity"] = len(all_validity)
        for task, layer in (("trigger", 8), ("entity_mention", 12), ("time_mention", 10)):
            head = self.core.task_modules[task]
            boundary = head.boundary(backbone.layer(layer), batch.source_token_mask)
            endpoint_logits = []
            residual_pred, residual_gold = [], []
            feature_indices = []
            for row in target.spans[task]:
                feature_index = index[_key(_kind(row), row)]
                feature_indices.append(feature_index)
                align = row.alignment
                a, b = window_index[align.start_ref.window_id], window_index[align.end_ref.window_id]
                endpoint_logits.extend((boundary.start_logits[0, a, align.start_ref.token_position, 0],
                                        boundary.end_logits[0, b, align.end_ref.token_position, 0]))
                endpoint_logits.extend(source_boundary(row, _kind(row)))
                residual_pred.append(bridge.residuals[feature_index])
                residual_gold.append(shared.token_states.new_tensor((align.start_ref.char_delta,
                                                                     align.end_ref.char_delta)))
                if align.cross_window:
                    endpoint_logits.append(bridge.link_logits[feature_index])
                scores[task] += 1
            task_loss = (_positive(endpoint_logits, zero) + _residual(residual_pred, residual_gold, zero))
            if task == "trigger":
                task_loss = task_loss + _positive([head.span_score(bridge.states[pos]).squeeze(-1)
                                                   for pos in feature_indices], zero)
            elif task == "entity_mention" and feature_indices:
                indices = torch.tensor(feature_indices, dtype=torch.long, device=bridge.states.device)
                selected = bridge.states.index_select(0, indices).unsqueeze(0)
                geometry = torch.stack([torch.stack((bridge.residuals[pos, 0], bridge.residuals[pos, 1],
                                                     selected.new_tensor(min(row.alignment.end - row.alignment.start, 512) / 512),
                                                     selected.new_tensor(float(row.alignment.cross_window))))
                                        for row, pos in zip(target.spans[task], feature_indices)]).unsqueeze(0)
                logits = head.typing(selected, geometry, torch.ones((1, len(indices)), dtype=torch.bool,
                                                                     device=indices.device))[0]
                labels = torch.tensor([ENTITY_TYPES.index(row.label) for row in target.spans[task]],
                                      dtype=torch.long, device=indices.device)
                task_loss = task_loss + F.cross_entropy(logits, labels)
                task_loss = task_loss + F.softplus(-logits.gather(1, labels.unsqueeze(1))).mean()
            elif task == "time_mention" and feature_indices:
                indices = torch.tensor(feature_indices, dtype=torch.long, device=bridge.states.device)
                selected = bridge.states.index_select(0, indices).unsqueeze(0)
                geometry = torch.stack([torch.stack((bridge.residuals[pos, 0], bridge.residuals[pos, 1],
                                                     selected.new_tensor(min(row.alignment.end - row.alignment.start, 512) / 512),
                                                     selected.new_tensor(float(row.alignment.cross_window))))
                                        for row, pos in zip(target.spans[task], feature_indices)]).unsqueeze(0)
                logits = head.span(selected, geometry, torch.ones((1, len(indices)), dtype=torch.bool,
                                                                   device=indices.device))[0, :, 0]
                task_loss = task_loss + _positive(list(logits), zero)
            losses[task] = task_loss
        roles = target.roles
        if {role.role_id for role in roles} != {row.owner_id for row in target.spans["participant"]}:
            raise ValueError("participant span and role target IDs differ")
        participant_head = self.core.task_modules["participant"]
        event_rows = {row.owner_id: row for row in semantic if row.label == "EVENT"}
        if roles:
            event_states, token_rows, event_positions, row_positions = [], [], [], []
            role_scores, role_residual, role_truth = [], [], []
            for role in roles:
                event = event_rows[role.event_id]
                event_state = bridge.states[index[_key("EVENT", event)]]
                role_index = index[("PARTICIPANT", role.alignment.start, role.alignment.end)]
                role_state = bridge.states[role_index]
                role_scores.append(participant_head.span_score(torch.cat((event_state, role_state)))[
                    PARTICIPANT_ROLES.index(role.role)])
                role_residual.append(bridge.residuals[role_index])
                role_truth.append(shared.token_states.new_tensor((role.alignment.start_ref.char_delta,
                                                                  role.alignment.end_ref.char_delta)))
                for ref in (role.alignment.start_ref, role.alignment.end_ref):
                    row_id = window_index[ref.window_id]
                    event_states.append(event_state)
                    token_rows.append(shared.token_states[0, row_id])
                    event_align = event.alignment
                    if event_align.canonical_window_id == ref.window_id:
                        event_positions.append((row_id, event_align.start_ref.token_position,
                                                event_align.end_ref.token_position + 1))
                    else:
                        event_positions.append((row_id, 0, 0))
                    row_positions.append((row_id, ref.token_position))
            role_boundary = participant_head.boundary(
                torch.stack(event_states), torch.stack(token_rows),
                torch.tensor(event_positions, device=shared.token_states.device),
                torch.stack([batch.source_token_mask[0, row_id] for row_id, _ in row_positions]))
            positive = list(role_scores)
            for offset, role in enumerate(roles):
                label = PARTICIPANT_ROLES.index(role.role)
                source_row = next(row for row in target.spans["participant"] if row.owner_id == role.role_id)
                positive.extend(source_boundary(source_row, "PARTICIPANT"))
                positive.append(role_boundary[2 * offset, row_positions[2 * offset][1], label, 0])
                positive.append(role_boundary[2 * offset + 1, row_positions[2 * offset + 1][1], label, 1])
                if role.alignment.cross_window:
                    role_index = index[("PARTICIPANT", role.alignment.start, role.alignment.end)]
                    positive.append(bridge.link_logits[role_index])
                scores["participant"] += 1
            losses["participant"] = _positive(positive, zero) + _residual(role_residual, role_truth, zero)
        else:
            losses["participant"] = zero
        statement_rows = {row.owner_id: row for row in semantic if row.label == "STATEMENT"}
        types = [row for row in target.classes if row.task == "statement_type"]
        if types:
            indices = torch.tensor([index[_key("STATEMENT", statement_rows[row.owner_id])]
                                    for row in types], dtype=torch.long, device=bridge.states.device)
            features = bridge.states.index_select(0, indices).unsqueeze(0)
            logits = self.core.task_modules["statement_type"](
                features, torch.ones((1, len(types)), dtype=torch.bool, device=features.device)).logits[0]
            labels = torch.tensor([STATEMENT_TYPES.index(row.label) for row in types],
                                  dtype=torch.long, device=features.device)
            losses["statement_type"] = F.cross_entropy(logits, labels)
            scores["statement_type"] = len(types)
        else:
            losses["statement_type"] = zero
        result = ExtractionLossResult(losses, counts, scores, cross)
        result.validate()
        return result
