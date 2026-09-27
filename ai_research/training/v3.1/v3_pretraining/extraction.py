"""검증된 train Gold의 exact span을 5번 fresh head loss로 연결한다.

Gold ID와 label은 이 adapter 밖으로 전달하지 않는다. 공유 core는 한 번 계산된
backbone/DCE를 소비하며, loss에는 반올림한 token span이나 truncation mask가 없다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import torch
from torch.nn import functional as F

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from models.v3_pretraining.extraction_heads import ENTITY_TYPES, PARTICIPANT_ROLES, STATEMENT_TYPES
from models.v3_pretraining.exact_span import KIND_LAYER
from runtime.v3_pretraining.v23_features import (canonical_scores, event_candidate_state,
                                                  native_states, sentence_cell)
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
    """양성만 밀어 올린다. 확정된 음성이 없는 책임에만 남긴다."""
    return torch.stack([F.softplus(-value) for value in logits]).mean() if logits else zero


def _discriminative(positive: list[torch.Tensor], negative: list[torch.Tensor],
                    zero: torch.Tensor) -> torch.Tensor:
    """확정된 양성/음성을 가르는 BCEWithLogits.

    reduction은 두 cohort를 각각 평균한 뒤 더한다. 음성 표본 수를 바꿔도 loss
    scale이 따라 커지지 않고, 음성이 많다는 이유로 양성 신호가 묽어지지도 않는다.
    모든 logit을 크게 만드는 해는 음성 항에서 그대로 벌점을 받는다.
    """
    if not positive and not negative:
        return zero
    total = zero
    if positive:
        total = total + F.binary_cross_entropy_with_logits(
            torch.stack(positive), torch.ones(len(positive), device=zero.device, dtype=zero.dtype))
    if negative:
        total = total + F.binary_cross_entropy_with_logits(
            torch.stack(negative), torch.zeros(len(negative), device=zero.device, dtype=zero.dtype))
    return total


def _residual(predictions: list[torch.Tensor], targets: list[torch.Tensor],
              zero: torch.Tensor) -> torch.Tensor:
    return F.smooth_l1_loss(torch.stack(predictions), torch.stack(targets)) if predictions else zero


def _geometry(states: torch.Tensor, residuals: torch.Tensor,
              rows: list, positions: list[int]) -> torch.Tensor:
    """Train/runtime이 공유하는 exact-span 4-scalar geometry를 만든다."""
    return torch.stack([
        torch.stack((residuals[position, 0], residuals[position, 1],
                     states.new_tensor(min(row.alignment.end - row.alignment.start, 512) / 512),
                     states.new_tensor(float(row.alignment.cross_window))))
        for row, position in zip(rows, positions)
    ]).unsqueeze(0)


@dataclass(frozen=True, slots=True)
class ExtractionLossResult:
    losses: dict[str, torch.Tensor]
    target_count: dict[str, int]
    scored_count: dict[str, int]
    cross_window_count: dict[str, int]
    # 규칙별 음성 사용 수. 책임이 다르므로 호출자도 합산해 보고하지 않는다.
    negative_count: dict[str, int] = field(default_factory=dict)
    unrepresentable_negative_count: dict[str, int] = field(default_factory=dict)
    supervision_census: dict[str, dict[str, int]] = field(default_factory=dict)

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

    def __init__(self, core: V3Core, *, discriminative: bool = True,
                 profile: str = "V3_WINDOW") -> None:
        missing = set(TASKS) & set(core.unimplemented_tasks)
        if missing:
            raise ValueError(f"extraction heads not registered: {sorted(missing)}")
        self.core = core
        if profile not in ("V3_WINDOW", "V23_BASELINE"):
            raise ValueError("unknown extraction training profile")
        self.profile = profile
        # False면 수정 전 양성 전용 목적함수를 그대로 재현한다. 통제 pilot에서
        # 학습 목표 변경 효과만 분리하기 위한 스위치이며 기본값은 수정된 계약이다.
        self.discriminative = discriminative

    @staticmethod
    def _proposal_supervision(target: ArticleTargets, shared: SharedForwardLease,
                              window_index: dict[str, int], profile: str):
        """in-window joint proposal cell의 양성/음성을 모은다.

        cell은 ``(window, start token, end token, label)``이며 runtime 후보 검색이
        읽는 값과 같다. cross-window Gold/음성은 이 격자에 좌표가 없으므로 음성으로
        쓰지 않고 별도로 센다.
        """
        labels = ("EVENT", "STATEMENT")

        def cell(alignment, label: str):
            if label not in labels:
                return None
            if profile == "V23_BASELINE":
                local = sentence_cell(target.layout, alignment.start, alignment.end)
                if local is None:
                    return None
                window, first, last, _first_token, _last_token = local
                return shared.proposal_logits[0, window, first, last - 1,
                                              labels.index(label)]
            if alignment.canonical_window_id is None:
                return None
            return shared.proposal_logits[0, window_index[alignment.canonical_window_id],
                                          alignment.start_ref.token_position,
                                          alignment.end_ref.token_position,
                                          labels.index(label)]

        positive = []
        for row in target.spans["semantic_proposer"]:
            value = cell(row.alignment, row.label)
            if value is not None:
                positive.append(value)
        negative: list = []
        counts: dict[str, int] = {}
        unrepresentable: dict[str, int] = {}
        for row in target.span_negatives:
            if row.kind not in labels:
                continue
            # N1은 기존 joint proposal cell의 exact-boundary 선택과 별도
            # boundary-fitness producer를 함께 감독한다. semantic validity로는
            # 넓히지 않는다.
            if row.rule not in ("N1_BOUNDARY_MISMATCH", "N2_KIND_EXCLUSIVE",
                                "N3_REPORTING_WRAPPER"):
                continue
            value = cell(row.alignment, row.kind)
            if value is None:
                unrepresentable[row.rule] = unrepresentable.get(row.rule, 0) + 1  # cross-window cell 없음
                continue
            negative.append(value)
            key = f"{row.rule}:{row.responsibility}"
            counts[key] = counts.get(key, 0) + 1
        return positive, {"logits": negative, "counts": counts}, unrepresentable

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
        # N1 boundary fitness와 N2/N3 kind decision, reviewed negative가 같은
        # exact bridge pass에서 표현을 얻는다. N4는 D1에 따라 비활성이다.
        span_scored_negatives = tuple(
            row for row in target.span_negatives
            if row.rule in ("N1_BOUNDARY_MISMATCH", "N2_KIND_EXCLUSIVE",
                            "N3_REPORTING_WRAPPER"))
        for row in span_scored_negatives:
            unique.setdefault((row.kind, row.alignment.start, row.alignment.end),
                              (row.alignment, row.kind))
        reviewed_negative = tuple(
            row for row in target.reviewed_span_decisions if row.verdict == "NEGATIVE")
        for row in reviewed_negative:
            unique.setdefault((row.kind, row.alignment.start, row.alignment.end),
                              (row.alignment, row.kind))
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
        negative_used: dict[str, int] = {}
        unrepresentable_negative: dict[str, int] = {}
        losses: dict[str, torch.Tensor] = {}
        counts = {task: len(target.spans[task]) if task in target.spans else 0 for task in TASKS}
        counts["statement_type"] = sum(row.task == "statement_type" for row in target.classes)
        cross = {task: sum(row.alignment.cross_window for row in target.spans[task])
                 if task in target.spans else 0 for task in TASKS}
        scores = {task: 0 for task in TASKS}
        reviewed_by_kind = {
            kind: {
                "positive": len(target.spans[task]),
                "negative": sum(row.kind == kind and row.verdict == "NEGATIVE"
                                for row in target.reviewed_span_decisions),
                "ignored": sum(row.kind == kind and row.verdict in ("IGNORE", "OMISSION_SUSPECTED")
                               for row in target.reviewed_span_decisions),
            }
            for kind, task in (("ENTITY", "entity_mention"), ("TIME", "time_mention"),
                               ("PARTICIPANT", "participant"))
        }
        supervision_census = {
            "entity_mention:MENTION_EXISTENCE": reviewed_by_kind["ENTITY"],
            "time_mention:MENTION_EXISTENCE": reviewed_by_kind["TIME"],
            "participant:ROLE_FILLER_EXISTENCE": reviewed_by_kind["PARTICIPANT"],
        }
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
            local_cell = (sentence_cell(target.layout, alignment.start, alignment.end)
                          if self.profile == "V23_BASELINE" else None)
            if self.profile == "V23_BASELINE" and local_cell is not None:
                window, first, last, _first_token, _last_token = local_cell
                label = ("EVENT", "STATEMENT").index(row.label)
                proposer_logits.append(shared.proposal_logits[0, window, first,
                                                               last - 1, label])
            elif alignment.canonical_window_id is None or self.profile == "V23_BASELINE":
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
        # 생성 endpoint logit은 확정된 음성이 없으므로 양성 전용 retrieval
        # auxiliary로 남긴다. in-window joint proposal cell은 N1/N2/N3의 기존
        # proposal-cell 감독을 받지만 runtime에서는 retrieval에만 쓰이며 final
        # rank/acceptance는 아래 exact decision producer가 별도로 맡는다.
        proposal_positive, proposal_negative, unrepresentable = self._proposal_supervision(
            target, shared, window_index, self.profile)
        if self.discriminative:
            negative_used.update(proposal_negative["counts"])
        unrepresentable_negative.update(unrepresentable)
        supervision_census["semantic_proposer:JOINT_PROPOSAL_CELL"] = {
            "positive": len(proposal_positive),
            "negative": len(proposal_negative["logits"]) if self.discriminative else 0,
            "ignored": sum(unrepresentable.values()),
        }
        losses["semantic_proposer"] = (_positive(proposer_logits, zero)
                                       + (_discriminative(proposal_positive,
                                                          proposal_negative["logits"], zero)
                                          if self.discriminative
                                          else _positive(proposal_positive, zero)))
        if self.profile == "V23_BASELINE":
            canonical_rows = list(semantic) + [row for row in span_scored_negatives
                                                  if row.kind in ("EVENT", "STATEMENT")]
            canonical_values = canonical_scores(
                layout=target.layout, batch=batch, backbone=backbone, shared=shared,
                core=self.core,
                rows=[(row.alignment.start, row.alignment.end, None)
                      for row in canonical_rows])
            local_boundary = [value[1][("EVENT", "STATEMENT").index(row.label)]
                              for row, value in zip(semantic, canonical_values)
                              if value is not None]
            local_validity = [value[0][("EVENT", "STATEMENT").index(row.label)]
                              for row, value in zip(semantic, canonical_values)
                              if value is not None]
            canonical_negative_boundary = [
                value[1][("EVENT", "STATEMENT").index(row.kind)]
                for row, value in zip(canonical_rows[len(semantic):],
                                      canonical_values[len(semantic):])
                if value is not None and row.rule == "N1_BOUNDARY_MISMATCH"]
            canonical_negative_validity = [
                value[0][("EVENT", "STATEMENT").index(row.kind)]
                for row, value in zip(canonical_rows[len(semantic):],
                                      canonical_values[len(semantic):])
                if value is not None and row.rule in ("N2_KIND_EXCLUSIVE",
                                                       "N3_REPORTING_WRAPPER")]
        elif local_semantic:
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
        if self.profile != "V23_BASELINE":
            canonical_negative_boundary = canonical_negative_validity = []
        boundary_head = self.core.task_modules["semantic_boundary"]
        validity_head = self.core.task_modules["semantic_validity"]
        residual = boundary_head(bridge.states[semantic_index], bridge.residuals[semantic_index]) if semantic else bridge.residuals
        residual_truth = [shared.token_states.new_tensor((row.alignment.start_ref.char_delta,
                                                          row.alignment.end_ref.char_delta)) for row in semantic]
        exact_semantic_index = ([feature_index for row, feature_index in zip(semantic, semantic_index)
                                 if sentence_cell(target.layout, row.alignment.start,
                                                  row.alignment.end) is None]
                                if self.profile == "V23_BASELINE" else semantic_index)
        boundary_positive = (list(boundary_head.fitness_score(
            bridge.states[exact_semantic_index])) if exact_semantic_index else [])
        boundary_negative_rows = [
            row for row in span_scored_negatives
            if row.kind in ("EVENT", "STATEMENT") and row.rule == "N1_BOUNDARY_MISMATCH"
            and (self.profile != "V23_BASELINE" or
                 sentence_cell(target.layout, row.alignment.start,
                               row.alignment.end) is None)
        ]
        boundary_negative_positions = [
            index[(row.kind, row.alignment.start, row.alignment.end)]
            for row in boundary_negative_rows]
        boundary_negative = (list(boundary_head.fitness_score(
            bridge.states[boundary_negative_positions]))
                             if boundary_negative_positions else [])
        if self.profile == "V23_BASELINE":
            boundary_negative = [*boundary_negative, *canonical_negative_boundary]
        if self.discriminative:
            for row in boundary_negative_rows:
                key = f"{row.rule}:{row.responsibility}"
                negative_used[key] = negative_used.get(key, 0) + 1
        losses["semantic_boundary"] = (_residual(list(residual), residual_truth, zero)
                                         + _positive(local_boundary, zero)
                                         + (_discriminative(boundary_positive,
                                                            boundary_negative, zero)
                                            if self.discriminative
                                            else _positive(boundary_positive, zero)))
        supervision_census["semantic_boundary:EXACT_SPAN_FITNESS"] = {
            "positive": len(boundary_positive),
            "negative": len(boundary_negative) if self.discriminative else 0,
            "ignored": sum(row.kind in ("EVENT", "STATEMENT")
                           for row in target.span_ignores),
        }
        scores["semantic_boundary"] = len(residual_truth)
        all_validity = [validity_head(bridge.states[feature_index:feature_index + 1])[0]
                        for feature_index in exact_semantic_index]
        # Exact kind decision은 N2 kind 배타성과 N3 reporting wrapper를 직접 본다.
        # 경계 변형(N1)은 의미 부적격 주장이 아니므로 여기에 전파하지 않는다.
        validity_negative_rows = [
            row for row in span_scored_negatives
            if row.rule in ("N2_KIND_EXCLUSIVE", "N3_REPORTING_WRAPPER")
            and (self.profile != "V23_BASELINE" or
                 sentence_cell(target.layout, row.alignment.start,
                               row.alignment.end) is None)
        ]
        validity_negative = [
            validity_head(bridge.states[index[(row.kind, row.alignment.start,
                                               row.alignment.end)]:
                                        index[(row.kind, row.alignment.start,
                                               row.alignment.end)] + 1])[0]
            for row in validity_negative_rows]
        if self.profile == "V23_BASELINE":
            validity_negative.extend(canonical_negative_validity)
        if self.discriminative:
            for row in validity_negative_rows:
                key = f"{row.rule}:{row.responsibility}"
                negative_used[key] = negative_used.get(key, 0) + 1
        losses["semantic_validity"] = (_positive(local_validity, zero)
                                       + (_discriminative(all_validity, validity_negative, zero)
                                          if self.discriminative
                                          else _positive(all_validity, zero)))
        supervision_census["semantic_validity:KIND_DECISION"] = {
            "positive": len(all_validity),
            "negative": len(validity_negative) if self.discriminative else 0,
            "ignored": sum(row.kind in ("EVENT", "STATEMENT") and
                           row.rule == "N1_BOUNDARY_MISMATCH"
                           for row in span_scored_negatives),
        }
        if self.profile == "V23_BASELINE":
            supervision_census["semantic_validity:CANONICAL_DECISION"] = {
                "positive": len(local_validity),
                "negative": len(canonical_negative_validity) if self.discriminative else 0,
                "ignored": 0,
            }
            supervision_census["semantic_validity:EXACT_DECISION"] = {
                "positive": len(all_validity),
                "negative": len(validity_negative_rows) if self.discriminative else 0,
                "ignored": 0,
            }
        scores["semantic_validity"] = (len(all_validity) + len(local_validity)
                                       if self.profile == "V23_BASELINE" else len(all_validity))
        for task, layer in (("trigger", 8), ("entity_mention", 12), ("time_mention", 10)):
            head = self.core.task_modules[task]
            boundary = head.boundary(backbone.layer(layer), batch.source_token_mask)
            endpoint_logits = []
            trigger_boundary_negative = []
            residual_pred, residual_gold = [], []
            feature_indices = []
            for row in target.spans[task]:
                feature_index = index[_key(_kind(row), row)]
                feature_indices.append(feature_index)
                align = row.alignment
                a, b = window_index[align.start_ref.window_id], window_index[align.end_ref.window_id]
                if (self.profile != "V23_BASELINE" or task == "trigger" or
                        align.cross_window):
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
            if task == "trigger" and self.discriminative:
                gold_starts = {row.alignment.start for row in target.spans[task]}
                gold_ends = {row.alignment.end for row in target.spans[task]}
                for row in span_scored_negatives:
                    if row.kind != "TRIGGER" or row.rule != "N1_BOUNDARY_MISMATCH":
                        continue
                    align = row.alignment
                    if align.start not in gold_starts:
                        window = window_index[align.start_ref.window_id]
                        trigger_boundary_negative.append(
                            boundary.start_logits[0, window, align.start_ref.token_position, 0])
                    if align.end not in gold_ends:
                        window = window_index[align.end_ref.window_id]
                        trigger_boundary_negative.append(
                            boundary.end_logits[0, window, align.end_ref.token_position, 0])
                task_loss = task_loss + _discriminative([], trigger_boundary_negative, zero)
            if task == "trigger":
                supervision_census["trigger:ENDPOINT_BOUNDARY"] = {
                    "positive": 2 * len(target.spans[task]),
                    "negative": len(trigger_boundary_negative),
                    "ignored": 0,
                }
            if self.profile == "V23_BASELINE" and task in ("entity_mention", "time_mention"):
                positive_rows = list(target.spans[task])
                kind = "ENTITY" if task == "entity_mention" else "TIME"
                negative_rows = [row for row in reviewed_negative if row.kind == kind]
                all_rows = positive_rows + negative_rows
                if all_rows:
                    positions = [index[(kind, row.alignment.start, row.alignment.end)]
                                 for row in all_rows]
                    fallback = bridge.states[positions]
                    fallback_geometry = _geometry(
                        bridge.states, bridge.residuals, all_rows, positions)[0]
                    native, geometry, _ = native_states(
                        kind=kind, layout=target.layout, batch=batch, backbone=backbone,
                        shared=shared, core=self.core,
                        rows=[(row.alignment.start, row.alignment.end, None)
                              for row in all_rows],
                        fallback_states=fallback,
                        fallback_geometry=fallback_geometry)
                    mask = torch.ones((1, len(all_rows)), dtype=torch.bool,
                                      device=native.device)
                    if kind == "ENTITY":
                        logits = head.typing(native.unsqueeze(0), geometry.unsqueeze(0), mask)[0]
                        if positive_rows:
                            # A Gold mention authorizes its named type only. Other
                            # type channels at the same span are not implicit negatives.
                            named = torch.stack([
                                logits[row_index, ENTITY_TYPES.index(row.label)]
                                for row_index, row in enumerate(positive_rows)])
                            task_loss = task_loss + F.softplus(-named).mean()
                        if negative_rows and self.discriminative:
                            task_loss = task_loss + F.binary_cross_entropy_with_logits(
                                logits[len(positive_rows):],
                                torch.zeros_like(logits[len(positive_rows):]))
                    else:
                        logits = head.span(native.unsqueeze(0), geometry.unsqueeze(0), mask)[0, :, 0]
                        task_loss = task_loss + (_discriminative(
                            list(logits[:len(positive_rows)]),
                            list(logits[len(positive_rows):]) if self.discriminative else [], zero))
                    if self.discriminative:
                        for row in negative_rows:
                            key = f"{row.reason}:{row.responsibility}:{row.kind}:{row.authority_id}"
                            negative_used[key] = negative_used.get(key, 0) + 1
                losses[task] = task_loss
                continue
            if task == "trigger":
                trigger_negative_rows = [row for row in span_scored_negatives
                                         if row.kind == "TRIGGER" and
                                         row.rule == "N1_BOUNDARY_MISMATCH"]
                negative_scores = [
                    head.span_score(bridge.states[index[("TRIGGER", row.alignment.start,
                                                         row.alignment.end)]]).squeeze(-1)
                    for row in trigger_negative_rows]
                if self.discriminative:
                    for row in trigger_negative_rows:
                        key = f"{row.rule}:{row.responsibility}"
                        negative_used[key] = negative_used.get(key, 0) + 1
                positive_scores = [head.span_score(bridge.states[pos]).squeeze(-1)
                                   for pos in feature_indices]
                task_loss = task_loss + (_discriminative(positive_scores, negative_scores, zero)
                                         if self.discriminative
                                         else _positive(positive_scores, zero))
                supervision_census["trigger:EXACT_SPAN_FITNESS"] = {
                    "positive": len(positive_scores),
                    "negative": len(negative_scores) if self.discriminative else 0,
                    "ignored": sum(row.kind == "TRIGGER" for row in target.span_ignores),
                }
            elif task == "entity_mention":
                positive_rows = list(target.spans[task])
                negative_rows = [row for row in reviewed_negative if row.kind == "ENTITY"]
                positive_scores: list[torch.Tensor] = []
                negative_scores: list[torch.Tensor] = []
                if feature_indices:
                    indices = torch.tensor(feature_indices, dtype=torch.long,
                                           device=bridge.states.device)
                    selected = bridge.states.index_select(0, indices).unsqueeze(0)
                    geometry = _geometry(bridge.states, bridge.residuals,
                                         positive_rows, feature_indices)
                    mask = torch.ones((1, len(indices)), dtype=torch.bool,
                                      device=indices.device)
                    existence = head.existence(selected, geometry, mask)[0, :, 0]
                    positive_scores = list(existence)
                    type_logits = head.typing(selected, geometry, mask)[0]
                    labels = torch.tensor(
                        [ENTITY_TYPES.index(row.label) for row in positive_rows],
                        dtype=torch.long, device=indices.device)
                    # Type CE는 존재 판별과 독립이다. 올바른 type logit을 별도
                    # existence surrogate로 다시 밀어 올리지 않는다.
                    task_loss = task_loss + F.cross_entropy(type_logits, labels)
                if negative_rows:
                    negative_positions = [
                        index[("ENTITY", row.alignment.start, row.alignment.end)]
                        for row in negative_rows
                    ]
                    indices = torch.tensor(negative_positions, dtype=torch.long,
                                           device=bridge.states.device)
                    selected = bridge.states.index_select(0, indices).unsqueeze(0)
                    geometry = _geometry(bridge.states, bridge.residuals,
                                         negative_rows, negative_positions)
                    mask = torch.ones((1, len(indices)), dtype=torch.bool,
                                      device=indices.device)
                    negative_scores = list(head.existence(selected, geometry, mask)[0, :, 0])
                task_loss = task_loss + (
                    _discriminative(positive_scores, negative_scores, zero)
                    if self.discriminative else _positive(positive_scores, zero))
                if self.discriminative:
                    for row in negative_rows:
                        key = (f"{row.reason}:{row.responsibility}:{row.kind}:"
                               f"{row.authority_id}")
                        negative_used[key] = negative_used.get(key, 0) + 1
            elif task == "time_mention":
                positive_rows = list(target.spans[task])
                negative_rows = [row for row in reviewed_negative if row.kind == "TIME"]
                positive_scores: list[torch.Tensor] = []
                negative_scores: list[torch.Tensor] = []
                if feature_indices:
                    indices = torch.tensor(feature_indices, dtype=torch.long,
                                           device=bridge.states.device)
                    selected = bridge.states.index_select(0, indices).unsqueeze(0)
                    geometry = _geometry(bridge.states, bridge.residuals,
                                         positive_rows, feature_indices)
                    positive_scores = list(head.span(
                        selected, geometry,
                        torch.ones((1, len(indices)), dtype=torch.bool,
                                   device=indices.device))[0, :, 0])
                if negative_rows:
                    negative_positions = [
                        index[("TIME", row.alignment.start, row.alignment.end)]
                        for row in negative_rows
                    ]
                    indices = torch.tensor(negative_positions, dtype=torch.long,
                                           device=bridge.states.device)
                    selected = bridge.states.index_select(0, indices).unsqueeze(0)
                    geometry = _geometry(bridge.states, bridge.residuals,
                                         negative_rows, negative_positions)
                    negative_scores = list(head.span(
                        selected, geometry,
                        torch.ones((1, len(indices)), dtype=torch.bool,
                                   device=indices.device))[0, :, 0])
                task_loss = task_loss + (
                    _discriminative(positive_scores, negative_scores, zero)
                    if self.discriminative else _positive(positive_scores, zero))
                if self.discriminative:
                    for row in negative_rows:
                        key = (f"{row.reason}:{row.responsibility}:{row.kind}:"
                               f"{row.authority_id}")
                        negative_used[key] = negative_used.get(key, 0) + 1
            losses[task] = task_loss
        roles = target.roles
        if {role.role_id for role in roles} != {row.owner_id for row in target.spans["participant"]}:
            raise ValueError("participant span and role target IDs differ")
        participant_head = self.core.task_modules["participant"]
        event_rows = {row.owner_id: row for row in semantic if row.label == "EVENT"}
        role_scores: list[torch.Tensor] = []
        role_residual: list[torch.Tensor] = []
        role_truth: list[torch.Tensor] = []
        retrieval_positive: list[torch.Tensor] = []
        if roles:
            event_states, token_rows, event_positions, row_positions = [], [], [], []
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
            for offset, role in enumerate(roles):
                label = PARTICIPANT_ROLES.index(role.role)
                source_row = next(row for row in target.spans["participant"] if row.owner_id == role.role_id)
                retrieval_positive.extend(source_boundary(source_row, "PARTICIPANT"))
                retrieval_positive.append(
                    role_boundary[2 * offset, row_positions[2 * offset][1], label, 0])
                retrieval_positive.append(
                    role_boundary[2 * offset + 1, row_positions[2 * offset + 1][1], label, 1])
                if role.alignment.cross_window:
                    role_index = index[("PARTICIPANT", role.alignment.start, role.alignment.end)]
                    retrieval_positive.append(bridge.link_logits[role_index])
                scores["participant"] += 1
        participant_negative_rows = [
            row for row in reviewed_negative if row.kind == "PARTICIPANT"]
        participant_negative_scores = []
        for row in participant_negative_rows:
            event = event_rows[row.owner_id]
            event_state = bridge.states[index[_key("EVENT", event)]]
            role_state = bridge.states[index[
                ("PARTICIPANT", row.alignment.start, row.alignment.end)]]
            participant_negative_scores.append(
                participant_head.span_score(torch.cat((event_state, role_state)))[
                    PARTICIPANT_ROLES.index(row.role)])
            if self.discriminative and self.profile != "V23_BASELINE":
                key = (f"{row.reason}:{row.responsibility}:{row.kind}:"
                       f"{row.authority_id}")
                negative_used[key] = negative_used.get(key, 0) + 1
        participant_decision = (
            _discriminative(role_scores, participant_negative_scores, zero)
            if self.discriminative else _positive(role_scores, zero))
        participant_residual = _residual(role_residual, role_truth, zero)
        participant_retrieval = _positive(retrieval_positive, zero)
        if self.profile == "V23_BASELINE":
            def b2_decision(event: SpanTarget, row) -> tuple[torch.Tensor, tuple] | None:
                cell = sentence_cell(target.layout, row.alignment.start,
                                     row.alignment.end)
                if cell is None:
                    return None
                window, first, last, _first_token, _last_token = cell
                native_event = event_candidate_state(
                    layout=target.layout, batch=batch, backbone=backbone,
                    shared=shared, core=self.core,
                    start=event.alignment.start, end=event.alignment.end)
                event_state = (native_event if native_event is not None else
                               bridge.states[index[_key("EVENT", event)]])
                event_cell = sentence_cell(target.layout, event.alignment.start,
                                           event.alignment.end,
                                           target.layout.windows[window].window_id)
                event_positions = (window, event_cell[1], event_cell[2]) if event_cell else (window, 0, 0)
                logits = participant_head.boundary(
                    event_state.unsqueeze(0), shared.token_states[0, window:window + 1],
                    torch.tensor([event_positions], dtype=torch.long,
                                 device=shared.token_states.device),
                    batch.source_token_mask[0, window:window + 1])[0]
                label = PARTICIPANT_ROLES.index(row.role)
                probability = (torch.sigmoid(logits[first, label, 0]) *
                               torch.sigmoid(logits[last - 1, label, 1])).sqrt()
                key = (event.owner_id, row.role, window, first, last)
                return torch.logit(probability.clamp(1e-8, 1 - 1e-8)), key

            b2_positive = []
            positive_cells = set()
            for role in roles:
                event = event_rows[role.event_id]
                scored = b2_decision(event, role)
                if scored is not None:
                    b2_positive.append(scored[0])
                    positive_cells.add(scored[1])
            b2_negative = []
            for row in participant_negative_rows:
                scored = b2_decision(event_rows[row.owner_id], row)
                if scored is not None and scored[1] not in positive_cells:
                    b2_negative.append(scored[0])
            if self.discriminative:
                for row in participant_negative_rows:
                    key = f"{row.reason}:{row.responsibility}:{row.kind}:{row.authority_id}"
                    negative_used[key] = negative_used.get(key, 0) + 1
            losses["participant"] = (
                participant_residual
                + _discriminative(b2_positive, b2_negative if self.discriminative else [], zero)
                + participant_decision)
        else:
            losses["participant"] = (
                participant_retrieval + participant_decision + participant_residual)
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
        result = ExtractionLossResult(losses, counts, scores, cross,
                                      negative_used, unrepresentable_negative,
                                      supervision_census)
        result.validate()
        return result
