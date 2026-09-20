"""검증된 r05.3 Gold를 손실 없는 task target과 lazy pair universe로 변환한다.

Gold ID는 target 내부의 결합 키이며 모델 feature가 아니다. 임의의 미기록 의미
span을 음성으로 만들지 않고, 명시된 closed-world pair domain만 음성화한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from itertools import combinations, product
import json
import random
from typing import Iterator, Mapping

from jsonschema import Draft202012Validator

from models.v3_pretraining.task_contract import PAIR_TASKS, SPAN_TASKS
from runtime.v3_pretraining.source_layout import LayoutBuilder, RawArticle, SourceLayout, SpanAlignment
from training.scripts.v3_gold_intake import SCHEMA, validate_article


@lru_cache(maxsize=1)
def _gold_validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


@dataclass(frozen=True, slots=True)
class ValidatedGoldArticle:
    """Gold/source/schema/reference가 통과한 학습 전용 입력."""

    raw: RawArticle
    annotations: Mapping[str, object]
    split: str

    @classmethod
    def from_record(cls, raw: RawArticle, gold: dict, *, split: str) -> "ValidatedGoldArticle":
        if split != "train":
            raise ValueError("v3 implementation compiler accepts existing train Gold only")
        envelope = {"version": "articlelocal-semantic-gold-v1.3",
                    "guideline_version": "articlelocal-semantic-guideline-r05.3", "articles": [gold]}
        error = next(_gold_validator().iter_errors(envelope), None)
        if error is not None:
            raise ValueError(f"Gold v1.3 schema: {error.message}")
        reasons = validate_article(gold, {"article_id": raw.article_id,
                                          "article": raw.content})
        if reasons:
            raise ValueError(f"Gold article validation: {reasons[0]}")
        return cls(raw, gold, split)


@dataclass(frozen=True, slots=True)
class SpanTarget:
    task: str
    owner_id: str
    alignment: SpanAlignment
    label: str


@dataclass(frozen=True, slots=True)
class RoleTarget:
    role_id: str
    event_id: str
    role: str
    alignment: SpanAlignment
    entity_id: str | None
    resolution_mask: str


@dataclass(frozen=True, slots=True)
class AssertorTarget:
    statement_id: str
    alignment: SpanAlignment | None
    entity_id: str | None
    source_mask: str
    resolution_mask: str


@dataclass(frozen=True, slots=True)
class ClassTarget:
    task: str
    owner_id: str
    label: str
    provenance: str


@dataclass(frozen=True, slots=True)
class TimeNormalizationTarget:
    time_id: str
    value: str | None
    normalization_mask: str


@dataclass(frozen=True, slots=True)
class PairTarget:
    task: str
    left_id: str
    right_id: str
    positive: bool


@dataclass(frozen=True, slots=True)
class PairUniverse:
    """전체 eligible universe를 저장하지 않고 순회/재현 가능한 음성 표본을 만든다."""

    task: str
    left_ids: tuple[str, ...]
    right_ids: tuple[str, ...]
    positive_pairs: frozenset[tuple[str, str]]
    shape: str  # CROSS, ORDERED_DISTINCT, UNORDERED_DISTINCT

    def __post_init__(self) -> None:
        left, right = set(self.left_ids), set(self.right_ids)
        if len(left) != len(self.left_ids) or len(right) != len(self.right_ids):
            raise ValueError(f"{self.task}: duplicate endpoint ID")
        if self.shape not in ("CROSS", "ORDERED_DISTINCT", "UNORDERED_DISTINCT"):
            raise ValueError(f"{self.task}: unknown pair shape")
        if self.shape == "UNORDERED_DISTINCT" and self.left_ids != self.right_ids:
            raise ValueError("unordered pair universe requires identical endpoints")
        if any(a not in left or b not in right or
               (self.shape != "CROSS" and a == b) or
               (self.shape == "UNORDERED_DISTINCT" and self.left_ids.index(a) >= self.right_ids.index(b))
               for a, b in self.positive_pairs):
            raise ValueError(f"{self.task}: positive endpoint outside eligible universe")

    def _coordinates(self) -> Iterator[tuple[str, str]]:
        if self.shape == "CROSS":
            yield from product(self.left_ids, self.right_ids)
        elif self.shape == "ORDERED_DISTINCT":
            yield from ((a, b) for a in self.left_ids for b in self.right_ids if a != b)
        elif self.shape == "UNORDERED_DISTINCT":
            if self.left_ids != self.right_ids:
                raise ValueError("unordered pair universe requires identical endpoints")
            yield from combinations(self.left_ids, 2)
        else:
            raise ValueError(f"unknown pair universe shape: {self.shape}")

    def __iter__(self) -> Iterator[PairTarget]:
        for left, right in self._coordinates():
            yield PairTarget(self.task, left, right, (left, right) in self.positive_pairs)

    @property
    def total_count(self) -> int:
        if self.shape == "CROSS":
            return len(self.left_ids) * len(self.right_ids)
        if self.shape == "ORDERED_DISTINCT":
            return len(self.left_ids) * len(self.right_ids) - len(set(self.left_ids) & set(self.right_ids))
        return len(self.left_ids) * (len(self.left_ids) - 1) // 2

    def counts(self) -> dict[str, int]:
        return {"positive": len(self.positive_pairs), "negative": self.total_count - len(self.positive_pairs),
                "ignored": 0, "unrepresentable": 0}

    def sample_negatives(self, *, limit: int, seed: int, content_sha256: str) -> tuple[PairTarget, ...]:
        """학습용 재현 표본만 뽑으며 평가의 논리적 universe는 그대로 둔다."""
        if limit < 0:
            raise ValueError("negative sample limit must be nonnegative")
        stable = int(sha256(f"{seed}:{content_sha256}:{self.task}".encode()).hexdigest()[:16], 16)
        rng = random.Random(stable)
        sample: list[PairTarget] = []
        observed = 0
        for row in self:
            if row.positive:
                continue
            observed += 1
            if len(sample) < limit:
                sample.append(row)
            elif limit:
                slot = rng.randrange(observed)
                if slot < limit:
                    sample[slot] = row
        return tuple(sorted(sample, key=lambda row: (row.left_id, row.right_id)))


@dataclass(frozen=True, slots=True)
class RankTarget:
    left_id: str
    right_id: str
    left_preferred: bool | None
    loss_mask: str  # SUPERVISE or TIE_IGNORE


@dataclass(frozen=True, slots=True)
class RankUniverse:
    nodes: tuple[tuple[str, int], ...]

    def __iter__(self) -> Iterator[RankTarget]:
        for (left, left_rank), (right, right_rank) in combinations(self.nodes, 2):
            yield RankTarget(left, right, None if left_rank == right_rank else left_rank < right_rank,
                             "TIE_IGNORE" if left_rank == right_rank else "SUPERVISE")

    def counts(self) -> dict[str, int]:
        ranks = [rank for _, rank in self.nodes]
        ties = sum(a == b for a, b in combinations(ranks, 2))
        return {"positive": len(ranks) * (len(ranks) - 1) // 2 - ties,
                "negative": 0, "ignored": ties, "unrepresentable": 0}


@dataclass(frozen=True, slots=True)
class ArticleTargets:
    article_version_id: str
    content_sha256: str
    layout: SourceLayout
    spans: Mapping[str, tuple[SpanTarget, ...]]
    roles: tuple[RoleTarget, ...]
    assertors: tuple[AssertorTarget, ...]
    classes: tuple[ClassTarget, ...]
    time_normalization: tuple[TimeNormalizationTarget, ...]
    pairs: Mapping[str, PairUniverse]
    primary: RankUniverse

    def coverage(self) -> dict[str, dict[str, int]]:
        result = {task: {"positive": len(self.spans[task]), "negative": 0, "ignored": 0,
                         "unrepresentable": 0} for task in SPAN_TASKS}
        for task, universe in self.pairs.items():
            result[task] = universe.counts()
        result["statement_type"] = {"positive": sum(row.task == "statement_type" for row in self.classes),
                                    "negative": 0, "ignored": 0, "unrepresentable": 0}
        result["entity_priority"] = {"positive": sum(row.task == "entity_priority" for row in self.classes),
                                    "negative": 0, "ignored": 0, "unrepresentable": 0}
        result["time_normalization"] = {"positive": sum(row.normalization_mask == "SUPERVISE" for row in self.time_normalization),
                                       "negative": 0, "ignored": sum(row.normalization_mask == "IGNORE" for row in self.time_normalization),
                                       "unrepresentable": 0}
        result["place_resolution"] = {"positive": sum(r.role == "PLACE" and r.resolution_mask == "SUPERVISE" for r in self.roles),
                                      "negative": 0, "ignored": sum(r.role == "PLACE" and r.resolution_mask == "IGNORE" for r in self.roles),
                                      "unrepresentable": 0}
        result["assertor_resolution"] = {"positive": sum(a.resolution_mask == "SUPERVISE" for a in self.assertors),
                                         "negative": 0, "ignored": sum(a.resolution_mask == "IGNORE" for a in self.assertors),
                                         "unrepresentable": 0}
        result["primary"] = self.primary.counts()
        result["assertor_source"]["ignored"] = sum(a.source_mask == "IGNORE" for a in self.assertors)
        return result


class TargetCompiler:
    def __init__(self, layout_builder: LayoutBuilder) -> None:
        self.layout_builder = layout_builder

    def compile(self, article: ValidatedGoldArticle) -> ArticleTargets:
        if not isinstance(article, ValidatedGoldArticle):
            raise TypeError("Gold compiler requires ValidatedGoldArticle, not raw runtime input")
        gold = article.annotations
        layout = self.layout_builder.build(article.raw)
        spans: dict[str, list[SpanTarget]] = {task: [] for task in SPAN_TASKS}
        roles: list[RoleTarget] = []
        assertors: list[AssertorTarget] = []
        classes: list[ClassTarget] = []
        normalizations: list[TimeNormalizationTarget] = []
        def add(task: str, owner: str, span: dict, label: str) -> None:
            spans[task].append(SpanTarget(task, owner, layout.align(span), label))
        for event in gold["events"]:
            eid = event["event_id"]
            for task in ("semantic_proposer", "semantic_boundary", "semantic_validity"):
                add(task, eid, event["span"], "EVENT")
            add("trigger", eid, event["trigger"], "TRIGGER")
            for collection, label in (("actors", "ACTOR"), ("targets", "TARGET"), ("places", "PLACE")):
                for index, participant in enumerate(event[collection]):
                    role_id = f"{eid}:{label}:{index}"
                    aligned = layout.align(participant["span"])
                    roles.append(RoleTarget(role_id, eid, label, aligned, participant["entity_id"],
                                            "IGNORE" if participant["entity_id"] is None else "SUPERVISE"))
                    spans["participant"].append(SpanTarget("participant", role_id, aligned, label))
        for statement in gold["statements"]:
            sid = statement["statement_id"]
            for task in ("semantic_proposer", "semantic_boundary", "semantic_validity"):
                add(task, sid, statement["span"], "STATEMENT")
            classes.append(ClassTarget("statement_type", sid, statement["type"], "Gold Statement.type"))
            assertor = statement["assertor"]
            if assertor is None:
                assertors.append(AssertorTarget(sid, None, None, "IGNORE", "IGNORE"))
            else:
                aligned = layout.align(assertor["span"])
                add("assertor_source", sid, assertor["span"], "ASSERTOR")
                assertors.append(AssertorTarget(sid, aligned, assertor["entity_id"], "SUPERVISE",
                                                "IGNORE" if assertor["entity_id"] is None else "SUPERVISE"))
        for mention in gold["entity_mentions"]:
            mid = mention["mention_id"]
            add("entity_mention", mid, mention["span"], mention["type"])
            classes.append(ClassTarget("entity_priority", mid, "RETAIN_EXACT", "Gold EntityMention exact boundary; not importance_rank"))
        for mention in gold["time_mentions"]:
            tid = mention["time_id"]
            add("time_mention", tid, mention["span"], "TIME")
            value = mention["normalized_value"]
            normalizations.append(TimeNormalizationTarget(tid, value, "IGNORE" if value is None else "SUPERVISE"))
        entity_ids = tuple(c["entity_id"] for c in gold["entity_clusters"])
        entity_membership = {mid: c["entity_id"] for c in gold["entity_clusters"] for mid in c["mention_ids"]}
        mention_ids = tuple(m["mention_id"] for m in gold["entity_mentions"])
        event_ids = tuple(e["event_id"] for e in gold["events"])
        event_membership = {eid: c["cluster_id"] for c in gold["event_clusters"] for eid in c["event_ids"]}
        time_ids = tuple(t["time_id"] for t in gold["time_mentions"])
        cluster_ids = tuple(c["cluster_id"] for c in gold["event_clusters"])
        statement_ids = tuple(s["statement_id"] for s in gold["statements"])
        entity_coref = frozenset((a, b) for a, b in combinations(mention_ids, 2)
                                    if entity_membership[a] == entity_membership[b])
        event_coref = frozenset((a, b) for a, b in combinations(event_ids, 2)
                                   if event_membership[a] == event_membership[b])
        resolved_roles = tuple(r for r in roles if r.resolution_mask == "SUPERVISE")
        resolved_assertors = tuple(a for a in assertors if a.resolution_mask == "SUPERVISE")
        relation_rows = gold["relations"]
        pairs = {
            "entity_coreference": PairUniverse("entity_coreference", mention_ids, mention_ids, entity_coref, "UNORDERED_DISTINCT"),
            "event_coreference": PairUniverse("event_coreference", event_ids, event_ids, event_coref, "UNORDERED_DISTINCT"),
            "role_entity": PairUniverse("role_entity", tuple(r.role_id for r in resolved_roles), entity_ids,
                                        frozenset((r.role_id, r.entity_id) for r in resolved_roles), "CROSS"),
            "event_time": PairUniverse("event_time", event_ids, time_ids,
                                       frozenset((e["event_id"], tid) for e in gold["events"] for tid in e["times"]), "CROSS"),
            "assertor_entity": PairUniverse("assertor_entity", tuple(a.statement_id for a in resolved_assertors), entity_ids,
                                            frozenset((a.statement_id, a.entity_id) for a in resolved_assertors), "CROSS"),
            "about": PairUniverse("about", statement_ids, cluster_ids,
                                  frozenset((r["source_statement_id"], r["target_event_cluster_id"]) for r in relation_rows if r["relation"] == "ABOUT"), "CROSS"),
            "causes": PairUniverse("causes", cluster_ids, cluster_ids,
                                   frozenset((r["source_event_cluster_id"], r["target_event_cluster_id"]) for r in relation_rows if r["relation"] == "CAUSES"), "ORDERED_DISTINCT"),
        }
        rank = RankUniverse(tuple((f"E:{c['cluster_id']}", c["importance_rank"]) for c in gold["event_clusters"])
                            + tuple((f"S:{s['statement_id']}", s["importance_rank"]) for s in gold["statements"]))
        return ArticleTargets(article.raw.article_version_id, article.raw.content_sha256, layout,
                              {task: tuple(rows) for task, rows in spans.items()}, tuple(roles), tuple(assertors),
                              tuple(classes), tuple(normalizations), pairs, rank)
