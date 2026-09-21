"""Gold-free article segmentation, tokenization, and absolute offset preservation."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

import torch

from models.contracts import ArticleBatch

from .contracts import ArticleInput, TokenAlignmentError
from .resolved_contracts import GroundingRef


@dataclass(frozen=True, slots=True)
class PreparedArticle:
    article: ArticleInput
    batch: ArticleBatch
    sentences: tuple[Mapping[str, Any], ...]

    def source_ref(self, char_start: int, char_end: int,
                   sentence_index: int | None = None) -> GroundingRef:
        """원문 값을 후보 row에 복사하지 않고 version+absolute offset으로 참조한다."""

        return GroundingRef(
            self.article.article_version_id, char_start, char_end, sentence_index,
        )

    def grounding_text(self, char_start: int, char_end: int,
                       sentence_index: int | None = None) -> str:
        return self.source_ref(char_start, char_end, sentence_index).text(
            article_version_id=self.article.article_version_id,
            source_text=self.article.content,
        )


class RuntimePreprocessor:
    """Build the verified target-free tokenizer layout without importing training code."""

    def __init__(self, tokenizer: Any, *, max_sentence_tokens: int = 128) -> None:
        self.tokenizer = tokenizer
        self.max_sentence_tokens = max_sentence_tokens

    def prepare(self, article: ArticleInput) -> PreparedArticle:
        spans = split_sentence_spans(article.content)
        encoded = self._tokenize(spans)
        sentence_count = len(spans)
        batch = ArticleBatch(
            encoded["input_ids"][None],
            encoded["attention_mask"][None],
            encoded["source_token_mask"][None],
            torch.ones(1, sentence_count, dtype=torch.bool),
            torch.arange(sentence_count, dtype=torch.long)[None],
            encoded["token_offsets"][None],
            encoded["sentence_offsets"][None],
            (article.article_id,),
            (article.content,),
            (article.published_at,),
        )
        batch.validate()
        sentences = []
        for index, span in enumerate(spans):
            active = torch.nonzero(encoded["source_token_mask"][index], as_tuple=False).flatten()
            positions = active.tolist()
            offsets = encoded["token_offsets"][index, active].tolist()
            tokens = []
            for position, (local_start, local_end) in zip(positions, offsets):
                char_start = span.start + int(local_start)
                char_end = span.start + int(local_end)
                text = article.content[char_start:char_end]
                if not text:
                    raise TokenAlignmentError(f"empty source token at sentence {index}, token {position}")
                tokens.append(
                    {
                        "token_index": position,
                        "start": char_start,
                        "end": char_end,
                        "text": text,
                    }
                )
            sentences.append(
                {
                    "sentence_index": index,
                    "sentence_id": f"S{index:04d}:{span.start}-{span.end}",
                    "start": span.start,
                    "end": span.end,
                    "text": span.text,
                    "positions": positions,
                    "offsets": offsets,
                    "source_token_indices": positions,
                    "valid_start_token_indices": positions,
                    "valid_end_token_indices": positions,
                    "source_token_count": len(positions),
                    "character_count": span.end - span.start,
                    "tokens": tokens,
                }
            )
        self.validate_offsets(article, tuple(sentences))
        return PreparedArticle(article, batch, tuple(sentences))

    def _tokenize(self, spans: tuple[SentenceSpan, ...]) -> dict[str, torch.Tensor]:
        """Preserve the former ``ArticleCollator._tokenize`` tensor contract exactly."""

        if not getattr(self.tokenizer, "is_fast", False):
            raise ValueError("exact offset runtime requires a fast tokenizer")
        rows = []
        for sentence in spans:
            encoded = self.tokenizer(
                sentence.text,
                padding="max_length",
                truncation=True,
                max_length=self.max_sentence_tokens,
                return_offsets_mapping=True,
                return_special_tokens_mask=True,
                return_tensors="pt",
            )
            rows.append(
                (
                    encoded["input_ids"][0].long(),
                    encoded["attention_mask"][0].bool(),
                    encoded["special_tokens_mask"][0].bool(),
                    encoded["offset_mapping"][0].long(),
                    torch.tensor((sentence.start, sentence.end), dtype=torch.long),
                )
            )
        if not rows:
            raise ValueError("article has no tokenizable sentence")
        input_ids = torch.stack([row[0] for row in rows])
        attention_mask = torch.stack([row[1] for row in rows])
        special = torch.stack([row[2] for row in rows])
        offsets = torch.stack([row[3] for row in rows])
        source_token_mask = attention_mask & ~special & offsets.ne(0).any(dim=-1)
        offsets = torch.where(
            source_token_mask.unsqueeze(-1), offsets, torch.full_like(offsets, -1)
        )
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "source_token_mask": source_token_mask,
            "token_offsets": offsets,
            "sentence_offsets": torch.stack([row[4] for row in rows]),
        }

    @staticmethod
    def validate_offsets(article: ArticleInput, sentences: tuple[Mapping[str, Any], ...]) -> None:
        for sentence in sentences:
            if article.content[sentence["start"] : sentence["end"]] != sentence["text"]:
                raise TokenAlignmentError("sentence absolute offset round-trip failed")
            for token in sentence["tokens"]:
                if article.content[token["start"] : token["end"]] != token["text"]:
                    raise TokenAlignmentError("token absolute offset round-trip failed")


def token_to_character_span(
    content: str,
    sentence: Mapping[str, Any],
    token_start: int,
    token_end: int,
) -> tuple[int, int, str]:
    tokens = {int(item["token_index"]): item for item in sentence["tokens"]}
    if token_start not in tokens or token_end - 1 not in tokens:
        raise TokenAlignmentError(
            f"token span [{token_start},{token_end}) has no source offset in sentence {sentence['sentence_index']}"
        )
    start = int(tokens[token_start]["start"])
    end = int(tokens[token_end - 1]["end"])
    return start, end, content[start:end]


@dataclass(frozen=True, slots=True)
class SentenceSpan:
    text: str
    start: int
    end: int


_DECIMAL = re.compile(r"(?<![\w.])\d+(?:\.\d+)+(?:%|[A-Za-z가-힣]+)?")
_EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"']+")
_URL_TRAILING = ".,;:!?)]}”’"
_TERMINATORS = ".!?"
_CLOSINGS = "\"')]}”’」』】〉》"


def split_sentence_spans(text: str) -> tuple[SentenceSpan, ...]:
    """Deterministic sentence spans copied from the verified training utility contract."""

    if not text:
        return ()
    protected = _protected_ranges(text)
    output: list[SentenceSpan] = []
    segment_start = 0
    index = 0
    while index < len(text):
        if text[index] in _TERMINATORS and not _protected(index, protected):
            end = index + 1
            while end < len(text) and text[end] in _TERMINATORS and not _protected(end, protected):
                end += 1
            while end < len(text) and text[end] in _CLOSINGS:
                end += 1
            _append(output, text, segment_start, end)
            segment_start, index = end, end
        else:
            index += 1
    _append(output, text, segment_start, len(text))
    return tuple(output)


def _protected_ranges(text: str) -> tuple[tuple[int, int], ...]:
    ranges = [
        (match.start(), match.end())
        for pattern in (_DECIMAL, _EMAIL)
        for match in pattern.finditer(text)
    ]
    for match in _URL.finditer(text):
        end = match.end()
        while end > match.start() and text[end - 1] in _URL_TRAILING:
            end -= 1
        ranges.append((match.start(), end))
    return tuple(sorted(ranges))


def _protected(index: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= index < end for start, end in ranges)


def _append(output: list[SentenceSpan], text: str, start: int, end: int) -> None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start < end:
        span = SentenceSpan(text[start:end], start, end)
        if text[span.start : span.end] != span.text:
            raise AssertionError("sentence offset round-trip failed")
        output.append(span)
