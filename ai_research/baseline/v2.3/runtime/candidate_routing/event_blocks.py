"""Audit-only Event pair preparation and bounded overlapping block selection.

The module shares the v2.2 policy-feature primitives, but no production call
path uses its selected pairs. A missing fine pair remains unevaluated. Blocks
limit posting visits, per-Event membership, block size and unique pair count;
they never expand a connected component into a Cartesian pair universe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from itertools import combinations
from hashlib import sha256
import json
from pathlib import Path

from runtime.eventframe.event_identity import (
    ROLES, _literal_index, _max_literal_jaccard, _ngrams, _norm,
    _normalized_times, _score, _sets_for_frame,
)


@dataclass(frozen=True, slots=True)
class EventBlockPolicy:
    policy_id: str
    block_size: int
    membership_per_event: int
    visit_per_event: int
    fine_pair_per_article: int
    posting_cap: int
    global_reserve: int

    @classmethod
    def from_config(cls, path: str | Path) -> "EventBlockPolicy":
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if (value.get("schema_version") != "articlelocal-bcr-event-block-shadow-v1"
            or value.get("mode") != "SHADOW_ONLY"
            or value.get("published") is not False):
            raise ValueError("Event block policy must remain shadow-only")
        policy = cls(**value["policy"])
        policy.validate()
        return policy

    def validate(self) -> None:
        if (not self.policy_id or not 2 <= self.block_size <= 32
            or not 1 <= self.membership_per_event <= 8
            or not 1 <= self.visit_per_event <= 256
            or not 1 <= self.fine_pair_per_article <= 10000
            or not 1 <= self.posting_cap <= self.visit_per_event
            or not 0 <= self.global_reserve < self.block_size):
            raise ValueError("Event block budget is invalid/unbounded")


@dataclass(frozen=True, slots=True)
class EventSignals:
    event_id: str
    sentence_index: int
    text: str
    acceptance_score: float
    trigger_text: str
    roles: tuple[frozenset, frozenset, frozenset]
    role_literals: tuple[tuple, tuple, tuple]
    normalized_times: frozenset
    raw_time_ids: frozenset
    availability: frozenset[str]
    text_norm: str = field(init=False)
    text_grams: frozenset[str] = field(init=False)
    trigger_norm: str = field(init=False)
    trigger_grams: frozenset[str] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "text_norm", _norm(self.text))
        object.__setattr__(self, "text_grams", frozenset(_ngrams(self.text)))
        object.__setattr__(self, "trigger_norm", _norm(self.trigger_text))
        object.__setattr__(self, "trigger_grams",
                           frozenset(_ngrams(self.trigger_text)))


def prepare_event_signals(frames, time_expressions, *,
                          identity_handoff=None, role_handoff=None
                          ) -> tuple[EventSignals, ...]:
    """Compute each Event's exact scalar v2.2 pair-feature inputs once."""
    time_by_id = {str(row["prediction_id"]): row for row in time_expressions}
    signals = []
    for frame in frames:
        event = frame["event"]
        event_id = str(event["prediction_id"])
        resolved = _sets_for_frame(frame, identity_handoff)
        role_literals = []
        for role in ROLES:
            if role_handoff is not None:
                aggregate = role_handoff.aggregate(event_id, role)
                texts = aggregate.literal_texts if aggregate is not None else ()
            else:
                texts = tuple(row.get("text", "") for row in
                              frame.get("participants", {}).get(role, {}).get("items", ()))
            role_literals.append(_literal_index(texts))
        trigger = frame.get("trigger", {}).get("item")
        time_ids = frozenset(str(row["target_time_prediction_id"])
                             for row in frame.get("time", {}).get("items", ())
                             if row.get("target_time_prediction_id"))
        signals.append(EventSignals(
            event_id, int(event["sentence_index"]), str(event["text"]),
            _score(event), str(trigger.get("text", "")) if trigger else "",
            tuple(frozenset(resolved[role]) for role in ROLES),
            tuple(role_literals), frozenset(_normalized_times(frame, time_by_id)),
            time_ids,
            frozenset(("event_text", "sentence", "trigger", "resolved_entity",
                       "time", "role_literal", "acceptance_score")),
        ))
    ids = [row.event_id for row in signals]
    if len(ids) != len(set(ids)):
        raise ValueError("Event signals need unique canonical mention IDs")
    return tuple(signals)


