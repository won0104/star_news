"""Frozen TOP32→Canonical V3 scorer의 accepted hypothesis 경계.

The proposer owns only the TOP32 candidate identity universe.  Canonical V3
receives RAW/DCE token states and candidate spans; proposer score/rank never
enter its feature path.  Acceptance is the independent Semantic AND Boundary
decision followed only by exact same-label duplicate removal. Family와 최종 mention
결정은 mention_consolidation이 맡는다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import time
from typing import Any, Mapping

import torch

from .contracts import ArticleInput
from .models import CANONICAL_V3_LABELS, CanonicalV3SemanticRuntimeModel
from .preprocessing import PreparedArticle, token_to_character_span
from .resolved_contracts import AcceptedSpanHypothesis


@dataclass(frozen=True, slots=True)
class SemanticRun:
    accepted_hypotheses: tuple[AcceptedSpanHypothesis, ...]
    trace: Mapping[str, Any]
    debug: Mapping[str, Any]


def stable_prediction_id(
    article: ArticleInput,
    runtime_config_id: str,
    kind: str,
    char_start: int,
    char_end: int,
) -> str:
    value = "|".join(
        (
            str(article.article_version_id),
            runtime_config_id,
            kind,
            str(char_start),
            str(char_end),
        )
    )
    prefix = "EVP" if kind == "EVENT" else "STP"
    return f"{prefix}-" + sha256(value.encode("utf-8")).hexdigest()[:20]


def stable_candidate_id(
    article: ArticleInput,
    socket_version: str,
    sentence_index: int,
    token_start: int,
    token_end: int,
    label: str,
) -> str:
    value = "|".join(
        (
            str(article.article_version_id),
            socket_version,
            str(sentence_index),
            str(token_start),
            str(token_end),
            label,
        )
    )
    return "SPC-" + sha256(value.encode("utf-8")).hexdigest()[:20]


def top32_candidates(
    token_mask: torch.BoolTensor,
    proposal_logits: torch.Tensor,
    *,
    top_k: int,
    max_span_width: int,
) -> tuple[tuple[tuple[int, int, int, int], float, int], ...]:
    """Apply the historical score-desc/start/end TOP32 rule per sentence/label."""

    probabilities = proposal_logits.sigmoid().detach().cpu()[0]
    mask = token_mask.detach().cpu()[0]
    selected: dict[tuple[int, int, int, int], tuple[float, int]] = {}
    for sentence_index in range(mask.shape[0]):
        positions = torch.nonzero(mask[sentence_index], as_tuple=False).flatten().tolist()
        for label_index in range(len(CANONICAL_V3_LABELS)):
            cell = []
            for token_start in positions:
                for end_inclusive in positions:
                    if token_start > end_inclusive:
                        continue
                    token_end = end_inclusive + 1
                    if token_end - token_start > max_span_width:
                        continue
                    identity = (sentence_index, token_start, token_end, label_index)
                    cell.append(
                        (
                            identity,
                            float(
                                probabilities[
                                    sentence_index,
                                    token_start,
                                    end_inclusive,
                                    label_index,
                                ]
                            ),
                        )
                    )
            cell.sort(key=lambda item: (-item[1], item[0][1], item[0][2]))
            for rank, (identity, score) in enumerate(cell[:top_k], start=1):
                selected[identity] = (score, rank)
    return tuple((identity, *selected[identity]) for identity in sorted(selected))


class FixedCanonicalV3SemanticRuntime:
    """Generate canonical-A candidates and score them with frozen Canonical V3."""

    def __init__(
        self,
        model: CanonicalV3SemanticRuntimeModel,
        config: Mapping[str, Any],
        proposer_checkpoint_sha: str,
        v3_checkpoint_sha: str,
    ) -> None:
        self.model = model
        self.config = config
        self.proposer_checkpoint_sha = proposer_checkpoint_sha
        self.v3_checkpoint_sha = v3_checkpoint_sha

    @torch.inference_mode()
    def run(self, prepared: PreparedArticle, backbone, *, debug_trace: bool,
            diagnostic_sink=None) -> SemanticRun:
        started = time.perf_counter()
        batch = prepared.batch.to(next(self.model.parameters()).device)
        self.model.eval()
        raw_states, dce_states, proposal_logits = self.model.encode_and_propose(batch, backbone)
        policy = self.config["candidate_policy"]
        candidates = top32_candidates(
            batch.source_token_mask,
            proposal_logits,
            top_k=int(policy["top_k"]),
            max_span_width=int(policy["max_span_width_tokens"]),
        )
        proposal_tensor = torch.tensor(
            [identity[:3] for identity, _score, _rank in candidates],
            dtype=torch.long,
            device=raw_states.device,
        ).reshape(1, -1, 3)
        proposal_mask = torch.ones(
            1, len(candidates), dtype=torch.bool, device=raw_states.device
        )
        output = self.model.canonical_v3(
            raw_states,
            dce_states,
            proposal_tensor,
            proposal_mask,
            batch.source_token_mask,
        )
        semantic_scores = output.semantic_logits.sigmoid()[0].detach().cpu()
        boundary_scores = output.boundary_logits.sigmoid()[0].detach().cpu()
        acceptance = self.config["acceptance"]
        semantic_threshold = float(acceptance["semantic_threshold"])
        boundary_threshold = float(acceptance["boundary_threshold"])
        accepted_rows: list[AcceptedSpanHypothesis] = []
        seen: set[tuple[int, int, int, str]] = set()
        rejected = Counter()
        for index, (identity, proposal_score, candidate_rank) in enumerate(candidates):
            sentence_index, token_start, token_end, label_index = identity
            label = CANONICAL_V3_LABELS[label_index]
            semantic_score = float(semantic_scores[index, label_index])
            boundary_score = float(boundary_scores[index, label_index])
            semantic_pass = semantic_score >= semantic_threshold
            boundary_pass = boundary_score >= boundary_threshold
            accepted = semantic_pass and boundary_pass
            if not semantic_pass:
                rejected["SEMANTIC_REJECTED"] += 1
            elif not boundary_pass:
                rejected["BOUNDARY_REJECTED"] += 1
            sentence = prepared.sentences[sentence_index]
            char_start, char_end, _text = token_to_character_span(
                prepared.article.content, sentence, token_start, token_end
            )
            candidate_id = stable_candidate_id(
                prepared.article, str(self.config["socket_version"]),
                sentence_index, token_start, token_end, label,
            )
            exact_key = (sentence_index, token_start, token_end, label)
            if accepted and exact_key in seen:
                rejected["EXACT_DUPLICATE"] += 1
                accepted = False
                reason = "EXACT_DUPLICATE"
            else:
                reason = ("ACCEPTED_HYPOTHESIS" if accepted else
                          "SEMANTIC_REJECTED" if not semantic_pass else "BOUNDARY_REJECTED")
            if diagnostic_sink is not None and diagnostic_sink.level.value != "SUMMARY":
                record = {
                    "component": "semantic_proposition",
                    "candidate_id": candidate_id,
                    "article_version_id": prepared.article.article_version_id,
                    "kind": label,
                    "sentence_index": sentence_index,
                    "char_start": char_start,
                    "char_end": char_end,
                    "decision": reason,
                    "semantic_score": semantic_score,
                    "boundary_score": boundary_score,
                }
                if debug_trace:
                    record.update({
                        "proposal_score": proposal_score,
                        "candidate_rank": candidate_rank,
                        "proposal_metadata_usage": "TRACE_ONLY",
                    })
                diagnostic_sink.record(
                    "candidate" if debug_trace else "decision", record,
                )
            if not accepted:
                continue
            seen.add(exact_key)
            accepted_rows.append(AcceptedSpanHypothesis(
                hypothesis_id=candidate_id,
                kind=label,
                grounding=prepared.source_ref(char_start, char_end, sentence_index),
                sentence_id=sentence["sentence_id"],
                sentence_index=sentence_index,
                token_start=token_start,
                token_end=token_end,
                semantic_score=semantic_score,
                boundary_score=boundary_score,
                semantic_threshold=semantic_threshold,
                boundary_threshold=boundary_threshold,
            ))
        accepted_rows.sort(
            key=lambda row: (
                row.sentence_index,
                row.grounding.char_start,
                row.grounding.char_end,
                row.kind,
            )
        )
        elapsed = time.perf_counter() - started
        trace = {
            "stage": "② Semantic Proposition Span Socket",
            "component": "canonical-A TOP32 → Canonical V3",
            "checkpoint_sha": self.v3_checkpoint_sha,
            "proposer_checkpoint_sha": self.proposer_checkpoint_sha,
            "config": {
                "candidate_policy": policy,
                "acceptance": acceptance,
                "decoder": self.config["decoder"],
            },
            "input_count": int(batch.source_token_mask.sum()),
            "candidate_count": len(candidates),
            "output_count": len(accepted_rows),
            "drop_reason_counts": dict(rejected),
            "warnings": [self.config["known_limitation"]],
            "elapsed_seconds": elapsed,
        }
        return SemanticRun(tuple(accepted_rows), trace, {})
