"""Explicit V2.1 assembly stage orchestration with V2 pass-through behavior."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Generic, Mapping, TypeVar

from .assembly_input import AssemblyInputAdapter
from .canonicalization import CanonicalizationPipeline
from .derivation import DeterministicDerivationPipeline
from .materialization import PublicMaterializer
from .observability import AssemblyAuditTrail, StageCensus
from .output_profiles import OutputProfile, OutputProfileProjector


PublicResultT = TypeVar("PublicResultT")


@dataclass(frozen=True, slots=True)
class AssemblyFoundationOutcome(Generic[PublicResultT]):
    output: PublicResultT
    audit: AssemblyAuditTrail


class AssemblyFoundationPipeline(Generic[PublicResultT]):
    """Run typed assembly stages without altering the current public payload."""

    def __init__(
        self,
        *,
        input_adapter: AssemblyInputAdapter,
        canonicalization: CanonicalizationPipeline,
        derivation: DeterministicDerivationPipeline,
        materializer: PublicMaterializer[PublicResultT],
        output_projector: OutputProfileProjector[PublicResultT],
    ) -> None:
        self.input_adapter = input_adapter
        self.canonicalization = canonicalization
        self.derivation = derivation
        self.materializer = materializer
        self.output_projector = output_projector

    def run(
        self,
        source: Any,
        *,
        output_profile: OutputProfile | str = OutputProfile.PUBLIC,
    ) -> AssemblyFoundationOutcome[PublicResultT]:
        input_started = time.perf_counter()
        resolved = self.input_adapter.adapt(source)
        input_count = len(resolved.identity_ids()) + len(resolved.semantic_edges)
        input_census = StageCensus(
            stage="ASSEMBLY_INPUT_ADAPTATION",
            input_count=input_count,
            output_count=input_count,
            preserved_count=input_count,
            collapsed_count=0,
            derived_count=0,
            unresolved_count=len(resolved.unmaterialized_evidence),
            policy_id=self.input_adapter.policy_id,
            elapsed_seconds=time.perf_counter() - input_started,
        )

        canonical = self.canonicalization.run(resolved)
        derived = self.derivation.run(canonical)

        materialization_started = time.perf_counter()
        materialized = self.materializer.materialize(derived)
        payload = materialized.to_dict()  # type: ignore[attr-defined]
        public_count = len(payload["nodes"]) + len(payload["edges"])
        materialization_census = StageCensus(
            stage="PUBLIC_MATERIALIZATION",
            input_count=input_count,
            output_count=public_count,
            preserved_count=public_count,
            collapsed_count=0,
            derived_count=0,
            unresolved_count=0,
            policy_id=self.materializer.policy_id,
            elapsed_seconds=time.perf_counter() - materialization_started,
        )

        projection_started = time.perf_counter()
        selected_profile = OutputProfile(output_profile)
        output = self.output_projector.project(materialized, selected_profile)
        projection_census = StageCensus(
            stage="OUTPUT_PROJECTION",
            input_count=public_count,
            output_count=public_count,
            preserved_count=public_count,
            collapsed_count=0,
            derived_count=0,
            unresolved_count=0,
            policy_id=self.output_projector.contract.contract_id,
            elapsed_seconds=time.perf_counter() - projection_started,
        )
        audit = AssemblyAuditTrail(
            canonicalization_ledger=tuple(
                decision.to_dict() for decision in canonical.decisions
            ),
            derivation_ledger=tuple(
                decision.to_dict() for decision in derived.decisions
            ),
            stage_census=(
                input_census,
                canonical.census,
                derived.census,
                materialization_census,
                projection_census,
            ),
            output_profile=selected_profile.value,
            canonical_identity_index=canonical.identity_index.to_dict(),
            canonicalization_pair_diagnostics=canonical.pair_diagnostics,
            canonicalization_scope_census=canonical.scope_census,
        )
        return AssemblyFoundationOutcome(output, audit)
