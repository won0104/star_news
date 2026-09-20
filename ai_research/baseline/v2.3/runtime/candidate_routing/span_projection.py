"""Request-local Entity token-span projection dedupe inside one selected chunk.

Only identical Entity encoder inputs share a projection. Boundary-specific fine
features remain per candidate. This object stores scalar keys and indices only;
encoder tensors belong to the caller's StageScope and die with that chunk.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProjectionIdentity:
    article_version_id: str
    content_sha256: str
    policy_id: str
    policy_sha256: str
    representation_layer: int
    span_kind: str
    backbone_object_id: int
    context_object_id: int
    encoder_object_id: int
    encoder_checkpoint_sha256: str
    device: str
    dtype: str


class ChunkProjectionReuse:
    """Deduplicate selected rows by (sentence, token_start, token_end)."""

    def __init__(self, identity: ProjectionIdentity):
        self.identity = identity
        self._keys: dict[tuple[int, int, int], int] = {}
        self._closed = False

    def select_rows(self, rows: list[dict], current: ProjectionIdentity
                    ) -> tuple[list[dict], list[int], int, int]:
        if self._closed or current != self.identity:
            raise ValueError("Entity projection cache identity/policy/hash mismatch")
        if current.span_kind != "ENTITY" or current.representation_layer != 12:
            raise ValueError("projection reuse is Entity layer-12 only")
        unique = []
        indices = []
        for row in rows:
            key = (int(row["sentence_index"]), int(row["token_start"]),
                   int(row["token_end"]))
            if key not in self._keys:
                self._keys[key] = len(unique)
                unique.append(row)
            indices.append(self._keys[key])
        misses = len(unique)
        return unique, indices, len(rows) - misses, misses

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._keys.clear()
        self._closed = True
