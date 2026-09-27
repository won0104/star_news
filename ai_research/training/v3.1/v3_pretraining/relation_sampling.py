"""D7 relation negative sampling과 class-balanced risk 계약.

이 모듈은 compiler가 정한 eligible/label authority를 바꾸지 않는다. 호출자가
source-grounded membership tag를 제공하면 stable hash 순서로 최대 32개 음성을
고르고, overlapping membership과 실제 ``sampled_from``을 분리해 기록한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import TYPE_CHECKING, Iterable, Mapping, Sequence

if TYPE_CHECKING:
    import torch
    from training.v3_pretraining.targets import PairUniverse


RELATION_SAMPLING_POLICY_VERSION = "relation-stratified-class-balanced-v1.1"
RELATION_SAMPLING_SEED = 1008
RELATION_NEGATIVE_LIMIT = 32
ABOUT_LEXICAL_POLICY = "EXACT_TRIGGER_SUBSTRING_V1"
RELATION_TRAINING_METADATA_SCHEMA_VERSION = "relation-training-metadata-v2"

RELATION_QUOTAS: Mapping[str, tuple[tuple[str, int], ...]] = {
    "assertor_entity": (("option_confounder", 16), ("uniform", 16)),
    "about": (("same_sentence", 4), ("adjacent_sentence", 4),
              ("non_adjacent", 4), ("shared_resolved_entity", 6),
              ("lexical_overlap", 6), ("uniform", 8)),
    "causes": (("reverse_positive", 8), ("same_sentence", 3),
               ("adjacent_sentence", 3), ("non_adjacent", 3),
               ("shared_resolved_entity", 4), ("shared_trigger", 3),
               ("uniform", 8)),
}


@dataclass(frozen=True, slots=True)
class RelationSamplingPolicy:
    version: str = RELATION_SAMPLING_POLICY_VERSION
    seed: int = RELATION_SAMPLING_SEED
    negative_limit: int = RELATION_NEGATIVE_LIMIT
    about_lexical_policy: str = ABOUT_LEXICAL_POLICY

    def validate(self) -> None:
        if (self.version != RELATION_SAMPLING_POLICY_VERSION
                or self.seed != RELATION_SAMPLING_SEED
                or self.negative_limit != RELATION_NEGATIVE_LIMIT
                or self.about_lexical_policy != ABOUT_LEXICAL_POLICY):
            raise ValueError("relation sampling policy differs from approved D7 contract")
        if any(sum(value for _, value in quotas) != self.negative_limit
               for quotas in RELATION_QUOTAS.values()):
            raise AssertionError("D7 relation quotas must total 32")

    def to_dict(self) -> dict:
        self.validate()
        return {**asdict(self),
                "quotas": {task: [[name, count] for name, count in quotas]
                           for task, quotas in RELATION_QUOTAS.items()},
                "objective": "ARTICLE_LANE_CLASS_BALANCED_SAMPLED_RISK"}

    def fingerprint(self) -> str:
        return sha256(json.dumps(self.to_dict(), sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _json_digest(value: object) -> str:
    """JSON-safe digest shared by checkpoint writers and every strict loader."""
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def build_relation_training_metadata(
        policy: RelationSamplingPolicy,
        articles: Mapping[str, object],
) -> dict[str, object]:
    """Build the sole D7 metadata envelope accepted by resume and serving."""
    policy.validate()
    ordered_articles = {key: articles[key] for key in sorted(articles)}
    body: dict[str, object] = {
        "schema_version": RELATION_TRAINING_METADATA_SCHEMA_VERSION,
        "policy": policy.to_dict(),
        "policy_sha256": policy.fingerprint(),
        "articles": ordered_articles,
        "articles_sha256": _json_digest(ordered_articles),
    }
    return {**body, "metadata_sha256": _json_digest(body)}


def validate_relation_training_metadata(
        value: object,
        *,
        expected_policy: RelationSamplingPolicy,
) -> dict[str, object]:
    """Fail closed on schema, policy fingerprint, article digest, or envelope drift."""
    expected_policy.validate()
    required = {"schema_version", "policy", "policy_sha256", "articles",
                "articles_sha256", "metadata_sha256"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("checkpoint relation sampling metadata schema differs")
    articles = value["articles"]
    body = {key: value[key] for key in required if key != "metadata_sha256"}
    if (value["schema_version"] != RELATION_TRAINING_METADATA_SCHEMA_VERSION
            or value["policy"] != expected_policy.to_dict()
            or value["policy_sha256"] != expected_policy.fingerprint()
            or not isinstance(articles, dict)
            or value["articles_sha256"] != _json_digest(articles)
            or value["metadata_sha256"] != _json_digest(body)):
        raise ValueError("checkpoint relation sampling policy/digest differs")
    lanes = {"assertor_entity", "about", "causes"}
    required_lane_fields = {
        "policy_version", "policy_sha256", "seed", "content_sha256", "task",
        "eligible_positive", "eligible_negative", "sampled_positive",
        "sampled_negative", "sample_duplicate_count",
        "positive_negative_intersection", "article_id", "target_contract_sha256",
    }
    for article_id, article in articles.items():
        if (not isinstance(article_id, str) or not article_id
                or not isinstance(article, dict) or set(article) != lanes):
            raise ValueError("checkpoint relation article metadata schema differs")
        for lane, row in article.items():
            if (not isinstance(row, dict)
                    or not required_lane_fields <= set(row)
                    or row["task"] != lane
                    or row["article_id"] != article_id
                    or row["policy_version"] != expected_policy.version
                    or row["policy_sha256"] != expected_policy.fingerprint()
                    or row["seed"] != expected_policy.seed):
                raise ValueError("checkpoint relation lane metadata schema differs")
    return {key: articles[key] for key in sorted(articles)}


@dataclass(frozen=True, slots=True)
class RelationPair:
    task: str
    left_id: str
    right_id: str
    positive: bool


@dataclass(frozen=True, slots=True)
class SampledNegative:
    pair: RelationPair
    sampled_from: str
    membership: tuple[str, ...]
    stable_key: str


@dataclass(frozen=True, slots=True)
class RelationSample:
    task: str
    positives: tuple[RelationPair, ...]
    negatives: tuple[SampledNegative, ...]
    census: Mapping[str, object]

    @property
    def pairs(self) -> tuple[RelationPair, ...]:
        return self.positives + tuple(row.pair for row in self.negatives)


def _stable_key(policy: RelationSamplingPolicy, *, content_sha256: str,
                task: str, pair: tuple[str, str]) -> str:
    material = (f"{policy.seed}\0{content_sha256}\0{task}\0{policy.version}"
                f"\0{pair[0]}\0{pair[1]}")
    return sha256(material.encode()).hexdigest()


def deterministic_stratified_sample(
        universe: "PairUniverse", *, content_sha256: str,
        memberships: Mapping[tuple[str, str], Iterable[str]],
        policy: RelationSamplingPolicy | None = None,
) -> RelationSample:
    """Positive를 전부 보존하고 승인 quota 순서로 unique negative를 고른다."""
    policy = policy or RelationSamplingPolicy()
    policy.validate()
    if universe.task not in RELATION_QUOTAS:
        raise ValueError("D7 sampler only owns the three relation lanes")
    eligible = tuple(row for row in universe if not row.positive)
    eligible_pairs = {(row.left_id, row.right_id) for row in eligible}
    if set(memberships) - eligible_pairs:
        raise ValueError("stratum membership references positive/ineligible pair")
    tags = {pair: frozenset(values) for pair, values in memberships.items()}
    known = {name for name, _ in RELATION_QUOTAS[universe.task] if name != "uniform"}
    if any(value - known for value in tags.values()):
        raise ValueError("unknown relation stratum membership")
    keyed = sorted(
        ((_stable_key(policy, content_sha256=content_sha256, task=universe.task,
                      pair=(row.left_id, row.right_id)), row)
         for row in eligible),
        key=lambda item: (item[0], item[1].left_id, item[1].right_id))
    selected: dict[tuple[str, str], SampledNegative] = {}
    quota_rows: list[dict[str, object]] = []
    shortage = 0
    for name, base_quota in RELATION_QUOTAS[universe.task]:
        requested = base_quota + (shortage if name == "uniform" else 0)
        pool = [(key, row) for key, row in keyed
                if (row.left_id, row.right_id) not in selected
                and (name == "uniform" or
                     name in tags.get((row.left_id, row.right_id), ()))]
        chosen = pool[:requested]
        for key, row in chosen:
            pair = (row.left_id, row.right_id)
            selected[pair] = SampledNegative(
                RelationPair(universe.task, row.left_id, row.right_id, False),
                name, tuple(sorted(tags.get(pair, ()))), key)
        shortfall = requested - len(chosen)
        quota_rows.append({"stratum": name, "base_quota": base_quota,
                           "requested_after_refill": requested,
                           "eligible_membership": sum(
                               name == "uniform" or name in tags.get(
                                   (row.left_id, row.right_id), ()) for row in eligible),
                           "available_when_selected": len(pool),
                           "selected": len(chosen), "shortfall": shortfall,
                           "refill_received": shortage if name == "uniform" else 0})
        if name != "uniform":
            shortage += shortfall
    negatives = tuple(selected[pair] for pair in sorted(selected))
    if len(negatives) > policy.negative_limit or len({(row.pair.left_id, row.pair.right_id)
                                                       for row in negatives}) != len(negatives):
        raise AssertionError("D7 negative limit/uniqueness contract failed")
    positives = tuple(RelationPair(universe.task, left, right, True)
                      for left, right in sorted(universe.positive_pairs))
    positive_set = {(row.left_id, row.right_id) for row in positives}
    negative_set = {(row.pair.left_id, row.pair.right_id) for row in negatives}
    if positive_set & negative_set:
        raise AssertionError("relation sample mixed positive and negative authority")
    membership_counts = {name: sum(name in tags.get(
        (row.left_id, row.right_id), ()) for row in eligible) for name in known}
    sampled_from = {name: sum(row.sampled_from == name for row in negatives)
                    for name, _ in RELATION_QUOTAS[universe.task]}
    eligible_positive = len(positives)
    eligible_negative = len(eligible)
    sampled_total = eligible_positive + len(negatives)
    census = {
        "policy_version": policy.version,
        "policy_sha256": policy.fingerprint(),
        "seed": policy.seed,
        "content_sha256": content_sha256,
        "task": universe.task,
        "eligible_positive": eligible_positive,
        "eligible_negative": eligible_negative,
        "eligible_ignored": 0,
        "sampled_positive": eligible_positive,
        "sampled_negative": len(negatives),
        "negative_limit": policy.negative_limit,
        "sample_duplicate_count": 0,
        "positive_negative_intersection": 0,
        "eligible_positive_prevalence": (
            eligible_positive / (eligible_positive + eligible_negative)
            if eligible_positive + eligible_negative else None),
        "sampled_positive_prevalence": (
            eligible_positive / sampled_total if sampled_total else None),
        "membership_counts_overlapping": membership_counts,
        "sampled_from_counts_exclusive": sampled_from,
        "selected_negative_pairs": [
            {"left_id": row.pair.left_id, "right_id": row.pair.right_id,
             "sampled_from": row.sampled_from,
             "membership": list(row.membership), "stable_key": row.stable_key}
            for row in negatives],
        "quota": quota_rows,
    }
    return RelationSample(universe.task, positives, negatives, census)


@dataclass(frozen=True, slots=True)
class ClassBalancedLoss:
    loss: torch.Tensor
    positive_sum: torch.Tensor
    negative_sum: torch.Tensor
    positive_count: int
    negative_count: int
    positive_weight: float
    negative_weight: float


def class_balanced_pair_loss(
        chunks: Sequence[tuple["torch.Tensor", "torch.Tensor"]], *,
        zero: "torch.Tensor",
) -> ClassBalancedLoss:
    """Chunk size와 partial chunk에 무관하게 class별 sum/count를 집계한다."""
    from torch.nn import functional as F

    positive_sum = zero
    negative_sum = zero
    positive_count = 0
    negative_count = 0
    for logits, labels in chunks:
        if logits.shape != labels.shape or logits.ndim != 1:
            raise ValueError("relation loss chunks require aligned scalar logits/labels")
        if not bool(((labels == 0) | (labels == 1)).all()):
            raise ValueError("relation class-balanced labels must be binary")
        values = F.binary_cross_entropy_with_logits(logits, labels, reduction="none")
        positive = labels == 1
        negative = labels == 0
        if bool(positive.any()):
            positive_sum = positive_sum + values[positive].sum()
            positive_count += int(positive.sum().item())
        if bool(negative.any()):
            negative_sum = negative_sum + values[negative].sum()
            negative_count += int(negative.sum().item())
    if positive_count and negative_count:
        positive_weight = negative_weight = 0.5
    elif positive_count:
        positive_weight, negative_weight = 1.0, 0.0
    elif negative_count:
        positive_weight, negative_weight = 0.0, 1.0
    else:
        positive_weight = negative_weight = 0.0
    loss = zero
    if positive_count:
        loss = loss + positive_weight * positive_sum / positive_count
    if negative_count:
        loss = loss + negative_weight * negative_sum / negative_count
    return ClassBalancedLoss(loss, positive_sum, negative_sum,
                             positive_count, negative_count,
                             positive_weight, negative_weight)
