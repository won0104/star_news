"""Step 6 structural token/window and character-boundary selector.

This is the single selector source for offline shadow and explicit bounded Entity
runtime. It visits inexpensive token/boundary coordinates before any span model;
Gold, fine logits, Entity identity, and fallback decisions are outside its scope.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re


TIME_CUES = re.compile(
    r"\d|년|월|일|시|분|초|주|최근|지난|다음|오늘|내일|어제|당시|이날|전날|"
    r"동안|기간|매일|매주|매월|매년|오전|오후|새벽|하반기|상반기|이후|이전"
)
NONWORD = re.compile(r"[\s\W]", re.UNICODE)
FROZEN_FINE_SHA256 = "8437157e51f42973c0c61fa4c0b7f5d466ceb9480f118044f13ad6790920fc96"
FROZEN_PRIORITY_SHA256 = "544fa6f1570c6bbb7808be6d72db0710a472417ff5066f955a87831701ff93f6"


@dataclass(frozen=True, slots=True)
class Lane:
    name: str
    max_tokens: int
    max_chars: int
    chunk: int
    typed_labels: int


@dataclass(frozen=True, slots=True)
class Budget:
    policy_id: str
    token_multiplier: int | None
    window_cap: int | None
    global_reserve_fraction: float
    boundary_options: int | None


@dataclass(frozen=True, slots=True)
class EntitySpanBoundedContract:
    """Pinned explicit T14/C6 budget; never selected by default v2.2 config."""

    budget: Budget
    selector_sha256: str
    config_sha256: str
    config_path: Path
    fine_checkpoint_sha256: str
    priority_checkpoint_sha256: str

    @property
    def policy_id(self) -> str:
        return self.budget.policy_id

    @classmethod
    def from_config(cls, path: str | Path) -> "EntitySpanBoundedContract":
        file = Path(path).resolve()
        raw = file.read_bytes()
        payload = json.loads(raw)
        budget = Budget(**payload["budget"])
        selector_digest = sha256(Path(__file__).read_bytes()).hexdigest()
        if (payload.get("schema_version") != "articlelocal-bcr-entity-span-budget-v1"
            or payload.get("mode") != "EXPLICIT_BOUNDED_ONLY"
            or payload.get("source_step65_recommendation")
               != "RECOMMEND_FOR_STEP7"
            or budget != Budget("STRUCTURAL_T14_C6", 14, 1536, 0.125, 6)
            or payload.get("selector_source_path")
               != "runtime/candidate_routing/span_budget.py"
            or payload.get("selector_source_sha256") != selector_digest
            or payload.get("fine_checkpoint_sha256") != FROZEN_FINE_SHA256
            or payload.get("priority_checkpoint_sha256") != FROZEN_PRIORITY_SHA256
            or float(payload.get("fine_threshold", -1)) != 0.7
            or float(payload.get("priority_threshold", -1)) != 0.3
            or payload.get("fine_feature_denominator_tokens") != 20
            or payload.get("fine_feature_denominator_characters") != 56
            or payload.get("projection_cache_scope") != "SELECTED_CHUNK_ONLY"
            or payload.get("published") is not False):
            raise ValueError("Entity bounded T14/C6 policy/source contract differs")
        return cls(budget, selector_digest, sha256(raw).hexdigest(), file,
                   payload["fine_checkpoint_sha256"],
                   payload["priority_checkpoint_sha256"])

    def validate(self) -> None:
        if (self.budget != Budget("STRUCTURAL_T14_C6", 14, 1536, 0.125, 6)
            or sha256(Path(__file__).read_bytes()).hexdigest() != self.selector_sha256
            or sha256(self.config_path.read_bytes()).hexdigest() != self.config_sha256):
            raise ValueError("Entity bounded policy/source changed after load")


def pair_candidate_count(left: dict, right: dict, max_chars: int) -> int:
    """Character start×end의 유효 조합 수를 product materialization 없이 센다."""
    count = 0
    for start in range(int(left["start"]), int(left["end"])):
        minimum = max(int(right["start"]) + 1, start + 1)
        maximum = min(int(right["end"]), start + max_chars)
        count += max(maximum - minimum + 1, 0)
    return count


def token_pairs(prepared, lane: Lane) -> tuple[list[dict], dict]:
    pairs = []
    widths = Counter()
    candidate_count = boundary_variant_count = considered = 0
    for sentence in prepared.sentences:
        tokens = sentence["tokens"]
        for left_index, left in enumerate(tokens):
            for right_index in range(left_index,
                                     min(len(tokens), left_index + lane.max_tokens)):
                right = tokens[right_index]
                considered += 1
                valid_count = pair_candidate_count(left, right, lane.max_chars)
                if not valid_count:
                    continue
                width = right_index - left_index + 1
                widths[width] += valid_count
                candidate_count += valid_count
                boundary_valid = int(
                    int(right["end"]) - int(left["start"]) <= lane.max_chars
                )
                boundary_variant_count += valid_count - boundary_valid
                text = prepared.article.content[int(left["start"]):int(right["end"])]
                score = (8.0 / (1.0 + width)
                         + 0.08 * float(len(text) <= lane.max_chars)
                         + 0.05 * float(text[:1].isalnum() and text[-1:].isalnum()))
                if lane.name == "TIME":
                    score += 2.0 * float(bool(TIME_CUES.search(text)))
                else:
                    score += 0.12 * float(any(char.isdigit() for char in text))
                pairs.append({
                    "key": (int(sentence["sentence_index"]), int(left["token_index"]),
                            int(right["token_index"]) + 1),
                    "sentence": int(sentence["sentence_index"]),
                    "left": left, "right": right, "width": width,
                    "source_token_count": len(tokens),
                    "valid_count": valid_count, "rank": score,
                })
    return pairs, {
        "considered_token_span_count": considered,
        "eligible_token_span_count": len(pairs),
        "candidate_count": candidate_count,
        "character_boundary_variant_count": boundary_variant_count,
        "token_width_counts": dict(sorted(widths.items())),
    }


def unary_positions(content: str, token: dict, *, start: bool,
                    cap: int | None) -> tuple[tuple[int, ...], int]:
    begin, end = int(token["start"]), int(token["end"])
    positions = range(begin, end) if start else range(begin + 1, end + 1)

    def rank(position: int) -> tuple[float, int]:
        full = position == (begin if start else end)
        previous = content[position - 1] if position else ""
        following = content[position] if position < len(content) else ""
        split = bool(previous and following and (
            bool(NONWORD.match(previous)) or bool(NONWORD.match(following))
            or previous.isdigit() != following.isdigit()
        ))
        return (10.0 * full + 2.0 * split
                - min(position - begin, end - position) * 0.1,
                -position if start else position)

    ordered = sorted(positions, key=rank, reverse=True)
    return tuple(ordered[:cap] if cap is not None else ordered), len(ordered)


def selected_token_keys(pairs: list[dict], budget: Budget) -> set[tuple[int, int, int]]:
    if budget.token_multiplier is None:
        return {pair["key"] for pair in pairs}
    by_sentence = defaultdict(list)
    for pair in pairs:
        by_sentence[pair["sentence"]].append(pair)
    selected = set()
    ordering = lambda row: (-row["rank"], row["width"], row["key"])
    for sentence_pairs in by_sentence.values():
        quota = min(budget.window_cap,
                    budget.token_multiplier * sentence_pairs[0]["source_token_count"])
        selected.update(row["key"] for row in sorted(sentence_pairs, key=ordering)[:quota])
    global_quota = math.ceil(budget.global_reserve_fraction * len(pairs))
    selected.update(row["key"] for row in sorted(pairs, key=ordering)[:global_quota])
    return selected


def selected_boundaries(prepared, pairs: list[dict], lane: Lane,
                        budget: Budget) -> tuple[dict, dict]:
    token_keys = selected_token_keys(pairs, budget)
    boundaries = {}
    census = Counter()
    census["token_span_cheaply_ranked"] = len(pairs)
    census["token_span_retained"] = len(token_keys)
    content = prepared.article.content
    for pair in pairs:
        if pair["key"] not in token_keys:
            continue
        starts, start_visit = unary_positions(
            content, pair["left"], start=True, cap=budget.boundary_options
        )
        ends, end_visit = unary_positions(
            content, pair["right"], start=False, cap=budget.boundary_options
        )
        census["cheap_boundary_position_visited"] += start_visit + end_visit
        census["cheap_character_cross_pair_visited"] += len(starts) * len(ends)
        valid = sum(0 < end - start <= lane.max_chars
                    for start in starts for end in ends)
        # source offset 범위와 width만 본다. Fine head와 Gold는 사용하지 않는다.
        if valid:
            census["fine_candidate_rows"] += valid
            census["unique_expensive_token_projection_keys"] += 1
            boundaries[pair["key"]] = (set(starts), set(ends))
    return boundaries, dict(census)
