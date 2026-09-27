"""검증된 Gold를 손실 없는 task target과 lazy pair universe로 변환한다.

Gold ID는 target 내부의 결합 키이며 모델 feature가 아니다. 임의의 미기록 의미
span을 음성으로 만들지 않고, 명시된 closed-world pair domain만 음성화한다.

기본 validation contract는 historical r05.3 재현을 위해 고정한다. r06.0 intake는
명시적 contract를 넘겨 같은 compiler를 사용하며, 두 schema/envelope를 묵시적으로
호환 취급하지 않는다.

span 음성 규칙 N1~N3은 각자 자기 책임에만 적용하고 N4는 D1 계약으로 비활성이다.
ENTITY/TIME/PARTICIPANT의 exact decision 음성은 train-only reviewed sidecar만
받는다. 경계 불일치를 semantic 부적격으로, kind 배타성을 span 존재 부정으로
전파하지 않는다. 근거가 없는 경우는 음성이 아니라 IGNORE다.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import random
import re
from typing import Iterator, Mapping

from jsonschema import Draft202012Validator

from models.v3_pretraining.task_contract import PAIR_TASKS, SPAN_TASKS
from runtime.v3_pretraining.source_layout import LayoutBuilder, RawArticle, SourceLayout, SpanAlignment
from training.v3_pretraining.negative_authority import ReviewedNegativeAuthority
from training.scripts.v3_gold_intake import SCHEMA, validate_article


REPO = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class GoldValidationContract:
    """Gold envelope와 schema 권한을 한 묶음으로 고정한다."""

    contract_id: str
    version: str
    guideline_version: str
    schema_path: Path


LEGACY_R05_3_GOLD_CONTRACT = GoldValidationContract(
    "articlelocal-gold-validation-r05.3-v1",
    "articlelocal-semantic-gold-v1.3",
    "articlelocal-semantic-guideline-r05.3",
    SCHEMA,
)
R06_0_GOLD_CONTRACT = GoldValidationContract(
    "articlelocal-gold-validation-r06.0-v1",
    "articlelocal-semantic-gold-v1.4",
    "articlelocal-semantic-guideline-r06.0",
    REPO / "data/gold/schema/articlelocal-semantic-gold-v1.4.schema.json",
)


@lru_cache(maxsize=None)
def _gold_validator(schema_path: str) -> Draft202012Validator:
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_gold_record(raw: RawArticle, gold: Mapping[str, object], *,
                         contract: GoldValidationContract) -> None:
    """명시된 envelope/schema와 source-grounded hard invariant를 검사한다."""
    envelope = {"version": contract.version,
                "guideline_version": contract.guideline_version,
                "articles": [gold]}
    validate_gold_envelope(envelope, contract=contract)
    reasons = validate_article(dict(gold), {"article_id": raw.article_id,
                                           "article": raw.content})
    if reasons:
        raise ValueError(f"Gold article validation: {reasons[0]}")


def validate_gold_envelope(envelope: Mapping[str, object], *,
                           contract: GoldValidationContract) -> None:
    """merged 또는 single-article envelope를 지정 schema로 직접 검증한다."""
    error = next(_gold_validator(str(contract.schema_path)).iter_errors(envelope), None)
    if error is not None:
        raise ValueError(f"{contract.contract_id} schema: {error.message}")


@dataclass(frozen=True, slots=True)
class ValidatedGoldArticle:
    """Gold/source/schema/reference가 통과한 학습 전용 입력."""

    raw: RawArticle
    annotations: Mapping[str, object]
    split: str
    validation_contract_id: str

    @classmethod
    def from_record(cls, raw: RawArticle, gold: dict, *, split: str,
                    contract: GoldValidationContract = LEGACY_R05_3_GOLD_CONTRACT,
                    ) -> "ValidatedGoldArticle":
        if split != "train":
            raise ValueError("v3 implementation compiler accepts existing train Gold only")
        return cls._validated(raw, gold, split=split, contract=contract)

    @classmethod
    def from_evaluation_record(cls, raw: RawArticle, gold: dict, *,
                               split: str,
                               contract: GoldValidationContract = LEGACY_R05_3_GOLD_CONTRACT,
                               ) -> "ValidatedGoldArticle":
        """Create an explicitly read-only dev/test input without relabeling its split."""
        if split not in ("dev", "test"):
            raise ValueError("v3 evaluation compiler accepts explicit dev/test Gold only")
        return cls._validated(raw, gold, split=split, contract=contract)

    @classmethod
    def _validated(cls, raw: RawArticle, gold: dict, *, split: str,
                   contract: GoldValidationContract) -> "ValidatedGoldArticle":
        validate_gold_record(raw, gold, contract=contract)
        return cls(raw, gold, split, contract.contract_id)


# r05.3 근거가 확인된 span 음성 규칙. 규칙마다 책임이 다르므로 절대 합산하지 않는다.
NEGATIVE_RULES = {
    # Gold와 같은 kind지만 exact 좌표가 아닌 경계 변형. "그 exact span이 아니다"만 말한다.
    "N1_BOUNDARY_MISMATCH": "EXACT_SPAN_FITNESS",
    # 같은 좌표가 다른 proposition kind의 Gold다. r05.3 §2.1/§2.2의 kind 배타성.
    "N2_KIND_EXCLUSIVE": "DETECTION",
    # r05.3 §2.1이 EVENT에서 명시적으로 제외한 순수 reporting wrapper.
    "N3_REPORTING_WRAPPER": "EVENT_DETECTION_AND_VALIDITY",
    # Gold Event가 없는 위치의 Trigger. Event 집합 완결성에 종속되므로 가드가 필요하다.
    "N4_TRIGGER_WITHOUT_EVENT": "TRIGGER_DETECTION",
}
IGNORE_REASONS = (
    "I1_REPEAT_OCCURRENCE",      # §2.5 반복 언급은 허용형이라 음성으로 확정할 수 없다
    "I2_OVERLAPS_GOLD",          # Gold와 겹쳐 책임을 분리할 수 없다
    "I3_OMISSION_SUSPECTED",     # annotation 누락이 의심된다
)
# 음성 규칙을 적용하는 kind. ENTITY/TIME은 §5.1/§6.1의 annotation 범위가 달라 제외한다.
NEGATIVE_KINDS = ("EVENT", "STATEMENT", "TRIGGER")
# §4.2.3이 Statement span에서 제외하는 attribution/reporting carrier. 닫는 따옴표와
# 인용 조사를 건너뛴 뒤 보고 동사로 끝나는 경우만 wrapper로 본다. `…며 "` 처럼 다음
# 인용으로 이어지는 형태는 완결된 wrapper가 아니므로 일부러 제외한다.
REPORTING_VERBS = ("말했다", "밝혔다", "전했다", "설명했다", "덧붙였다", "보도했다",
                   "추정했다", "전해졌다", "알려졌다", "진술했다")
_REPORTING_WRAPPER = re.compile(
    r"^[”\"'’」\s]*(?:이라고|라고|고|며)?\s*(?:" + "|".join(REPORTING_VERBS) + r")")
# N1 변형이 Gold 경계에서 벗어나는 최대 source-token 수와 Gold span당 상한.
# 가장 가까운 경계부터 결정적으로 고른다. 무작위 표본이 아니라 재현 가능한 상위 k다.
BOUNDARY_PERTURBATION_TOKENS = 2
BOUNDARY_NEGATIVES_PER_GOLD = 8


@dataclass(frozen=True, slots=True)
class SpanNegative:
    """한 규칙이 한 책임에 대해서만 주장하는 음성 span."""

    rule: str
    responsibility: str
    kind: str
    alignment: SpanAlignment
    anchor_gold_id: str

    def __post_init__(self) -> None:
        if self.rule not in NEGATIVE_RULES or self.kind not in NEGATIVE_KINDS:
            raise ValueError("span negative needs a known r05.3 rule and kind")
        if self.responsibility != NEGATIVE_RULES[self.rule]:
            raise ValueError(f"{self.rule}: responsibility cannot be widened")


@dataclass(frozen=True, slots=True)
class SpanIgnore:
    """음성으로 확정할 근거가 없어 손실에서 제외하는 span."""

    reason: str
    kind: str
    alignment: SpanAlignment
    anchor_gold_id: str

    def __post_init__(self) -> None:
        if self.reason not in IGNORE_REASONS or self.kind not in NEGATIVE_KINDS:
            raise ValueError("span ignore needs a known reason and kind")


@dataclass(frozen=True, slots=True)
class ReviewedSpanDecision:
    """승인된 train-only sidecar에서 온 exact decision target과 provenance."""

    candidate_id: str
    kind: str
    owner_id: str
    role: str | None
    role_status: str | None
    alignment: SpanAlignment
    proposed_label: str
    verdict: str
    reason: str
    responsibility: str
    authority_id: str
    reviewer: str
    review_version: str
    sidecar_sha256: str
    related_gold_ids: tuple[str, ...]


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
class UnifiedEntityMentionTarget:
    """P3 identity mention. Grounded role uses share their exact Native mention ID."""

    mention_id: str
    alignment: SpanAlignment
    entity_type: str | None  # None is internal UNKNOWN, never a pre-coref GENERIC label.
    gold_entity_id: str | None
    origins: tuple[str, ...]
    role_use_ids: tuple[str, ...] = ()


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
    supervision_mask: str = "SUPERVISE"


@dataclass(frozen=True, slots=True)
class PairUniverse:
    """전체 eligible universe를 저장하지 않고 순회/재현 가능한 음성 표본을 만든다."""

    task: str
    left_ids: tuple[str, ...]
    right_ids: tuple[str, ...]
    positive_pairs: frozenset[tuple[str, str]]
    shape: str  # CROSS, ORDERED_DISTINCT, UNORDERED_DISTINCT
    supervised_identity: Mapping[str, str | None] | None = None
    negative_authority: str | None = None

    def __post_init__(self) -> None:
        left, right = set(self.left_ids), set(self.right_ids)
        if len(left) != len(self.left_ids) or len(right) != len(self.right_ids):
            raise ValueError(f"{self.task}: duplicate endpoint ID")
        if self.shape not in ("CROSS", "ORDERED_DISTINCT", "UNORDERED_DISTINCT"):
            raise ValueError(f"{self.task}: unknown pair shape")
        if self.shape == "UNORDERED_DISTINCT" and self.left_ids != self.right_ids:
            raise ValueError("unordered pair universe requires identical endpoints")
        if self.supervised_identity is not None:
            if (self.task != "entity_coreference" or self.shape != "UNORDERED_DISTINCT"
                    or set(self.supervised_identity) != left
                    or self.negative_authority != "DISTINCT_KNOWN_GOLD_ENTITY_IDS_V1"):
                raise ValueError("Entity coreference needs explicit known-cluster negative authority")
        if any(a not in left or b not in right or
               (self.shape != "CROSS" and a == b) or
               (self.shape == "UNORDERED_DISTINCT" and self.left_ids.index(a) >= self.right_ids.index(b))
               for a, b in self.positive_pairs):
            raise ValueError(f"{self.task}: positive endpoint outside eligible universe")
        if self.supervised_identity is not None and any(
                self.supervised_identity[a] is None or
                self.supervised_identity[a] != self.supervised_identity[b]
                for a, b in self.positive_pairs):
            raise ValueError("Entity coreference positive lacks supervised shared identity")

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
            mask = ("IGNORE" if self.supervised_identity is not None and
                    (self.supervised_identity[left] is None or
                     self.supervised_identity[right] is None) else "SUPERVISE")
            yield PairTarget(self.task, left, right,
                             (left, right) in self.positive_pairs, mask)

    @property
    def total_count(self) -> int:
        if self.shape == "CROSS":
            return len(self.left_ids) * len(self.right_ids)
        if self.shape == "ORDERED_DISTINCT":
            return len(self.left_ids) * len(self.right_ids) - len(set(self.left_ids) & set(self.right_ids))
        return len(self.left_ids) * (len(self.left_ids) - 1) // 2

    def counts(self) -> dict[str, int]:
        if self.supervised_identity is None:
            supervised = self.total_count
        else:
            known = sum(value is not None for value in self.supervised_identity.values())
            supervised = known * (known - 1) // 2
        return {"positive": len(self.positive_pairs),
                "negative": supervised - len(self.positive_pairs),
                "ignored": self.total_count - supervised, "unrepresentable": 0}

    def sample_negatives(self, *, limit: int, seed: int, content_sha256: str) -> tuple[PairTarget, ...]:
        """학습용 재현 표본만 뽑으며 평가의 논리적 universe는 그대로 둔다."""
        if limit < 0:
            raise ValueError("negative sample limit must be nonnegative")
        stable = int(sha256(f"{seed}:{content_sha256}:{self.task}".encode()).hexdigest()[:16], 16)
        rng = random.Random(stable)
        sample: list[PairTarget] = []
        observed = 0
        for row in self:
            if row.positive or row.supervision_mask == "IGNORE":
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
    entity_mentions: tuple[UnifiedEntityMentionTarget, ...] = ()
    span_negatives: tuple[SpanNegative, ...] = ()
    span_ignores: tuple[SpanIgnore, ...] = ()
    reviewed_span_decisions: tuple[ReviewedSpanDecision, ...] = ()

    def negative_counts(self) -> dict[str, int]:
        """규칙별 음성 수. 책임이 다르므로 호출자도 합산해서 보고하지 않는다."""
        return {rule: sum(row.rule == rule for row in self.span_negatives)
                for rule in NEGATIVE_RULES}

    def ignore_counts(self) -> dict[str, int]:
        return {reason: sum(row.reason == reason for row in self.span_ignores)
                for reason in IGNORE_REASONS}

    def coverage(self) -> dict[str, dict[str, int]]:
        result = {task: {"positive": len(self.spans[task]), "negative": 0, "ignored": 0,
                         "unrepresentable": 0} for task in SPAN_TASKS}
        for task, universe in self.pairs.items():
            result[task] = universe.counts()
        result["statement_type"] = {"positive": sum(row.task == "statement_type" for row in self.classes),
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
        result["assertor_source"]["negative"] = sum(
            a.source_mask == "NO_EXPLICIT_SOURCE" for a in self.assertors)
        result["assertor_source"]["ignored"] = sum(
            a.source_mask == "IGNORE" for a in self.assertors)
        task_for_kind = {"ENTITY": "entity_mention", "TIME": "time_mention",
                         "PARTICIPANT": "participant"}
        for row in self.reviewed_span_decisions:
            task = task_for_kind[row.kind]
            if row.verdict == "NEGATIVE":
                result[task]["negative"] += 1
            elif row.verdict in ("IGNORE", "OMISSION_SUSPECTED"):
                result[task]["ignored"] += 1
        return result


def _token_boundary_variants(layout: SourceLayout, start: int, end: int,
                             reach: int = BOUNDARY_PERTURBATION_TOKENS,
                             limit: int = BOUNDARY_NEGATIVES_PER_GOLD) -> tuple[tuple[int, int], ...]:
    """Gold 경계를 이웃 source token 경계로 옮긴 변형만 만든다.

    후보 검색이 실제로 도달할 수 있는 좌표(= source token 경계)만 쓰므로, 임의의
    문자 offset을 만들어 도달 불가능한 음성을 학습시키지 않는다.
    """
    starts = layout.bridge_token_starts
    ends = layout.bridge_token_ends
    try:
        first = starts.index(start)
        last = ends.index(end)
    except ValueError:
        return ()  # subtoken 경계 Gold는 residual 책임이라 경계 변형을 만들지 않는다
    left = [(abs(i - first), starts[i])
            for i in range(max(first - reach, 0), min(first + reach + 1, len(starts)))]
    right = [(abs(i - last), ends[i])
             for i in range(max(last - reach, 0), min(last + reach + 1, len(ends)))]
    variants = [(ds + de, a, b) for ds, a in left for de, b in right
                if a < b and (a, b) != (start, end)]
    variants.sort(key=lambda row: row)  # 가까운 경계 우선, 동률은 좌표 순
    return tuple((a, b) for _distance, a, b in variants[:limit])


def _trigger_width_range(trigger_spans: Mapping[tuple[int, int], str]) -> tuple[int, int]:
    """이 기사 Gold trigger의 문자 길이 범위. trigger가 없으면 보수적 기본값."""
    widths = [b - a for a, b in trigger_spans]
    return (min(widths), max(widths)) if widths else (2, 16)


def _trigger_sized_spans(layout: SourceLayout, region_start: int, region_end: int,
                         widths: tuple[int, int], limit: int = 16) -> tuple[tuple[int, int], ...]:
    """구간 안에서 Gold trigger와 같은 크기의 source-token 경계 span만 세어 만든다.

    statement 크기의 변형을 trigger 음성으로 쓰면 길이 단서만 학습되므로 쓰지 않는다.
    """
    low, high = widths
    starts = [value for value in layout.bridge_token_starts if region_start <= value < region_end]
    ends = set(layout.bridge_token_ends)
    output: list[tuple[int, int]] = []
    for start in starts:
        for end in range(start + low, min(start + high, region_end) + 1):
            if end in ends:
                output.append((start, end))
    output.sort(key=lambda row: (row[0], row[1]))
    return tuple(output[:limit])


def _reporting_wrapper_end(content: str, end: int) -> int | None:
    """Statement 뒤에 붙는 §4.2.3 carrier의 끝 offset. 없으면 None."""
    match = _REPORTING_WRAPPER.match(content[end:end + 24])
    return end + match.end() if match else None


class TargetCompiler:
    def __init__(self, layout_builder: LayoutBuilder, *,
                 negative_authority: ReviewedNegativeAuthority | None = None,
                 enable_trigger_absence_negatives: bool = False) -> None:
        self.layout_builder = layout_builder
        self.negative_authority = negative_authority
        # D1은 N4를 비활성으로 승인했다. 과거 진단용 bool을 켜서 권한을 우회하는
        # 것을 허용하지 않는다.
        if enable_trigger_absence_negatives:
            raise ValueError("N4 trigger absence negatives are disabled by approved D1")
        self.enable_trigger_absence_negatives = False

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
                assertors.append(AssertorTarget(sid, None, None,
                                                "NO_EXPLICIT_SOURCE", "IGNORE"))
            else:
                aligned = layout.align(assertor["span"])
                add("assertor_source", sid, assertor["span"], "ASSERTOR")
                assertors.append(AssertorTarget(sid, aligned, assertor["entity_id"], "SUPERVISE",
                                                "IGNORE" if assertor["entity_id"] is None else "SUPERVISE"))
        for mention in gold["entity_mentions"]:
            mid = mention["mention_id"]
            add("entity_mention", mid, mention["span"], mention["type"])
        for mention in gold["time_mentions"]:
            tid = mention["time_id"]
            add("time_mention", tid, mention["span"], "TIME")
            value = mention["normalized_value"]
            normalizations.append(TimeNormalizationTarget(tid, value, "IGNORE" if value is None else "SUPERVISE"))
        entity_ids = tuple(c["entity_id"] for c in gold["entity_clusters"])
        entity_membership = {mid: c["entity_id"] for c in gold["entity_clusters"] for mid in c["mention_ids"]}
        unified_mentions = {
            m["mention_id"]: UnifiedEntityMentionTarget(
                m["mention_id"], layout.align(m["span"]), m["type"],
                entity_membership[m["mention_id"]], ("NATIVE",))
            for m in gold["entity_mentions"]}
        exact_native = {}
        for mention in unified_mentions.values():
            key = (mention.gold_entity_id, mention.alignment.start,
                   mention.alignment.end, mention.alignment.text)
            exact_native.setdefault(key, []).append(mention.mention_id)
        for role in roles:
            if role.entity_id is None and role.role != "PLACE":
                raise ValueError("Gold ACTOR/TARGET requires exact EntityMention grounding")
            key = (role.entity_id, role.alignment.start, role.alignment.end,
                   role.alignment.text)
            native_ids = exact_native.get(key, ()) if role.entity_id is not None else ()
            if len(native_ids) > 1 and len({unified_mentions[mid].entity_type
                                            for mid in native_ids}) != 1:
                raise ValueError("Gold role has conflicting exact EntityMention types")
            if native_ids:
                # Distinct Gold IDs can share one exact span/entity/type. Keep all
                # Native mentions and record their common ROLE use without choosing
                # an arbitrary ID or editing the frozen Gold.
                for native_id in native_ids:
                    mention = unified_mentions[native_id]
                    unified_mentions[native_id] = UnifiedEntityMentionTarget(
                        mention.mention_id, mention.alignment, mention.entity_type,
                        mention.gold_entity_id, ("NATIVE", "ROLE"),
                        (*mention.role_use_ids, role.role_id))
            elif role.role in ("ACTOR", "TARGET"):
                raise ValueError("Gold ACTOR/TARGET lacks exact EntityMention grounding")
            else:
                mention_id = "ROLE:" + role.role_id
                if mention_id in unified_mentions:
                    raise ValueError("ROLE mention ID collides with Native ID")
                unified_mentions[mention_id] = UnifiedEntityMentionTarget(
                    mention_id, role.alignment, None, role.entity_id,
                    ("ROLE",), (role.role_id,))
        mention_ids = tuple(unified_mentions)
        unified_membership = {mid: row.gold_entity_id
                              for mid, row in unified_mentions.items()}
        event_ids = tuple(e["event_id"] for e in gold["events"])
        event_membership = {eid: c["cluster_id"] for c in gold["event_clusters"] for eid in c["event_ids"]}
        time_ids = tuple(t["time_id"] for t in gold["time_mentions"])
        cluster_ids = tuple(c["cluster_id"] for c in gold["event_clusters"])
        statement_ids = tuple(s["statement_id"] for s in gold["statements"])
        entity_coref = frozenset((a, b) for a, b in combinations(mention_ids, 2)
                                    if unified_membership[a] is not None and
                                    unified_membership[a] == unified_membership[b])
        event_coref = frozenset((a, b) for a, b in combinations(event_ids, 2)
                                   if event_membership[a] == event_membership[b])
        resolved_assertors = tuple(a for a in assertors if a.resolution_mask == "SUPERVISE")
        relation_rows = gold["relations"]
        pairs = {
            "entity_coreference": PairUniverse(
                "entity_coreference", mention_ids, mention_ids, entity_coref,
                "UNORDERED_DISTINCT", unified_membership,
                "DISTINCT_KNOWN_GOLD_ENTITY_IDS_V1"),
            "event_coreference": PairUniverse("event_coreference", event_ids, event_ids, event_coref, "UNORDERED_DISTINCT"),
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
        negatives, ignores = self._span_negatives(article, layout, spans)
        reviewed = self._reviewed_span_decisions(article, layout)
        return ArticleTargets(article.raw.article_version_id, article.raw.content_sha256, layout,
                              {task: tuple(rows) for task, rows in spans.items()}, tuple(roles), tuple(assertors),
                              tuple(classes), tuple(normalizations), pairs, rank,
                              tuple(unified_mentions.values()),
                              negatives, ignores, reviewed)

    def _reviewed_span_decisions(self, article: ValidatedGoldArticle,
                                 layout: SourceLayout) -> tuple[ReviewedSpanDecision, ...]:
        """Sidecar row를 Gold 보호 규칙과 exact source alignment로 닫는다."""
        if self.negative_authority is None:
            return ()
        if article.split != "train":
            return ()  # train-only authority never labels dev/test
        rows = self.negative_authority.records_for(
            article.raw.article_id, article.raw.content_sha256)
        if not rows:
            return ()
        gold = article.annotations
        content = article.raw.content
        entity_gold = {
            (row["span"]["start"], row["span"]["end"]): (row["mention_id"], row["type"])
            for row in gold["entity_mentions"]
        }
        # Referential role/assertor evidence can be a valid role-derived GENERIC Entity
        # even when it is absent from entity_mentions.
        entity_protected = set(entity_gold)
        for event in gold["events"]:
            for collection in ("actors", "targets", "places"):
                entity_protected.update(
                    (row["span"]["start"], row["span"]["end"]) for row in event[collection])
        entity_protected.update(
            (statement["assertor"]["span"]["start"], statement["assertor"]["span"]["end"])
            for statement in gold["statements"] if statement["assertor"] is not None)
        time_gold = {
            (row["span"]["start"], row["span"]["end"]): row["time_id"]
            for row in gold["time_mentions"]
        }
        event_by_id = {row["event_id"]: row for row in gold["events"]}
        collection_for_role = {"ACTOR": "actors", "TARGET": "targets", "PLACE": "places"}
        compiled: list[ReviewedSpanDecision] = []
        for row in rows:
            if not 0 <= row.start < row.end <= len(content) or content[row.start:row.end] != row.text:
                raise ValueError(f"{row.candidate_id}: sidecar source text/offset differs")
            coordinate = (row.start, row.end)
            if row.kind == "ENTITY":
                if row.verdict == "NEGATIVE" and coordinate in entity_protected:
                    raise ValueError(f"{row.candidate_id}: valid Entity/role endpoint cannot be negative")
                if row.verdict == "POSITIVE":
                    gold_row = entity_gold.get(coordinate)
                    if gold_row is None or gold_row[1] != row.proposed_label:
                        raise ValueError(f"{row.candidate_id}: sidecar positive must match typed Entity Gold")
            elif row.kind == "TIME":
                if row.verdict == "NEGATIVE" and coordinate in time_gold:
                    raise ValueError(f"{row.candidate_id}: unresolved/recorded TimeMention cannot be negative")
                if row.verdict == "POSITIVE" and coordinate not in time_gold:
                    raise ValueError(f"{row.candidate_id}: sidecar positive must match Time Gold")
            else:
                event = event_by_id.get(row.owner_id)
                if event is None or row.role is None:
                    raise ValueError(f"{row.candidate_id}: participant owner/role is unknown")
                role_rows = event[collection_for_role[row.role]]
                if row.verdict == "NEGATIVE" and role_rows:
                    raise ValueError(f"{row.candidate_id}: ABSENT contradicts listed participant Gold")
                if row.verdict == "POSITIVE" and not any(
                        (value["span"]["start"], value["span"]["end"]) == coordinate
                        for value in role_rows):
                    raise ValueError(f"{row.candidate_id}: participant positive must match Gold")
            compiled.append(ReviewedSpanDecision(
                row.candidate_id, row.kind, row.owner_id, row.role, row.role_status,
                layout.align({"start": row.start, "end": row.end, "text": row.text}),
                row.proposed_label, row.verdict, row.reason, row.responsibility,
                self.negative_authority.authority_id,
                self.negative_authority.reviewer,
                self.negative_authority.review_version,
                self.negative_authority.sha256,
                row.related_gold_ids,
            ))
        return tuple(compiled)

    def _span_negatives(self, article: ValidatedGoldArticle, layout: SourceLayout,
                        spans: Mapping[str, list[SpanTarget]]
                        ) -> tuple[tuple[SpanNegative, ...], tuple[SpanIgnore, ...]]:
        """r05.3 근거가 확인된 N1~N4만 만든다. 근거가 없으면 음성이 아니라 IGNORE다."""
        content = layout.article.content
        gold = article.annotations
        event_spans = {(e["span"]["start"], e["span"]["end"]): e["event_id"] for e in gold["events"]}
        statement_spans = {(s["span"]["start"], s["span"]["end"]): s["statement_id"]
                           for s in gold["statements"]}
        trigger_spans = {(e["trigger"]["start"], e["trigger"]["end"]): e["event_id"]
                         for e in gold["events"]}
        by_kind = {"EVENT": event_spans, "STATEMENT": statement_spans, "TRIGGER": trigger_spans}
        occupied = set(event_spans) | set(statement_spans) | set(trigger_spans)
        negatives: list[SpanNegative] = []
        ignores: list[SpanIgnore] = []
        seen: set[tuple[str, str, int, int]] = set()

        def emit(rule: str, kind: str, start: int, end: int, anchor: str) -> None:
            key = (rule, kind, start, end)
            if key in seen or not 0 <= start < end <= len(content):
                return
            seen.add(key)
            negatives.append(SpanNegative(rule, NEGATIVE_RULES[rule], kind,
                                          layout.align({"start": start, "end": end,
                                                        "text": content[start:end]}), anchor))

        def skip(reason: str, kind: str, start: int, end: int, anchor: str) -> None:
            ignores.append(SpanIgnore(reason, kind,
                                      layout.align({"start": start, "end": end,
                                                    "text": content[start:end]}), anchor))

        # N1: 같은 kind의 exact 좌표가 아닌 경계 변형. 경계 책임에만 쓴다.
        for kind in NEGATIVE_KINDS:
            same = by_kind[kind]
            for (start, end), gid in same.items():
                for variant in _token_boundary_variants(layout, start, end):
                    if variant in same:
                        continue  # 다른 Gold의 exact span은 음성이 아니다
                    if variant in occupied:
                        continue  # 다른 kind의 Gold다. N2가 kind 책임으로 처리한다
                    emit("N1_BOUNDARY_MISMATCH", kind, variant[0], variant[1], gid)

        # N2: 같은 좌표의 다른 proposition kind. §2.1/§2.2의 배타성.
        for (start, end), gid in event_spans.items():
            if (start, end) not in statement_spans:
                emit("N2_KIND_EXCLUSIVE", "STATEMENT", start, end, gid)
        for (start, end), gid in statement_spans.items():
            if (start, end) not in event_spans:
                emit("N2_KIND_EXCLUSIVE", "EVENT", start, end, gid)

        # N3: §2.1이 EVENT에서 제외한 순수 reporting wrapper.
        for (start, end), gid in statement_spans.items():
            wrapped = _reporting_wrapper_end(content, end)
            if wrapped is None:
                continue
            if (start, wrapped) in event_spans:
                skip("I2_OVERLAPS_GOLD", "EVENT", start, wrapped, gid)
                continue
            emit("N3_REPORTING_WRAPPER", "EVENT", start, wrapped, gid)

        # N4: Gold Event가 없는 Statement 구간의 trigger 후보.
        # 같은 occurrence 재진술이 조금이라도 의심되면 음성 대신 IGNORE다.
        trigger_surface = {content[a:b] for a, b in trigger_spans}
        widths = _trigger_width_range(trigger_spans)
        for (start, end), gid in statement_spans.items():
            # IGNORE 집계는 N4 활성 여부와 무관하게 남긴다. 어떤 구간이 왜 음성이
            # 될 수 없었는지가 승인 조건의 보고 대상이다.
            if any(a < end and start < b for a, b in event_spans):
                skip("I2_OVERLAPS_GOLD", "TRIGGER", start, end, gid)
                continue
            if any(a < end and start < b for a, b in trigger_spans):
                skip("I2_OVERLAPS_GOLD", "TRIGGER", start, end, gid)
                continue
            if self._restates_gold_event(content, start, end, gold, trigger_surface):
                skip("I1_REPEAT_OCCURRENCE", "TRIGGER", start, end, gid)
                continue
            if not self.enable_trigger_absence_negatives:
                continue
            for a, b in _trigger_sized_spans(layout, start, end, widths):
                if (a, b) in occupied:
                    continue
                emit("N4_TRIGGER_WITHOUT_EVENT", "TRIGGER", a, b, gid)
        return tuple(negatives), tuple(ignores)

    @staticmethod
    def _restates_gold_event(content: str, start: int, end: int, gold: Mapping[str, object],
                             trigger_surface: set[str]) -> bool:
        """Statement 구간이 이미 기록된 Event occurrence의 재진술로 의심되는가.

        r05.3 §2.5의 반복 언급은 허용형 서술이라 미기록을 음성으로 확정할 수 없다.
        표면형 재사용과 role filler 공유를 모두 의심 신호로 본다.
        """
        text = content[start:end]
        if any(surface and surface in text for surface in trigger_surface):
            return True
        for event in gold["events"]:  # type: ignore[index]
            for collection in ("actors", "targets", "places"):
                for participant in event[collection]:
                    filler = participant["span"]["text"]
                    if len(filler) >= 2 and filler in text:
                        return True
        return False
