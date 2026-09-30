"""trainable span Head와 분리된 BIO/boundary/constrained decoding."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable, Sequence

import torch


@dataclass(frozen=True, slots=True)
class DecodedSpan:
    sentence_index: int
    token_start: int
    token_end: int
    label: str
    score: float
    character_start: int | None = None
    character_end: int | None = None

    @property
    def boundary(self) -> tuple[int, int, int]:
        return self.sentence_index, self.token_start, self.token_end


@dataclass(frozen=True, slots=True)
class BoundaryDecodeResult:
    """Boundary threshold를 통과한 pair 수와 deterministic 선택 결과."""

    spans: tuple[DecodedSpan, ...]
    candidate_count: int


class BIOFlatDecoder:
    """BIO argmax를 flat/non-overlap span으로 복원한다."""

    def __init__(self, labels: Sequence[str]) -> None:
        if not labels or labels[0] != "O":
            raise ValueError("BIO labels must start with O")
        self.labels = tuple(labels)

    def decode(
        self,
        logits: torch.Tensor,
        token_mask: torch.BoolTensor,
    ) -> list[list[list[DecodedSpan]]]:
        if logits.ndim != 4 or token_mask.shape != logits.shape[:3]:
            raise ValueError("BIO decoder expects logits [B,S,T,C]")
        probabilities = torch.softmax(logits, dim=-1)
        ids = probabilities.argmax(dim=-1)
        output: list[list[list[DecodedSpan]]] = []
        for batch_index in range(logits.shape[0]):
            article = []
            for sentence_index in range(logits.shape[1]):
                spans: list[DecodedSpan] = []
                active_label: str | None = None
                start = 0
                scores: list[float] = []
                valid_positions = torch.nonzero(
                    token_mask[batch_index, sentence_index], as_tuple=False
                ).flatten().tolist()
                for offset in range(len(valid_positions) + 1):
                    token_index = (
                        valid_positions[-1] + 1
                        if offset == len(valid_positions) and valid_positions
                        else (0 if offset == len(valid_positions) else valid_positions[offset])
                    )
                    label = "O" if offset == len(valid_positions) else self.labels[int(ids[batch_index, sentence_index, token_index])]
                    prefix, _, kind = label.partition("-")
                    if active_label is not None and (prefix != "I" or kind != active_label):
                        spans.append(DecodedSpan(sentence_index, start, token_index, active_label, sum(scores) / len(scores)))
                        active_label, scores = None, []
                    if prefix == "B" or (prefix == "I" and active_label is None):
                        active_label, start = kind, token_index
                        scores = [float(probabilities[batch_index, sentence_index, token_index, int(ids[batch_index, sentence_index, token_index])])]
                    elif prefix == "I" and kind == active_label:
                        scores.append(float(probabilities[batch_index, sentence_index, token_index, int(ids[batch_index, sentence_index, token_index])]))
                article.append(spans)
            output.append(article)
        return output


class BoundaryProposalDecoder:
    """독립 start/end probability에서 폭 제한 proposal을 만든다."""

    def __init__(self, labels: Sequence[str], threshold: float = 0.5, max_width: int = 96) -> None:
        self.labels = tuple(labels)
        self.threshold = threshold
        self.max_width = max_width

    def decode(self, start_logits: torch.Tensor, end_logits: torch.Tensor, mask: torch.BoolTensor) -> list[DecodedSpan]:
        return list(self.decode_with_diagnostics(start_logits, end_logits, mask).spans)

    def decode_with_diagnostics(
        self,
        start_logits: torch.Tensor,
        end_logits: torch.Tensor,
        mask: torch.BoolTensor,
    ) -> BoundaryDecodeResult:
        starts = torch.sigmoid(start_logits).detach()
        ends = torch.sigmoid(end_logits).detach()
        proposals = []
        for sentence in range(start_logits.shape[0]):
            for label_index, label in enumerate(self.labels):
                start_ids = torch.nonzero((starts[sentence, :, label_index] >= self.threshold) & mask[sentence], as_tuple=False).flatten().tolist()
                end_ids = torch.nonzero((ends[sentence, :, label_index] >= self.threshold) & mask[sentence], as_tuple=False).flatten().tolist()
                for start, end_inclusive in product(start_ids, end_ids):
                    if start <= end_inclusive and end_inclusive - start + 1 <= self.max_width:
                        score = float((starts[sentence, start, label_index] * ends[sentence, end_inclusive, label_index]).sqrt())
                        proposals.append(DecodedSpan(sentence, start, end_inclusive + 1, label, score))
        return BoundaryDecodeResult(tuple(proposals), len(proposals))


class GreedyOneToOneBoundaryDecoder:
    """Confidence 순으로 start/end를 한 번씩만 쓰는 historical-style decoder.

    Exact duplicate는 endpoint 1:1 제약으로 제거한다. 서로 다른 endpoint를 사용하는 span의
    overlap/nesting은 허용하며, label·문장별 출력 cap으로 무제한 조합을 막는다.
    """

    def __init__(
        self,
        labels: Sequence[str],
        threshold: float = 0.5,
        max_width: int = 64,
        max_outputs_per_label_sentence: int = 4,
    ) -> None:
        if max_width <= 0 or max_outputs_per_label_sentence <= 0:
            raise ValueError("Greedy boundary decoder limits must be positive")
        self.labels = tuple(labels)
        self.threshold = threshold
        self.max_width = max_width
        self.max_outputs_per_label_sentence = max_outputs_per_label_sentence

    def decode(
        self,
        start_logits: torch.Tensor,
        end_logits: torch.Tensor,
        mask: torch.BoolTensor,
    ) -> list[DecodedSpan]:
        return list(self.decode_with_diagnostics(start_logits, end_logits, mask).spans)

    def decode_with_diagnostics(
        self,
        start_logits: torch.Tensor,
        end_logits: torch.Tensor,
        mask: torch.BoolTensor,
    ) -> BoundaryDecodeResult:
        starts = torch.sigmoid(start_logits).detach()
        ends = torch.sigmoid(end_logits).detach()
        selected: list[DecodedSpan] = []
        candidate_count = 0
        for sentence in range(start_logits.shape[0]):
            for label_index, label in enumerate(self.labels):
                start_ids = torch.nonzero(
                    (starts[sentence, :, label_index] >= self.threshold)
                    & mask[sentence],
                    as_tuple=False,
                ).flatten().tolist()
                end_ids = torch.nonzero(
                    (ends[sentence, :, label_index] >= self.threshold)
                    & mask[sentence],
                    as_tuple=False,
                ).flatten().tolist()
                candidates: list[DecodedSpan] = []
                for start in start_ids:
                    for end_inclusive in end_ids:
                        width = end_inclusive - start + 1
                        if 1 <= width <= self.max_width:
                            score = float(
                                (
                                    starts[sentence, start, label_index]
                                    * ends[sentence, end_inclusive, label_index]
                                ).sqrt()
                            )
                            candidates.append(
                                DecodedSpan(
                                    sentence,
                                    start,
                                    end_inclusive + 1,
                                    label,
                                    score,
                                )
                            )
                candidate_count += len(candidates)
                used_starts: set[int] = set()
                used_ends: set[int] = set()
                for candidate in sorted(
                    candidates,
                    key=lambda item: (
                        -item.score,
                        item.token_start,
                        item.token_end,
                    ),
                ):
                    end_inclusive = candidate.token_end - 1
                    if (
                        candidate.token_start in used_starts
                        or end_inclusive in used_ends
                    ):
                        continue
                    selected.append(candidate)
                    used_starts.add(candidate.token_start)
                    used_ends.add(end_inclusive)
                    if (
                        len(used_starts)
                        >= self.max_outputs_per_label_sentence
                    ):
                        break
        return BoundaryDecodeResult(tuple(selected), candidate_count)


@dataclass(frozen=True, slots=True)
class SemanticConstraintConfig:
    threshold: float = 0.5
    max_outputs_per_sentence: int = 12
    allow_cross_label_exact_boundary: bool = True
    allow_nested: bool = True
    containment_margin: float = 0.08
    overlap_margin: float = 0.05


class SemanticConstraintDecoder:
    """confidence 순으로 prefix/suffix/merged proposition 중복을 제한한다."""

    def __init__(self, config: SemanticConstraintConfig | None = None) -> None:
        self.config = config or SemanticConstraintConfig()

    def decode(self, candidates: Iterable[DecodedSpan]) -> list[DecodedSpan]:
        selected: list[DecodedSpan] = []
        counts: dict[int, int] = {}
        for candidate in sorted(candidates, key=lambda item: (-item.score, item.token_start, item.token_end, item.label)):
            if candidate.score < self.config.threshold:
                continue
            if counts.get(candidate.sentence_index, 0) >= self.config.max_outputs_per_sentence:
                continue
            if any(self._conflicts(candidate, accepted) for accepted in selected):
                continue
            selected.append(candidate)
            counts[candidate.sentence_index] = counts.get(candidate.sentence_index, 0) + 1
        return sorted(selected, key=lambda item: (item.sentence_index, item.token_start, item.token_end, item.label))

    def _conflicts(self, candidate: DecodedSpan, accepted: DecodedSpan) -> bool:
        if candidate.sentence_index != accepted.sentence_index:
            return False
        if candidate.boundary == accepted.boundary:
            return not (
                self.config.allow_cross_label_exact_boundary and candidate.label != accepted.label
            )
        overlap = max(candidate.token_start, accepted.token_start) < min(candidate.token_end, accepted.token_end)
        if not overlap:
            return False
        candidate_contains = candidate.token_start <= accepted.token_start and accepted.token_end <= candidate.token_end
        accepted_contains = accepted.token_start <= candidate.token_start and candidate.token_end <= accepted.token_end
        if candidate_contains or accepted_contains:
            if self.config.allow_nested and candidate.label != accepted.label:
                return False
            return candidate.score + self.config.containment_margin < accepted.score
        return candidate.score <= accepted.score + self.config.overlap_margin


def attach_character_offsets(
    spans: Iterable[DecodedSpan],
    token_offsets: torch.LongTensor,
    sentence_offsets: torch.LongTensor,
) -> list[DecodedSpan]:
    output = []
    for span in spans:
        local_start = int(token_offsets[span.sentence_index, span.token_start, 0])
        local_end = int(token_offsets[span.sentence_index, span.token_end - 1, 1])
        article_start = int(sentence_offsets[span.sentence_index, 0]) + local_start
        article_end = int(sentence_offsets[span.sentence_index, 0]) + local_end
        output.append(
            DecodedSpan(
                span.sentence_index,
                span.token_start,
                span.token_end,
                span.label,
                span.score,
                article_start,
                article_end,
            )
        )
    return output
