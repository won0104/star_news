"""Fixed Semantic boundary → proposal → verifier → acceptance → decoder path."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import time
from typing import Any, Mapping

import torch

from .contracts import ArticleInput
from .models import SEMANTIC_LABELS, SemanticRuntimeModel
from .preprocessing import PreparedArticle, token_to_character_span


@dataclass(frozen=True, slots=True)
class SemanticRun:
    propositions: tuple[Mapping[str, Any], ...]
    trace: Mapping[str, Any]
    debug: Mapping[str, Any]


def stable_prediction_id(
    article: ArticleInput,
    runtime_config_id: str,
    kind: str,
    char_start: int,
    char_end: int,
) -> str:
    from hashlib import sha256

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


def _select(values: Mapping[int, float], floor: float, k: int) -> tuple[int, ...]:
    filtered = {position: score for position, score in values.items() if score >= floor}
    return tuple(sorted(filtered, key=lambda position: (-filtered[position], position))[:k])


def _proposal_universe(prepared: PreparedArticle, start, end, policy, width):
    proposals = set()
    selected = {}
    for sentence in prepared.sentences:
        si = sentence["sentence_index"]
        positions = sentence["positions"]
        for label_index in range(len(SEMANTIC_LABELS)):
            starts = _select(
                {position: float(start[0, si, position, label_index]) for position in positions},
                float(policy["floor"]),
                int(policy["k"]),
            )
            ends = _select(
                {position: float(end[0, si, position, label_index]) for position in positions},
                float(policy["floor"]),
                int(policy["k"]),
            )
            selected[si, label_index] = {"starts": starts, "ends_inclusive": ends}
            for token_start in starts:
                for end_inclusive in ends:
                    if token_start <= end_inclusive and end_inclusive - token_start + 1 <= width:
                        proposals.add((si, token_start, end_inclusive + 1, label_index))
    return tuple(sorted(proposals)), selected


def _conflict(candidate, accepted) -> str | None:
    if candidate["sentence_index"] != accepted["sentence_index"]:
        return None
    a0, a1 = candidate["token_start"], candidate["token_end"]
    b0, b1 = accepted["token_start"], accepted["token_end"]
    if (a0, a1) == (b0, b1):
        return (
            "SAME_BOUNDARY_SAME_LABEL"
            if candidate["kind"] == accepted["kind"]
            else None
        )
    # SEMANTIC_PRESERVING allows overlap/nesting; exact same-label duplicates only.
    return None


class FixedSemanticRuntime:
    def __init__(self, model: SemanticRuntimeModel, config: Mapping[str, Any], checkpoint_sha: str):
        self.model = model
        self.config = config
        self.checkpoint_sha = checkpoint_sha

    @torch.inference_mode()
    def run(self, prepared: PreparedArticle, backbone, *, debug_trace: bool) -> SemanticRun:
        started = time.perf_counter()
        batch = prepared.batch.to(next(self.model.parameters()).device)
        self.model.eval()
        context, output = self.model(batch, backbone)
        boundary_done = time.perf_counter()
        start = output.boundaries.start_logits.sigmoid()
        end = output.boundaries.end_logits.sigmoid()
        policy = self.config["candidate_policy"]
        proposals, selected = _proposal_universe(
            prepared, start, end, policy, int(self.config["max_span_width_tokens"])
        )
        unique_spans = sorted({proposal[:3] for proposal in proposals})
        scores: dict[tuple[int, int, int], list[float]] = {}
        verifier_started = time.perf_counter()
        for offset in range(0, len(unique_spans), int(self.config["verifier_batch_size"])):
            part = unique_spans[offset : offset + int(self.config["verifier_batch_size"])]
            if not part:
                continue
            tensor = torch.tensor(part, dtype=torch.long, device=start.device)[None]
            mask = torch.ones(1, len(part), dtype=torch.bool, device=start.device)
            logits = self.model.semantic.head.score_proposals(
                context.token_states,
                context.sentence_states,
                tensor,
                mask,
                batch.source_token_mask,
            )[0].sigmoid().cpu().tolist()
            scores.update(zip(part, logits))
        verifier_done = time.perf_counter()
        acceptance = self.config["acceptance"]
        decisions = []
        reject_counts = Counter()
        for si, token_start, token_end, label_index in proposals:
            p_start = float(start[0, si, token_start, label_index])
            p_end = float(end[0, si, token_end - 1, label_index])
            boundary_score = math.sqrt(p_start * p_end)
            verifier_score = float(scores[si, token_start, token_end][label_index])
            accepted = (
                verifier_score >= float(acceptance["verifier_threshold"])
                and boundary_score >= float(acceptance["boundary_floor"])
            )
            if not accepted:
                reject_counts[
                    "VERIFIER_THRESHOLD"
                    if verifier_score < float(acceptance["verifier_threshold"])
                    else "BOUNDARY_FLOOR"
                ] += 1
            char_start, char_end, text = token_to_character_span(
                prepared.article.content, prepared.sentences[si], token_start, token_end
            )
            proposal_id = stable_prediction_id(
                prepared.article,
                self.config["source_semantic_runtime_config_id"],
                "PROPOSAL_" + SEMANTIC_LABELS[label_index],
                char_start,
                char_end,
            )
            decisions.append(
                {
                    "proposal_id": proposal_id,
                    "kind": SEMANTIC_LABELS[label_index],
                    "sentence_index": si,
                    "sentence_id": prepared.sentences[si]["sentence_id"],
                    "token_start": token_start,
                    "token_end": token_end,
                    "char_start": char_start,
                    "char_end": char_end,
                    "text": text,
                    "start_score": p_start,
                    "end_score": p_end,
                    "boundary_score": boundary_score,
                    "verifier_score": verifier_score,
                    "acceptance_score": verifier_score,
                    "accepted": accepted,
                }
            )
        ordered = sorted(
            (row for row in decisions if row["accepted"]),
            key=lambda row: (
                -row["acceptance_score"],
                -row["verifier_score"],
                -row["boundary_score"],
                row["sentence_index"],
                row["token_start"],
                row["token_end"],
                row["kind"],
            ),
        )
        kept = []
        sentence_counts = Counter()
        for row in ordered:
            if sentence_counts[row["sentence_index"]] >= int(self.config["decoder"]["sentence_cap"]):
                reject_counts["SENTENCE_OUTPUT_CAP"] += 1
                continue
            if any(_conflict(row, old) for old in kept):
                reject_counts["SAME_BOUNDARY_SAME_LABEL"] += 1
                continue
            kept.append(row)
            sentence_counts[row["sentence_index"]] += 1
        ranks = Counter()
        propositions = []
        for row in kept:
            ranks[row["sentence_index"]] += 1
            prediction_id = stable_prediction_id(
                prepared.article,
                self.config["canonical_runtime_config_id"],
                row["kind"],
                row["char_start"],
                row["char_end"],
            )
            propositions.append(
                {
                    "prediction_id": prediction_id,
                    "proposal_id": row["proposal_id"],
                    "kind": row["kind"],
                    "article_id": prepared.article.article_id,
                    "sentence_id": row["sentence_id"],
                    "sentence_index": row["sentence_index"],
                    "char_start": row["char_start"],
                    "char_end": row["char_end"],
                    "token_start": row["token_start"],
                    "token_end": row["token_end"],
                    "text": row["text"],
                    "boundary_score": row["boundary_score"],
                    "verifier_score": row["verifier_score"],
                    "acceptance_score": row["acceptance_score"],
                    "decoder_rank": ranks[row["sentence_index"]],
                    "checkpoint_sha": self.checkpoint_sha,
                    "runtime_config_id": self.config["canonical_runtime_config_id"],
                    "provenance": {
                        "source": "EXPERIMENTAL_PREDICTION",
                        "semantic_runtime_source_config_id": self.config[
                            "source_semantic_runtime_config_id"
                        ],
                        "decoder_decision": "ACCEPTED",
                    },
                    "representation_source": "frozen KF-DeBERTa L8 + selected Semantic DocumentContextEncoder token states",
                }
            )
        propositions.sort(
            key=lambda row: (
                row["sentence_index"], row["char_start"], row["char_end"], row["kind"]
            )
        )
        debug = {}
        if debug_trace:
            debug = {
                "selected_boundaries": {
                    f"{si}:{SEMANTIC_LABELS[li]}": {
                        "starts": list(value["starts"]),
                        "ends_inclusive": list(value["ends_inclusive"]),
                    }
                    for (si, li), value in selected.items()
                },
                "proposals": decisions,
            }
        return SemanticRun(
            tuple(propositions),
            {
                "stage": "③ 구간 추출부",
                "component": "Semantic Proposition",
                "checkpoint_sha": self.checkpoint_sha,
                "config": {
                    "candidate_policy": policy,
                    "acceptance": acceptance,
                    "decoder": self.config["decoder"],
                },
                "input_count": sum(len(sentence["positions"]) for sentence in prepared.sentences),
                "candidate_count": len(proposals),
                "output_count": len(propositions),
                "drop_reason_counts": dict(reject_counts),
                "warnings": [],
                "elapsed_seconds": time.perf_counter() - started,
                "boundary_context_seconds": boundary_done - started,
                "verifier_seconds": verifier_done - verifier_started,
            },
            debug,
        )
