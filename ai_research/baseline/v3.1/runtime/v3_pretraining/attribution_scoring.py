"""Gold 없는 Assertor source와 final local relation의 request 범위 실행 경로."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice, product
from typing import Mapping, Sequence

import torch

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from models.v3_pretraining.pair_context import (build_pair_context,
                                                summarize_statements)
from runtime.v3_pretraining.entity_identity import EntityClosure
from runtime.v3_pretraining.event_features import FinalClusterFeatureLease
from runtime.v3_pretraining.event_identity import EventClosure
from runtime.v3_pretraining.extraction_decode import DecodedSourceSpan
from runtime.v3_pretraining.relation_routing import RelationRoute
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
    decision_score: float | None = None
    rejection_reason: str | None = None
    winner_state: torch.Tensor | None = None


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
    existence_score = float(head.existence_logit(statement))
    if not len(tokens):
        return AssertorSourceDecode(statement_id, None, 0, False,
                                    rejection_reason="NO_ELIGIBLE_SOURCE_TOKEN")
    if existence_score < score_threshold:
        return AssertorSourceDecode(statement_id, None, 0, False,
                                    decision_score=existence_score,
                                    rejection_reason="BELOW_THRESHOLD")
    logits = head.token_logits(statement, tokens)
    starts = torch.argsort(logits[:, 0], descending=True)[:max_starts].tolist()
    ends = torch.argsort(logits[:, 1], descending=True)[:max_ends].tolist()
    # Match the original tensor addition before converting to Python floats,
    # but transfer the Cartesian score table once instead of synchronizing per
    # candidate on MPS.
    pair_scores = (logits[starts, 0].unsqueeze(1) +
                   logits[ends, 1].unsqueeze(0)).detach().cpu().tolist()
    pairs = sorted(((float(pair_scores[ai][bi]), a, b)
                    for ai, a in enumerate(starts)
                    for bi, b in enumerate(ends) if a <= b), reverse=True)
    selected = pairs[:max_pairs]
    best: DecodedSourceSpan | None = None
    best_state: torch.Tensor | None = None
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
        # The heads accept a leading candidate dimension. Keep the same Cartesian
        # candidates and Python score ordering while avoiding two head calls and
        # several device reads for every individual span.
        owners = statement.unsqueeze(0).expand_as(features.states)
        deltas = (features.residuals + head.residual_delta(
            owners, features.states, features.residuals)).detach().cpu().tolist()
        link_scores = features.link_logits.detach().cpu().tolist()
        span_scores = head.span_logit(owners, features.states).detach().cpu().tolist()
        for index, (boundary_score, _, _) in enumerate(chunk):
            source = aligned[index]
            delta = deltas[index]
            start = source.start + round(float(delta[0]))
            end = source.end + round(float(delta[1]))
            score = boundary_score + float(link_scores[index]) + float(span_scores[index])
            if not 0 <= start < end <= len(layout.article.content) or score < score_threshold:
                continue
            candidate = DecodedSourceSpan("ASSERTOR", None, start, end,
                                          layout.article.content[start:end], score,
                                          source.start_ref.window_id, source.end_ref.window_id)
            if best is None or candidate.score > best.score:
                best = candidate
                best_state = (features.states[index] if (start, end) ==
                              (source.start, source.end) else None)
    partial = len(starts) == max_starts or len(ends) == max_ends or len(pairs) > max_pairs
    if best is None:
        return AssertorSourceDecode(statement_id, None, len(selected), partial,
                                    decision_score=existence_score,
                                    rejection_reason="NO_SPAN_AT_OR_ABOVE_THRESHOLD")
    return AssertorSourceDecode(statement_id, best, len(selected), partial,
                                decision_score=best.extraction_score,
                                winner_state=best_state)


@torch.no_grad()
def decode_assertor_sources(*, statements: Sequence[tuple[str, SpanAlignment, torch.Tensor]],
                            layout: SourceLayout, batch: ArticleBatch,
                            backbone: BackboneOutput, shared: SharedForwardLease,
                            core: V3Core, bridge_states: torch.Tensor,
                            max_starts: int = 32, max_ends: int = 32,
                            max_pairs: int = 128, chunk_size: int = 32,
                            statement_batch_size: int = 8,
                            score_threshold: float = 0.0
                            ) -> tuple[AssertorSourceDecode, ...]:
    """Batch owner endpoint heads and encode the union of exact source spans once.

    Candidate order and winner comparisons remain owner-local. A winner state
    is handed off only when its corrected coordinate equals its exact producer.
    """
    if min(max_starts, max_ends, max_pairs, chunk_size, statement_batch_size) <= 0:
        raise ValueError("Assertor source budgets must be positive")
    if shared.closed or shared.token_states is None or shared.sentence_states is None or shared.document_state is None:
        raise RuntimeError("Assertor extraction needs live shared representation")
    if "assertor_source" not in core.task_modules:
        raise ValueError("Assertor source head is missing")
    if bridge_states.shape != (len(layout.bridge_tokens), shared.token_states.shape[-1]):
        raise ValueError("Assertor bridge states differ from the source layout")
    if len({sid for sid, _, _ in statements}) != len(statements):
        raise ValueError("duplicate Statement owner in Assertor source")
    for sid, alignment, state in statements:
        if (not sid or layout.reconstruct(alignment) !=
                (alignment.start, alignment.end, alignment.text) or
                state.shape != shared.document_state.shape[-1:]):
            raise ValueError("Statement source representation differs")
    if not statements:
        return ()
    if shared.token_states.device.type == "mps":
        # The MPS batched exact producer changes final scores beyond 1e-7 in
        # the fixed parity fixture. Keep the owner-local execution until that
        # numerical boundary can be met without changing acceptance.
        return tuple(decode_assertor_source(
            statement_id=sid, statement_alignment=alignment,
            layout=layout, batch=batch, backbone=backbone, shared=shared,
            core=core, statement_state=state, bridge_states=bridge_states,
            max_starts=max_starts, max_ends=max_ends, max_pairs=max_pairs,
            chunk_size=chunk_size, score_threshold=score_threshold)
            for sid, alignment, state in statements)
    head = core.task_modules["assertor_source"]
    selected_by_owner: list[list[tuple[float, int, int]]] = [[] for _ in statements]
    existence_by_owner: list[float | None] = [None] * len(statements)
    partial_by_owner = [False] * len(statements)
    early: dict[int, AssertorSourceDecode] = {}
    fallback_owners: set[int] = set()
    parity_tolerance = 1e-7
    for offset in range(0, len(statements), statement_batch_size):
        group = statements[offset:offset + statement_batch_size]
        owners = torch.stack([state for _, _, state in group])
        existence = head.existence_logit(owners).detach().cpu().tolist()
        active = [index for index, score in enumerate(existence)
                  if score >= score_threshold and len(bridge_states)]
        for index, (sid, _, _) in enumerate(group):
            global_index = offset + index
            existence_by_owner[global_index] = float(existence[index])
            if abs(float(existence[index]) - score_threshold) <= parity_tolerance:
                fallback_owners.add(global_index)
            if not len(bridge_states):
                early[global_index] = AssertorSourceDecode(
                    sid, None, 0, False, rejection_reason="NO_ELIGIBLE_SOURCE_TOKEN")
            elif index not in active:
                early[global_index] = AssertorSourceDecode(
                    sid, None, 0, False, decision_score=float(existence[index]),
                    rejection_reason="BELOW_THRESHOLD")
        if not active:
            continue
        active_owners = owners[active]
        tokens = bridge_states.unsqueeze(0).expand(len(active), -1, -1)
        owner_rows = active_owners.unsqueeze(1).expand_as(tokens)
        logits = head.token(torch.cat((owner_rows, tokens, owner_rows * tokens),
                                      dim=-1))
        for row_index, owner_index in enumerate(active):
            owner_logits = logits[row_index]
            start_order = torch.argsort(owner_logits[:, 0], descending=True)
            end_order = torch.argsort(owner_logits[:, 1], descending=True)
            starts = start_order[:max_starts].tolist()
            ends = end_order[:max_ends].tolist()
            pair_scores = (owner_logits[starts, 0].unsqueeze(1) +
                           owner_logits[ends, 1].unsqueeze(0)).detach().cpu().tolist()
            pairs = sorted(((float(pair_scores[ai][bi]), a, b)
                            for ai, a in enumerate(starts)
                            for bi, b in enumerate(ends) if a <= b), reverse=True)
            global_index = offset + owner_index
            # A batch-size-dependent rounding change at either endpoint cutoff
            # can change Cartesian membership before pair-score ties are seen.
            for channel, order, limit in ((0, start_order, max_starts),
                                          (1, end_order, max_ends)):
                ranked = owner_logits[order[:limit + 1], channel].detach().cpu().tolist()
                if any(abs(ranked[index] - ranked[index - 1]) <= parity_tolerance
                       for index in range(1, len(ranked))):
                    fallback_owners.add(global_index)
            if any(abs(pairs[index][0] - pairs[index - 1][0]) <= parity_tolerance
                   for index in range(1, len(pairs))):
                fallback_owners.add(global_index)
            selected_by_owner[global_index] = pairs[:max_pairs]
            partial_by_owner[global_index] = (
                len(starts) == max_starts or len(ends) == max_ends or
                len(pairs) > max_pairs)
    # Exact source states are owner-independent. Preserve per-owner boundary
    # ordering and fall back to the reference decoder near decision ties.
    alignments: dict[tuple[int, int], SpanAlignment] = {}
    for owner_index, selected in enumerate(selected_by_owner):
        if owner_index in fallback_owners:
            continue
        for _, a, b in selected:
            first, last = layout.bridge_tokens[a], layout.bridge_tokens[b]
            key = first.start, last.end
            if key not in alignments:
                alignments[key] = layout.align({
                    "start": key[0], "end": key[1],
                    "text": layout.article.content[key[0]:key[1]]})
    feature_rows: dict[tuple[int, int], tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = {}
    items = list(alignments.items())
    for offset in range(0, len(items), 256):
        group = items[offset:offset + 256]
        features = core.exact_source_span(
            layout=layout, batch=batch, backbone=backbone,
            token_states=shared.token_states, sentence_states=shared.sentence_states,
            document_state=shared.document_state, candidate_encoder=core.candidate_span,
            rows=tuple((alignment, "STATEMENT") for _, alignment in group))
        for index, (key, _) in enumerate(group):
            feature_rows[key] = (features.states[index], features.residuals[index],
                                 features.link_logits[index])
    outcomes: list[AssertorSourceDecode] = []
    for owner_index, (sid, statement_alignment, statement) in enumerate(statements):
        def owner_local():
            return decode_assertor_source(
                statement_id=sid, statement_alignment=statement_alignment,
                layout=layout, batch=batch, backbone=backbone, shared=shared,
                core=core, statement_state=statement, bridge_states=bridge_states,
                max_starts=max_starts, max_ends=max_ends, max_pairs=max_pairs,
                chunk_size=chunk_size, score_threshold=score_threshold)
        if owner_index in fallback_owners:
            outcomes.append(owner_local())
            continue
        if owner_index in early:
            outcomes.append(early[owner_index])
            continue
        selected = selected_by_owner[owner_index]
        best = None
        best_state = None
        accepted_scores = []
        for offset in range(0, len(selected), chunk_size):
            chunk = selected[offset:offset + chunk_size]
            coordinates = [(layout.bridge_tokens[a].start, layout.bridge_tokens[b].end)
                           for _, a, b in chunk]
            states = torch.stack([feature_rows[key][0] for key in coordinates])
            residuals = torch.stack([feature_rows[key][1] for key in coordinates])
            links = torch.stack([feature_rows[key][2] for key in coordinates])
            owners = statement.unsqueeze(0).expand_as(states)
            deltas = (residuals + head.residual_delta(
                owners, states, residuals)).detach().cpu().tolist()
            link_scores = links.detach().cpu().tolist()
            span_scores = head.span_logit(owners, states).detach().cpu().tolist()
            for index, (boundary_score, _, _) in enumerate(chunk):
                source = alignments[coordinates[index]]
                start = source.start + round(float(deltas[index][0]))
                end = source.end + round(float(deltas[index][1]))
                score = boundary_score + float(link_scores[index]) + float(span_scores[index])
                if abs(score - score_threshold) <= parity_tolerance:
                    fallback_owners.add(owner_index)
                if not 0 <= start < end <= len(layout.article.content) or score < score_threshold:
                    continue
                candidate = DecodedSourceSpan(
                    "ASSERTOR", None, start, end, layout.article.content[start:end],
                    score, source.start_ref.window_id, source.end_ref.window_id)
                accepted_scores.append(score)
                if best is None or candidate.score > best.score:
                    best = candidate
                    best_state = states[index] if coordinates[index] == (start, end) else None
        if len(accepted_scores) > 1:
            top_scores = sorted(accepted_scores, reverse=True)[:2]
            if top_scores[0] - top_scores[1] <= parity_tolerance:
                fallback_owners.add(owner_index)
        if owner_index in fallback_owners:
            outcomes.append(owner_local())
            continue
        if best is None:
            outcomes.append(AssertorSourceDecode(
                sid, None, len(selected), partial_by_owner[owner_index],
                decision_score=existence_by_owner[owner_index],
                rejection_reason="NO_SPAN_AT_OR_ABOVE_THRESHOLD"))
        else:
            outcomes.append(AssertorSourceDecode(
                sid, best, len(selected), partial_by_owner[owner_index],
                decision_score=best.extraction_score, winner_state=best_state))
    return tuple(outcomes)


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
    pair_context_census: dict[str, object] | None = None
    routing_trace: dict[str, object] | None = None
    raw_score_rows: dict[str, tuple[tuple[str, str, float], ...]] | None = None


@torch.no_grad()
def score_final_relations(*, core: V3Core, final: FinalClusterFeatureLease,
                          closure: EventClosure,
                          statement_states: Mapping[str, torch.Tensor],
                          statement_spans: Mapping[str, tuple[int, int]],
                          max_pairs: int = 4096, chunk_size: int = 64,
                          score_threshold: float | None = 0.0,
                          about_threshold: float | None = None,
                          causes_threshold: float | None = None,
                          about_route: RelationRoute | None = None,
                          causes_route: RelationRoute | None = None,
                          allowed_about_pairs: frozenset[tuple[str, str]] | None = None,
                          allowed_causes_pairs: frozenset[tuple[str, str]] | None = None,
                          legacy_prefix_fallback: bool = False,
                          include_diagnostics: bool = True) -> RelationDecode:
    """final local ID만 평가한다. PUBLIC allowed set은 기존 route와 교집합한다."""
    if closure.source_mode != "PREDICTED" or final.source_mode != "PREDICTED" or final.cluster_ids != tuple(
            row.local_id for row in closure.events):
        raise ValueError("relation runtime needs predicted final Event identity")
    if min(max_pairs, chunk_size) <= 0:
        raise ValueError("relation pair bounds must be positive")
    if include_diagnostics and (allowed_about_pairs is not None or
                                allowed_causes_pairs is not None):
        raise ValueError("PUBLIC-only relation restriction cannot replace full diagnostic audit")
    about_threshold = score_threshold if about_threshold is None else about_threshold
    causes_threshold = score_threshold if causes_threshold is None else causes_threshold
    if about_threshold is None or causes_threshold is None:
        raise ValueError("relation acceptance thresholds are required")
    view = final.view_for("RELATION")
    if view.original_sentence_states is None:
        raise RuntimeError("relation scorer lost PairContextV1 sentence carrier")
    if any(name not in core.task_modules for name in ("about", "causes")):
        raise ValueError("relation task heads are missing")
    statement_ids = tuple(statement_states)
    if set(statement_spans) != set(statement_ids):
        raise ValueError("Statement state/source geometry IDs differ")
    statement_summaries = summarize_statements(
        view.original_sentence_states, view.original_sentence_spans, statement_spans)
    cluster_ids = view.cluster_ids
    eligible_about = len(statement_ids) * len(cluster_ids)
    eligible_causes = len(cluster_ids) * (len(cluster_ids) - 1)
    routes = {"about": about_route, "causes": causes_route}
    allowed_pairs = {"about": allowed_about_pairs, "causes": allowed_causes_pairs}
    for lane, route, eligible in (("ABOUT", about_route, eligible_about),
                                  ("CAUSES", causes_route, eligible_causes)):
        if route is None:
            allowed = allowed_pairs[lane.lower()]
            if allowed is not None:
                # PUBLIC restriction is the actual fine universe when no route
                # exists; unrestricted diagnostic scoring keeps its full bound.
                left_ids = set(statement_ids if lane == "ABOUT" else cluster_ids)
                right_ids = set(cluster_ids)
                if (len(allowed) > max_pairs or
                        any(left not in left_ids or right not in right_ids or
                            (lane == "CAUSES" and left == right)
                            for left, right in allowed)):
                    raise ValueError("PUBLIC allowed relation pairs exceed bound or IDs")
            elif eligible > max_pairs and not legacy_prefix_fallback:
                raise ValueError("large relation universe needs validated bounded routing")
            continue
        allowed_left = set(statement_ids if lane == "ABOUT" else cluster_ids)
        allowed_right = set(cluster_ids)
        routed_pair_set = set(route.pairs)
        if (route.lane != lane or route.eligible_count != eligible or
                len(route.pairs) != len(routed_pair_set) or
                len(route.records) != len(route.pairs) or
                len(route.pairs) > max_pairs or
                any(record.get("query_id") != left or
                    record.get("candidate_id") != right or
                    record.get("policy_id") != route.policy_id or
                    record.get("policy_sha256") != route.policy_sha256 or
                    record.get("source_inventory_lineage") !=
                    route.source_inventory_lineage or
                    record.get("routing_status") != "ROUTING_SELECTED"
                    for (left, right), record in zip(route.pairs, route.records)) or
                any(left not in allowed_left or right not in allowed_right or
                    (lane == "CAUSES" and left == right)
                    for left, right in route.pairs) or
                (lane == "CAUSES" and any((right, left) not in routed_pair_set
                                          for left, right in route.pairs))):
            raise ValueError("relation routing and fine pair universe differ")
    facts = []
    raw_score_rows: dict[str, list[tuple[str, str, float]]] = {
        "about": [], "causes": []}
    scored = {}
    chunk_counts = {"about": 0, "causes": 0}
    provenance_sample: dict[str, list[dict[str, object]]] = {
        "about": [], "causes": []}
    max_feature_rows = 0
    max_bridge_gather = 0
    for name, total, iterator, threshold in (
            ("about", eligible_about, product(statement_ids, cluster_ids), about_threshold),
            ("causes", eligible_causes,
             ((a, b) for a in cluster_ids for b in cluster_ids if a != b), causes_threshold)):
        route = routes[name]
        allowed = allowed_pairs[name]
        if route is not None:
            selected = (route.pairs if allowed is None else
                        tuple(pair for pair in route.pairs if pair in allowed))
        elif allowed is not None:
            # Match Cartesian source order without materializing the full
            # universe merely to filter a bounded PUBLIC selection.
            left_index = {key: index for index, key in enumerate(
                statement_ids if name == "about" else cluster_ids)}
            right_index = {key: index for index, key in enumerate(cluster_ids)}
            selected = tuple(sorted(allowed, key=lambda pair: (
                left_index[pair[0]], right_index[pair[1]])))
        else:
            selected = (tuple(islice(iterator, max_pairs)) if legacy_prefix_fallback
                        else tuple(iterator))
        scored[name] = len(selected)
        cluster_index = {cid: index for index, cid in enumerate(cluster_ids)}
        for start in range(0, len(selected), chunk_size):
            chunk = selected[start:start + chunk_size]
            if include_diagnostics:
                chunk_counts[name] += 1
            left = torch.stack([statement_states[a] if name == "about" else
                                view.mean_reference[cluster_index[a]] for a, _ in chunk])
            right = torch.stack([view.mean_reference[cluster_index[b]] for _, b in chunk])
            left_summaries = [statement_summaries[a] if name == "about" else
                              view.event_sentence_summaries[cluster_index[a]] for a, _ in chunk]
            right_summaries = [view.event_sentence_summaries[cluster_index[b]]
                               for _, b in chunk]
            context = build_pair_context(
                left=left, right=right, left_summaries=left_summaries,
                right_summaries=right_summaries,
                sentence_states=view.original_sentence_states,
                document_state=view.document_state,
                include_provenance=include_diagnostics)
            if include_diagnostics:
                max_feature_rows = max(max_feature_rows, context.features.shape[0])
                max_bridge_gather = max(max_bridge_gather, context.max_bridge_gather)
            remaining = 4 - len(provenance_sample[name]) if include_diagnostics else 0
            if remaining > 0:
                provenance_sample[name].extend({
                    "source_id": source_id,
                    "target_id": target_id,
                    "left_anchor": row.left_anchor,
                    "right_anchor": row.right_anchor,
                    "actual_distance": row.actual_distance,
                    "left_sentence_indices": list(row.left_sentence_indices),
                    "right_sentence_indices": list(row.right_sentence_indices),
                    "bridge_sentence_indices": list(row.bridge_sentence_indices),
                } for (source_id, target_id), row in zip(
                    chunk[:remaining], context.provenance[:remaining]))
            logits = core.task_modules[name](context.features)
            if not torch.isfinite(logits).all():
                raise ValueError("relation scorer returned non-finite logits")
            score_rows = logits.detach().cpu().tolist()
            if include_diagnostics:
                raw_score_rows[name].extend(
                    (a, b, float(logit))
                    for (a, b), logit in zip(chunk, score_rows))
            facts.extend(RelationFact(name.upper(), a, b, logit)
                         for (a, b), logit in zip(chunk, score_rows)
                         if logit >= threshold)
    if not include_diagnostics:
        return RelationDecode(tuple(facts), eligible_about, eligible_causes,
                              scored["about"], scored["causes"],
                              scored["about"] < eligible_about or
                              scored["causes"] < eligible_causes)
    accepted_by_lane = {name: {(row.source_id, row.target_id) for row in facts
                               if row.relation == name}
                        for name in ("ABOUT", "CAUSES")}
    routing_trace = {name.upper(): {
        "policy_id": route.policy_id if route is not None else
        "LEGACY_PREFIX_AUDIT_FALLBACK" if legacy_prefix_fallback and
        total > max_pairs else "FULL_SMALL_UNIVERSE",
        "policy_sha256": route.policy_sha256 if route is not None else None,
        "source_inventory_lineage": route.source_inventory_lineage if route is not None else None,
        "eligible": total, "routing_selected": scored[name],
        "fine_scorer_input": scored[name],
        "not_evaluated_routing": total - scored[name],
        "selected_records": [
            {**record, "fine_status": (
                "FINE_ACCEPTED" if (record["query_id"], record["candidate_id"])
                in accepted_by_lane[name.upper()] else "FINE_REJECTED")}
            for record in route.records] if route is not None else [],
        "missing_pair_status": "NOT_EVALUATED_ROUTING",
        "fine_rejected": scored[name] - len(accepted_by_lane[name.upper()]),
        "fine_accepted": len(accepted_by_lane[name.upper()]),
    } for name, total in (("about", eligible_about), ("causes", eligible_causes))}
    return RelationDecode(tuple(facts), eligible_about, eligible_causes,
                          scored["about"], scored["causes"],
                          scored["about"] < eligible_about or scored["causes"] < eligible_causes,
                          pair_context_census={
                              "original_sentence_count": len(view.original_sentence_spans),
                              "original_sentence_tensor_shape": list(
                                  view.original_sentence_states.shape),
                              "statement_endpoint_summaries": len(statement_summaries),
                              "event_endpoint_summaries": len(
                                  view.event_sentence_summaries),
                              "about_chunks": chunk_counts["about"],
                              "causes_chunks": chunk_counts["causes"],
                              "max_pair_feature_shape": [max_feature_rows, 2057],
                              "max_bridge_gather": max_bridge_gather,
                              "provenance_sample": provenance_sample,
                          }, routing_trace=routing_trace,
                          raw_score_rows={name.upper(): tuple(rows)
                                          for name, rows in raw_score_rows.items()})
