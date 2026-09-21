"""Gold-free Trigger extraction and deterministic predicted-Event attachment.

The adapter preserves the audited Trigger boundary decoder and nearest-contained
attachment rule. Trigger evidence remains distinct from the Event proposition and
is never used as a Participant B2 feature or eligibility gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from types import SimpleNamespace
import time
from typing import Any, Mapping

import torch

from .models import TriggerRuntimeModel
from .preprocessing import PreparedArticle, token_to_character_span


@dataclass(frozen=True, slots=True)
class TriggerExtraction:
    """한 기사에서 한 번만 점수화한 문장별 occurrence와 추출 요약."""

    occurrences: tuple[Mapping[str, Any], ...]
    candidate_count: int
    elapsed_seconds: float


class FixedTriggerRuntime:
    """고정 Head의 occurrence 추출과 canonical Event attachment를 분리한다."""

    def __init__(
        self,
        model: TriggerRuntimeModel,
        config: Mapping[str, Any],
        checkpoint_sha: str,
        runtime_config_id: str,
    ) -> None:
        self.model = model
        self.config = config
        self.checkpoint_sha = checkpoint_sha
        self.runtime_config_id = runtime_config_id

    @torch.inference_mode()
    def extract(self, prepared: PreparedArticle, backbone) -> TriggerExtraction:
        """Event inventory와 무관하게 한 기사에서 Trigger Head를 정확히 한 번 소비한다."""

        started = time.perf_counter()
        batch = prepared.batch.to(next(self.model.parameters()).device)
        self.model.eval()
        output = self.model(batch, backbone)
        decoded = _greedy_decode(
            output.start_logits[0],
            output.end_logits[0],
            output.mask[0],
            threshold=float(self.config["threshold"]),
            max_width=int(self.config["max_width_tokens"]),
            output_cap=int(self.config["max_outputs_per_sentence"]),
        )
        pool = []
        for span in decoded.spans:
            sentence = prepared.sentences[span.sentence_index]
            char_start, char_end, text = token_to_character_span(
                prepared.article.content,
                sentence,
                span.token_start,
                span.token_end,
            )
            identity = "|".join(
                (
                    str(prepared.article.article_version_id),
                    self.runtime_config_id,
                    "TRIGGER",
                    str(char_start),
                    str(char_end),
                )
            )
            pool.append(
                {
                    "trigger_prediction_id": "TRG-"
                    + sha256(identity.encode("utf-8")).hexdigest()[:24],
                    "text": text,
                    "char_start": char_start,
                    "char_end": char_end,
                    "token_start": span.token_start,
                    "token_end": span.token_end,
                    "sentence_index": span.sentence_index,
                    "score": float(span.score),
                    "checkpoint_sha": self.checkpoint_sha,
                    "runtime_config_id": self.runtime_config_id,
                    "anchor_contract": "MINIMAL_SEMANTICALLY_SUFFICIENT_SURFACE_EVENT_ANCHOR",
                    "provenance": {
                        "source": "FIXED_CHECKPOINT_PREDICTION",
                        "gold_injected": False,
                        "participant_feature_used": False,
                    },
                }
            )
        return TriggerExtraction(
            tuple(pool), decoded.candidate_count, time.perf_counter() - started,
        )

    def attach(self, events, extraction: TriggerExtraction):
        """이미 추출된 occurrence만 canonical Event에 연결한다; model 호출 없음."""

        started = time.perf_counter()
        pool = extraction.occurrences
        attached = {}
        used = set()
        for event in events:
            eligible = [
                row
                for row in pool
                if row["sentence_index"] == event["sentence_index"]
                and event["char_start"] <= row["char_start"]
                and row["char_end"] <= event["char_end"]
            ]
            selected = min(
                eligible,
                key=lambda row: (
                    abs(row["char_start"] - event["char_start"]),
                    -row["score"],
                    row["char_start"],
                    row["char_end"],
                ),
                default=None,
            )
            if selected is not None:
                selected = {
                    **selected,
                    "source_event_prediction_id": event["prediction_id"],
                    "attachment_decision": "NEAREST_CONTAINED_TO_EVENT_START",
                }
                used.add(selected["trigger_prediction_id"])
            attached[event["prediction_id"]] = selected
        return attached, {
            "stage": "③ 구간 추출부 / ⑤ 방향 관계 판정부",
            "component": "Trigger boundary + deterministic Event attachment",
            "checkpoint_sha": self.checkpoint_sha,
            "input_count": len(events),
            "candidate_count": extraction.candidate_count,
            "output_count": len(pool),
            "attached_count": sum(value is not None for value in attached.values()),
            "unattached_trigger_count": len(pool) - len(used),
            "drop_reason_counts": {
                "NO_CONTAINED_TRIGGER": sum(value is None for value in attached.values())
            },
            "warnings": [],
            "elapsed_seconds": extraction.elapsed_seconds + time.perf_counter() - started,
        }

    def run(self, prepared: PreparedArticle, backbone, events):
        """옛 호출자용 adapter; 내부에서는 extract→attach를 한 번씩 수행한다."""

        return self.attach(events, self.extract(prepared, backbone))


def _greedy_decode(start_logits, end_logits, mask, *, threshold, max_width, output_cap):
    """Exact inference-only form of the audited greedy one-to-one decoder."""

    starts = torch.sigmoid(start_logits).detach()
    ends = torch.sigmoid(end_logits).detach()
    selected = []
    candidate_count = 0
    for sentence_index in range(start_logits.shape[0]):
        start_ids = torch.nonzero(
            (starts[sentence_index, :, 0] >= threshold) & mask[sentence_index],
            as_tuple=False,
        ).flatten().tolist()
        end_ids = torch.nonzero(
            (ends[sentence_index, :, 0] >= threshold) & mask[sentence_index],
            as_tuple=False,
        ).flatten().tolist()
        candidates = []
        for token_start in start_ids:
            for end_inclusive in end_ids:
                width = end_inclusive - token_start + 1
                if 1 <= width <= max_width:
                    score = float(
                        (
                            starts[sentence_index, token_start, 0]
                            * ends[sentence_index, end_inclusive, 0]
                        ).sqrt()
                    )
                    candidates.append(
                        SimpleNamespace(
                            sentence_index=sentence_index,
                            token_start=token_start,
                            token_end=end_inclusive + 1,
                            score=score,
                        )
                    )
        candidate_count += len(candidates)
        used_starts, used_ends = set(), set()
        for candidate in sorted(
            candidates,
            key=lambda item: (-item.score, item.token_start, item.token_end),
        ):
            end_inclusive = candidate.token_end - 1
            if candidate.token_start in used_starts or end_inclusive in used_ends:
                continue
            selected.append(candidate)
            used_starts.add(candidate.token_start)
            used_ends.add(end_inclusive)
            if len(used_starts) >= output_cap:
                break
    return SimpleNamespace(spans=tuple(selected), candidate_count=candidate_count)
