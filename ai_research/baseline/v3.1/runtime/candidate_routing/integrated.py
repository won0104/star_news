"""Explicit A+B+C candidate entry point over the authoritative v2.2 runtime.

It freezes five already implemented routing contracts and passes them to the
compact PUBLIC pipeline. It owns no scorer, Gold evaluator, reference fallback,
or request-spanning candidate cache. Model construction happens only in load().
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from .core import TierBudget
from .event_policy import EventIdentityBoundedContract
from .participant_entity import ParticipantEntityBoundedContract
from .span_budget import EntitySpanBoundedContract
from .temporal import TemporalBoundedContract
from .time_span_budget import TimeSpanBoundedContract


CONFIG = "runtime/configs/bcr-integrated-v23-rc1.json"


def _local_file(root: Path, name: str, expected_sha: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("integrated policy path is not package-relative")
    file = (root / relative).resolve()
    file.relative_to(root)
    if not file.is_file() or sha256(file.read_bytes()).hexdigest() != expected_sha:
        raise ValueError("integrated policy file is absent or SHA mismatched: " + name)
    return file


@dataclass(frozen=True, slots=True)
class IntegratedBoundedPolicies:
    root: Path
    config_sha256: str
    participant_entity: ParticipantEntityBoundedContract
    event_time: TemporalBoundedContract
    entity_span: EntitySpanBoundedContract
    time_span: TimeSpanBoundedContract
    event_identity: EventIdentityBoundedContract

    @classmethod
    def from_root(cls, root: str | Path | None = None) -> "IntegratedBoundedPolicies":
        package = (Path(root) if root is not None else
                   Path(__file__).resolve().parents[2]).resolve()
        file = package / CONFIG
        raw = file.read_bytes()
        config = json.loads(raw)
        lanes = config["active_lanes"]
        if (config.get("schema_version") != "articlelocal-bcr-integrated-candidate-v1"
            or config.get("release_candidate") != "v2.3"
            or config.get("release_status") != "PENDING_STEP12_FINAL_VALIDATION"
            or config.get("published") is not False
            or config.get("public_schema") != "articlelocal-kg-public-v2.2"
            or config.get("output_profile_contract") != "ASSEMBLY_OUTPUT_PROFILE_V3"
            or config.get("default_output_profile") != "PUBLIC"
            or config.get("default_runtime") != "ARTICLELOCAL_COMPACT_RUNTIME_V22_V1"
            or config.get("fine_checkpoints_and_thresholds") != "FROZEN_V22_UNCHANGED"
            or config.get("heavy_pair_capture_default") is not False
            or config.get("broad_reference_shadow_scoring_default") is not False):
            raise ValueError("integrated v2.3 candidate semantic/status contract differs")
        participant = lanes["participant_entity"]
        time = lanes["event_time"]
        entity = lanes["entity_span"]
        time_span = lanes["time_span"]
        event = lanes["event_identity"]
        if (participant["mode"] != "EXPLICIT_BOUNDED_K32"
            or participant["policy_id"] != "BCR_A_SHADOW_NESTED_R2_K32"
            or participant["shared_retrieval_policy_id"] != "BCR_A_SHADOW_SCALAR_R2_K64"
            or participant["selected_tier_quota"] != {"LOCAL":16,"NEAR":8,"GLOBAL":8}
            or participant["retrieval_tier_quota"] != {"LOCAL":32,"NEAR":16,"GLOBAL":16}
            or [participant[key] for key in ("query_visit_cap", "query_cheap_cap",
                 "posting_visit_cap", "retrieval_fine_cap", "selected_primary_fine_cap",
                 "failed_primary_rescue_fine_cap", "request_budget_per_query_upper_bound")]
               != [88,88,32,64,32,16,240]
            or time["mode"] != "EXPLICIT_BOUNDED_K80"
            or time["policy_id"] != "BCR_A_TIME_OCCURRENCE_R1_K80"
            or time["tier_quota"] != {"LOCAL":8,"NEAR":8,"GLOBAL":64}
            or [time[key] for key in ("query_visit_cap", "query_cheap_cap",
                "posting_visit_cap", "fine_pair_cap", "request_budget_per_event_upper_bound")]
               != [192,192,64,80,464]
            or time["multiple_positive_attachments"] is not True
            or time["unnormalized_time_eligible"] is not True
            or entity["mode"] != "EXPLICIT_BOUNDED_T14_C6"
            or time_span["mode"] != "EXPLICIT_BOUNDED_T16_C8"
            or event["mode"] != "EXPLICIT_BOUNDED"
            or event["source_shadow_policy_id"] != "SHADOW_C_MONOTONIC_SEED_CLIQUE_V1"
            or event["source_shadow_policy_sha256"] !=
               "53a3c8b72d4a1017f17f8612344a6e92a543ca0db40572d9ce55503170e5a23f"
            or event["per_channel_retain_quota"] !=
               {"LOCAL":3,"LEXICAL":5,"TRIGGER":2,"ENTITY":3,"TEMPORAL":2}
            or event["per_channel_visit_cap"] !=
               {"LOCAL":24,"LEXICAL":64,"TRIGGER":24,"ENTITY":48,"TEMPORAL":24}
            or [event[key] for key in ("neighborhood_size", "article_pair_hard_cap",
                "article_pair_linear_factor")] != [12,3072,32]
            or event["seed_protection"] is not True
            or event["missing_pair"] != "NOT_EVALUATED"):
            raise ValueError("integrated active bounded numerical contract differs")
        entity_contract = EntitySpanBoundedContract.from_config(
            _local_file(package,entity["config_path"],entity["config_sha256"]))
        time_contract = TimeSpanBoundedContract.from_config(
            _local_file(package,time_span["config_path"],time_span["config_sha256"]))
        event_contract = EventIdentityBoundedContract.from_config(
            _local_file(package,event["config_path"],event["config_sha256"]))
        if (entity_contract.policy_id != entity["policy_id"]
            or time_contract.policy_id != time_span["policy_id"]
            or event_contract.policy_id != event["policy_id"]
            or event_contract.source_shadow_policy_sha256 !=
               event["source_shadow_policy_sha256"]):
            raise ValueError("integrated component policy identity differs")
        participant_contract = ParticipantEntityBoundedContract(
            participant["policy_id"], "r2", participant["shared_retrieval_policy_id"],
            TierBudget(16,8,8), 2, 88, 88, 32, participant["source_manifest_sha256"])
        time_attachment_contract = TemporalBoundedContract(
            time["policy_id"], "r1", TierBudget(8,8,64),
            192,192,80,64,time["source_manifest_sha256"])
        return cls(package, sha256(raw).hexdigest(), participant_contract,
                   time_attachment_contract, entity_contract, time_contract,
                   event_contract)


class ArticleLocalBoundedCandidate:
    """One loaded pipeline plus immutable policies; article scopes own transient state."""

    def __init__(self, pipeline, policies: IntegratedBoundedPolicies) -> None:
        if pipeline.config.repository_root.resolve() != policies.root:
            raise ValueError("candidate pipeline imported another repository runtime")
        self.pipeline = pipeline
        self.policies = policies

    @classmethod
    def load(cls, *, device: str = "cpu") -> "ArticleLocalBoundedCandidate":
        """Construct actual tokenizer/component models; Step 11 static checks never call this."""
        from runtime.pipeline import ArticleLocalKGPipeline

        policies = IntegratedBoundedPolicies.from_root()
        pipeline = ArticleLocalKGPipeline.from_config(
            device=device, repository_root=policies.root)
        return cls(pipeline, policies)

    def eager_backbone(self) -> None:
        """Complete pinned lazy backbone preparation inside Model Loading Time."""
        self.pipeline.runtime.backbone._online_model()

    def run(self, article, *, validation_capture=None, application_profiler=None):
        """Return direct PUBLIC; no broad observer, pair dump or DEBUG replay by default."""
        p = self.policies
        return self.pipeline.run(
            article, output_profile="PUBLIC", validation_capture=validation_capture,
            application_profiler=application_profiler,
            participant_entity_bounded_policy=p.participant_entity,
            event_time_bounded_policy=p.event_time,
            entity_span_bounded_policy=p.entity_span,
            time_span_bounded_policy=p.time_span,
            event_identity_bounded_policy=p.event_identity,
        )
