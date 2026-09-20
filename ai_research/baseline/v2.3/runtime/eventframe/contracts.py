"""JSON-safe contracts for the canonical EventFrame runtime.

Character spans are Unicode-code-point offsets in half-open ``[start, end)`` form.
Lane status is explicit so an empty execution result is never confused with a lane
that was not run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping


LANE_STATUSES = ("EXECUTED", "EMPTY", "NOT_RUN", "BLOCKED", "UNRESOLVED", "ERROR")


@dataclass(frozen=True, slots=True)
class ArticleInput:
    article_id: str
    content: str
    published_at: str
    article_version_id: str | None = None
    title: str | None = None
    source: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.article_id, str) or not self.article_id:
            raise ValueError("article_id must be a non-empty string")
        if not isinstance(self.content, str) or not self.content:
            raise ValueError("content must be non-empty offset source-of-truth text")
        if not isinstance(self.published_at, str) or not self.published_at:
            raise ValueError(
                "published_at must be a non-empty string and is required for "
                "article-relative temporal normalization"
            )
        if self.article_version_id is None:
            version_source = json.dumps(
                {
                    "content": self.content,
                    "published_at": self.published_at,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            object.__setattr__(
                self,
                "article_version_id",
                "sha256:" + sha256(version_source.encode("utf-8")).hexdigest(),
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ArticleInput":
        content = value.get("content", value.get("raw_text", value.get("article")))
        if not isinstance(content, str):
            raise ValueError("article input requires content, raw_text, or article")
        if "article_id" not in value:
            raise ValueError("article input requires article_id")
        published_at = value.get("published_at", value.get("published"))
        if not isinstance(published_at, str) or not published_at:
            raise ValueError(
                "article input requires a non-empty published_at string "
                "(the published compatibility alias is also accepted)"
            )
        return cls(
            article_id=value["article_id"],
            content=content,
            published_at=published_at,
            article_version_id=value.get("article_version_id", value.get("version_id")),
            title=value.get("title"),
            source=value.get("source", value.get("source_name")),
            metadata=value.get("metadata") or {},
        )


@dataclass(frozen=True, slots=True)
class LaneResult:
    status: str
    items: tuple[Mapping[str, Any], ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in LANE_STATUSES:
            raise ValueError(f"invalid lane status: {self.status}")
        if self.status == "NOT_RUN" and self.items:
            raise ValueError("NOT_RUN lane cannot contain items")


@dataclass(frozen=True, slots=True)
class RuntimeFailure:
    category: str
    message: str
    component: str | None = None
    fatal: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArticleLocalRuntimeResult:
    schema_version: str
    runtime_config_id: str
    article: Mapping[str, Any]
    coverage: Mapping[str, Any]
    sentences: tuple[Mapping[str, Any], ...]
    events: tuple[Mapping[str, Any], ...]
    statements: tuple[Mapping[str, Any], ...]
    entity_mentions: LaneResult
    time_expressions: LaneResult
    resolution: Mapping[str, Any]
    relations: Mapping[str, Any]
    trace: tuple[Mapping[str, Any], ...]
    entity_candidate_priorities: LaneResult = field(
        default_factory=lambda: LaneResult(
            "NOT_RUN", (), "Entity candidate soft priority is not configured."
        )
    )
    local_entities: LaneResult = field(
        default_factory=lambda: LaneResult(
            "NOT_RUN", (), "Entity identity resolution is not configured."
        )
    )
    entity_coreference: LaneResult = field(
        default_factory=lambda: LaneResult(
            "NOT_RUN", (), "Entity coreference is not configured."
        )
    )
    participant_entity_resolutions: LaneResult = field(
        default_factory=lambda: LaneResult(
            "NOT_RUN", (), "Participant Entity resolution is not configured."
        )
    )
    local_events: LaneResult = field(
        default_factory=lambda: LaneResult(
            "NOT_RUN", (), "Event identity is not configured."
        )
    )
    event_coreference: LaneResult = field(
        default_factory=lambda: LaneResult(
            "NOT_RUN", (), "Event coreference is not configured."
        )
    )
    warnings: tuple[Mapping[str, Any], ...] = ()
    failures: tuple[RuntimeFailure, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # A JSON round-trip is part of the public contract, not just a test helper.
        try:
            return json.loads(json.dumps(payload, ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError) as error:
            raise SerializationError(f"runtime result is not JSON serializable: {error}") from error

    def to_diagnostic_dict(self) -> dict[str, Any]:
        """Viewer adapter seam; equivalent to the canonical JSON contract."""

        return self.to_dict()

    def pretty(self) -> str:
        """Raw compatibility EventFrame을 진단용으로 펼친다."""
        lines = [f"ARTICLE {self.article['article_id']}: {self.article.get('title') or ''}".rstrip()]
        for index, event in enumerate(self.events, start=1):
            proposition = event["event"]
            lines.append(f"\nRAW EVENTFRAME #{index} [{proposition['char_start']}:{proposition['char_end']}] {proposition['text']}")
            lines.append(f"  trigger: {event['trigger']['status']}")
            for role in ("ACTOR", "TARGET", "PLACE"):
                fillers = event["participants"][role]["items"]
                rendered = ", ".join(item["text"] for item in fillers) or "-"
                lines.append(f"  {role}: {rendered}")
        for index, statement in enumerate(self.statements, start=1):
            proposition = statement["proposition"]
            lines.append(f"\nSTATEMENT #{index} [{proposition['char_start']}:{proposition['char_end']}] {proposition['text']}")
            lines.append(f"  type: {statement['statement_type']['status']}")
        lines.append(f"\nENTITY MENTIONS: {self.entity_mentions.status} ({len(self.entity_mentions.items)})")
        lines.append(f"TIME EXPRESSIONS: {self.time_expressions.status} ({len(self.time_expressions.items)})")
        if self.warnings:
            lines.append("WARNINGS: " + ", ".join(item.get("code", "WARNING") for item in self.warnings))
        return "\n".join(lines) + "\n"


class RuntimeContractError(RuntimeError):
    category = "COMPONENT_RUNTIME_ERROR"

    def to_dict(self) -> dict[str, Any]:
        return asdict(RuntimeFailure(self.category, str(self), fatal=True))


class RuntimeConfigurationError(RuntimeContractError):
    category = "CONFIG_ERROR"


class CheckpointMismatchError(RuntimeContractError):
    category = "CHECKPOINT_MISMATCH"


class TokenAlignmentError(RuntimeContractError):
    category = "TOKEN_ALIGNMENT_ERROR"


class SerializationError(RuntimeContractError):
    category = "SERIALIZATION_ERROR"
