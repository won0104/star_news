"""원문을 보존하는 128-token sentence/bridge view와 문자 경계 역매핑.

Layout은 한 요청에서만 소유한다. Gold가 없어도 같은 window를 생성하며, overlap은
절대 문자 좌표로 닫는다. 학습 target과 PUBLIC carrier는 이 객체를 보관하지 않는다.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from hashlib import sha256
import math
from typing import Any

from runtime.eventframe.preprocessing import split_sentence_spans


LAYOUT_POLICY = "v3-source-window-sentence-and-bridge-v1"
SENTENCE_SPLIT_CONTRACT = "runtime-eventframe-split-sentence-spans-v1"
SOURCE_PREPROCESSING_CONTRACT = "v3-pinned-fast-tokenizer-source-offsets-v1"


@dataclass(frozen=True, slots=True)
class RawArticle:
    article_id: str
    article_version_id: str
    content: str
    content_sha256: str
    published_at: str | None = None

    def __post_init__(self) -> None:
        if not self.article_id or not self.article_version_id or not self.content:
            raise ValueError("article identity, version and source content are required")
        if sha256(self.content.encode("utf-8")).hexdigest() != self.content_sha256:
            raise ValueError("raw article content SHA mismatch")


@dataclass(frozen=True, slots=True)
class WindowToken:
    position: int
    token_id: int
    start: int
    end: int
    source_index: int


@dataclass(frozen=True, slots=True)
class SourceWindow:
    window_id: str
    view: str
    sentence_index: int | None
    input_ids: tuple[int, ...]
    tokens: tuple[WindowToken, ...]

    def __post_init__(self) -> None:
        if self.view not in ("sentence", "bridge") or not self.tokens:
            raise ValueError("source window needs a nonempty declared view")
        if len(self.input_ids) > 128:
            raise ValueError("source window exceeds 128 model tokens")


@dataclass(frozen=True, slots=True)
class BoundaryRef:
    window_id: str
    token_position: int
    char_delta: int
    char_position: int


@dataclass(frozen=True, slots=True)
class SpanAlignment:
    start: int
    end: int
    text: str
    start_ref: BoundaryRef
    end_ref: BoundaryRef
    canonical_window_id: str | None
    cross_sentence: bool
    cross_window: bool
    subtoken_or_gap_boundary: bool


@dataclass(frozen=True, slots=True)
class WindowSpanPrediction:
    article_version_id: str
    window_id: str
    kind: str
    start: int
    end: int
    label: str | None
    score: float


def close_window_predictions(layout: "SourceLayout",
                             predictions: tuple[WindowSpanPrediction, ...]) -> tuple[WindowSpanPrediction, ...]:
    """overlap의 같은 절대 근거만 닫는다. 멀리 반복된 언급은 보존한다."""
    merged: dict[tuple[str, int, int, str | None], WindowSpanPrediction] = {}
    for row in predictions:
        if row.article_version_id != layout.article.article_version_id or row.window_id not in layout.window_lookup:
            raise ValueError("window prediction producer/article mismatch")
        if not math.isfinite(row.score) or not (0 <= row.start < row.end <= len(layout.article.content)):
            raise ValueError("invalid window prediction span or score")
        window = layout.window_lookup[row.window_id]
        if window.view != "bridge":
            raise ValueError("v3 source closure accepts bridge predictions only")
        first_index, last_index = window.tokens[0].source_index, window.tokens[-1].source_index
        covered_start = layout.bridge_tokens[first_index - 1].end if first_index else 0
        covered_end = (layout.bridge_tokens[last_index + 1].start
                       if last_index + 1 < len(layout.bridge_tokens) else len(layout.article.content))
        if not (covered_start <= row.start < row.end <= covered_end):
            raise ValueError("prediction span falls outside its source window")
        key = layout.closure_key(row.kind, row.start, row.end, row.label)
        old = merged.get(key)
        if old is None or (row.score, row.window_id) > (old.score, old.window_id):
            merged[key] = row
    return tuple(merged[key] for key in sorted(merged, key=lambda value: (value[0], value[1], value[2], value[3] or "")))


@dataclass(frozen=True, slots=True)
class SourceLayout:
    article: RawArticle
    tokenizer_sha256: str
    windows: tuple[SourceWindow, ...]
    sentence_spans: tuple[tuple[int, int], ...]
    bridge_tokens: tuple[WindowToken, ...]
    bridge_token_starts: tuple[int, ...]
    bridge_token_ends: tuple[int, ...]
    bridge_windows_by_token: tuple[tuple[str, ...], ...]
    window_lookup: dict[str, SourceWindow]
    sentence_windows_by_index: tuple[tuple[tuple[int, SourceWindow], ...], ...]
    _runtime_source_tokens: dict[tuple[str, int], WindowToken] = field(
        default_factory=dict, compare=False, repr=False)
    _runtime_sentence_starts: tuple[int, ...] = field(default=(), compare=False, repr=False)
    _runtime_sentence_max_ends: tuple[int, ...] = field(default=(), compare=False, repr=False)
    _runtime_alignments: dict[tuple[int, int], SpanAlignment] = field(
        default_factory=dict, compare=False, repr=False)

    def align(self, span: dict[str, Any]) -> SpanAlignment:
        start, end, text = int(span["start"]), int(span["end"]), str(span["text"])
        if not (0 <= start < end <= len(self.article.content)) or self.article.content[start:end] != text:
            raise ValueError("Gold span does not round-trip to source content")
        # Global source-token index, not article number or Gold ID, is the alignment authority.
        if not self.bridge_tokens:
            raise ValueError("article has no source tokens")
        start_token = self.bridge_tokens[min(bisect_right(self.bridge_token_ends, start), len(self.bridge_tokens) - 1)]
        end_token = self.bridge_tokens[max(bisect_left(self.bridge_token_starts, end) - 1, 0)]
        if start_token.source_index > end_token.source_index:
            end_token = start_token
        start_ids = self.bridge_windows_by_token[start_token.source_index]
        end_ids = self.bridge_windows_by_token[end_token.source_index]
        common = [window_id for window_id in start_ids if window_id in end_ids]
        if common:
            start_window = end_window = self.window_lookup[common[0]]
            canonical = common[0]
        else:
            start_window, end_window, canonical = self.window_lookup[start_ids[0]], self.window_lookup[end_ids[0]], None
        def ref(window: SourceWindow, source_index: int, char: int, side: str) -> BoundaryRef:
            token = next(t for t in window.tokens if t.source_index == source_index)
            base = token.start if side == "start" else token.end
            return BoundaryRef(window.window_id, token.position, char - base, char)
        first_ref = ref(start_window, start_token.source_index, start, "start")
        last_ref = ref(end_window, end_token.source_index, end, "end")
        cross_sentence = not any(a <= start and end <= b for a, b in self.sentence_spans)
        aligned = SpanAlignment(start, end, text, first_ref, last_ref, canonical,
                                cross_sentence, canonical is None,
                                start != start_token.start or end != end_token.end)
        if self.reconstruct(aligned) != (start, end, text):
            raise AssertionError("source span alignment lost exact character coordinates")
        return aligned

    def align_runtime(self, start: int, end: int) -> SpanAlignment:
        """Align an exact source coordinate through request-owned token indexes.

        Window choice is the same source-only rule as ``align``. Retrieval
        provenance never participates in the choice. The bounded cache retains
        only recently reused coordinates and is cleared with the request.
        """
        if not 0 <= start < end <= len(self.article.content):
            raise ValueError("Gold span does not round-trip to source content")
        key = start, end
        cached = self._runtime_alignments.get(key)
        if cached is not None:
            return cached
        if not self.bridge_tokens:
            raise ValueError("article has no source tokens")
        if not self._runtime_source_tokens:
            self._runtime_source_tokens.update(
                ((window.window_id, token.source_index), token)
                for window in self.windows for token in window.tokens)
            sentence_ranges = sorted(self.sentence_spans)
            max_end = -1
            prefix_max_ends = []
            for _first, last in sentence_ranges:
                max_end = max(max_end, last)
                prefix_max_ends.append(max_end)
            object.__setattr__(self, "_runtime_sentence_starts",
                               tuple(first for first, _last in sentence_ranges))
            object.__setattr__(self, "_runtime_sentence_max_ends",
                               tuple(prefix_max_ends))
        start_token = self.bridge_tokens[min(
            bisect_right(self.bridge_token_ends, start), len(self.bridge_tokens) - 1)]
        end_token = self.bridge_tokens[max(
            bisect_left(self.bridge_token_starts, end) - 1, 0)]
        if start_token.source_index > end_token.source_index:
            end_token = start_token
        start_ids = self.bridge_windows_by_token[start_token.source_index]
        end_ids = self.bridge_windows_by_token[end_token.source_index]
        canonical = next((window_id for window_id in start_ids if window_id in end_ids), None)
        start_window_id = canonical or start_ids[0]
        end_window_id = canonical or end_ids[0]
        first = self._runtime_source_tokens[start_window_id, start_token.source_index]
        last = self._runtime_source_tokens[end_window_id, end_token.source_index]
        sentence_index = bisect_right(self._runtime_sentence_starts, start) - 1
        same_sentence = (sentence_index >= 0 and
                         end <= self._runtime_sentence_max_ends[sentence_index])
        aligned = SpanAlignment(
            start, end, self.article.content[start:end],
            BoundaryRef(start_window_id, first.position, start - first.start, start),
            BoundaryRef(end_window_id, last.position, end - last.end, end),
            canonical, not same_sentence, canonical is None,
            start != start_token.start or end != end_token.end,
        )
        if len(self._runtime_alignments) >= 4096:
            self._runtime_alignments.pop(next(iter(self._runtime_alignments)))
        self._runtime_alignments[key] = aligned
        return aligned

    def clear_runtime_indexes(self) -> None:
        """Release request-local alignment indexes after the final consumer."""
        self._runtime_source_tokens.clear()
        self._runtime_alignments.clear()
        object.__setattr__(self, "_runtime_sentence_starts", ())
        object.__setattr__(self, "_runtime_sentence_max_ends", ())

    def reconstruct(self, aligned: SpanAlignment) -> tuple[int, int, str]:
        start_token = next(t for t in self.window_lookup[aligned.start_ref.window_id].tokens if t.position == aligned.start_ref.token_position)
        end_token = next(t for t in self.window_lookup[aligned.end_ref.window_id].tokens if t.position == aligned.end_ref.token_position)
        start = start_token.start + aligned.start_ref.char_delta
        end = end_token.end + aligned.end_ref.char_delta
        return (start, end, self.article.content[start:end])

    @staticmethod
    def closure_key(kind: str, start: int, end: int, label: str | None = None) -> tuple[str, int, int, str | None]:
        """겹치는 window의 같은 근거만 닫고 반복 occurrence는 좌표로 구별한다."""
        return kind, start, end, label


class LayoutBuilder:
    """고정 fast tokenizer에서 Gold와 독립적인 sentence/bridge window를 만든다."""

    def __init__(self, tokenizer: Any, *, tokenizer_sha256: str,
                 max_model_tokens: int = 128, stride: int = 64) -> None:
        if not getattr(tokenizer, "is_fast", False):
            raise ValueError("exact source alignment requires a fast tokenizer")
        special = tokenizer.num_special_tokens_to_add(pair=False)
        if max_model_tokens != 128 or not 0 < stride < max_model_tokens - special:
            raise ValueError("v3 layout uses 128-token windows and a valid overlap stride")
        self.tokenizer = tokenizer
        self.tokenizer_sha256 = tokenizer_sha256
        self.capacity = max_model_tokens - special
        self.stride = stride
        probe = next(index for index in range(tokenizer.vocab_size) if index not in tokenizer.all_special_ids)
        probe_input = tokenizer.build_inputs_with_special_tokens([probe])
        if probe_input.count(probe) != 1:
            raise ValueError("tokenizer cannot locate contiguous source tokens")
        self.source_prefix = probe_input.index(probe)

    def build(self, article: RawArticle) -> SourceLayout:
        sentences = split_sentence_spans(article.content)
        if not sentences:
            raise ValueError("article has no nonblank sentence")
        windows: list[SourceWindow] = []
        for sentence_index, sentence in enumerate(sentences):
            ids, offsets = self._tokens(sentence.text, sentence.start)
            windows.extend(self._windows(ids, offsets, "sentence", sentence_index))
        ids, offsets = self._tokens(article.content, 0)
        windows.extend(self._windows(ids, offsets, "bridge", None))
        if not any(window.view == "bridge" for window in windows):
            raise ValueError("article contains no tokenizer source tokens")
        bridges = [window for window in windows if window.view == "bridge"]
        tokens = {token.source_index: token for window in bridges for token in window.tokens}
        by_token = [[] for _ in tokens]
        for window in bridges:
            for token in window.tokens:
                by_token[token.source_index].append(window.window_id)
        ordered = tuple(tokens[index] for index in sorted(tokens))
        starts, ends = tuple(token.start for token in ordered), tuple(token.end for token in ordered)
        if starts != tuple(sorted(starts)) or ends != tuple(sorted(ends)):
            raise ValueError("tokenizer offsets are not monotonic")
        sentence_windows: list[list[tuple[int, SourceWindow]]] = [
            [] for _ in sentences]
        for index, window in enumerate(windows):
            if window.view == "sentence":
                sentence_windows[window.sentence_index].append((index, window))
        return SourceLayout(article, self.tokenizer_sha256, tuple(windows),
                            tuple((s.start, s.end) for s in sentences),
                            ordered, starts, ends,
                            tuple(tuple(ids) for ids in by_token),
                            {window.window_id: window for window in windows},
                            tuple(tuple(rows) for rows in sentence_windows))

    def _tokens(self, text: str, offset: int) -> tuple[list[int], list[tuple[int, int]]]:
        encoded = self.tokenizer(text, add_special_tokens=False, truncation=False,
                                 return_offsets_mapping=True, verbose=False)
        ids = list(encoded["input_ids"])
        ranges = [(offset + int(a), offset + int(b)) for a, b in encoded["offset_mapping"]]
        if len(ids) != len(ranges) or any(a >= b for a, b in ranges):
            raise ValueError("tokenizer produced missing/empty source offsets")
        return ids, ranges

    def _windows(self, ids: list[int], offsets: list[tuple[int, int]],
                 view: str, sentence_index: int | None) -> list[SourceWindow]:
        output = []
        for start in range(0, len(ids), self.stride):
            chunk_ids = ids[start:start + self.capacity]
            if not chunk_ids:
                break
            input_ids = tuple(self.tokenizer.build_inputs_with_special_tokens(chunk_ids))
            source_positions = range(self.source_prefix, self.source_prefix + len(chunk_ids))
            if input_ids[self.source_prefix:self.source_prefix + len(chunk_ids)] != tuple(chunk_ids):
                raise ValueError("source token count differs after special tokens")
            tokens = tuple(WindowToken(position, int(token_id), *offsets[start + index], start + index)
                           for index, (position, token_id) in enumerate(zip(source_positions, chunk_ids)))
            prefix = f"S{sentence_index:04d}" if view == "sentence" else "B"
            output.append(SourceWindow(f"{prefix}:{start:06d}", view, sentence_index, input_ids, tokens))
            if start + self.capacity >= len(ids):
                break
        return output
