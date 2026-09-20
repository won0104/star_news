"""Gold 없는 Assertor source와 final local relation의 request 범위 실행 경로."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice, product
from typing import Mapping

import torch

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from runtime.v3_pretraining.entity_identity import EntityClosure
from runtime.v3_pretraining.event_features import FinalClusterFeatureLease
from runtime.v3_pretraining.event_identity import EventClosure
from runtime.v3_pretraining.extraction_decode import DecodedSourceSpan
from runtime.v3_pretraining.source_layout import SourceLayout, SpanAlignment


def proposition_extra_rows(layout: SourceLayout,
                           statements: Mapping[str, DecodedSourceSpan],
                           assertors: Mapping[str, DecodedSourceSpan]) -> tuple[tuple[str, SpanAlignment, str], ...]:
    """예측 source를 Event/Time과 같은 direct-gather pass에 넣는 local-key 계약."""
    if not set(assertors) <= set(statements):
        raise ValueError("Assertor source lacks owning predicted Statement")
    rows = []
    for sid, span in statements.items():
        if not sid or span.kind != "STATEMENT":
            raise ValueError("predicted Statement source row invalid")
        rows.append(("STATEMENT:" + sid, layout.align({"start": span.start,
                                                        "end": span.end, "text": span.text}),
                     "STATEMENT"))
    for sid, span in assertors.items():
        if span.kind != "ASSERTOR" or span.label is not None:
            raise ValueError("predicted Assertor source row invalid")
        rows.append(("ASSERTOR:" + sid, layout.align({"start": span.start,
                                                       "end": span.end, "text": span.text}),
                     "STATEMENT"))
    return tuple(rows)


def bridge_token_states(layout: SourceLayout, shared: SharedForwardLease, *,
                        bridge_positions: tuple[tuple[tuple[int, int], ...], ...] | None = None) -> torch.Tensor:
    """각 source token을 한 번만 사용하여 window duplicate의 가중치 증가를 막는다."""
    if shared.closed or shared.token_states is None:
        raise RuntimeError("live shared source token representation required")
    if bridge_positions is not None:
        if len(bridge_positions) != len(layout.bridge_tokens) or any(not row for row in bridge_positions):
            raise ValueError("Assertor bridge index differs from source layout")
        gathered = [shared.token_states[0, rows[0][0], rows[0][1]] for rows in bridge_positions]
    else:
        rows = {window.window_id: index for index, window in enumerate(layout.windows)}
        gathered = []
        for token in layout.bridge_tokens:
            window_id = layout.bridge_windows_by_token[token.source_index][0]
            window = layout.window_lookup[window_id]
            position = next(row.position for row in window.tokens
                            if row.source_index == token.source_index)
            gathered.append(shared.token_states[0, rows[window_id], position])
    if not gathered:
        return shared.token_states.new_empty((0, shared.token_states.shape[-1]))
    return torch.stack(gathered)


@dataclass(frozen=True, slots=True)
class AssertorSourceDecode:
    statement_id: str
    span: DecodedSourceSpan | None
    scored_pairs: int
    partial: bool
    policy_status: str = "PROVISIONAL_ENGINEERING_ONLY"


@torch.no_grad()
def decode_assertor_source(*, statement_id: str, statement_alignment: SpanAlignment,
                           layout: SourceLayout, batch: ArticleBatch,
                           backbone: BackboneOutput, shared: SharedForwardLease,
                           core: V3Core, statement_state: torch.Tensor | None = None,
                           bridge_states: torch.Tensor | None = None,
                           max_starts: int = 32, max_ends: int = 32,
                           max_pairs: int = 128, chunk_size: int = 32,
                           score_threshold: float = 0.0) -> AssertorSourceDecode:
    """Statement 조건부 source를 exact 문자 좌표로 복원; Entity는 여기서 만들지 않는다."""
    if min(max_starts, max_ends, max_pairs, chunk_size) <= 0:
        raise ValueError("Assertor source budget must be positive")
    if (not statement_id or layout.reconstruct(statement_alignment) !=
            (statement_alignment.start, statement_alignment.end, statement_alignment.text)):
        raise ValueError("Statement source alignment differs")
    if shared.closed or shared.token_states is None or shared.sentence_states is None or shared.document_state is None:
        raise RuntimeError("Assertor extraction needs live shared representation")
    if "assertor_source" not in core.task_modules:
        raise ValueError("Assertor source head is missing")
    statement = statement_state
    if statement is None:
        statement = core.exact_source_span(
            layout=layout, batch=batch, backbone=backbone, token_states=shared.token_states,
            sentence_states=shared.sentence_states, document_state=shared.document_state,
            candidate_encoder=core.candidate_span,
            rows=((statement_alignment, "STATEMENT"),)).states[0]
    elif statement.ndim != 1 or statement.shape[0] != shared.document_state.shape[-1]:
        raise ValueError("reused Statement representation has wrong shape")
    head = core.task_modules["assertor_source"]
    tokens = bridge_token_states(layout, shared) if bridge_states is None else bridge_states
    if tokens.ndim != 2 or tokens.shape != (len(layout.bridge_tokens), shared.token_states.shape[-1]):
        raise ValueError("reused Assertor bridge representation has wrong shape")
    if not len(tokens) or float(head.existence_logit(statement)) < score_threshold:
        return AssertorSourceDecode(statement_id, None, 0, False)
    logits = head.token_logits(statement, tokens)
    starts = torch.argsort(logits[:, 0], descending=True)[:max_starts].tolist()
    ends = torch.argsort(logits[:, 1], descending=True)[:max_ends].tolist()
    pairs = sorted(((float(logits[a, 0] + logits[b, 1]), a, b)
                    for a in starts for b in ends if a <= b), reverse=True)
    selected = pairs[:max_pairs]
    best: DecodedSourceSpan | None = None
    for offset in range(0, len(selected), chunk_size):
        chunk = selected[offset:offset + chunk_size]
        aligned = []
        for _, a, b in chunk:
            first, last = layout.bridge_tokens[a], layout.bridge_tokens[b]
            aligned.append(layout.align({"start": first.start, "end": last.end,
                                         "text": layout.article.content[first.start:last.end]}))
        features = core.exact_source_span(
            layout=layout, batch=batch, backbone=backbone,
            token_states=shared.token_states, sentence_states=shared.sentence_states,
            document_state=shared.document_state, candidate_encoder=core.candidate_span,
            rows=tuple((row, "STATEMENT") for row in aligned))
        for index, (boundary_score, _, _) in enumerate(chunk):
            source = aligned[index]
            delta = features.residuals[index] + head.residual_delta(
                statement, features.states[index], features.residuals[index])
            start = source.start + round(float(delta[0]))
            end = source.end + round(float(delta[1]))
            score = boundary_score + float(features.link_logits[index]) + float(
                head.span_logit(statement, features.states[index]))
            if not 0 <= start < end <= len(layout.article.content) or score < score_threshold:
                continue
            candidate = DecodedSourceSpan("ASSERTOR", None, start, end,
                                          layout.article.content[start:end], score,
                                          source.start_ref.window_id, source.end_ref.window_id)
            if best is None or candidate.score > best.score:
                best = candidate
    return AssertorSourceDecode(statement_id, best, len(selected),
                                len(starts) == max_starts or len(ends) == max_ends or
                                len(pairs) > max_pairs)


@dataclass(frozen=True, slots=True)
class AssertedByFact:
    statement_id: str
    entity_id: str | None
    start: int
    end: int
    text: str
    status: str
    evidence_id: str


def asserted_by_facts(closure: EntityClosure) -> tuple[AssertedByFact, ...]:
    return tuple(AssertedByFact(row.owner_id, row.local_entity_id, row.start, row.end,
                                row.text, row.status, row.evidence_id)
                 for row in closure.endpoints if row.role == "ASSERTOR")


@dataclass(frozen=True, slots=True)
class RelationFact:
    relation: str
    source_id: str
    target_id: str
    logit: float


@dataclass(frozen=True, slots=True)
class RelationDecode:
    facts: tuple[RelationFact, ...]
    eligible_about: int
    eligible_causes: int
    scored_about: int
    scored_causes: int
    partial: bool
    policy_status: str = "PROVISIONAL_ENGINEERING_ONLY"


@torch.no_grad()
def score_final_relations(*, core: V3Core, final: FinalClusterFeatureLease,
                          closure: EventClosure,
                          statement_states: Mapping[str, torch.Tensor],
                          max_pairs: int = 4096, chunk_size: int = 128,
                          score_threshold: float = 0.0) -> RelationDecode:
    """final local ID만 사용하고 ordered CAUSES를 별도 방향 head로 평가한다."""
    if closure.source_mode != "PREDICTED" or final.source_mode != "PREDICTED" or final.cluster_ids != tuple(
            row.local_id for row in closure.events):
        raise ValueError("relation runtime needs predicted final Event identity")
    if min(max_pairs, chunk_size) <= 0:
        raise ValueError("relation pair bounds must be positive")
    view = final.view_for("RELATION")
    if any(name not in core.task_modules for name in ("about", "causes")):
        raise ValueError("relation task heads are missing")
    statement_ids = tuple(statement_states)
    cluster_ids = view.cluster_ids
    eligible_about = len(statement_ids) * len(cluster_ids)
    eligible_causes = len(cluster_ids) * (len(cluster_ids) - 1)
    facts = []
    scored = {}
    for name, total, iterator in (
            ("about", eligible_about, product(statement_ids, cluster_ids)),
            ("causes", eligible_causes,
             ((a, b) for a in cluster_ids for b in cluster_ids if a != b))):
        selected = tuple(islice(iterator, max_pairs))
        scored[name] = len(selected)
        cluster_index = {cid: index for index, cid in enumerate(cluster_ids)}
        for start in range(0, len(selected), chunk_size):
            chunk = selected[start:start + chunk_size]
            left = torch.stack([statement_states[a] if name == "about" else
                                view.mean_reference[cluster_index[a]] for a, _ in chunk])
            right = torch.stack([view.mean_reference[cluster_index[b]] for _, b in chunk])
            logits = core.task_modules[name](left, right, view.document_state)
            if not torch.isfinite(logits).all():
                raise ValueError("relation scorer returned non-finite logits")
            facts.extend(RelationFact(name.upper(), a, b, float(logit))
                         for (a, b), logit in zip(chunk, logits)
                         if float(logit) >= score_threshold)
    return RelationDecode(tuple(facts), eligible_about, eligible_causes,
                          scored["about"], scored["causes"],
                          scored["about"] < eligible_about or scored["causes"] < eligible_causes)
