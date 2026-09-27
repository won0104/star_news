"""Checkpoint-bound source execution policies shared by serving and replay.

V3_WINDOW retains D3/D4 source budgets. V23_BASELINE binds lane-local decoding,
single acceptance, uncapped B2 mentions, and one post-source Entity closure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence, TypeVar

from runtime.v3_pretraining.acceptance import SCORE_CONTRACT_VERSION
from runtime.v3_pretraining.extraction_decode import RetrievalBudget


SOURCE_KINDS = ("EVENT", "STATEMENT", "ENTITY", "TIME", "TRIGGER")
SOURCE_FUNNEL_EXECUTION_VERSION = "r06-shared-source-funnel-v1"
V23_SOURCE_FUNNEL_EXECUTION_VERSION = "v23-unified-mention-coreference-v2-native-argmax"
# This separate SHA-bound execution contract is a shadow candidate, not a
# reinterpretation of existing V23 source artifacts.
V23_ROLE_FORWARDING_EXECUTION_VERSION = "v23-baseline-source-funnel-v3-role-forwarding-k2"
SpanT = TypeVar("SpanT")
ARTIFACT_EXECUTION_ORDER = (
    "retrieval", "route_quota_and_borrowing", "article_guard", "exact_scoring",
    "acceptance", "per_kind_cap", "trigger_containment",
    "entity_candidate_budget", "downstream",
)
V23_ARTIFACT_EXECUTION_ORDER = (
    "lane_specific_bounded_retrieval", "additive_cross_window_extension",
    "chunked_native_or_canonical_scoring", "single_lane_acceptance",
    "optional_trigger_attachment", "native_and_role_mentions",
    "selected_pair_entity_coreference", "event_role_projection", "downstream",
)
V23_ROLE_FORWARDING_EXECUTION_ORDER = (
    "lane_specific_bounded_retrieval", "additive_cross_window_extension",
    "chunked_native_or_canonical_scoring", "single_lane_acceptance",
    "optional_trigger_attachment", "participant_role_filler_top_k",
    "uncapped_entity_union", "downstream",
)
V23_ROLE_FORWARDING_POLICY = {
    "mode": "EVENT_ROLE_TOP_K", "limit": 2, "accept_threshold": None,
    "score_order": "EXTRACTION_SCORE_DESC_START_END_ASC",
}


class SourceFunnelContractError(ValueError):
    """A checkpoint, artifact, or runtime budget does not match the source policy."""


def contain_accepted_events(events: Sequence[SpanT],
                            triggers: Sequence[SpanT]) -> tuple[tuple[SpanT, SpanT], ...]:
    """Materialize only Events with a contained accepted Trigger, no Gold backfill."""
    retained = []
    for event in events:
        options = [row for row in triggers
                   if event.start <= row.start < row.end <= event.end]
        if options:
            retained.append((event, min(options,
                                        key=lambda row: (-row.score, row.start, row.end))))
    return tuple(retained)


def attach_optional_triggers(events: Sequence[SpanT],
                             triggers: Sequence[SpanT]) -> tuple[tuple[SpanT, SpanT | None], ...]:
    """A Canonical-accepted Event exists even without a contained Trigger."""
    attached = []
    for event in events:
        options = [row for row in triggers if event.start <= row.start < row.end <= event.end]
        trigger = min(options, key=lambda row: (-row.score, row.start, row.end)) if options else None
        attached.append((event, trigger))
    return tuple(attached)


def _sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise SourceFunnelContractError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise SourceFunnelContractError(f"{name} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class SourceFunnelPolicy:
    """Typed source-only contract; hashes refer to exact artifact bytes."""

    policy_sha256: str
    acceptance_sha256: str
    checkpoint_sha256: str
    score_contract_version: str
    retrieval: RetrievalBudget
    caps: tuple[tuple[str, int], ...]
    entity_candidate_budget: int
    thresholds: tuple[tuple[str, float], ...]
    boundary_thresholds: tuple[tuple[str, float], ...]
    participant_mode: str
    participant_threshold_status: str
    participant_threshold: float | None
    execution_order: tuple[str, ...]
    status: str = "PROVISIONAL_CHECKPOINT_BOUND_CALIBRATION"
    trigger_endpoint_threshold: float | None = None
    participant_endpoint_threshold: float | None = None
    participant_role_forwarding_limit: int | None = None

    @classmethod
    def load(cls, policy_path: str | Path, acceptance_path: str | Path, *,
             checkpoint_sha256: str, budget: Any) -> "SourceFunnelPolicy":
        policy_bytes = Path(policy_path).read_bytes()
        acceptance_bytes = Path(acceptance_path).read_bytes()
        return cls.from_artifacts(
            policy_bytes, acceptance_bytes,
            checkpoint_sha256=checkpoint_sha256, budget=budget)

    @classmethod
    def from_artifacts(cls, policy_bytes: bytes, acceptance_bytes: bytes, *,
                       checkpoint_sha256: str, budget: Any) -> "SourceFunnelPolicy":
        try:
            policy = json.loads(policy_bytes)
            acceptance = json.loads(acceptance_bytes)
        except (ValueError, TypeError) as error:
            raise SourceFunnelContractError("source funnel artifact JSON is invalid") from error
        if not isinstance(policy, dict) or not isinstance(acceptance, dict):
            raise SourceFunnelContractError("source funnel artifacts must be objects")
        acceptance_sha = _sha256(acceptance_bytes)
        if (policy.get("acceptance_artifact_sha256") != acceptance_sha or
                policy.get("checkpoint_sha256") != checkpoint_sha256 or
                acceptance.get("checkpoint_sha256") != checkpoint_sha256 or
                policy.get("score_contract_version") != SCORE_CONTRACT_VERSION or
                acceptance.get("score_contract_version") != SCORE_CONTRACT_VERSION):
            raise SourceFunnelContractError("source policy/acceptance/checkpoint binding differs")
        provisional = (
            policy.get("status") == "PROVISIONAL_ENGINEERING_ONLY" and
            acceptance.get("status") == "PROVISIONAL_ENGINEERING_ONLY" and
            acceptance.get("mode") == "CALIBRATION_CANDIDATE" and
            acceptance.get("scope") == "SOURCE_ACCEPTANCE_ONLY_NO_FULL_CASCADE" and
            acceptance.get("service_ready") is False and
            "predicted_validation_report_sha256" not in policy and
            "predicted_validation_report_sha256" not in acceptance)
        report_sha = policy.get("predicted_validation_report_sha256")
        validated = (
            policy.get("status") == "PREDICTED_VALIDATED" and
            acceptance.get("status") == "PREDICTED_VALIDATED" and
            acceptance.get("mode") == "SOURCE_SERVICE_CALIBRATED" and
            acceptance.get("scope") == "PREDICTED_SOURCE_CASCADE_VALIDATED" and
            acceptance.get("service_ready") is True and
            isinstance(report_sha, str) and len(report_sha) == 64 and
            all(char in "0123456789abcdef" for char in report_sha) and
            acceptance.get("predicted_validation_report_sha256") == report_sha)
        if (not (provisional or validated) or
                policy.get("test_access") != 0 or acceptance.get("test_access") != 0):
            raise SourceFunnelContractError("source artifacts lack a matching calibration status")
        try:
            retrieval = RetrievalBudget(**policy["retrieval_budget"])
        except (KeyError, TypeError, ValueError) as error:
            raise SourceFunnelContractError("retrieval budget schema differs") from error
        baseline = retrieval.candidate_profile == "V23_BASELINE"
        forwarding_limit = None
        if baseline and ("participant_role_forwarding" in policy or
                         policy.get("source_execution_version") !=
                         V23_SOURCE_FUNNEL_EXECUTION_VERSION):
            raise SourceFunnelContractError("V23 unified mention source contract differs")
        elif not baseline and ("participant_role_forwarding" in policy or
                               "source_execution_version" in policy):
            raise SourceFunnelContractError("V23 forwarding belongs only to V23 source policy")
        expected_order = (V23_ARTIFACT_EXECUTION_ORDER if baseline else
                          ARTIFACT_EXECUTION_ORDER)
        if tuple(policy.get("execution_order", ())) != expected_order:
            raise SourceFunnelContractError("source funnel execution order differs")
        if baseline:
            if (policy.get("article_guard") is not None or
                    policy.get("route_quota") is not None or
                    policy.get("borrowing_dedup_policy") is not None or
                    policy.get("per_kind_cap") is not None or
                    policy.get("entity_candidate_budget") is not None or
                    policy.get("trigger_containment_policy") !=
                    "OPTIONAL_CONTAINED_TRIGGER_ATTACHMENT" or
                    policy.get("per_kind_retrieval_override") != []):
                raise SourceFunnelContractError("v2.3 baseline contains v3 funnel budgets")
        elif (policy.get("article_guard") != retrieval.max_scored_candidates or
                policy.get("route_quota") != {
                    "in_window": retrieval.route_quota,
                    "cross_window": retrieval.route_quota} or
                policy.get("max_span_width", {}).get(
                    "in_window_source_tokens_all_generic_kinds") != retrieval.max_span_tokens or
                policy.get("borrowing_dedup_policy") !=
                "D3_IN_THEN_CROSS_DETERMINISTIC_ROUND_ROBIN_ABSOLUTE_SPAN_DEDUP" or
                policy.get("trigger_containment_policy") !=
                "TRIGGER_MUST_BE_CONTAINED_BY_ACCEPTED_EVENT" or
                policy.get("per_kind_retrieval_override") != []):
            raise SourceFunnelContractError("retrieval/containment contract differs")
        caps_payload = ({} if baseline else policy.get("per_kind_cap"))
        cap_names = set(SOURCE_KINDS) | {"PARTICIPANT_PER_EVENT_ROLE"}
        if (not baseline and (not isinstance(caps_payload, dict) or set(caps_payload) != cap_names or
                any(type(value) is not int or value <= 0 for value in caps_payload.values()))):
            raise SourceFunnelContractError("source cap schema differs")
        entity_budget = 0 if baseline else policy.get("entity_candidate_budget")
        if not baseline and (type(entity_budget) is not int or entity_budget <= 0):
            raise SourceFunnelContractError("Entity candidate budget differs")
        thresholds = acceptance.get("thresholds")
        boundary = acceptance.get("boundary_thresholds")
        statuses = acceptance.get("threshold_status")
        if (not isinstance(thresholds, dict) or
                set(thresholds) != cap_names - {"PARTICIPANT_PER_EVENT_ROLE"} | {"PARTICIPANT"} or
                not isinstance(boundary, dict) or set(boundary) != {"EVENT", "STATEMENT"} or
                not isinstance(statuses, dict) or set(statuses) != set(thresholds)):
            raise SourceFunnelContractError("source threshold schema differs")
        for kind in (SOURCE_KINDS if not baseline else
                     ("EVENT", "STATEMENT", "ENTITY", "TIME")):
            if statuses[kind] != "SELECTED":
                raise SourceFunnelContractError(f"{kind} source threshold is not selected")
        if baseline and (statuses["TRIGGER"] != "INACTIVE_V23_ENDPOINT_ONLY" or
                         thresholds["TRIGGER"] is not None or
                         statuses["PARTICIPANT"] != "INACTIVE_V23_ENDPOINT_ONLY" or
                         thresholds["PARTICIPANT"] is not None):
            raise SourceFunnelContractError(
                "v2.3 Trigger/Participant cannot have a second acceptance gate")
        source_thresholds = tuple((kind, _finite_number(thresholds[kind], kind))
                                  for kind in SOURCE_KINDS if not baseline or kind != "TRIGGER")
        boundary_thresholds = tuple((kind, _finite_number(boundary[kind], kind + "_BOUNDARY"))
                                    for kind in ("EVENT", "STATEMENT"))
        participant_status = statuses["PARTICIPANT"]
        if baseline:
            participant_mode = "V23_ENDPOINT_ONLY"
            participant_threshold = None
        elif participant_status == "INSUFFICIENT_AUTHORITY_SUPPORT":
            if thresholds["PARTICIPANT"] is not None:
                raise SourceFunnelContractError("uncalibrated Participant must not have a selected value")
            participant_mode = "LEGACY_RAW_ZERO_PROVISIONAL"
            participant_threshold = 0.0
        elif participant_status == "SELECTED":
            participant_mode = "CALIBRATED_SOURCE_CANDIDATE"
            participant_threshold = _finite_number(thresholds["PARTICIPANT"], "PARTICIPANT")
        else:
            raise SourceFunnelContractError("unknown Participant threshold status")
        endpoint_thresholds = acceptance.get("v23_endpoint_thresholds")
        if retrieval.candidate_profile == "V23_BASELINE":
            provenance = acceptance.get("v23_calibration_provenance")
            if (not isinstance(endpoint_thresholds, dict) or
                    set(endpoint_thresholds) != {"TRIGGER", "PARTICIPANT"} or
                    not isinstance(provenance, dict) or
                    provenance.get("source_profile") != "V23_BASELINE" or
                    provenance.get("legacy_release_thresholds_reused") is not False or
                    provenance.get("new_gold_dev_calibrated") is not True):
                raise SourceFunnelContractError(
                    "v2.3 endpoint gates need new-Gold checkpoint-bound calibration")
            trigger_endpoint = _finite_number(endpoint_thresholds["TRIGGER"],
                                              "TRIGGER_ENDPOINT")
            participant_endpoint = _finite_number(endpoint_thresholds["PARTICIPANT"],
                                                  "PARTICIPANT_ENDPOINT")
            if not 0.0 <= trigger_endpoint <= 1.0 or not 0.0 <= participant_endpoint <= 1.0:
                raise SourceFunnelContractError("endpoint probabilities must be in [0,1]")
        else:
            trigger_endpoint = participant_endpoint = None
        result = cls(
            _sha256(policy_bytes), acceptance_sha, checkpoint_sha256,
            SCORE_CONTRACT_VERSION, retrieval,
            (tuple() if baseline else tuple((kind, caps_payload[kind])
                  for kind in (*SOURCE_KINDS, "PARTICIPANT_PER_EVENT_ROLE"))), entity_budget,
            source_thresholds, boundary_thresholds, participant_mode,
            participant_status, participant_threshold,
            expected_order, status=policy["status"],
            trigger_endpoint_threshold=trigger_endpoint,
            participant_endpoint_threshold=participant_endpoint,
            participant_role_forwarding_limit=forwarding_limit)
        result.validate_budget(budget)
        return result

    def threshold(self, kind: str) -> float:
        if self.retrieval.candidate_profile == "V23_BASELINE" and kind == "TRIGGER":
            raise SourceFunnelContractError("v2.3 Trigger uses only its endpoint threshold")
        return dict(self.thresholds)[kind]

    def boundary_threshold(self, kind: str) -> float:
        return dict(self.boundary_thresholds)[kind]

    def cap(self, kind: str) -> int:
        if self.retrieval.candidate_profile == "V23_BASELINE":
            raise SourceFunnelContractError("v2.3 baseline has no generic source cap")
        return dict(self.caps)[kind]

    def validate_budget(self, budget: Any) -> None:
        """Reject a policy/runtime mismatch before source model execution."""
        expected = {
            "EVENT": budget.max_events, "STATEMENT": budget.max_statements,
            "ENTITY": budget.max_entities, "TIME": budget.max_times,
            "TRIGGER": budget.max_triggers,
            "PARTICIPANT_PER_EVENT_ROLE": budget.max_role_fillers_per_event_role,
        }
        if (budget.retrieval is None or asdict(budget.retrieval) != asdict(self.retrieval)
                or budget.retrieval_by_kind or
                (self.participant_role_forwarding_limit is not None and
                 self.participant_role_forwarding_limit !=
                 budget.max_role_fillers_per_event_role) or
                (self.retrieval.candidate_profile != "V23_BASELINE" and
                 (expected != dict(self.caps) or
                  budget.max_entity_candidates != self.entity_candidate_budget))):
            raise SourceFunnelContractError("runtime budget differs from source policy")

    def binding(self) -> dict[str, Any]:
        retrieval = asdict(self.retrieval)
        # Historical policy/checkpoint bindings used the original v3 field set.
        # The legacy v3 path keeps that digest; an explicit v2.3 profile gets a
        # different digest and must bring a newly bound policy artifact.
        if retrieval["candidate_profile"] == "V3_WINDOW":
            retrieval.pop("candidate_profile")
        binding = {
            "policy_sha256": self.policy_sha256,
            "source_acceptance_artifact_sha256": self.acceptance_sha256,
            "checkpoint_sha256": self.checkpoint_sha256,
            "score_contract_version": self.score_contract_version,
            "retrieval_budget_sha256": _sha256(json.dumps(
                retrieval, sort_keys=True,
                separators=(",", ":")).encode()),
            "execution_order_version": (V23_SOURCE_FUNNEL_EXECUTION_VERSION
                                        if self.retrieval.candidate_profile == "V23_BASELINE"
                                        else SOURCE_FUNNEL_EXECUTION_VERSION),
            "participant_mode": self.participant_mode,
            "participant_threshold_status": self.participant_threshold_status,
            "service_ready": self.status == "PREDICTED_VALIDATED",
        }
        if self.retrieval.candidate_profile == "V23_BASELINE":
            binding["v23_endpoint_thresholds"] = {
                "TRIGGER": self.trigger_endpoint_threshold,
                "PARTICIPANT": self.participant_endpoint_threshold}
            binding["active_source_thresholds"] = (
                "EVENT_SEMANTIC_AND_BOUNDARY", "STATEMENT_SEMANTIC_AND_BOUNDARY",
                "ENTITY_NATIVE", "TIME_NATIVE", "TRIGGER_ENDPOINT",
                "PARTICIPANT_ENDPOINT")
            binding["inactive_v3_funnel"] = (
                "ROUTE_QUOTA", "ARTICLE_GUARD", "PER_KIND_CAP",
                "TRIGGER_CONTAINMENT_GATE", "PARTICIPANT_SECOND_GATE_AND_K2",
                "ENTITY_128_BUDGET", "PARTICIPANT_ENTITY_RESOLVER")
        return binding
