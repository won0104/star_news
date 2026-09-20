"""Conservative ENTITY identity constraints and ambiguity diagnostics."""

from __future__ import annotations

from collections import defaultdict
import unicodedata

from .contracts import CanonicalizationContext, CanonicalizationResult
from .policies import NoOpCanonicalizationPolicy


ENTITY_IDENTITY_CONSTRAINT_POLICY_ID = "ENTITY_IDENTITY_CONSTRAINT_V1"


def normalized_surface(value: object) -> str:
    return "".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


class EntityIdentityConstraintPolicy:
    """Keep upstream LocalEntity identities and expose unsafe alias candidates."""

    policy_id = ENTITY_IDENTITY_CONSTRAINT_POLICY_ID
    policy_version = "1"
    target_scopes = ("ENTITY",)

    def apply(self, context: CanonicalizationContext) -> CanonicalizationResult:
        base = NoOpCanonicalizationPolicy().apply(context)
        decisions = []
        by_surface = defaultdict(list)
        for row in context.resolved_state.resolved_entities:
            by_surface[normalized_surface(row.get("properties", {}).get("canonical_name", ""))].append(row)
        diagnostics = []
        ambiguous_ids = {
            str(row["node_id"])
            for surface, rows in by_surface.items()
            if surface and len(rows) >= 2
            for row in rows
        }
        for row in base.decisions:
            if row.scope != "ENTITY":
                decisions.append(row)
                continue
            reason = (
                "AMBIGUOUS_NORMALIZED_SURFACE_DISTINCT_SOURCE_IDENTITY"
                if row.output_representative_id in ambiguous_ids
                else "UPSTREAM_LOCAL_ENTITY_IDENTITY_PRESERVED"
            )
            decisions.append(
                type(row)(
                    policy_id=self.policy_id,
                    policy_version=self.policy_version,
                    scope=row.scope,
                    input_ids=row.input_ids,
                    output_representative_id=row.output_representative_id,
                    member_ids=row.member_ids,
                    decision="PASS_THROUGH",
                    reason=reason,
                    preserved_evidence_references=row.preserved_evidence_references,
                    provenance=type(row.provenance)(
                        policy_id=self.policy_id,
                        policy_version=self.policy_version,
                        decision_type="PASS_THROUGH",
                        source_ids=row.member_ids,
                        representative_id=row.output_representative_id,
                        member_ids=row.member_ids,
                        reason=reason,
                        source_stage="CANONICALIZATION",
                        derived=False,
                        model_generated=False,
                    ),
                )
            )
        for surface, rows in sorted(by_surface.items()):
            if not surface or len(rows) < 2:
                continue
            types = sorted(
                {str(row.get("properties", {}).get("entity_type")) for row in rows}
            )
            diagnostics.append(
                {
                    "scope": "ENTITY",
                    "normalized_surface": surface,
                    "source_identity_ids": sorted(str(row["node_id"]) for row in rows),
                    "entity_types": types,
                    "decision": "KEEP_SEPARATE",
                    "reason": (
                        "ENTITY_TYPE_CONFLICT"
                        if len(types) >= 2
                        else "NORMALIZED_SURFACE_NOT_POSITIVE_IDENTITY_PROOF"
                    ),
                }
            )
        return CanonicalizationResult(
            context.resolved_state,
            tuple(decisions),
            tuple(diagnostics),
        )

