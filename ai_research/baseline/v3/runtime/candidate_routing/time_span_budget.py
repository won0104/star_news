"""Pinned Step 6 Time-only structural budget and request-chunk projection identity.

The shared selector applies Time lexical cue rank; this contract pins its Time
parameters and separates extraction from normalization. No Entity encoder state
or broad-reference fallback is reachable from this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from .span_budget import Budget


TIME_BUDGET = Budget("STRUCTURAL_T16_C8", 16, 2048, 0.15, 8)
TIME_FINE_SHA256 = "f612b9db0363dfe68868f949ea88b70aeaaba763e4892fc4e6f70eccf0999de5"


@dataclass(frozen=True, slots=True)
class TimeSpanBoundedContract:
    """Explicit frozen Time extraction budget; v2.2 default stays reference."""

    budget: Budget
    selector_sha256: str
    config_sha256: str
    config_path: Path
    fine_checkpoint_sha256: str

    @property
    def policy_id(self) -> str:
        return self.budget.policy_id

    @classmethod
    def from_config(cls, path: str | Path) -> "TimeSpanBoundedContract":
        file = Path(path).resolve()
        raw = file.read_bytes()
        value = json.loads(raw)
        selector = file.parents[2] / "runtime/candidate_routing/span_budget.py"
        selector_sha = sha256(selector.read_bytes()).hexdigest()
        source_step6 = file.parents[2] / value["source_step6_policy_path"]
        source_sha = sha256(source_step6.read_bytes()).hexdigest()
        if (value.get("schema_version") != "articlelocal-bcr-time-span-budget-v1"
            or value.get("mode") != "EXPLICIT_BOUNDED_ONLY"
            or Budget(**value["budget"]) != TIME_BUDGET
            or value.get("selector_source_path")
               != "runtime/candidate_routing/span_budget.py"
            or value.get("selector_source_sha256") != selector_sha
            or value.get("source_step6_policy_sha256") != source_sha
            or value.get("fine_checkpoint_sha256") != TIME_FINE_SHA256
            or value.get("fine_threshold") != 0.9
            or value.get("fine_feature_denominator_tokens") != 21
            or value.get("fine_feature_denominator_characters") != 44
            or value.get("candidate_chunk_size") != 1024
            or value.get("representation_layer") != 10
            or value.get("span_kind") != "TIME"
            or value.get("normalization_as_extraction_gate") is not False
            or value.get("projection_cache_scope") != "SELECTED_CHUNK_ONLY"
            or value.get("published") is not False):
            raise ValueError("Time T16/C8 pinned selector/scorer contract differs")
        selected = json.loads(source_step6.read_text(encoding="utf-8"))
        if (selected["choices"]["TIME"]["priority_policy_id"]
            != TIME_BUDGET.policy_id):
            raise ValueError("Step 6 Time selected shadow policy differs")
        return cls(TIME_BUDGET, selector_sha, sha256(raw).hexdigest(), file,
                   TIME_FINE_SHA256)

    def validate(self) -> None:
        latest = self.from_config(self.config_path)
        if latest != self:
            raise ValueError("Time budget/config/selector changed after load")


@dataclass(frozen=True, slots=True)
class TimeProjectionIdentity:
    article_version_id: str
    content_sha256: str
    policy_id: str
    policy_config_sha256: str
    backbone_object_id: int
    context_object_id: int
    encoder_object_id: int
    fine_checkpoint_sha256: str
    device: str
    dtype: str
    span_kind: str = "TIME"
    representation_layer: int = 10


class TimeChunkProjectionReuse:
    """Scalar-only selected Time token-span keys, never cross-chunk or task."""

    def __init__(self, identity: TimeProjectionIdentity):
        self.identity = identity
        self._positions: dict[tuple[int, int, int], int] = {}
        self._closed = False

    def select_rows(self, rows: list[dict], identity: TimeProjectionIdentity
                    ) -> tuple[list[dict], list[int], int, int]:
        if (self._closed or identity != self.identity
            or identity.span_kind != "TIME"
            or identity.representation_layer != 10):
            raise ValueError("Time projection identity/layer/policy mismatch")
        unique = []
        positions = []
        for row in rows:
            key = (int(row["sentence_index"]), int(row["token_start"]),
                   int(row["token_end"]))
            if key not in self._positions:
                self._positions[key] = len(unique)
                unique.append(row)
            positions.append(self._positions[key])
        return unique, positions, len(rows) - len(unique), len(unique)

    def close(self) -> None:
        self._positions.clear()
        self._closed = True
