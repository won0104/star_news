"""Representation-only public materialization adapter.

This boundary intentionally imports no model, scorer, tokenizer, coreference, or
training implementation. Semantic decisions must already exist in the derived
assembly state.
"""

from __future__ import annotations

from typing import Callable, Generic, Mapping, TypeVar

from ..canonicalization.contracts import (
    CanonicalIdentityIndex,
    CanonicalizationDecision,
)
from ..derivation.contracts import DerivedAssemblyState, DerivedFact


PublicResultT = TypeVar("PublicResultT")


class PublicMaterializer(Generic[PublicResultT]):
    """Convert a derived state to the fixed public representation and validate it."""

    policy_id = "PUBLIC_V2_MATERIALIZER"

    def __init__(
        self,
        projector: Callable[
            [
                Mapping[str, object],
                CanonicalIdentityIndex,
                tuple[CanonicalizationDecision, ...],
                tuple[DerivedFact, ...],
            ],
            PublicResultT,
        ],
        validator: Callable[[PublicResultT], Mapping[str, object]],
        validation_attacher: Callable[
            [PublicResultT, Mapping[str, object]], PublicResultT
        ],
    ) -> None:
        self._projector = projector
        self._validator = validator
        self._validation_attacher = validation_attacher

    def materialize(self, state: DerivedAssemblyState) -> PublicResultT:
        if not isinstance(state, DerivedAssemblyState):
            raise TypeError("PublicMaterializer accepts DerivedAssemblyState only")
        public_result = self._projector(
            state.canonical_state.resolved_state.to_legacy_graph(),
            state.canonical_state.identity_index,
            state.canonical_state.decisions,
            state.facts,
        )
        validation = self._validator(public_result)
        return self._validation_attacher(public_result, validation)
