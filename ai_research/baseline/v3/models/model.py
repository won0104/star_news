"""KF representations, task inductive bias, shared pair/context, deterministic boundaries 조립."""

from __future__ import annotations

from pathlib import Path

import torch
from torch import nn

from .backbone import KFDeBERTaBackbone
from .context import CandidateSpanEncoder, DocumentContextEncoder
from .contracts import (
    ArticleBatch,
    ArticleModelOutput,
    CandidateBatch,
    ConstructionOutput,
    ModelConfig,
    PairOutput,
    EVENT_ARGUMENT_ROLES,
    PRODUCTION_RELATION_ONTOLOGY,
    gather_candidates,
)
from .events.features import EventFeatureAssembler, EventFeatureEncoder
from .pairs.directed import DirectedPairEncoder
from .tasks import BaselineTaskRegistry, TaskRegistry
from .tasks.relation_ontology import ProductionTaskRegistry


class ArticleLocalKGModel(nn.Module):
    """교체 가능한 기준 model.

    Parameter sharing:
    - KF backbone: 모든 task 공유, 한 forward에서 L8/L10/L12 제공
    - L8 DocumentContextEncoder: Presence/Semantic/downstream span encoder 공유
    - CandidateSpanEncoder: StatementType와 모든 pair task 공유
    - DirectedPairEncoder: Assertor/Argument와 ontology별 relation family가 공유
    - Entity/Event coreference: class만 재사용하고 parameter는 전혀 공유하지 않음
    """

    def __init__(
        self,
        backbone: KFDeBERTaBackbone,
        config: ModelConfig,
        *,
        task_registry: TaskRegistry | None = None,
        directed_pair_encoder: DirectedPairEncoder | None = None,
        event_feature_encoder: EventFeatureEncoder | None = None,
    ) -> None:
        super().__init__()
        if backbone.hidden_size != config.context.input_hidden_size:
            raise ValueError("backbone/context hidden dimensions differ")
        self.config = config
        self.backbone = backbone
        self.document_context = DocumentContextEncoder(config.context)
        self.candidate_span_encoder = CandidateSpanEncoder(config.context, config.layers)
        self.tasks = task_registry or (
            ProductionTaskRegistry(config)
            if config.relation_ontology_mode == PRODUCTION_RELATION_ONTOLOGY
            else BaselineTaskRegistry(config)
        )
        self.directed_pair_encoder = directed_pair_encoder or DirectedPairEncoder(
            config.pairs,
            task_names=config.pair_tasks,
        )
        self.event_feature_assembler = EventFeatureAssembler(
            role_presence_threshold=config.event_role_presence_threshold
        )
        self.event_feature_encoder = event_feature_encoder or EventFeatureEncoder(
            config.pairs.hidden_size, config.dropout
        )

    @classmethod
    def from_pretrained(
        cls,
        config: ModelConfig | None = None,
        *,
        cache_dir: str | Path,
    ) -> "ArticleLocalKGModel":
        resolved = config or ModelConfig()
        return cls(
            KFDeBERTaBackbone.from_pretrained(resolved.backbone, cache_dir=cache_dir),
            resolved,
        )

    def forward(
        self,
        batch: ArticleBatch,
        candidates: CandidateBatch | None = None,
        *,
        event_threshold: float = 0.5,
        statement_threshold: float = 0.5,
        event_feature_mode: str | None = None,
        argument_pooling: str | None = None,
    ) -> ArticleModelOutput:
        if candidates is not None:
            candidates.validate(tuple(batch.input_ids.shape))
        backbone = self.backbone(batch)
        return self.forward_from_backbone(
            batch,
            backbone,
            candidates,
            event_threshold=event_threshold,
            statement_threshold=statement_threshold,
            event_feature_mode=event_feature_mode,
            argument_pooling=argument_pooling,
        )

    def forward_from_backbone(
        self,
        batch: ArticleBatch,
        backbone,
        candidates: CandidateBatch | None = None,
        *,
        event_threshold: float = 0.5,
        statement_threshold: float = 0.5,
        event_feature_mode: str | None = None,
        argument_pooling: str | None = None,
    ) -> ArticleModelOutput:
        """검증된 frozen-backbone cache를 기존 Head 경로에 주입한다.

        이 경계는 backbone 이후의 trainable representation을 캐시하지 않는다. 온라인
        ``forward``도 동일 경계를 호출하므로 cache/online orchestration 차이가 생기지 않는다.
        """

        if candidates is not None:
            candidates.validate(tuple(batch.input_ids.shape))
        if tuple(backbone.attention_mask.shape) != tuple(batch.attention_mask.shape):
            raise ValueError("cached backbone attention shape differs from article batch")
        if tuple(backbone.sentence_mask.shape) != tuple(batch.sentence_mask.shape):
            raise ValueError("cached backbone sentence shape differs from article batch")
        context = self.document_context(
            backbone.layer(self.config.layers.sentence_presence),
            batch.source_token_mask,
            batch.sentence_mask,
            batch.sentence_positions,
        )
        presence = self.tasks["sentence_presence"](
            sentence_states=context.sentence_states,
            sentence_mask=batch.sentence_mask,
            event_threshold=event_threshold,
            statement_threshold=statement_threshold,
        )
        # Presence output deliberately does not mask any span task.
        entity_adapter = self.tasks["entity"]
        entity = entity_adapter(
            token_states=backbone.layer(entity_adapter.representation_layer),
            token_mask=batch.source_token_mask,
        )
        time_adapter = self.tasks["time"]
        time = time_adapter(
            token_states=backbone.layer(time_adapter.representation_layer),
            token_mask=batch.source_token_mask,
        )
        trigger_adapter = self.tasks["trigger"]
        trigger = trigger_adapter(
            token_states=backbone.layer(trigger_adapter.representation_layer),
            token_mask=batch.source_token_mask,
        )
        semantic = self.tasks["semantic"](
            token_states=context.token_states,
            sentence_states=context.sentence_states,
            token_mask=batch.source_token_mask,
            proposals=None if candidates is None else candidates.semantic_proposal_indices,
            proposal_mask=None if candidates is None else candidates.semantic_proposal_mask,
        )
        construction = None
        if candidates is not None:
            construction = self._construction(
                backbone,
                context,
                batch.source_token_mask,
                candidates,
                event_feature_mode=event_feature_mode,
                argument_pooling=argument_pooling,
            )
        task_outputs = {
            "sentence_presence": presence,
            "entity": entity,
            "time": time,
            "trigger": trigger,
            "semantic": semantic,
        }
        if construction is not None:
            task_outputs["statement_type"] = construction.statement_type
            task_outputs.update(construction.pairs)
        return ArticleModelOutput(
            backbone=backbone,
            context=context,
            presence=presence,
            entity=entity,
            time=time,
            trigger=trigger,
            semantic=semantic,
            construction=construction,
            task_outputs=task_outputs,
        )

    def _construction(
        self,
        backbone,
        context,
        source_token_mask,
        candidates,
        *,
        event_feature_mode: str | None = None,
        argument_pooling: str | None = None,
    ) -> ConstructionOutput:
        candidate_states = self.candidate_span_encoder(
            backbone, context, candidates, source_token_mask
        )
        statement_states = gather_candidates(candidate_states, candidates.statement_indices)
        statement_type = self.tasks["statement_type"](
            states=statement_states, mask=candidates.statement_mask
        )
        outputs: dict[str, PairOutput] = {}
        # Argument는 EventFeatureBundle보다 먼저, relation family는 Event enrichment 후 실행한다.
        for name in ("assertor", "argument"):
            pairs = candidates.pairs[name]
            states, mask = self.directed_pair_encoder(
                candidate_states,
                candidates.span_indices,
                candidates.span_kind_ids,
                candidates.span_mask,
                pairs,
                context.document_state,
                task_name=name,
            )
            outputs[name] = self.tasks[name](
                pair_states=states,
                pair_mask=mask,
                class_mask=pairs.class_mask,
            )

        entity_pairs = candidates.pairs["entity_coreference"]
        outputs["entity_coreference"] = self.tasks["entity_coreference"](
            candidate_states=candidate_states,
            candidate_spans=candidates.span_indices,
            candidate_mask=candidates.span_mask,
            pairs=entity_pairs,
            document_state=context.document_state,
        )
        resolved_mode = event_feature_mode or (
            "oracle_teacher_forced"
            if candidates.oracle_argument_role_weights is not None
            else "predicted_cascaded"
        )
        role_weights = self._argument_role_weights(
            outputs["argument"],
            candidates,
            feature_mode=resolved_mode,
            pooling=argument_pooling or self.config.predicted_argument_pooling,
        )
        event_features = self.event_feature_assembler(
            candidate_states=candidate_states,
            candidates=candidates,
            sentence_states=context.sentence_states,
            document_state=context.document_state,
            argument_role_weights=role_weights,
            feature_source=resolved_mode,
        )
        event_states = self.event_feature_encoder(event_features)
        enriched_candidate_states = self._scatter_event_states(
            candidate_states, candidates, event_states
        )

        for name in self.config.hard_relation_tasks:
            relation_pairs = candidates.pairs[name]
            relation_states, relation_mask = self.directed_pair_encoder(
                enriched_candidate_states,
                candidates.span_indices,
                candidates.span_kind_ids,
                candidates.span_mask,
                relation_pairs,
                context.document_state,
                task_name=name,
            )
            outputs[name] = self.tasks[name](
                pair_states=relation_states,
                pair_mask=relation_mask,
                class_mask=relation_pairs.class_mask,
            )

        event_pairs = candidates.pairs["event_coreference"]
        outputs["event_coreference"] = self.tasks["event_coreference"](
            candidate_states=enriched_candidate_states,
            candidate_spans=candidates.span_indices,
            candidate_mask=candidates.span_mask,
            pairs=event_pairs,
            document_state=context.document_state,
        )
        return ConstructionOutput(
            candidate_states=enriched_candidate_states,
            statement_type=statement_type,
            pairs=outputs,
            event_features=event_features,
            event_states=event_states,
            event_feature_mode=resolved_mode,
        )

    def construct_from_encoded(
        self,
        output: ArticleModelOutput,
        source_token_mask: torch.BoolTensor,
        candidates: CandidateBatch,
        *,
        event_feature_mode: str = "predicted_cascaded",
        argument_pooling: str | None = None,
    ) -> ConstructionOutput:
        """decoded candidates를 두 번째 backbone forward 없이 construction Head에 전달한다."""

        candidates.validate(tuple(source_token_mask.shape))
        return self._construction(
            output.backbone,
            output.context,
            source_token_mask,
            candidates,
            event_feature_mode=event_feature_mode,
            argument_pooling=argument_pooling,
        )

    def _argument_role_weights(
        self,
        argument: PairOutput,
        candidates: CandidateBatch,
        *,
        feature_mode: str,
        pooling: str,
    ) -> torch.Tensor:
        if feature_mode == "oracle_teacher_forced":
            if candidates.oracle_argument_role_weights is None:
                raise ValueError("oracle Event features require oracle argument role weights")
            return candidates.oracle_argument_role_weights
        if feature_mode != "predicted_cascaded":
            raise ValueError("feature_mode must be oracle_teacher_forced or predicted_cascaded")
        if pooling not in {"decoded", "soft"}:
            raise ValueError("argument pooling must be decoded or soft")
        probabilities = torch.softmax(argument.logits, dim=-1)
        role_columns = []
        for role in EVENT_ARGUMENT_ROLES:
            try:
                role_columns.append(self.config.taxonomy.argument_labels.index(role))
            except ValueError as error:
                raise ValueError(f"Argument taxonomy lacks Event feature role {role}") from error
        if pooling == "soft":
            result = probabilities[..., role_columns]
        else:
            predicted = probabilities.argmax(dim=-1)
            result = torch.stack(
                [predicted.eq(label_id) for label_id in role_columns], dim=-1
            ).to(probabilities.dtype)
        return result * argument.mask.unsqueeze(-1)

    @staticmethod
    def _scatter_event_states(candidate_states, candidates, event_states):
        if candidate_states.shape[1] == 0 or candidates.event_indices.shape[1] == 0:
            return candidate_states
        one_hot = torch.nn.functional.one_hot(
            candidates.event_indices.clamp(0, candidate_states.shape[1] - 1),
            num_classes=candidate_states.shape[1],
        ).to(candidate_states.dtype)
        one_hot = one_hot * candidates.event_mask.unsqueeze(-1)
        updates = torch.einsum("ben,beh->bnh", one_hot, event_states)
        updated = one_hot.sum(dim=1).gt(0).unsqueeze(-1)
        return torch.where(updated, updates, candidate_states)

    def parameter_report(self) -> dict[str, dict[str, int]]:
        """top-level module별 total/trainable parameter 수를 중복 없이 보고한다."""

        report = {}
        for name, module in self.named_children():
            if name == "tasks":
                continue
            parameters = list(module.parameters())
            report[name] = {
                "total": sum(parameter.numel() for parameter in parameters),
                "trainable": sum(parameter.numel() for parameter in parameters if parameter.requires_grad),
            }
        for task_name, adapter in self.tasks.items():
            parameters = list(adapter.parameters())
            report[f"task/{task_name}"] = {
                "total": sum(parameter.numel() for parameter in parameters),
                "trainable": sum(
                    parameter.numel()
                    for parameter in parameters
                    if parameter.requires_grad
                ),
            }
        report["__model__"] = {
            "total": sum(parameter.numel() for parameter in self.parameters()),
            "trainable": sum(parameter.numel() for parameter in self.parameters() if parameter.requires_grad),
        }
        return report
