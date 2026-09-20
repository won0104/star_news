"""검증된 train Time value·Event attachment Gold를 fresh head gradient에 연결한다.

Time span extraction은 5번 loss가 소유한다. null normalization은 value loss만
IGNORE하며 textual Time 및 Event attachment 양성은 그대로 남긴다.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch.nn import functional as F

from models.contracts import ArticleBatch, BackboneOutput
from models.v3_pretraining.architecture import SharedForwardLease, V3Core
from models.v3_pretraining.time_heads import TIME_CHARS, TIME_FORMATS, time_format
from runtime.v3_pretraining.source_layout import SpanAlignment
from runtime.v3_pretraining.temporal import TimeMentionEvidence, close_time_occurrences, parse_canonical_time
from runtime.v3_pretraining.temporal_scoring import (EventTimeFeatureLease,
                                                     encode_event_time_features, event_time_geometry)
from training.v3_pretraining.targets import ArticleTargets


@dataclass(frozen=True, slots=True)
class TimeLossResult:
    losses: dict[str, torch.Tensor]
    normalized_supervised: int
    normalization_ignored: int
    attachment_positive: int
    attachment_negative_sampled: int
    attached_null_normalization: int


def gold_time_occurrences(target: ArticleTargets):
    """Gold exact source와 attachment를 소실 없이 scalar occurrence로 검증한다."""
    norms = {row.time_id: row for row in target.time_normalization}
    mentions = tuple(TimeMentionEvidence(row.owner_id, row.alignment.start,
                                         row.alignment.end, row.alignment.text,
                                         norms[row.owner_id].value,
                                         "GOLD" if norms[row.owner_id].value is not None else "UNRESOLVED")
                     for row in target.spans["time_mention"])
    return close_time_occurrences(target.layout.article, mentions,
                                  tuple(target.pairs["event_time"].positive_pairs))


class TimeGoldAdapter:
    def __init__(self, core: V3Core, *, negative_limit: int = 128,
                 chunk_size: int = 128) -> None:
        if any(task in core.unimplemented_tasks for task in ("time_normalization", "event_time")):
            raise ValueError("stage 7 Time heads are not registered")
        if negative_limit <= 0 or chunk_size <= 0:
            raise ValueError("Time pair sample/chunk sizes must be positive")
        self.core = core
        self.negative_limit = negative_limit
        self.chunk_size = chunk_size

    def encode(self, target: ArticleTargets, batch: ArticleBatch,
               backbone: BackboneOutput, shared: SharedForwardLease,
               *, extra_rows: tuple[tuple[str, SpanAlignment, str], ...] = ()) -> EventTimeFeatureLease:
        events = tuple((row.owner_id, row.alignment) for row in target.spans["semantic_proposer"]
                       if row.label == "EVENT")
        times = tuple((row.owner_id, row.alignment) for row in target.spans["time_mention"])
        return encode_event_time_features(layout=target.layout, batch=batch, backbone=backbone,
                                          shared=shared, core=self.core, events=events, times=times,
                                          extra_rows=extra_rows, source_mode="GOLD_ORACLE")

    def loss(self, target: ArticleTargets, lease: EventTimeFeatureLease) -> TimeLossResult:
        if (lease.closed or lease.source_mode != "GOLD_ORACLE" or
                lease.article_version_id != target.article_version_id or
                lease.content_sha256 != target.content_sha256):
            raise ValueError("Time Gold loss needs a live matching oracle feature lease")
        if lease.event_states is None or lease.time_states is None or lease.document_state is None:
            raise RuntimeError("Time feature lease has lost its tensor owner")
        pair_universe = target.pairs["event_time"]
        if lease.event_ids != pair_universe.left_ids or lease.time_ids != pair_universe.right_ids:
            raise ValueError("Time feature ID order differs from Gold eligible universe")
        gold_time_occurrences(target)
        device = lease.document_state.device
        zero = lease.document_state.sum() * 0
        supervised = [(position, row.value, parse_canonical_time(row.value))
                      for position, row in enumerate(target.time_normalization) if row.value is not None]
        if tuple(row.time_id for row in target.time_normalization) != lease.time_ids:
            raise ValueError("Time normalization IDs differ from source features")
        if supervised:
            indices = torch.tensor([position for position, _, _ in supervised],
                                   dtype=torch.long, device=device)
            max_length = max(len(value) for _, value, _ in supervised)
            format_logits, char_logits = self.core.task_modules["time_normalization"](
                lease.time_states.index_select(0, indices), length=max_length)
            format_labels = torch.tensor([TIME_FORMATS.index(time_format(parsed.kind, parsed.granularity))
                                          for _, _, parsed in supervised], dtype=torch.long, device=device)
            character_labels = torch.full((len(supervised), max_length), -100,
                                          dtype=torch.long, device=device)
            for index, (_, value, _) in enumerate(supervised):
                character_labels[index, :len(value)] = torch.tensor([TIME_CHARS.index(char) for char in value],
                                                                     dtype=torch.long, device=device)
            normalization_loss = (F.cross_entropy(format_logits, format_labels) +
                                  F.cross_entropy(char_logits.flatten(0, 1),
                                                  character_labels.flatten()))
        else:
            normalization_loss = zero
        sample = sorted(pair_universe.positive_pairs) + [
            (row.left_id, row.right_id) for row in pair_universe.sample_negatives(
                limit=self.negative_limit, seed=self.core.config.seed,
                content_sha256=target.content_sha256)]
        event_index = {eid: index for index, eid in enumerate(lease.event_ids)}
        time_index = {tid: index for index, tid in enumerate(lease.time_ids)}
        pair_losses = []
        for start in range(0, len(sample), self.chunk_size):
            chunk = sample[start:start + self.chunk_size]
            coordinates = [(event_index[eid], time_index[tid]) for eid, tid in chunk]
            indices = torch.tensor(coordinates, dtype=torch.long, device=device)
            labels = torch.tensor([float(pair in pair_universe.positive_pairs) for pair in chunk],
                                  dtype=lease.document_state.dtype, device=device)
            logits = self.core.task_modules["event_time"](
                lease.event_states, lease.time_states, indices, lease.document_state,
                event_time_geometry(lease, coordinates, content_length=len(target.layout.article.content)))
            pair_losses.append(F.binary_cross_entropy_with_logits(logits, labels, reduction="sum"))
        attachment_loss = sum(pair_losses) / len(sample) if sample else zero
        losses = {"time_normalization": normalization_loss, "event_time": attachment_loss}
        if any(not torch.isfinite(value) for value in losses.values()):
            raise ValueError("Time loss is non-finite")
        null_ids = {row.time_id for row in target.time_normalization if row.value is None}
        return TimeLossResult(losses, len(supervised), len(null_ids),
                              len(pair_universe.positive_pairs),
                              len(sample) - len(pair_universe.positive_pairs),
                              sum(tid in null_ids for _, tid in pair_universe.positive_pairs))
