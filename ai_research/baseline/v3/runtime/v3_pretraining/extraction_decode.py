"""Gold 없는 source-token endpoint 제안과 exact 문자 복원.

정책 예산은 임시이며 production threshold가 아니다. 제한에 걸리면 partial을
명시한다. 중복 window는 절대 문자 좌표로 닫고 반복 occurrence는 보존한다.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import torch

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from models.v3_pretraining.exact_span import KIND_LAYER
from models.v3_pretraining.extraction_heads import ENTITY_TYPES, STATEMENT_TYPES
from models.v3_pretraining.extraction_heads import PARTICIPANT_ROLES
from runtime.v3_pretraining.source_layout import SourceLayout, SpanAlignment


@dataclass(frozen=True, slots=True)
class DecodeBudget:
    max_starts: int = 64
    max_ends: int = 64
    max_pairs: int = 256
    chunk_size: int = 64
    status: str = "PROVISIONAL_ENGINEERING_ONLY"

    def __post_init__(self) -> None:
        if min(self.max_starts, self.max_ends, self.max_pairs, self.chunk_size) <= 0:
            raise ValueError("decode budgets must be positive")


@dataclass(frozen=True, slots=True)
class DecodedSourceSpan:
    kind: str
    label: str | None
    start: int
    end: int
    text: str
    score: float
    start_window_id: str
    end_window_id: str


@dataclass(frozen=True, slots=True)
class DecodeResult:
    spans: tuple[DecodedSourceSpan, ...]
    eligible_pairs: int
    scored_pairs: int
    invalid_predictions: int
    partial: bool
    policy_status: str


@dataclass(slots=True)
class SourceDecodeContext:
    """한 요청의 generic endpoint와 bridge 좌표만 소유한다."""

    layout_id: int
    token_state_id: int
    window_index: dict[str, int]
    bridge_positions: tuple[tuple[tuple[int, int], ...], ...]
    generic_endpoints: torch.Tensor | None
    closed: bool = False

    def release_generic_endpoints(self) -> None:
        self.generic_endpoints = None

    def close(self) -> None:
        self.release_generic_endpoints()
        self.window_index.clear()
        self.bridge_positions = ()
        self.closed = True


def source_decode_context(layout: SourceLayout, shared: SharedForwardLease,
                          core: V3Core) -> SourceDecodeContext:
    """generic 다섯 kind의 endpoint를 한 번 계산하고 bridge lookup을 고정한다."""
    if shared.closed or shared.token_states is None:
        raise RuntimeError("source decode needs a live shared representation")
    window_index = {window.window_id: row for row, window in enumerate(layout.windows)}
    local_position = {(window.window_id, token.source_index): token.position
                      for window in layout.windows if window.view == "bridge"
                      for token in window.tokens}
    positions = tuple(tuple((window_index[window_id], local_position[window_id, token.source_index])
                            for window_id in layout.bridge_windows_by_token[token.source_index])
                      for token in layout.bridge_tokens)
    return SourceDecodeContext(id(layout), id(shared.token_states), window_index, positions,
                               core.exact_source_span.endpoint_logits(shared.token_states))


def event_source_state(*, alignment: SpanAlignment, layout: SourceLayout,
                       batch: ArticleBatch, backbone: BackboneOutput,
                       shared: SharedForwardLease, core: V3Core) -> torch.Tensor:
    """한 Event의 세 role이 공유할 exact-span representation을 만든다."""
    if layout.reconstruct(alignment) != (alignment.start, alignment.end, alignment.text):
        raise ValueError("Event source alignment differs")
    if "participant" not in core.task_modules:
        raise ValueError("Event-conditioned Participant head is not registered")
    return core.exact_source_span(
        layout=layout, batch=batch, backbone=backbone,
        token_states=shared.token_states, sentence_states=shared.sentence_states,
        document_state=shared.document_state, candidate_encoder=core.candidate_span,
        rows=((alignment, "EVENT"),)).states[0]


@torch.no_grad()
def decode_source_spans(*, kind: str, layout: SourceLayout, batch: ArticleBatch,
                        backbone: BackboneOutput, shared: SharedForwardLease,
                        core: V3Core, budget: DecodeBudget = DecodeBudget(),
                        event_alignment: SpanAlignment | None = None,
                        role: str | None = None,
                        context: SourceDecodeContext | None = None,
                        event_state: torch.Tensor | None = None) -> DecodeResult:
    """같은 backbone/DCE 출력만으로 cross-window 후보를 작은 chunk에서 평가한다."""
    if kind not in KIND_LAYER or shared.closed or shared.token_states is None:
        raise ValueError("known kind and live shared representation are required")
    if kind == "PARTICIPANT" and (event_alignment is None or role not in PARTICIPANT_ROLES):
        raise ValueError("Participant decoding requires an Event span and ACTOR/TARGET/PLACE role")
    if kind != "PARTICIPANT" and (event_alignment is not None or role is not None):
        raise ValueError("Event-conditioned role arguments belong only to Participant decoding")
    if kind != "PARTICIPANT" and event_state is not None:
        raise ValueError("reused Event representation belongs only to Participant decoding")
    if len(layout.windows) != batch.input_ids.shape[1] or batch.contents[0] != layout.article.content:
        raise ValueError("decoder source layout differs from model input")
    if context is not None and (context.closed or context.layout_id != id(layout) or
                                context.token_state_id != id(shared.token_states)):
        raise ValueError("source decode context belongs to a different request")
    endpoints = (context.generic_endpoints if context is not None else
                 core.exact_source_span.endpoint_logits(shared.token_states)) if kind != "PARTICIPANT" else None
    if kind != "PARTICIPANT" and endpoints is None:
        raise RuntimeError("generic source endpoints were already released")
    channel = list(KIND_LAYER).index(kind)
    task_boundary = None
    if kind in ("TRIGGER", "ENTITY", "TIME"):
        task_name, layer = {"TRIGGER": ("trigger", 8), "ENTITY": ("entity_mention", 12),
                            "TIME": ("time_mention", 10)}[kind]
        if task_name in core.task_modules:
            task_boundary = core.task_modules[task_name].boundary(
                backbone.layer(layer), batch.source_token_mask)
    window_index = (context.window_index if context is not None else
                    {window.window_id: row for row, window in enumerate(layout.windows)})
    if context is not None:
        bridge_positions = context.bridge_positions
    else:
        local_position = {(window.window_id, token.source_index): token.position
                          for window in layout.windows if window.view == "bridge"
                          for token in window.tokens}
        bridge_positions = tuple(tuple((window_index[window_id], local_position[window_id, token.source_index])
                                      for window_id in layout.bridge_windows_by_token[token.source_index])
                                 for token in layout.bridge_tokens)
    role_logits = None
    bridge_row_index = None
    if kind == "PARTICIPANT":
        if event_state is None:
            event_state = event_source_state(
                alignment=event_alignment, layout=layout, batch=batch, backbone=backbone,
                shared=shared, core=core)
        elif event_state.ndim != 1 or event_state.shape[0] != shared.token_states.shape[-1]:
            raise ValueError("reused Event representation has wrong shape")
        bridge_rows = [position for position, window in enumerate(layout.windows) if window.view == "bridge"]
        bridge_row_index = {row: index for index, row in enumerate(bridge_rows)}
        event_positions = [(position, event_alignment.start_ref.token_position,
                            event_alignment.end_ref.token_position + 1)
                           if event_alignment.canonical_window_id == layout.windows[position].window_id
                           else (position, 0, 0) for position in bridge_rows]
        role_logits = core.task_modules["participant"].boundary(
            event_state.unsqueeze(0).expand(len(bridge_rows), -1),
            shared.token_states[0, bridge_rows],
            torch.tensor(event_positions, dtype=torch.long, device=shared.token_states.device),
            batch.source_token_mask[0, bridge_rows])
    starts: list[tuple[float, int]] = []
    ends: list[tuple[float, int]] = []
    for token in layout.bridge_tokens:
        start_scores = []
        end_scores = []
        for row, local in bridge_positions[token.source_index]:
            if kind == "PARTICIPANT":
                role_row = bridge_row_index[row]
                role_channel = PARTICIPANT_ROLES.index(role)
                start_scores.append(float(role_logits[role_row, local, role_channel, 0]))
                end_scores.append(float(role_logits[role_row, local, role_channel, 1]))
            else:
                start_scores.append(float(endpoints[0, row, local, channel, 0]))
                end_scores.append(float(endpoints[0, row, local, channel, 1]))
            if task_boundary is not None:
                start_scores[-1] += float(task_boundary.start_logits[0, row, local, 0])
                end_scores[-1] += float(task_boundary.end_logits[0, row, local, 0])
        starts.append((max(start_scores), token.source_index))
        ends.append((max(end_scores), token.source_index))
    starts.sort(key=lambda value: (-value[0], value[1]))
    ends.sort(key=lambda value: (-value[0], value[1]))
    selected_starts, selected_ends = starts[:budget.max_starts], ends[:budget.max_ends]
    pairs = [(start_score + end_score, start_index, end_index)
             for start_score, start_index in selected_starts
             for end_score, end_index in selected_ends if start_index <= end_index]
    pairs.sort(key=lambda value: (-value[0], value[1], value[2]))
    eligible = len(pairs)
    partial = len(starts) > budget.max_starts or len(ends) > budget.max_ends or eligible > budget.max_pairs
    selected = pairs[:budget.max_pairs]
    retained: dict[tuple[str, int, int, str | None], DecodedSourceSpan] = {}
    invalid = 0
    for start in range(0, len(selected), budget.chunk_size):
        chunk = selected[start:start + budget.chunk_size]
        aligned = []
        for _, first, last in chunk:
            left, right = layout.bridge_tokens[first], layout.bridge_tokens[last]
            aligned.append(layout.align({"start": left.start, "end": right.end,
                                         "text": layout.article.content[left.start:right.end]}))
        output = core.exact_source_span(
            layout=layout, batch=batch, backbone=backbone,
            token_states=shared.token_states, sentence_states=shared.sentence_states,
            document_state=shared.document_state, candidate_encoder=core.candidate_span,
            rows=[(row, kind) for row in aligned])
        labels: list[str | None] = [kind] * len(chunk)
        type_scores = [0.0] * len(chunk)
        residuals = output.residuals
        if kind in ("EVENT", "STATEMENT") and all(
                name in core.task_modules for name in ("semantic_boundary", "semantic_validity")):
            residuals = core.task_modules["semantic_boundary"](output.states, output.residuals)
            validity = core.task_modules["semantic_validity"](output.states)
            type_scores = [float(value) for value in validity]
            for index, row in enumerate(aligned):
                if row.canonical_window_id is not None:
                    window = window_index[row.canonical_window_id]
                    label = ("EVENT", "STATEMENT").index(kind)
                    type_scores[index] += float(shared.proposal_logits[
                        0, window, row.start_ref.token_position,
                        row.end_ref.token_position, label])
        elif kind == "TRIGGER":
            logits = core.task_modules["trigger"].span_score(output.states).squeeze(-1)
            type_scores = [float(value) for value in logits]
        if kind == "ENTITY":
            if "entity_mention" not in core.task_modules:
                raise ValueError("Entity type head is not registered")
            geometry = torch.stack([
                torch.stack((output.residuals[index, 0], output.residuals[index, 1],
                             output.states.new_tensor(min(row.end - row.start, 512) / 512),
                             output.states.new_tensor(float(row.cross_window))))
                for index, row in enumerate(aligned)]).unsqueeze(0)
            logits = core.task_modules["entity_mention"].typing(
                output.states.unsqueeze(0), geometry,
                torch.ones((1, len(chunk)), dtype=torch.bool, device=output.states.device))[0]
            type_ids = logits.argmax(dim=-1)
            labels = [ENTITY_TYPES[int(value)] for value in type_ids]
            type_scores = [float(logits[index, type_ids[index]]) for index in range(len(chunk))]
        elif kind == "STATEMENT":
            if "statement_type" not in core.task_modules:
                raise ValueError("StatementType head is not registered")
            logits = core.task_modules["statement_type"](
                output.states.unsqueeze(0),
                torch.ones((1, len(chunk)), dtype=torch.bool, device=output.states.device)).logits[0]
            type_ids = logits.argmax(dim=-1)
            labels = [STATEMENT_TYPES[int(value)] for value in type_ids]
            type_scores = [float(logits[index, type_ids[index]]) for index in range(len(chunk))]
        elif kind == "PARTICIPANT":
            labels = [role] * len(chunk)
            role_logits = core.task_modules["participant"].span_score(
                torch.cat((event_state.unsqueeze(0).expand(len(chunk), -1), output.states), dim=-1))
            type_scores = [float(role_logits[index, PARTICIPANT_ROLES.index(role)])
                           for index in range(len(chunk))]
        elif kind == "TIME":
            geometry = torch.stack([
                torch.stack((output.residuals[index, 0], output.residuals[index, 1],
                             output.states.new_tensor(min(row.end - row.start, 512) / 512),
                             output.states.new_tensor(float(row.cross_window))))
                for index, row in enumerate(aligned)]).unsqueeze(0)
            logits = core.task_modules["time_mention"].span(
                output.states.unsqueeze(0), geometry,
                torch.ones((1, len(chunk)), dtype=torch.bool, device=output.states.device))[0, :, 0]
            type_scores = [float(value) for value in logits]
        for offset, (pair_score, _, _) in enumerate(chunk):
            source = aligned[offset]
            start_char = source.start + round(float(residuals[offset, 0]))
            end_char = source.end + round(float(residuals[offset, 1]))
            if not (0 <= start_char < end_char <= len(layout.article.content)):
                invalid += 1
                continue
            score = pair_score + float(output.link_logits[offset]) + type_scores[offset]
            if not math.isfinite(score):
                invalid += 1
                continue
            candidate = DecodedSourceSpan(kind, labels[offset], start_char, end_char,
                                          layout.article.content[start_char:end_char], score,
                                          source.start_ref.window_id, source.end_ref.window_id)
            key = layout.closure_key(kind, start_char, end_char, labels[offset])
            old = retained.get(key)
            if old is None or candidate.score > old.score:
                retained[key] = candidate
    ordered = tuple(sorted(retained.values(), key=lambda row: (row.start, row.end, row.kind)))
    return DecodeResult(ordered, eligible, len(selected), invalid, partial, budget.status)
