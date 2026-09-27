"""Train-only reviewed extraction negative의 권한과 provenance를 검증한다.

이 sidecar는 Gold를 보충하거나 바꾸지 않는다. Gold에 없는 후보를 자동 음성으로
만들지 않고, 사람이 검토한 exact candidate의 NEGATIVE/IGNORE 판정만 extraction
decision loss에 전달한다. PARTICIPANT 음성은 명시적 role_status=ABSENT에 한한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Mapping


SCHEMA_VERSION = "v3-reviewed-extraction-negative-authority-v1"
REVIEWED_KINDS = ("ENTITY", "TIME", "PARTICIPANT")
VERDICTS = ("POSITIVE", "NEGATIVE", "IGNORE", "OMISSION_SUSPECTED")
PARTICIPANT_ROLES = ("ACTOR", "TARGET", "PLACE")
PARTICIPANT_ROLE_STATUSES = ("PRESENT", "ABSENT", "PRESENT_UNLISTED", "UNKNOWN")
ENTITY_LABELS = ("PERSON", "ORGANIZATION", "LOCATION", "PRODUCT", "GENERIC")
ENTITY_EXISTENCE_SENTINEL = "ENTITY"
ENTITY_NEGATIVE_REASONS = (
    "REVIEWED_MENTION_ABSENT",  # legacy r05 authority
    "ENTITY_MALFORMED_NONREFERENTIAL_SPAN",
    "ENTITY_NONREFERENTIAL_PREDICATE",
    "ENTITY_OTHER_CERTAIN_NONMENTION",
)
TIME_NEGATIVE_REASONS = (
    "REVIEWED_MENTION_ABSENT",  # legacy r05 authority
    "TIME_NON_TEMPORAL_NUMBER",
    "TIME_ASPECT_OR_DISCOURSE_ONLY",
    "TIME_OTHER_CERTAIN_NONMENTION",
)
IGNORE_REASONS = (
    "VALID_NESTED_OR_REPEAT",
    "VALID_UNLISTED_ENTITY",
    "BOUNDARY_ONLY_NOT_EXISTENCE",
    "VALID_TIME_NOT_NEGATIVE",
    "ANNOTATION_OMISSION_SUSPECTED",
    "UNRESOLVED_OR_UNKNOWN",
    "ROLE_PRESENT_CANDIDATE_NEGATIVE_NOT_AUTHORIZED",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _exact_fields(payload: Mapping[str, object], expected: set[str], *, where: str) -> None:
    if set(payload) != expected:
        raise ValueError(f"{where}: fields differ: {sorted(set(payload) ^ expected)}")


def _nonempty(value: object, *, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where}: non-empty string required")
    return value


@dataclass(frozen=True, slots=True)
class ReviewedCandidate:
    """한 exact candidate에 대한 검토 판정. offset은 end-exclusive다."""

    candidate_id: str
    kind: str
    owner_id: str
    role: str | None
    role_status: str | None
    start: int
    end: int
    text: str
    proposed_label: str
    verdict: str
    reason: str
    responsibility: str
    related_gold_ids: tuple[str, ...]

    @classmethod
    def from_payload(cls, payload: Mapping[str, object], *, where: str) -> "ReviewedCandidate":
        _exact_fields(payload, {
            "candidate_id", "kind", "owner_id", "role", "role_status", "span",
            "proposed_label", "verdict", "reason", "responsibility",
            "related_gold_ids",
        }, where=where)
        span = payload["span"]
        if not isinstance(span, Mapping):
            raise ValueError(f"{where}.span: object required")
        _exact_fields(span, {"start", "end", "text"}, where=f"{where}.span")
        start, end, text = span["start"], span["end"], span["text"]
        if (not isinstance(start, int) or isinstance(start, bool)
                or not isinstance(end, int) or isinstance(end, bool)
                or not isinstance(text, str) or not 0 <= start < end
                or end - start != len(text)):
            raise ValueError(f"{where}.span: valid end-exclusive character span required")
        kind = _nonempty(payload["kind"], where=f"{where}.kind")
        verdict = _nonempty(payload["verdict"], where=f"{where}.verdict")
        role = payload["role"]
        role_status = payload["role_status"]
        related = payload["related_gold_ids"]
        if kind not in REVIEWED_KINDS or verdict not in VERDICTS:
            raise ValueError(f"{where}: unsupported kind or verdict")
        if role is not None and (not isinstance(role, str) or role not in PARTICIPANT_ROLES):
            raise ValueError(f"{where}.role: unsupported participant role")
        if role_status is not None and not isinstance(role_status, str):
            raise ValueError(f"{where}.role_status: string or null required")
        if (not isinstance(related, list)
                or any(not isinstance(value, str) or not value for value in related)):
            raise ValueError(f"{where}.related_gold_ids: string list required")
        proposed = _nonempty(payload["proposed_label"], where=f"{where}.proposed_label")
        reason = _nonempty(payload["reason"], where=f"{where}.reason")
        responsibility = _nonempty(payload["responsibility"],
                                   where=f"{where}.responsibility")
        if kind == "PARTICIPANT":
            if role not in PARTICIPANT_ROLES or proposed != role:
                raise ValueError(f"{where}: participant label must equal its role")
            if role_status not in PARTICIPANT_ROLE_STATUSES:
                raise ValueError(f"{where}: participant role status is not approved")
            if responsibility != "ROLE_FILLER_EXISTENCE":
                raise ValueError(f"{where}: participant responsibility differs")
            if verdict == "NEGATIVE" and (role_status != "ABSENT"
                                           or reason != "REVIEWED_ROLE_ABSENT"):
                raise ValueError(f"{where}: participant negative needs reviewed ABSENT authority")
        else:
            if role is not None or role_status is not None:
                raise ValueError(f"{where}: entity/time candidate cannot carry role status")
            if responsibility != "MENTION_EXISTENCE":
                raise ValueError(f"{where}: mention responsibility differs")
            if kind == "TIME" and proposed != "TIME":
                raise ValueError(f"{where}: TIME proposed label differs")
            if (kind == "ENTITY"
                    and proposed not in ENTITY_LABELS
                    and not (proposed == ENTITY_EXISTENCE_SENTINEL
                             and verdict != "POSITIVE")):
                raise ValueError(f"{where}: ENTITY proposed label differs")
            if (kind == "ENTITY" and verdict == "NEGATIVE"
                    and reason not in ENTITY_NEGATIVE_REASONS):
                raise ValueError(f"{where}: ENTITY negative reason differs")
            if (kind == "TIME" and verdict == "NEGATIVE"
                    and reason not in TIME_NEGATIVE_REASONS):
                raise ValueError(f"{where}: TIME negative reason differs")
        if verdict in ("IGNORE", "OMISSION_SUSPECTED") and reason not in IGNORE_REASONS:
            raise ValueError(f"{where}: IGNORE reason is not approved")
        if verdict == "POSITIVE" and reason != "CONFIRMED_GOLD":
            raise ValueError(f"{where}: sidecar positive may only confirm existing Gold")
        return cls(
            _nonempty(payload["candidate_id"], where=f"{where}.candidate_id"),
            kind,
            _nonempty(payload["owner_id"], where=f"{where}.owner_id"),
            role,
            role_status,
            start,
            end,
            text,
            proposed,
            verdict,
            reason,
            responsibility,
            tuple(related),
        )


@dataclass(frozen=True, slots=True)
class ReviewedArticle:
    article_id: str
    content_sha256: str
    candidates: tuple[ReviewedCandidate, ...]


@dataclass(frozen=True, slots=True)
class ReviewedNegativeAuthority:
    """검토자·버전·내용 digest가 고정된 train-only sidecar."""

    authority_id: str
    reviewer: str
    review_version: str
    articles: tuple[ReviewedArticle, ...]
    sha256: str

    @classmethod
    def from_json(cls, path: str | Path) -> "ReviewedNegativeAuthority":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "ReviewedNegativeAuthority":
        _exact_fields(payload, {
            "schema_version", "split", "authority_id", "reviewer",
            "review_version", "articles",
        }, where="sidecar")
        if payload["schema_version"] != SCHEMA_VERSION or payload["split"] != "train":
            raise ValueError("negative authority must use the approved train-only schema")
        article_rows = payload["articles"]
        if not isinstance(article_rows, list):
            raise ValueError("sidecar.articles: list required")
        articles: list[ReviewedArticle] = []
        seen_articles: set[str] = set()
        for article_index, row in enumerate(article_rows):
            where = f"sidecar.articles[{article_index}]"
            if not isinstance(row, Mapping):
                raise ValueError(f"{where}: object required")
            _exact_fields(row, {"article_id", "content_sha256", "candidates"}, where=where)
            article_id = _nonempty(row["article_id"], where=f"{where}.article_id")
            digest = _nonempty(row["content_sha256"], where=f"{where}.content_sha256")
            if article_id in seen_articles or not _SHA256.fullmatch(digest):
                raise ValueError(f"{where}: duplicate article or invalid content SHA")
            seen_articles.add(article_id)
            candidate_rows = row["candidates"]
            if not isinstance(candidate_rows, list):
                raise ValueError(f"{where}.candidates: list required")
            candidates = tuple(
                ReviewedCandidate.from_payload(candidate, where=f"{where}.candidates[{index}]")
                for index, candidate in enumerate(candidate_rows)
                if isinstance(candidate, Mapping)
            )
            if len(candidates) != len(candidate_rows):
                raise ValueError(f"{where}.candidates: every row must be an object")
            ids = [candidate.candidate_id for candidate in candidates]
            if len(ids) != len(set(ids)):
                raise ValueError(f"{where}: duplicate candidate ID")
            articles.append(ReviewedArticle(article_id, digest, candidates))
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")).encode()
        return cls(
            _nonempty(payload["authority_id"], where="sidecar.authority_id"),
            _nonempty(payload["reviewer"], where="sidecar.reviewer"),
            _nonempty(payload["review_version"], where="sidecar.review_version"),
            tuple(articles),
            sha256(canonical).hexdigest(),
        )

    def records_for(self, article_id: str, content_sha256: str) -> tuple[ReviewedCandidate, ...]:
        row = next((article for article in self.articles
                    if article.article_id == article_id), None)
        if row is None:
            return ()
        if row.content_sha256 != content_sha256:
            raise ValueError("negative authority content SHA differs from joined train article")
        return row.candidates
