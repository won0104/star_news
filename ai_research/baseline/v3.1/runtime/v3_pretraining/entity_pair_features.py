"""학습과 서빙이 공유하는 source-only Entity pair feature 계약.

Router의 aggregate rank나 Gold identity는 입력하지 않는다. 후보별 정규화는
한 번만 수행하고, pair 함수는 순서에 무관한 primitive evidence만 반환한다.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import Sequence

from runtime.v3_pretraining.entity_pair_blocking import _alias, _grams, _surface


ENTITY_PAIR_FEATURE_VERSION = "v31-symmetric-source-primitives-v1"
ENTITY_PAIR_FEATURE_NAMES = (
    "exact_same_coordinate",
    "exact_normalized_surface",
    "alias_match",
    "normalized_surface_containment",
    "character_bigram_jaccard",
    "same_known_entity_type",
    "known_entity_type_conflict",
    "type_unknown_present",
    "same_sentence",
    "sentence_distance",
    "normalized_character_distance",
    "both_role_origin",
    "mixed_native_role_origin",
    "span_overlap",
)


@dataclass(frozen=True, slots=True)
class EntityPairContext:
    content_length: int
    sentence_spans: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if (self.content_length <= 0 or not self.sentence_spans or
                any(not 0 <= start < end <= self.content_length
                    for start, end in self.sentence_spans) or
                any(left[1] > right[0] for left, right in
                    zip(self.sentence_spans, self.sentence_spans[1:]))):
            raise ValueError("Entity pair context needs ordered source sentences")


@dataclass(frozen=True, slots=True)
class EntityPairMention:
    start: int
    end: int
    text: str
    entity_type: str | None
    origins: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreparedEntityPairMention:
    start: int
    end: int
    entity_type: str | None
    origins: frozenset[str]
    sentence_index: int
    surface: str
    alias: str
    bigrams: frozenset[str]


def prepare_entity_pair_mention(mention: EntityPairMention, context: EntityPairContext
                                ) -> PreparedEntityPairMention:
    """Compute reusable source primitives for one exact candidate."""
    if not 0 <= mention.start < mention.end <= context.content_length:
        raise ValueError("Entity pair mention coordinates differ from article")
    starts = tuple(start for start, _ in context.sentence_spans)
    sentence = bisect_right(starts, mention.start) - 1
    if sentence < 0 or mention.start >= context.sentence_spans[sentence][1]:
        raise ValueError("Entity pair mention has no containing sentence")
    surface = _surface(mention.text)
    alias = _alias(mention.text)
    return PreparedEntityPairMention(
        mention.start, mention.end, mention.entity_type,
        frozenset(mention.origins), sentence, surface, alias, _grams(alias))


def prepare_entity_pair_mentions(mentions: Sequence[EntityPairMention],
                                 context: EntityPairContext
                                 ) -> tuple[PreparedEntityPairMention, ...]:
    return tuple(prepare_entity_pair_mention(row, context) for row in mentions)


def build_entity_pair_features(left: PreparedEntityPairMention,
                               right: PreparedEntityPairMention,
                               context: EntityPairContext) -> tuple[float, ...]:
    """Return symmetric features in ENTITY_PAIR_FEATURE_NAMES order."""
    both_known = left.entity_type is not None and right.entity_type is not None
    overlap = max(left.start, right.start) < min(left.end, right.end)
    union = left.bigrams | right.bigrams
    left_native = bool(left.origins & {"NER", "NATIVE"})
    right_native = bool(right.origins & {"NER", "NATIVE"})
    left_role_only = "ROLE" in left.origins and not left_native
    right_role_only = "ROLE" in right.origins and not right_native
    return (
        float((left.start, left.end) == (right.start, right.end)),
        float(bool(left.surface and left.surface == right.surface)),
        float(bool(left.alias and left.alias == right.alias)),
        float(bool(left.alias and right.alias and
                   (left.alias in right.alias or right.alias in left.alias))),
        len(left.bigrams & right.bigrams) / len(union) if union else 0.0,
        float(both_known and left.entity_type == right.entity_type),
        float(both_known and left.entity_type != right.entity_type),
        float(not both_known),
        float(left.sentence_index == right.sentence_index),
        min(abs(left.sentence_index - right.sentence_index) / 8.0, 1.0),
        min(abs(left.start - right.start) / context.content_length, 1.0),
        float("ROLE" in left.origins and "ROLE" in right.origins),
        float((left_role_only and right_native) or
              (right_role_only and left_native)),
        float(overlap),
    )