def prepared_pair_policy_features(left: EventSignals, right: EventSignals
                                  ) -> list[float]:
    """Exact policy-feature parity on complete handoff inputs; no fine score."""
    a, b = left.text_grams, right.text_grams
    x, y = left.trigger_grams, right.trigger_grams
    same_time = bool(left.normalized_times & right.normalized_times)
    conflict = bool(left.normalized_times and right.normalized_times and not same_time)
    normalized_left, normalized_right = left.text_norm, right.text_norm
    return [
        len(a & b) / len(a | b) if a or b else 0.0,
        float(normalized_left in normalized_right or normalized_right in normalized_left),
        len(x & y) / len(x | y) if x or y else 0.0,
        *[
            (1.0 if left.roles[index] & right.roles[index]
             else _max_literal_jaccard(left.role_literals[index],
                                       right.role_literals[index]))
            for index in range(len(ROLES))
        ],
        float(conflict),
        float(same_time or bool(left.raw_time_ids & right.raw_time_ids)),
        min(abs(left.sentence_index - right.sentence_index), 32) / 32.0,
        min(left.acceptance_score, right.acceptance_score),
        float(bool(left.trigger_text and right.trigger_text)),
        float(bool(left.raw_time_ids and right.raw_time_ids)),
    ]


def saved_event_signals(sidecar, content: str, sentence_spans
                        ) -> tuple[EventSignals, ...]:
    """Use current A+B mention IDs/text only; unavailable handoffs stay unknown."""
    rows = []
    for item in sidecar["semantic"]:
        if item["kind"] != "EVENT":
            continue
        start, end = int(item["char_start"]), int(item["char_end"])
        sentence = next((index for index, row in enumerate(sentence_spans)
                         if row.start <= start and end <= row.end), None)
        if sentence is None:
            raise ValueError("saved Event span is not in runtime sentence segmentation")
        rows.append(EventSignals(
            str(item["prediction_id"]), sentence, content[start:end], 0.0, "",
            (frozenset(),) * 3, (_literal_index(()),) * 3,
            frozenset(), frozenset(), frozenset(("event_text", "sentence")),
        ))
    if len({row.event_id for row in rows}) != len(rows):
        raise ValueError("saved Event mention ID duplicated")
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class BlockRoute:
    blocks: tuple[tuple[str, ...], ...]
    pairs: frozenset[tuple[str, str]]
    census: dict


