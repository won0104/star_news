"""Gold-free scalar candidate routing for final Statement/EventCluster relations.

Routes only choose fine-scorer inputs. Missing pairs are NOT_EVALUATED_ROUTING;
neither a route key nor its cheap score is a relation decision.
"""

from __future__ import annotations

from collections import defaultdict
from bisect import bisect_left
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping, Sequence

from runtime.v3_pretraining.event_identity import LocalEventState
from runtime.v3_pretraining.source_layout import RawArticle


ABOUT_POLICY_ID = "ABOUT_MULTI_CHANNEL_ROUTING_V1"
CAUSES_POLICY_ID = "CAUSES_MULTI_CHANNEL_ROUTING_V1"
ASSERTED_BY_POLICY_ID = "ASSERTED_BY_OPTION_ROUTING_V1"


def identity_policy_sha256(kind: str, pair_routing_sha256: str) -> str:
    """Bind a pair policy to the current final identity closure implementation."""
    if kind not in ("ENTITY", "EVENT") or len(pair_routing_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in pair_routing_sha256):
        raise ValueError("identity policy needs a known closure and pair policy SHA")
    closure = Path(__file__).with_name(
        "entity_identity.py" if kind == "ENTITY" else "event_identity.py")
    return sha256(json.dumps({"kind": kind, "pair_routing_sha256": pair_routing_sha256,
                              "closure_code_sha256": sha256(closure.read_bytes()).hexdigest()},
                             sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RelationRoutingPolicy:
    lane: str
    per_query_budget: int
    posting_visit_budget: int

    def __post_init__(self) -> None:
        if (self.lane not in ("ABOUT", "CAUSES") or
                type(self.per_query_budget) is not int or
                type(self.posting_visit_budget) is not int or min(
                self.per_query_budget, self.posting_visit_budget) < 1):
            raise ValueError("relation routing needs a known lane and positive bounds")

    @property
    def policy_id(self) -> str:
        return ABOUT_POLICY_ID if self.lane == "ABOUT" else CAUSES_POLICY_ID

    @property
    def sha256(self) -> str:
        return sha256(json.dumps({"id": self.policy_id, "k": self.per_query_budget,
                                  "visits": self.posting_visit_budget},
                                 sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class PredictedRelationRoutingArtifact:
    """The future Phase 6 gate; an oracle curve cannot instantiate this loader."""

    about: RelationRoutingPolicy
    causes: RelationRoutingPolicy
    full_score_limit: int
    checkpoint_sha256: str
    source_policy_sha256: str
    source_acceptance_sha256: str
    entity_identity_policy_sha256: str
    event_identity_policy_sha256: str
    structural_candidate_source: str
    structural_candidate_sha256: str
    predicted_validation_report_sha256: str
    artifact_sha256: str

    @classmethod
    def load_predicted_validated(
            cls, path: str | Path, *, checkpoint_sha256: str,
            source_policy_sha256: str, source_acceptance_sha256: str,
            entity_identity_policy_sha256: str,
            event_identity_policy_sha256: str) -> "PredictedRelationRoutingArtifact":
        data = Path(path).read_bytes()
        row = json.loads(data)
        digest = lambda value: isinstance(value, str) and len(value) == 64 and all(
            char in "0123456789abcdef" for char in value)
        required = {"schema_version", "source_profile", "selection_status",
                    "policies", "full_score_limit", "checkpoint_sha256",
                    "source_policy_sha256", "source_acceptance_sha256",
                    "entity_identity_policy_sha256", "event_identity_policy_sha256",
                    "structural_candidate_source", "structural_candidate_sha256",
                    "predicted_validation_report_sha256"}
        if (not isinstance(row, dict) or set(row) != required or
                row["schema_version"] != "v23-final-relation-routing-v2" or
                row["source_profile"] != "V23_BASELINE" or
                row["selection_status"] != "PREDICTED_VALIDATED" or
                row["checkpoint_sha256"] != checkpoint_sha256 or
                row["source_policy_sha256"] != source_policy_sha256 or
                row["source_acceptance_sha256"] != source_acceptance_sha256 or
                row["entity_identity_policy_sha256"] != entity_identity_policy_sha256 or
                row["event_identity_policy_sha256"] != event_identity_policy_sha256 or
                row["structural_candidate_source"] !=
                "ORACLE_UPSTREAM_STATE_UPPER_BOUND" or
                type(row["full_score_limit"]) is not int or
                row["full_score_limit"] < 1 or
                any(not digest(row[key]) for key in (
                    "structural_candidate_sha256", "predicted_validation_report_sha256")) or
                not isinstance(row["policies"], dict) or
                set(row["policies"]) != {"ABOUT", "CAUSES"}):
            raise ValueError("V23 relation routing requires predicted-validated binding")
        policies = {}
        for lane in ("ABOUT", "CAUSES"):
            config = row["policies"][lane]
            if (not isinstance(config, dict) or
                    set(config) != {"per_query_budget", "posting_visit_budget",
                                    "policy_sha256"}):
                raise ValueError("relation routing policy schema differs")
            policy = RelationRoutingPolicy(lane, config["per_query_budget"],
                                           config["posting_visit_budget"])
            if config["policy_sha256"] != policy.sha256:
                raise ValueError("relation routing policy SHA differs")
            policies[lane] = policy
        return cls(policies["ABOUT"], policies["CAUSES"], row["full_score_limit"],
                   checkpoint_sha256, source_policy_sha256,
                   source_acceptance_sha256, entity_identity_policy_sha256,
                   event_identity_policy_sha256,
                   row["structural_candidate_source"],
                   row["structural_candidate_sha256"],
                   row["predicted_validation_report_sha256"], sha256(data).hexdigest())


@dataclass(frozen=True, slots=True)
class RelationRoute:
    lane: str
    pairs: tuple[tuple[str, str], ...]
    records: tuple[dict[str, object], ...]
    eligible_count: int
    visited_postings: int
    budget_exhausted_queries: int
    policy_id: str
    policy_sha256: str
    source_inventory_lineage: str

    def routing_status(self, pair: tuple[str, str]) -> str:
        return ("ROUTING_SELECTED" if pair in self.pairs else
                "NOT_EVALUATED_ROUTING")


@dataclass(frozen=True, slots=True)
class _EventKeys:
    event_id: str
    spans: tuple[tuple[int, int], ...]
    sentences: frozenset[int]
    anchor: int
    entity_ids: frozenset[str]
    time_keys: frozenset[str]
    trigger_surfaces: frozenset[str]


def _sentences(spans: Sequence[tuple[int, int]],
               sentence_spans: Sequence[tuple[int, int]]) -> frozenset[int]:
    found = frozenset(index for start, end in spans
                      for index, (left, right) in enumerate(sentence_spans)
                      if max(start, left) < min(end, right))
    if not found:
        raise ValueError("relation endpoint has no source sentence")
    return found


def _event_keys(events: Sequence[LocalEventState],
                sentence_spans: Sequence[tuple[int, int]],
                time_values: Mapping[str, str | None]) -> tuple[_EventKeys, ...]:
    rows = []
    for event in events:
        spans = tuple((row.start, row.end) for row in event.member_groundings) or (
            (event.start, event.end),)
        time_keys = {"ID:" + row.time_id for row in event.times}
        time_keys.update("VALUE:" + value for row in event.times
                         if (value := time_values.get(row.time_id)) is not None)
        rows.append(_EventKeys(
            event.local_id, spans, _sentences(spans, sentence_spans),
            min(start for start, _ in spans),
            frozenset(row.entity_id for row in event.roles if row.entity_id),
            frozenset(time_keys),
            frozenset(text.casefold() for _, _, text, _ in event.triggers if text)))
    if len({row.event_id for row in rows}) != len(rows):
        raise ValueError("relation EventCluster IDs must be unique")
    return tuple(rows)


def _lineage(article: RawArticle, statements: Mapping[str, tuple[int, int]],
             events: Sequence[_EventKeys], *,
             entity_spans: Mapping[str, Sequence[tuple[int, int]]] | None = None,
             assertor_entities: Mapping[str, str] | None = None) -> str:
    payload = {"article_version_id": article.article_version_id,
               "content_sha256": article.content_sha256,
               "statements": sorted((key, *span) for key, span in statements.items()),
               "events": sorted((row.event_id, row.spans,
                                 sorted(row.entity_ids), sorted(row.time_keys),
                                 sorted(row.trigger_surfaces)) for row in events),
               "entity_spans": sorted((key, sorted(spans))
                                      for key, spans in (entity_spans or {}).items()),
               "assertor_entities": sorted((assertor_entities or {}).items())}
    return sha256(json.dumps(payload, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def _record(*, lane: str, left: str, right: str, keys: Sequence[str],
            score: float, rank: int, policy_id: str, policy_sha256: str,
            lineage: str) -> dict[str, object]:
    return {"query_id": left, "candidate_id": right, "routing_lane": lane,
            "matched_route_keys": list(sorted(keys)), "cheap_score": score,
            "candidate_rank": rank, "routing_status": "ROUTING_SELECTED",
            "fine_status": "NOT_RUN", "policy_id": policy_id,
            "policy_sha256": policy_sha256,
            "source_inventory_lineage": lineage}


def full_relation_route(*, lane: str, article: RawArticle,
                        statements: Mapping[str, tuple[int, int]],
                        events: Sequence[LocalEventState],
                        sentence_spans: Sequence[tuple[int, int]],
                        shadow: bool = False) -> RelationRoute:
    """Explicit small-universe scoring or audit-only all-pair shadow."""
    if lane not in ("ABOUT", "CAUSES"):
        raise ValueError("unknown relation lane")
    keyed = _event_keys(events, sentence_spans, {})
    lineage = _lineage(article, statements, keyed)
    pairs = (tuple((sid, row.event_id) for sid in statements for row in keyed)
             if lane == "ABOUT" else tuple((a.event_id, b.event_id)
                                            for a in keyed for b in keyed if a != b))
    policy_id = ((lane + "_ALL_PAIR_SHADOW_REFERENCE") if shadow else
                 lane + "_FULL_SMALL_UNIVERSE")
    policy_sha = sha256(policy_id.encode()).hexdigest()
    ranks: dict[str, int] = defaultdict(int)
    records = []
    for left, right in pairs:
        ranks[left] += 1
        records.append(_record(lane=lane, left=left, right=right,
                               keys=(policy_id,), score=0.0, rank=ranks[left],
                               policy_id=policy_id, policy_sha256=policy_sha,
                               lineage=lineage))
    return RelationRoute(lane, pairs, tuple(records), len(pairs), 0, 0,
                         policy_id, policy_sha, lineage)


def route_about(*, article: RawArticle,
                statements: Mapping[str, tuple[int, int]],
                events: Sequence[LocalEventState],
                sentence_spans: Sequence[tuple[int, int]],
                entity_spans: Mapping[str, Sequence[tuple[int, int]]],
                assertor_entities: Mapping[str, str] = {},
                policy: RelationRoutingPolicy) -> RelationRoute:
    """Union containment, local, Entity, lexical and sparse fallback postings."""
    if policy.lane != "ABOUT":
        raise ValueError("ABOUT requires its own lane policy")
    keyed = _event_keys(events, sentence_spans, {})
    lineage = _lineage(article, statements, keyed, entity_spans=entity_spans,
                       assertor_entities=assertor_entities)
    by_id = {row.event_id: row for row in keyed}
    sentence_index: dict[int, set[str]] = defaultdict(set)
    entity_index: dict[str, set[str]] = defaultdict(set)
    trigger_index: dict[str, set[str]] = defaultdict(set)
    for row in keyed:
        for sentence in row.sentences:
            sentence_index[sentence].add(row.event_id)
        for entity_id in row.entity_ids:
            entity_index[entity_id].add(row.event_id)
        for trigger in row.trigger_surfaces:
            trigger_index[trigger[:2]].add(row.event_id)
    anchors = sorted(keyed, key=lambda row: (row.anchor, row.event_id))
    anchor_positions = [row.anchor for row in anchors]
    selected = []
    records = []
    visited = exhausted = 0
    for sid, (start, end) in statements.items():
        if not 0 <= start < end <= len(article.content):
            raise ValueError("Statement source geometry differs from article")
        sentences = _sentences(((start, end),), sentence_spans)
        statement_entities = {eid for eid, spans in entity_spans.items()
                              if any(max(start, a) < min(end, b) for a, b in spans)}
        if sid in assertor_entities:
            statement_entities.add(assertor_entities[sid])
        cues: dict[str, set[str]] = defaultdict(set)
        overlap_candidates: set[str] = set()
        for sentence in sentences:
            overlap_candidates.update(sentence_index.get(sentence, ()))
            for offset in range(-2, 3):
                posting = sorted(sentence_index.get(sentence + offset, ()))[:policy.posting_visit_budget]
                visited += len(posting)
                for eid in posting:
                    cues[eid].add("LOCAL:" + str(abs(offset)))
        for entity_id in statement_entities:
            posting = sorted(entity_index.get(entity_id, ()))[:policy.posting_visit_budget]
            visited += len(posting)
            for eid in posting:
                cues[eid].add("ENTITY:" + entity_id)
        text = article.content[start:end].casefold()
        for eid in sorted(overlap_candidates)[:policy.posting_visit_budget]:
            visited += 1
            row = by_id[eid]
            if any(max(start, a) < min(end, b) for a, b in row.spans):
                cues[eid].add("CONTAINMENT:OVERLAP")
            if any(start <= a and b <= end for a, b in row.spans):
                cues[eid].add("CONTAINMENT:INSIDE")
        lexical_candidates = set()
        for key in set(text) | {text[i:i + 2] for i in range(len(text) - 1)}:
            lexical_candidates.update(trigger_index.get(key, ()))
        for eid in sorted(lexical_candidates)[:policy.posting_visit_budget]:
            visited += 1
            row = by_id[eid]
            if any(trigger in text for trigger in row.trigger_surfaces):
                cues[eid].add("LEXICAL:EXACT_TRIGGER_SUBSTRING_V1")
        if len(cues) < min(2, len(keyed)):
            position = bisect_left(anchor_positions, start)
            nearby = [anchors[i] for i in (position - 1, position)
                      if 0 <= i < len(anchors)]
            nearest = min(nearby, key=lambda row: (abs(row.anchor - start),
                                                   row.event_id)) if nearby else None
            for row in (*((nearest,) if nearest else ()), *(anchors[i] for i in
                         sorted({0, len(anchors) // 2, len(anchors) - 1}) if anchors)):
                cues[row.event_id].add("FALLBACK:SOURCE_ANCHOR")
        ranked = []
        for eid, keys in cues.items():
            row = by_id[eid]
            distance = min(abs(a - start) for a, _ in row.spans)
            sentence_distance = min(abs(a - b) for a in sentences for b in row.sentences)
            score = (4 * any(key.startswith("CONTAINMENT") for key in keys) +
                     2 * sum(key.startswith("ENTITY:") for key in keys) +
                     2 * any(key.startswith("LEXICAL") for key in keys) +
                     1 / (1 + sentence_distance) + 1 / (1 + distance))
            ranked.append((-score, eid, keys))
        ranked.sort()
        exhausted += len(ranked) > policy.per_query_budget or len(ranked) > policy.posting_visit_budget
        for rank, (negative_score, eid, keys) in enumerate(
                ranked[:min(policy.per_query_budget, policy.posting_visit_budget)], 1):
            selected.append((sid, eid))
            records.append(_record(lane="ABOUT", left=sid, right=eid, keys=keys,
                                   score=-negative_score, rank=rank,
                                   policy_id=policy.policy_id,
                                   policy_sha256=policy.sha256, lineage=lineage))
    return RelationRoute("ABOUT", tuple(selected), tuple(records),
                         len(statements) * len(keyed), visited, exhausted,
                         policy.policy_id, policy.sha256, lineage)


def route_causes(*, article: RawArticle, events: Sequence[LocalEventState],
                 sentence_spans: Sequence[tuple[int, int]],
                 time_values: Mapping[str, str | None] = {},
                 policy: RelationRoutingPolicy) -> RelationRoute:
    """Select unordered causal candidates, then retain both fine-head directions."""
    if policy.lane != "CAUSES":
        raise ValueError("CAUSES requires its own lane policy")
    keyed = _event_keys(events, sentence_spans, time_values)
    lineage = _lineage(article, {}, keyed)
    sentence_index: dict[int, set[int]] = defaultdict(set)
    entity_index: dict[str, set[int]] = defaultdict(set)
    time_index: dict[str, set[int]] = defaultdict(set)
    for index, row in enumerate(keyed):
        for sentence in row.sentences:
            sentence_index[sentence].add(index)
        for entity_id in row.entity_ids:
            entity_index[entity_id].add(index)
        for time_key in row.time_keys:
            time_index[time_key].add(index)
    anchor_order = sorted(range(len(keyed)),
                          key=lambda index: (keyed[index].anchor, keyed[index].event_id))
    anchor_positions = [keyed[index].anchor for index in anchor_order]
    selected: dict[tuple[int, int], tuple[float, set[str]]] = {}
    visited = exhausted = 0
    for index, row in enumerate(keyed):
        cues: dict[int, set[str]] = defaultdict(set)
        for sentence in row.sentences:
            for offset in range(-2, 3):
                posting = sorted(sentence_index.get(sentence + offset, ()))[:policy.posting_visit_budget]
                visited += len(posting)
                for other in posting:
                    if other != index:
                        cues[other].add("LOCAL:" + str(abs(offset)))
        for entity_id in row.entity_ids:
            posting = sorted(entity_index[entity_id])[:policy.posting_visit_budget]
            visited += len(posting)
            for other in posting:
                if other != index:
                    cues[other].add("SHARED_ENTITY:" + entity_id)
        for time_key in row.time_keys:
            posting = sorted(time_index[time_key])[:policy.posting_visit_budget]
            visited += len(posting)
            for other in posting:
                if other != index:
                    cues[other].add("TEMPORAL:" + time_key)
        if len(cues) < min(2, len(keyed) - 1):
            position = bisect_left(anchor_positions, row.anchor)
            near = [anchor_order[i] for i in range(max(0, position - 2),
                                                   min(len(anchor_order), position + 3))
                    if anchor_order[i] != index]
            nearest = min(near, key=lambda j: (abs(keyed[j].anchor - row.anchor),
                                                keyed[j].event_id)) if near else None
            anchor_candidates = [anchor_order[i] for i in
                                 sorted({0, len(anchor_order) // 2,
                                         len(anchor_order) - 1}) if anchor_order[i] != index]
            for other in (*((nearest,) if nearest is not None else ()),
                          *anchor_candidates):
                cues[other].add("FAR_RESERVE:SOURCE_ANCHOR")
        ranked = []
        for other, keys in cues.items():
            peer = keyed[other]
            sentence_distance = min(abs(a - b) for a in row.sentences for b in peer.sentences)
            score = (3 * (sentence_distance == 0) +
                     2 * sum(key.startswith("SHARED_ENTITY") for key in keys) +
                     2 * sum(key.startswith("TEMPORAL") for key in keys) +
                     1 / (1 + sentence_distance) +
                     1 / (1 + abs(row.anchor - peer.anchor)))
            ranked.append((-score, peer.event_id, other, keys))
        ranked.sort()
        exhausted += len(ranked) > policy.per_query_budget or len(ranked) > policy.posting_visit_budget
        for negative_score, _peer_id, other, keys in ranked[:min(
                policy.per_query_budget, policy.posting_visit_budget)]:
            pair = (min(index, other), max(index, other))
            previous = selected.get(pair)
            selected[pair] = ((-negative_score, set(keys)) if previous is None else
                              (max(-negative_score, previous[0]),
                               previous[1] | keys))
    pairs = []
    records = []
    ranks: dict[str, int] = defaultdict(int)
    for (a, b), (score, keys) in sorted(selected.items()):
        for left, right in ((a, b), (b, a)):
            left_id, right_id = keyed[left].event_id, keyed[right].event_id
            ranks[left_id] += 1
            pairs.append((left_id, right_id))
            records.append(_record(lane="CAUSES", left=left_id, right=right_id,
                                   keys=keys, score=score, rank=ranks[left_id],
                                   policy_id=policy.policy_id,
                                   policy_sha256=policy.sha256, lineage=lineage))
    return RelationRoute("CAUSES", tuple(pairs), tuple(records),
                         len(keyed) * (len(keyed) - 1), visited, exhausted,
                         policy.policy_id, policy.sha256, lineage)
