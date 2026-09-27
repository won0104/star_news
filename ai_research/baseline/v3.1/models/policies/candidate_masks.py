"""Candidate descriptor와 학습 가능한 scorer에 전달할 관찰 feature.

이 파일은 pair를 제거하지 않는다. 구조적 eligibility, 학습 sampling, runtime pruning은
각각 ``eligibility.py``, ``sampling.py``, ``pruning.py``의 독립 책임이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True, slots=True)
class CandidateDescriptor:
    candidate_id: str
    kind: str
    sentence_index: int
    start: int
    end: int
    text: str
    label: str = ""
    entity_type: str | None = None
    trigger: str | None = None


class PairFeatureExtractor:
    """Hard mask로 쓰지 않는 관찰 feature 네 개를 계산한다.

    반환 순서는 containment, surface similarity, same entity type,
    inverse sentence distance다. 이 값들은 scorer와 optional sampler/pruner의
    ranking signal이며 baseline EligibilityMask에는 관여하지 않는다.
    """

    feature_names = (
        "containment",
        "surface_similarity",
        "same_entity_type",
        "inverse_sentence_distance",
    )

    def features(
        self,
        source: CandidateDescriptor,
        target: CandidateDescriptor,
    ) -> tuple[float, float, float, float]:
        distance = abs(source.sentence_index - target.sentence_index)
        same_type = (
            source.entity_type is not None
            and target.entity_type is not None
            and source.entity_type == target.entity_type
        )
        return (
            float(_contains(source, target) or _contains(target, source)),
            _surface_similarity(source.text, target.text),
            float(same_type),
            1.0 / (1.0 + distance),
        )


def _contains(container: CandidateDescriptor, item: CandidateDescriptor) -> bool:
    return container.start <= item.start and item.end <= container.end


def _normalized(text: str) -> str:
    return "".join(character.lower() for character in text if character.isalnum())


def _surface_similarity(left: str, right: str) -> float:
    left_norm, right_norm = _normalized(left), _normalized(right)
    if not left_norm or not right_norm:
        return 0.0
    return float(SequenceMatcher(None, left_norm, right_norm).ratio())
