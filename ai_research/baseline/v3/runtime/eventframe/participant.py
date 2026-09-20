"""Fixed predicted Event → B2 ACTOR/TARGET/PLACE raw evidence path."""

from __future__ import annotations

import math
import time
from typing import Any, Mapping

import torch

from .models import PARTICIPANT_ROLES, ParticipantB2RuntimeModel
from .preprocessing import PreparedArticle, token_to_character_span


def close_duplicate_fillers(rows, *, diagnostic_sink=None):
    """동일 Event/role/source 좌표의 명백한 B2 중복만 닫는다."""
    selected = {}
    absorbed = 0
    for row in rows:
        key = (
            row["source_event_prediction_id"], row["role"],
            int(row["char_start"]), int(row["char_end"]),
        )
        previous = selected.get(key)
        if previous is None:
            selected[key] = row
            continue
        absorbed += 1
        winner = max((previous, row), key=lambda item: (
            float(item["score"]), -int(item["token_start"]),
            -int(item["token_end"]), str(item["text"]),
        ))
        selected[key] = winner
        if diagnostic_sink is not None:
            diagnostic_sink.record("decision", {
                "component": "participant_b2_boundary",
                "source_event_prediction_id": key[0], "role": key[1],
                "char_start": key[2], "char_end": key[3],
                "decision": "ABSORB_EXACT_FILLER_COORDINATE",
                "absorbed_score": float((row if winner is previous else previous)["score"]),
                "primary_score": float(winner["score"]),
            })
    return sorted(selected.values(), key=lambda item: (
        int(item["char_start"]), int(item["char_end"]),
        int(item["token_start"]), int(item["token_end"]),
    )), absorbed


class FixedParticipantB2Runtime:
    def __init__(self, model: ParticipantB2RuntimeModel, config: Mapping[str, Any], checkpoint_sha: str):
        self.model = model
        self.config = config
        self.checkpoint_sha = checkpoint_sha

    @torch.inference_mode()
    def run(self, prepared: PreparedArticle, backbone, events, *,
            canonical_only=False, diagnostic_sink=None):
        started = time.perf_counter()
        event_ids = [str(event["prediction_id"]) for event in events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("Participant B2 cannot score a canonical Event twice")
        if canonical_only and any(
            event.get("kind") != "EVENT"
            or event.get("article_id") != prepared.article.article_id
            for event in events
        ):
            raise ValueError("Participant B2 requires canonical EventMention projections")
        runtime_events = [
            {
                "event_id": event["prediction_id"],
                "aligned": [
                    event["sentence_index"],
                    event["token_start"],
                    event["token_end"],
                ],
            }
            for event in events
        ]
        if not runtime_events:
            return {}, {
                "stage": "③ 구간 추출부",
                "component": "Event-conditioned Participant B2",
                "checkpoint_sha": self.checkpoint_sha,
                "input_count": 0,
                "candidate_count": 0,
                "output_count": 0,
                "drop_reason_counts": {},
                "warnings": [],
                "elapsed_seconds": 0.0,
            }
        batch = prepared.batch.to(next(self.model.parameters()).device)
        self.model.eval()
        logits, _ = self.model.forward_events(batch, backbone, runtime_events)
        probabilities = logits.sigmoid()
        threshold = float(self.config["threshold"])
        max_width = int(self.config["max_width_tokens"])
        output: dict[str, dict[str, list[dict[str, Any]]]] = {}
        width_rejected = 0
        duplicate_absorbed = 0
        for event_index, event in enumerate(runtime_events):
            sentence_index = event["aligned"][0]
            sentence = prepared.sentences[sentence_index]
            valid = set(sentence["source_token_indices"])
            role_output = {role: [] for role in PARTICIPANT_ROLES}
            for role_index, role in enumerate(PARTICIPANT_ROLES):
                starts = [
                    position
                    for position in sentence["valid_start_token_indices"]
                    if float(probabilities[event_index, position, role_index, 0]) >= threshold
                ]
                ends = [
                    position + 1
                    for position in sentence["valid_end_token_indices"]
                    if float(probabilities[event_index, position, role_index, 1]) >= threshold
                ]
                for token_start in starts:
                    for token_end in ends:
                        if token_start >= token_end:
                            continue
                        if token_end - token_start > max_width or not all(
                            position in valid for position in range(token_start, token_end)
                        ):
                            width_rejected += 1
                            continue
                        char_start, char_end, text = token_to_character_span(
                            prepared.article.content, sentence, token_start, token_end
                        )
                        score = math.sqrt(
                            float(probabilities[event_index, token_start, role_index, 0])
                            * float(probabilities[event_index, token_end - 1, role_index, 1])
                        )
                        role_output[role].append(
                            {
                                "role": role,
                                "text": text,
                                "char_start": char_start,
                                "char_end": char_end,
                                "token_start": token_start,
                                "token_end": token_end,
                                "score": score,
                                "source": "B2",
                                "resolution_status": "NOT_RESOLVED",
                                "source_event_prediction_id": event["event_id"],
                                "b2_checkpoint_sha": self.checkpoint_sha,
                                "decode_decision": "INDEPENDENT_START_END_CARTESIAN_ACCEPTED",
                                "provenance": {
                                    "source": "EXPERIMENTAL_PREDICTION",
                                    "entity_prerequisite_used": False,
                                    "auxiliary_signal_used": False,
                                },
                            }
                        )
            if canonical_only:
                for role in PARTICIPANT_ROLES:
                    role_output[role], absorbed = close_duplicate_fillers(
                        role_output[role], diagnostic_sink=diagnostic_sink,
                    )
                    duplicate_absorbed += absorbed
            output[event["event_id"]] = role_output
        count = sum(len(items) for roles in output.values() for items in roles.values())
        return output, {
            "stage": "③ 구간 추출부",
            "component": "Event-conditioned Participant B2",
            "checkpoint_sha": self.checkpoint_sha,
            "input_count": len(runtime_events),
            "candidate_count": int(probabilities.shape[0] * probabilities.shape[1] * 3 * 2),
            "output_count": count,
            "drop_reason_counts": {
                "WIDTH_OR_NONCONTIGUOUS": width_rejected,
                "ABSORBED_EXACT_FILLER_COORDINATE": duplicate_absorbed,
            },
            "warnings": [],
            "elapsed_seconds": time.perf_counter() - started,
        }