def route_event_blocks(signals: tuple[EventSignals, ...],
                       policy: EventBlockPolicy) -> BlockRoute:
    """Finite OR-posting route; no all-pair materialization or global ALL."""
    policy.validate()
    by_id = {row.event_id: row for row in signals}
    if len(by_id) != len(signals):
        raise ValueError("Event signals contain duplicate IDs")
    ordered = tuple(sorted(by_id))
    postings: dict[tuple[str, object], list[str]] = defaultdict(list)
    for event_id in ordered:
        row = by_id[event_id]
        postings[("sentence", row.sentence_index)].append(event_id)
        if "trigger" in row.availability and row.trigger_text:
            postings[("trigger", row.trigger_norm)].append(event_id)
        if "resolved_entity" in row.availability:
            for entity_id in sorted(set().union(*row.roles)):
                postings[("entity", entity_id)].append(event_id)
        if "time" in row.availability:
            for key in sorted(row.normalized_times, key=str):
                postings[("time", key)].append(event_id)
            for key in sorted(row.raw_time_ids):
                postings[("time_occurrence", key)].append(event_id)
        for gram in sorted(row.text_grams):
            postings[("text_gram", gram)].append(event_id)
    for values in postings.values():
        values.sort()
    members = defaultdict(int)
    blocks = []
    pairs: set[tuple[str, str]] = set()
    visits = cheap_ranked = duplicate_pairs = posting_truncated = 0
    budget_skipped = 0
    max_query_visit = 0
    grounds_seen = defaultdict(int)
    for center in ordered:
        row = by_id[center]
        if members[center] >= policy.membership_per_event:
            budget_skipped += 1
            continue
        keys = [("sentence", index) for index in range(
            row.sentence_index - 3, row.sentence_index + 4)]
        if "trigger" in row.availability and row.trigger_text:
            keys.append(("trigger", row.trigger_norm))
        if "resolved_entity" in row.availability:
            keys.extend(("entity", key) for key in sorted(set().union(*row.roles)))
        if "time" in row.availability:
            keys.extend(("time", key)
                        for key in sorted(row.normalized_times, key=str))
            keys.extend(("time_occurrence", key)
                        for key in sorted(row.raw_time_ids))
        keys.extend(("text_gram", gram) for gram in sorted(row.text_grams))
        found: dict[str, set[str]] = defaultdict(set)
        query_visits = 0
        for key in keys:
            posting = postings.get(key, ())
            if len(posting) > policy.posting_cap:
                posting_truncated += 1
            for candidate in posting[:policy.posting_cap]:
                if candidate == center:
                    continue
                if query_visits >= policy.visit_per_event:
                    budget_skipped += 1
                    break
                query_visits += 1
                visits += 1
                found[candidate].add(key[0])
            if query_visits >= policy.visit_per_event:
                break
        max_query_visit = max(max_query_visit, query_visits)
        cheap_ranked += len(found)
        for grounds in found.values():
            for ground in grounds:
                grounds_seen[ground] += 1
        local = [candidate for candidate in found
                 if "sentence" in found[candidate]]
        global_candidates = [candidate for candidate in found
                             if "sentence" not in found[candidate]]

        def rank(candidate: str):
            target = by_id[candidate]
            shared = len(row.text_grams & target.text_grams)
            return (-len(found[candidate]), -shared,
                    abs(row.sentence_index - target.sentence_index), candidate)

        local.sort(key=rank)
        global_candidates.sort(key=rank)
        selected = global_candidates[:policy.global_reserve]
        selected += [candidate for candidate in local + global_candidates
                     if candidate not in selected]
        block = [center]
        for candidate in selected:
            if len(block) >= policy.block_size:
                break
            if members[candidate] >= policy.membership_per_event:
                budget_skipped += 1
                continue
            prospective = {tuple(sorted(pair)) for pair in
                           combinations((*block, candidate), 2)}
            if len(pairs | prospective) > policy.fine_pair_per_article:
                budget_skipped += 1
                continue
            block.append(candidate)
        if len(block) < 2:
            continue
        block = sorted(block)
        for event_id in block:
            members[event_id] += 1
        for pair in combinations(block, 2):
            if pair in pairs:
                duplicate_pairs += 1
            pairs.add(pair)
        blocks.append(tuple(block))
    census = {
        "policy_id": policy.policy_id,
        "event_count": len(signals),
        "full_possible_pair_count": len(signals) * (len(signals) - 1) // 2,
        "blocked_unique_pair_count": len(pairs),
        "block_count": len(blocks),
        "max_block_size": max(map(len, blocks), default=0),
        "max_event_membership": max(members.values(), default=0),
        "retrieval_posting_visits": visits,
        "max_query_posting_visits": max_query_visit,
        "cheap_ranked_unique_per_query_sum": cheap_ranked,
        "duplicate_block_pair_encounters_deduped": duplicate_pairs,
        "posting_truncation_count": posting_truncated,
        "skipped_by_budget_count": budget_skipped,
        "retrieval_grounds_seen": dict(sorted(grounds_seen.items())),
        "missing_pair_semantics": "NOT_EVALUATED",
        "production_pair_deleted": False,
    }
    if (census["max_block_size"] > policy.block_size
        or census["max_event_membership"] > policy.membership_per_event
        or census["max_query_posting_visits"] > policy.visit_per_event
        or len(pairs) > policy.fine_pair_per_article):
        raise AssertionError("Event block budget accounting failed")
    return BlockRoute(tuple(blocks), frozenset(pairs), census)
