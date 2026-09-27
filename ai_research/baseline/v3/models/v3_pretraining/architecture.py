"""고정 KF backbone 위에 fresh task core를 만드는 단계 4 architecture 경계.

Gold adapter, runtime checkpoint loader, no_grad wrapper, legacy task weight는 없다.
공유 DCE는 하나이며 아직 감독 연결 전인 head는 registry에서 미구현으로 남는다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json

import torch
from torch import nn

from models.context import CandidateSpanEncoder, DocumentContextEncoder
from models.contracts import ArticleBatch, BackboneConfig, BackboneOutput, ContextConfig, TaskLayerPolicy
from models.spans.canonical_v3 import CanonicalSpanRepresentationV3, JointSpanProposalHead
from models.v3_pretraining.exact_span import ExactSourceSpanBridge
from models.v3_pretraining.pair_context import PAIR_CONTEXT_VERSION
from models.v3_pretraining.task_contract import HEAD_TASKS, TASK_DEFINITIONS, TRAINING_PHASES
from runtime.v3_pretraining.source_layout import LAYOUT_POLICY


PINNED_TOKENIZER_SHA256 = "915388090e2d63e3869c54b5334d6005e453a51de12088d908175dd765fd8372"


@dataclass(frozen=True, slots=True)
class V3ArchitectureConfig:
    run_id: str
    seed: int = 1008
    backbone: BackboneConfig = field(default_factory=lambda: BackboneConfig(local_files_only=True))
    context: ContextConfig = field(default_factory=ContextConfig)
    layers: TaskLayerPolicy = field(default_factory=TaskLayerPolicy)
    tokenizer_sha256: str = PINNED_TOKENIZER_SHA256
    layout_policy: str = LAYOUT_POLICY
    relation_pair_contract: str = PAIR_CONTEXT_VERSION
    dtype: str = "float32"

    def __post_init__(self) -> None:
        if (not self.run_id or self.tokenizer_sha256 != PINNED_TOKENIZER_SHA256
                or self.layout_policy != LAYOUT_POLICY
                or self.relation_pair_contract != PAIR_CONTEXT_VERSION):
            raise ValueError("fresh run, pinned tokenizer and v3 source layout are required")
        pinned = BackboneConfig()
        if (self.backbone.trainable or not self.backbone.local_files_only
                or self.backbone.required_layers != (8, 10, 12)
                or self.backbone.model_id != pinned.model_id
                or self.backbone.revision != pinned.revision
                or self.backbone.expected_weights_sha256 != pinned.expected_weights_sha256):
            raise ValueError("v3 core expects a fixed pretrained L8/L10/L12 backbone")
        if (self.dtype != "float32" or self.layers != TaskLayerPolicy()
                or self.context.input_hidden_size != 768 or self.context.hidden_size != 256):
            raise ValueError("v3 representation layer/dtype contract differs from pinned rc2")

    def fingerprint(self) -> str:
        return sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class UnimplementedTaskError(RuntimeError):
    """Full model activation requires real, registered task modules."""


class SharedForwardLease:
    """한 요청의 마지막 tensor consumer 뒤 명시적으로 닫는 temporary feature lease."""

    def __init__(self, *, token_states: torch.Tensor, sentence_states: torch.Tensor,
                 document_state: torch.Tensor, proposal_logits: torch.Tensor) -> None:
        self.token_states: torch.Tensor | None = token_states
        self.sentence_states: torch.Tensor | None = sentence_states
        self.document_state: torch.Tensor | None = document_state
        self.proposal_logits: torch.Tensor | None = proposal_logits
        self.closed = False

    def close(self) -> None:
        self.token_states = None
        self.sentence_states = None
        self.document_state = None
        self.proposal_logits = None
        self.closed = True

    def __enter__(self) -> "SharedForwardLease":
        if self.closed:
            raise RuntimeError("feature lease is closed")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


class V3Core(nn.Module):
    """단일 DCE·후보 표현 owner와 단계별 task 등록 지점을 가진 학습 core."""

    def __init__(self, config: V3ArchitectureConfig) -> None:
        super().__init__()
        self.config = config
        self.document_context = DocumentContextEncoder(config.context)
        self.candidate_span = CandidateSpanEncoder(config.context, config.layers)
        self.exact_source_span = ExactSourceSpanBridge(hidden_size=config.context.hidden_size,
                                                      raw_size=config.context.input_hidden_size)
        self.semantic_proposer = JointSpanProposalHead(hidden_size=config.context.hidden_size,
                                                       labels=2, projection_size=128)
        self.canonical_span = CanonicalSpanRepresentationV3()
        self.primary_adapter = nn.Sequential(nn.Linear(config.context.hidden_size, config.context.hidden_size),
                                             nn.GELU(), nn.LayerNorm(config.context.hidden_size))
        self.task_modules = nn.ModuleDict()
        self._ready_tasks: set[str] = {"semantic_proposer"}
        self.assert_unique_parameters()

    @property
    def unimplemented_tasks(self) -> tuple[str, ...]:
        return tuple(name for name in HEAD_TASKS if name not in self._ready_tasks)

    def register_task(self, name: str, module: nn.Module | None, *, source_run_id: str) -> None:
        """같은 fresh run의 새 module만 등록한다; 공유 core는 중복 소유하지 않는다."""
        if name not in TASK_DEFINITIONS or name in self._ready_tasks:
            raise ValueError(f"unknown or already registered task: {name}")
        if source_run_id != self.config.run_id:
            raise ValueError("task module came from another training run")
        missing = [dep for dep in TASK_DEFINITIONS[name].dependencies if dep not in self._ready_tasks]
        if missing:
            raise UnimplementedTaskError(f"{name} requires upstream tasks: {missing}")
        if not isinstance(module, nn.Module):
            raise TypeError("task implementation must be nn.Module")
        owned = {id(parameter) for parameter in self.parameters()}
        fresh_ids = [id(parameter) for _, parameter in module.named_parameters(remove_duplicate=False)]
        if any(parameter_id in owned for parameter_id in fresh_ids) or len(set(fresh_ids)) != len(fresh_ids):
            raise ValueError("task module aliases a shared or previously registered parameter")
        self.task_modules[name] = module
        self._ready_tasks.add(name)
        self.assert_unique_parameters()

    def require_full_model(self) -> None:
        if self.unimplemented_tasks:
            raise UnimplementedTaskError(f"v3 full model has unimplemented tasks: {self.unimplemented_tasks}")

    def assert_unique_parameters(self) -> None:
        seen: set[int] = set()
        for name, parameter in self.named_parameters(remove_duplicate=False):
            if id(parameter) in seen:
                raise ValueError(f"optimizer parameter has multiple owners: {name}")
            seen.add(id(parameter))

    def optimizer_parameters(self) -> tuple[nn.Parameter, ...]:
        self.assert_unique_parameters()
        return tuple(parameter for parameter in self.parameters() if parameter.requires_grad)

    def forward_shared(self, batch: ArticleBatch, backbone: BackboneOutput) -> SharedForwardLease:
        """rc2의 all-valid L8 view와 공유 DCE/proposer만 실행한다; Gold를 받지 않는다."""
        batch.validate()
        if tuple(backbone.layer(8).shape[:3]) != tuple(batch.input_ids.shape):
            raise ValueError("backbone producer and source view shape differ")
        if (not torch.equal(backbone.attention_mask, batch.attention_mask)
                or not torch.equal(backbone.sentence_mask, batch.sentence_mask)):
            raise ValueError("backbone producer masks differ from source view")
        context = self.document_context(backbone.layer(8), batch.source_token_mask,
                                        batch.sentence_mask, batch.sentence_positions)
        proposals = self.semantic_proposer(context.token_states)
        return SharedForwardLease(token_states=context.token_states,
                                  sentence_states=context.sentence_states,
                                  document_state=context.document_state,
                                  proposal_logits=proposals)

    def initialization_manifest(self) -> dict:
        """task parameter별 owner·fresh provenance·byte digest; weight 파일을 만들지 않는다."""
        self.assert_unique_parameters()
        rows = []
        for name, parameter in self.named_parameters():
            owner = name.split(".", 1)[0]
            if owner == "task_modules":
                owner = name.split(".", 2)[1]
            payload = parameter.detach().cpu().contiguous().numpy().tobytes()
            rows.append({"name": name, "owner": owner, "shape": list(parameter.shape),
                         "dtype": str(parameter.dtype), "sha256": sha256(payload).hexdigest(),
                         "provenance": "FRESH_INIT_SAME_RUN"})
        return {
            "run_id": self.config.run_id,
            "seed": self.config.seed,
            "config_sha256": self.config.fingerprint(),
            "backbone": {"provenance": "FIXED_PRETRAINED_EXTERNAL_ONLY",
                         "model_id": self.config.backbone.model_id,
                         "revision": self.config.backbone.revision,
                         "weights_sha256": self.config.backbone.expected_weights_sha256},
            "ready_tasks": sorted(self._ready_tasks),
            "unimplemented_tasks": list(self.unimplemented_tasks),
            "parameter_count": sum(parameter.numel() for parameter in self.parameters()),
            "parameters": rows,
        }


class V3ArchitectureFactory:
    @staticmethod
    def fresh_core(config: V3ArchitectureConfig) -> V3Core:
        """전역 RNG를 보존하고 task checkpoint 접근 없이 fresh core를 만든다."""
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(config.seed)
            return V3Core(config)

    @staticmethod
    def full_model(config: V3ArchitectureConfig) -> V3Core:
        core = V3ArchitectureFactory.fresh_core(config)
        core.require_full_model()
        return core
