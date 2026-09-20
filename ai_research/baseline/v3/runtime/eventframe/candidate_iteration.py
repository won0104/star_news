"""기존 span universe와 정렬 순서를 유지하는 문장별 후보 스트림.

scorer 경로는 offset과 작은 수치 feature만 받고, 원문 text는 승인 시점에
단일 기사 source에서 만든다. 기존 공개 enumerator의 list/text 계약은 유지한다.
"""

from __future__ import annotations

from collections import defaultdict
from heapq import merge
from itertools import islice
from typing import Iterator


def _token_pair_rows(sentence, left, right, *, token_width: int,
                     max_token_width: int, max_character_width: int,
                     character_boundaries: bool,
                     selected_starts=None, selected_ends=None) -> Iterator[dict]:
    if selected_starts is not None:
        starts = sorted(selected_starts)
    elif character_boundaries:
        starts = range(int(left["start"]), int(left["end"]))
    else:
        starts = (int(left["start"]),)
    if selected_ends is not None:
        ends = sorted(selected_ends)
    elif character_boundaries:
        ends = range(int(right["start"]) + 1, int(right["end"]) + 1)
    else:
        ends = (int(right["end"]),)
    left_width = max(int(left["end"]) - int(left["start"]), 1)
    right_width = max(int(right["end"]) - int(right["start"]), 1)
    for char_start in starts:
        for char_end in ends:
            char_width = char_end - char_start
            if char_width <= 0 or char_width > max_character_width:
                continue
            yield {
                "sentence_index": int(sentence["sentence_index"]),
                "sentence_id": sentence["sentence_id"],
                "token_start": int(left["token_index"]),
                "token_end": int(right["token_index"]) + 1,
                "char_start": int(char_start),
                "char_end": int(char_end),
                "boundary_features": (
                    (char_start - int(left["start"])) / left_width,
                    (char_end - int(right["start"])) / right_width,
                    char_width / max_character_width,
                    token_width / max_token_width,
                ),
            }


def iter_span_candidates(prepared, *, max_token_width: int,
                         max_character_width: int,
                         character_boundaries: bool) -> Iterator[dict]:
    """기존 stable sort의 (sentence, char_start, char_end) 순서로 한 문장씩 생성한다."""

    for sentence in sorted(prepared.sentences, key=lambda row: row["sentence_index"]):
        tokens = sentence["tokens"]
        sources = (
            _token_pair_rows(
                sentence, left, tokens[right_index],
                token_width=right_index - left_index + 1,
                max_token_width=max_token_width,
                max_character_width=max_character_width,
                character_boundaries=character_boundaries,
            )
            for left_index, left in enumerate(tokens)
            for right_index in range(
                left_index, min(len(tokens), left_index + max_token_width)
            )
        )
        yield from merge(*sources, key=lambda row: (row["char_start"], row["char_end"]))


def iter_candidate_chunks(rows: Iterator[dict], chunk_size: int) -> Iterator[list[dict]]:
    if chunk_size <= 0:
        raise ValueError("candidate chunk size must be positive")
    while chunk := list(islice(rows, chunk_size)):
        yield chunk


def iter_bounded_span_candidates(prepared, boundaries: dict, *,
                                 max_token_width: int,
                                 max_character_width: int) -> Iterator[dict]:
    """Use only selected token keys and character positions before fine packing.

    The original row/feature builder and stable sentence/offset order are shared
    with the broad iterator. Per-left merges bound the number of live generators.
    """
    selected_by_sentence = defaultdict(list)
    for (sentence_index, left_index, right_exclusive), options in boundaries.items():
        selected_by_sentence[sentence_index].append((left_index, right_exclusive, options))
    for sentence in sorted(prepared.sentences, key=lambda row: row["sentence_index"]):
        tokens = {int(row["token_index"]): row for row in sentence["tokens"]}
        by_left: dict[int, list[tuple[int, tuple[set, set]]]] = {}
        for left_index, right_exclusive, options in selected_by_sentence[
            sentence["sentence_index"]
        ]:
            if (left_index not in tokens or right_exclusive - 1 not in tokens
                or not 0 < right_exclusive - left_index <= max_token_width):
                raise ValueError("bounded token-span key differs from prepared article")
            by_left.setdefault(left_index, []).append((right_exclusive, options))
        left_sources = []
        for left_index, rights in sorted(by_left.items()):
            pair_sources = (
                _token_pair_rows(
                    sentence, tokens[left_index], tokens[right_exclusive - 1],
                    token_width=right_exclusive - left_index,
                    max_token_width=max_token_width,
                    max_character_width=max_character_width,
                    character_boundaries=True,
                    selected_starts=options[0], selected_ends=options[1],
                )
                for right_exclusive, options in sorted(rights)
            )
            left_sources.append(merge(*pair_sources,
                                      key=lambda row: (row["char_start"], row["char_end"])))
        yield from merge(*left_sources, key=lambda row: (row["char_start"], row["char_end"]))
