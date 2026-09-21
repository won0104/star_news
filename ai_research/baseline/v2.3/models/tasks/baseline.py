"""Baseline v1 task adapter 구현과 기본 registry factory.

각 adapter는 target tensorization, neural forward, loss, decode, metric contract를
소유한다. 공통 backbone/context/pair encoder는 model orchestration이 한 번만 생성한다.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import torch
from torch import nn
from torch.nn import functional as F

from ..attributes.statement_type import StatementTypeHead
from ..contracts import (
    BoundaryHeadOutput,
    ModelConfig,
    PairOutput,
    PresenceOutput,
    SemanticSpanOutput,
    TokenHeadOutput,
    TriggerDecodeConfig,
    TriggerTrainingConfig,
)
from ..decoding.spans import (
    BIOFlatDecoder,
    BoundaryProposalDecoder,
    DecodedSpan,
    GreedyOneToOneBoundaryDecoder,
    SemanticConstraintConfig,
    SemanticConstraintDecoder,
)
from ..pairs.argument import ArgumentHead
from ..pairs.assertor import AssertorHead
from ..pairs.entity_coreference import EntityCoreferenceHead
from ..pairs.event_coreference import EventCoreferenceHead
from ..pairs.relation import RelationHead
from ..sentence.presence import SentencePresenceHead
from ..spans.entity import EntityBIOHead
from ..spans.semantic import SemanticSpanHead
from ..spans.time import TimeBIOHead
from ..spans.trigger import TriggerBoundaryHead
from .base import (
    ClassificationLossStrategy,
    CrossEntropyLossStrategy,
    TargetBuildContext,
    TaskAdapter,
    TaskLossResult,
    TaskRegistry,
)
from .statistics import (
    binary_report,
    exact_item_report,
    multiclass_report,
    presence_report,
)
from .trigger import TriggerBoundaryLossStrategy


class SentencePresenceTaskAdapter(TaskAdapter):
    task_name = "sentence_presence"

    def __init__(self, head: SentencePresenceHead) -> None:
        super().__init__()
        self.head = head

    def build_targets(self, context):
        batch, sentences, _ = context.batch_shape
        target = torch.zeros(batch, sentences, 2)
        for span in context.aligned_spans.get("semantic", ()):
            if span.label == "EVENT":
                target[span.batch_index, span.sentence_index, 0] = 1.0
            elif span.label == "STATEMENT":
                target[span.batch_index, span.sentence_index, 1] = 1.0
        mask = context.sentence_mask.unsqueeze(-1).expand(-1, -1, 2).clone()
        return {"task/sentence_presence/bits": target, "task/sentence_presence/mask": mask}

    def forward(self, **kwargs):
        return self.head(
            kwargs["sentence_states"],
            kwargs["sentence_mask"],
            event_threshold=kwargs.get("event_threshold", 0.5),
            statement_threshold=kwargs.get("statement_threshold", 0.5),
        )

    def compute_loss(self, output, targets, *, options):
        bits = targets["task/sentence_presence/bits"]
        mask = targets["task/sentence_presence/mask"]
        event = _masked_bce(output.bit_logits[..., 0], bits[..., 0], mask[..., 0])
        statement = _masked_bce(
            output.bit_logits[..., 1], bits[..., 1], mask[..., 1]
        )
        state_target = bits[..., 0].long() + 2 * bits[..., 1].long()
        state = _masked_ce(output.state_logits, state_target, mask.all(dim=-1))
        weight = float(options.get("sentence_state_lambda", 0.25))
        return TaskLossResult(
            {self.task_name: event + statement + weight * state},
            {
                "sentence_presence/event_bce": event,
                "sentence_presence/statement_bce": statement,
                "sentence_presence/state_ce": state,
            },
        )

    def decode(self, output, **kwargs):
        del kwargs
        return output.state_ids

    def metric_records(self, output, targets):
        bits = targets["task/sentence_presence/bits"]
        active = targets["task/sentence_presence/mask"].all(dim=-1)
        return {
            "gold_bits": bits[active].long().cpu().tolist(),
            "bit_scores": torch.sigmoid(output.bit_logits[active]).cpu().tolist(),
        }

    def metrics(self, **records):
        return presence_report(
            records.get("gold_bits", ()),
            records.get("bit_scores", ()),
            event_threshold=float(records.get("event_threshold", 0.5)),
            statement_threshold=float(records.get("statement_threshold", 0.5)),
        )


class BIOExtractionTaskAdapter(TaskAdapter):
    """BIO family의 lifecycle; Entity/Time은 서로 다른 instance/head/layer를 쓴다."""

    def __init__(
        self,
        task_name: str,
        head: nn.Module,
        labels: Sequence[str],
        representation_layer: int,
    ) -> None:
        super().__init__()
        self.task_name = task_name
        self.head = head
        self.labels = tuple(labels)
        self.representation_layer = representation_layer

    def build_targets(self, context):
        target = torch.full(context.batch_shape, -100, dtype=torch.long)
        target[context.source_token_mask] = 0
        for span in context.aligned_spans.get(self.task_name, ()):
            target[span.batch_index, span.sentence_index, span.token_start] = self.labels.index(
                f"B-{span.label}"
            )
            if span.token_end - span.token_start > 1:
                target[
                    span.batch_index,
                    span.sentence_index,
                    span.token_start + 1 : span.token_end,
                ] = self.labels.index(f"I-{span.label}")
        return {f"task/{self.task_name}": target}

    def forward(self, **kwargs):
        return self.head(kwargs["token_states"], kwargs["token_mask"])

    def compute_loss(self, output, targets, *, options):
        del options
        target = targets[f"task/{self.task_name}"]
        loss = _token_ce(output.logits, target)
        return TaskLossResult(
            {self.task_name: loss}, {f"task/{self.task_name}": loss}
        )

    def decode(self, output, **kwargs):
        del kwargs
        nested = BIOFlatDecoder(self.labels).decode(output.logits, output.mask)
        return [
            [span for sentence in article for span in sentence] for article in nested
        ]

    def metrics(self, **records):
        return exact_item_report(records.get("gold", ()), records.get("predicted", ()))


class TriggerTaskAdapter(TaskAdapter):
    task_name = "trigger"

    def __init__(
        self,
        head: TriggerBoundaryHead,
        representation_layer: int,
        *,
        training_config: TriggerTrainingConfig | None = None,
        decode_config: TriggerDecodeConfig | None = None,
        loss_strategy: TriggerBoundaryLossStrategy | None = None,
    ) -> None:
        super().__init__()
        self.head = head
        self.representation_layer = representation_layer
        self.training_config = training_config or TriggerTrainingConfig()
        self.decode_config = decode_config or TriggerDecodeConfig()
        self.loss_strategy = loss_strategy or TriggerBoundaryLossStrategy(
            self.training_config
        )

    def replace_loss_strategy(self, strategy: TriggerBoundaryLossStrategy) -> None:
        """Head를 바꾸지 않고 boundary 학습 계약만 교체한다."""

        self.loss_strategy = strategy
        self.training_config = strategy.config

    def build_targets(self, context):
        shape = (*context.batch_shape, 1)
        start, end = torch.zeros(shape), torch.zeros(shape)
        for span in context.aligned_spans.get("trigger", ()):
            start[span.batch_index, span.sentence_index, span.token_start, 0] = 1.0
            end[span.batch_index, span.sentence_index, span.token_end - 1, 0] = 1.0
        return {"task/trigger/start": start, "task/trigger/end": end}

    def forward(self, **kwargs):
        return self.head(kwargs["token_states"], kwargs["token_mask"])

    def compute_loss(self, output, targets, *, options):
        loss, components = self.loss_strategy(
            output.start_logits,
            output.end_logits,
            targets["task/trigger/start"],
            targets["task/trigger/end"],
            output.mask,
            sample_step=int(options.get("trigger_sample_step", 0)),
        )
        components["task/trigger"] = loss
        return TaskLossResult({self.task_name: loss}, components)

    def decode(self, output, **kwargs):
        decoder = kwargs.get("decoder")
        if decoder is None:
            decoder_name = str(
                kwargs.get("decoder_name", self.decode_config.decoder)
            )
            common = {
                "labels": ("TRIGGER",),
                "threshold": float(
                    kwargs.get(
                        "boundary_threshold", self.decode_config.threshold
                    )
                ),
            }
            if decoder_name == "cartesian":
                decoder = BoundaryProposalDecoder(
                    **common,
                    max_width=int(
                        kwargs.get("max_width", self.decode_config.max_width)
                    ),
                )
            elif decoder_name == "greedy_one_to_one":
                output_cap = kwargs.get(
                    "max_outputs_per_sentence_label",
                    self.decode_config.max_outputs_per_sentence_label,
                )
                if output_cap is None:
                    raise ValueError("greedy Trigger decoder requires an output cap")
                decoder = GreedyOneToOneBoundaryDecoder(
                    **common,
                    max_width=int(
                        kwargs.get("max_width", self.decode_config.max_width)
                    ),
                    max_outputs_per_label_sentence=int(output_cap),
                )
            else:
                raise ValueError(f"unknown Trigger decoder: {decoder_name}")
        return [
            decoder.decode(
                output.start_logits[row], output.end_logits[row], output.mask[row]
            )
            for row in range(output.start_logits.shape[0])
        ]

    def metrics(self, **records):
        return exact_item_report(records.get("gold", ()), records.get("predicted", ()))


class SemanticTaskAdapter(TaskAdapter):
    task_name = "semantic"

    def __init__(
        self,
        head: SemanticSpanHead,
        labels: Sequence[str],
        representation_layer: int,
        max_span_width: int,
    ) -> None:
        super().__init__()
        self.head = head
        self.labels = tuple(labels)
        self.representation_layer = representation_layer
        self.max_span_width = max_span_width

    def replace_verifier(self, verifier: nn.Module) -> None:
        """Biaffine verifier ablation을 model/trainer 변경 없이 적용한다."""

        self.head.verifier = verifier

    def build_targets(self, context):
        shape = (*context.batch_shape, len(self.labels))
        start, end = torch.zeros(shape), torch.zeros(shape)
        for span in context.aligned_spans.get("semantic", ()):
            label = self.labels.index(span.label)
            start[span.batch_index, span.sentence_index, span.token_start, label] = 1.0
            end[span.batch_index, span.sentence_index, span.token_end - 1, label] = 1.0
        verify = torch.zeros(
            *context.semantic_proposal_shape, len(self.labels), dtype=torch.float
        )
        for proposal in context.aligned_proposals:
            for label in proposal.labels:
                verify[
                    proposal.batch_index,
                    proposal.proposal_index,
                    self.labels.index(label),
                ] = 1.0
        return {
            "task/semantic/start": start,
            "task/semantic/end": end,
            "task/semantic/verify": verify,
        }

    def forward(self, **kwargs):
        return self.head(
            kwargs["token_states"],
            kwargs["sentence_states"],
            kwargs["token_mask"],
            proposals=kwargs.get("proposals"),
            proposal_mask=kwargs.get("proposal_mask"),
        )

    def compute_loss(self, output, targets, *, options):
        del options
        boundary = _boundary_loss(
            output.boundaries.start_logits,
            output.boundaries.end_logits,
            targets["task/semantic/start"],
            targets["task/semantic/end"],
            output.boundaries.mask,
        )
        if output.proposal_logits is None or output.proposal_mask is None:
            raise ValueError("semantic training loss requires proposal verification")
        verification = _masked_bce(
            output.proposal_logits,
            targets["task/semantic/verify"],
            output.proposal_mask.unsqueeze(-1).expand_as(output.proposal_logits),
        )
        return TaskLossResult(
            {"semantic_boundary": boundary, "semantic_verification": verification},
            {
                "task/semantic_boundary": boundary,
                "task/semantic_verification": verification,
            },
        )

    def decode(self, output, **kwargs):
        return self.decode_diagnostics(output, **kwargs)["final"]

    def decode_diagnostics(self, output, **kwargs):
        token_states = kwargs["token_states"]
        sentence_states = kwargs["sentence_states"]
        token_mask = kwargs["token_mask"]
        proposal_decoder = BoundaryProposalDecoder(
            self.labels,
            float(kwargs.get("boundary_threshold", 0.5)),
            int(kwargs.get("max_width", self.max_span_width)),
        )
        constraint = SemanticConstraintDecoder(
            SemanticConstraintConfig(
                threshold=float(kwargs.get("verification_threshold", 0.5)),
                max_outputs_per_sentence=int(kwargs.get("max_outputs_per_sentence", 12)),
            )
        )
        boundary_rows = []
        final_rows = []
        for row in range(output.boundaries.start_logits.shape[0]):
            proposals = proposal_decoder.decode(
                output.boundaries.start_logits[row],
                output.boundaries.end_logits[row],
                output.boundaries.mask[row],
            )
            boundary_rows.append(proposals)
            if not proposals:
                final_rows.append([])
                continue
            unique = sorted({item.boundary for item in proposals})
            indices = torch.tensor(
                unique, device=token_states.device, dtype=torch.long
            ).unsqueeze(0)
            mask = torch.ones(1, len(unique), device=token_states.device, dtype=torch.bool)
            validity = torch.sigmoid(
                self.head.score_proposals(
                    token_states[row : row + 1],
                    sentence_states[row : row + 1],
                    indices,
                    mask,
                    token_mask[row : row + 1],
                )[0]
            )
            boundary_score = {
                (item.boundary, item.label): item.score for item in proposals
            }
            verified = []
            for proposal_index, boundary in enumerate(unique):
                for label_index, label in enumerate(self.labels):
                    if (boundary, label) not in boundary_score:
                        continue
                    score = (
                        boundary_score[(boundary, label)]
                        * float(validity[proposal_index, label_index])
                    ) ** 0.5
                    verified.append(DecodedSpan(*boundary, label, score))
            final_rows.append(constraint.decode(verified))
        return {"boundary_proposal": boundary_rows, "final": final_rows}

    def metric_records(self, output, targets):
        if output.proposal_logits is None or output.proposal_mask is None:
            return {}
        probabilities = torch.sigmoid(output.proposal_logits)
        target = targets["task/semantic/verify"]
        records = {}
        for label_index, label in enumerate(self.labels):
            active = output.proposal_mask
            records[f"verifier_gold/{label}"] = (
                target[..., label_index][active].long().cpu().tolist()
            )
            records[f"verifier_scores/{label}"] = (
                probabilities[..., label_index][active].cpu().tolist()
            )
        return records

    def metrics(self, **records):
        gold = records.get("gold", ())
        predicted = records.get("predicted", ())
        final = exact_item_report(gold, predicted)
        result = dict(final)
        result.update({f"final/{name}": value for name, value in final.items()})

        boundary = exact_item_report(
            gold, records.get("boundary_proposal_predicted", ())
        )
        result.update(
            {f"boundary_proposal/{name}": value for name, value in boundary.items()}
        )
        for label in self.labels:
            label_gold = [item for item in gold if len(item) > 1 and item[1] == label]
            label_final = [
                item for item in predicted if len(item) > 1 and item[1] == label
            ]
            label_boundary = [
                item
                for item in records.get("boundary_proposal_predicted", ())
                if len(item) > 1 and item[1] == label
            ]
            for stage, values in (
                ("final", exact_item_report(label_gold, label_final)),
                (
                    "boundary_proposal",
                    exact_item_report(label_gold, label_boundary),
                ),
            ):
                result.update(
                    {
                        f"{stage}/{label}/{name}": value
                        for name, value in values.items()
                    }
                )

        threshold = float(records.get("verification_threshold", 0.5))
        all_gold: list[int] = []
        all_scores: list[float] = []
        for label in self.labels:
            verifier_gold = records.get(f"verifier_gold/{label}", ())
            verifier_scores = records.get(f"verifier_scores/{label}", ())
            if not verifier_gold and not verifier_scores:
                continue
            report = binary_report(
                verifier_gold, verifier_scores, threshold=threshold
            )
            result.update(
                {
                    f"verifier/{label}/precision": report["positive_precision"],
                    f"verifier/{label}/recall": report["positive_recall"],
                    f"verifier/{label}/f1": report["positive_f1"],
                    f"verifier/{label}/pr_auc": report["pr_auc"],
                    f"verifier/{label}/support": report["support"],
                    f"verifier/{label}/positive_count": report["positive_count"],
                }
            )
            all_gold.extend(int(value) for value in verifier_gold)
            all_scores.extend(float(value) for value in verifier_scores)
        verifier = binary_report(all_gold, all_scores, threshold=threshold)
        result.update(
            {
                "verifier/precision": verifier["positive_precision"],
                "verifier/recall": verifier["positive_recall"],
                "verifier/f1": verifier["positive_f1"],
                "verifier/pr_auc": verifier["pr_auc"],
                "verifier/support": verifier["support"],
                "verifier/positive_count": verifier["positive_count"],
            }
        )
        return result


class StatementTypeTaskAdapter(TaskAdapter):
    task_name = "statement_type"

    def __init__(self, head: StatementTypeHead, labels: Sequence[str]) -> None:
        super().__init__()
        self.head = head
        self.labels = tuple(labels)
        self.loss_strategy = CrossEntropyLossStrategy()

    def build_targets(self, context):
        return {"task/statement_type": context.prepared_targets["statement_type"]}

    def forward(self, **kwargs):
        return self.head(kwargs["states"], kwargs["mask"])

    def compute_loss(self, output, targets, *, options):
        del options
        loss = self.loss_strategy(
            output.logits, targets["task/statement_type"], output.mask
        )
        return TaskLossResult({self.task_name: loss}, {"task/statement_type": loss})

    def decode(self, output, **kwargs):
        del kwargs
        probabilities = torch.softmax(output.logits, dim=-1)
        return probabilities.argmax(dim=-1), probabilities

    def metric_records(self, output, targets):
        target = targets["task/statement_type"]
        active = output.mask & target.ne(-100)
        probabilities = torch.softmax(output.logits[active], dim=-1)
        return {
            "gold": target[active].cpu().tolist(),
            "predicted": probabilities.argmax(dim=-1).cpu().tolist(),
            "probabilities": probabilities.cpu().tolist(),
        }

    def metrics(self, **records):
        return multiclass_report(
            records.get("gold", ()),
            records.get("predicted", ()),
            self.labels,
            probabilities=records.get("probabilities"),
        )


class DirectedPairTaskAdapter(TaskAdapter):
    def __init__(
        self,
        task_name: str,
        head: nn.Module,
        labels: Sequence[str],
        loss_strategy: ClassificationLossStrategy | None = None,
    ) -> None:
        super().__init__()
        self.task_name = task_name
        self.head = head
        self.labels = tuple(labels)
        self.loss_strategy = loss_strategy or CrossEntropyLossStrategy()

    def build_targets(self, context):
        return {
            f"task/{self.task_name}": context.prepared_targets[
                f"pair/{self.task_name}"
            ]
        }

    def forward(self, **kwargs):
        class_mask = kwargs.get("class_mask")
        if self.task_name == "assertor":
            return self.head(kwargs["pair_states"], kwargs["pair_mask"])
        return self.head(kwargs["pair_states"], kwargs["pair_mask"], class_mask)

    def compute_loss(self, output, targets, *, options):
        del options
        loss = self.loss_strategy(
            output.logits, targets[f"task/{self.task_name}"], output.mask
        )
        return TaskLossResult(
            {self.task_name: loss}, {f"task/{self.task_name}": loss}
        )

    def decode(self, output, **kwargs):
        del kwargs
        probabilities = torch.softmax(output.logits, dim=-1)
        return probabilities.argmax(dim=-1), probabilities

    def metric_records(self, output, targets):
        target = targets[f"task/{self.task_name}"]
        active = output.mask & target.ne(-100)
        probabilities = torch.softmax(output.logits[active], dim=-1)
        return {
            "gold": target[active].cpu().tolist(),
            "predicted": probabilities.argmax(dim=-1).cpu().tolist(),
            "probabilities": probabilities.cpu().tolist(),
        }

    def metrics(self, **records):
        positive = tuple(label for label in self.labels if label != "NONE")
        return multiclass_report(
            records.get("gold", ()),
            records.get("predicted", ()),
            self.labels,
            probabilities=records.get("probabilities"),
            positive_labels=positive,
        )


class CoreferenceTaskAdapter(TaskAdapter):
    """Entity/Event 각각 독립 Head와 독립 loss strategy를 소유한다."""

    def __init__(
        self,
        task_name: str,
        head: nn.Module,
        labels: Sequence[str],
        loss_strategy: ClassificationLossStrategy | None = None,
    ) -> None:
        super().__init__()
        self.task_name = task_name
        self.head = head
        self.labels = tuple(labels)
        self.loss_strategy = loss_strategy or CrossEntropyLossStrategy()

    def build_targets(self, context):
        return {
            f"task/{self.task_name}": context.prepared_targets[
                f"pair/{self.task_name}"
            ]
        }

    def forward(self, **kwargs):
        return self.head(
            kwargs["candidate_states"],
            kwargs["candidate_spans"],
            kwargs["candidate_mask"],
            kwargs["pairs"],
            kwargs["document_state"],
        )

    def compute_loss(self, output, targets, *, options):
        del options
        loss = self.loss_strategy(
            output.logits, targets[f"task/{self.task_name}"], output.mask
        )
        return TaskLossResult(
            {self.task_name: loss}, {f"task/{self.task_name}": loss}
        )

    def decode(self, output, **kwargs):
        del kwargs
        probabilities = torch.softmax(output.logits, dim=-1)
        return probabilities.argmax(dim=-1), probabilities

    def metric_records(self, output, targets):
        target = targets[f"task/{self.task_name}"]
        active = output.mask & target.ne(-100)
        probabilities = torch.softmax(output.logits[active], dim=-1)
        return {
            "gold": target[active].cpu().tolist(),
            "predicted": probabilities.argmax(dim=-1).cpu().tolist(),
            "probabilities": probabilities.cpu().tolist(),
        }

    def metrics(self, **records):
        probabilities = records.get("probabilities")
        predicted = records.get("predicted", ())
        if probabilities is not None:
            merge_id = self.labels.index("MERGE")
            threshold = float(records.get("threshold", 0.5))
            predicted = [
                merge_id if row[merge_id] >= threshold else self.labels.index("KEEP")
                for row in probabilities
            ]
        report = multiclass_report(
            records.get("gold", ()),
            predicted,
            self.labels,
            probabilities=probabilities,
            positive_labels=("MERGE",),
        )
        # Explicit stable keys required by sparse-coreference dashboards.
        report["MERGE/precision"] = report["per_class/MERGE/precision"]
        report["MERGE/recall"] = report["per_class/MERGE/recall"]
        report["MERGE/f1"] = report["per_class/MERGE/f1"]
        report["MERGE/pr_auc"] = report["per_class/MERGE/pr_auc"]
        report["cluster_metric/interface_available"] = 1.0
        return report


class BaselineTaskRegistry(TaskRegistry):
    """채택된 baseline Head만 등록한다. Experimental adapter는 명시 주입해야 한다."""

    def __init__(
        self,
        config: ModelConfig,
        *,
        entity_adapter: TaskAdapter | None = None,
        semantic_verifier: nn.Module | None = None,
        trigger_loss_strategy: TriggerBoundaryLossStrategy | None = None,
        entity_coreference_loss: ClassificationLossStrategy | None = None,
        event_coreference_loss: ClassificationLossStrategy | None = None,
    ) -> None:
        taxonomy = config.taxonomy
        adapters: list[TaskAdapter] = [
            SentencePresenceTaskAdapter(
                SentencePresenceHead(config.context.hidden_size, config.dropout)
            ),
            entity_adapter
            or BIOExtractionTaskAdapter(
                "entity",
                EntityBIOHead(
                    config.context.input_hidden_size,
                    config.head_hidden_size,
                    len(taxonomy.entity_bio_labels),
                    config.dropout,
                ),
                taxonomy.entity_bio_labels,
                config.layers.entity,
            ),
            BIOExtractionTaskAdapter(
                "time",
                TimeBIOHead(
                    config.context.input_hidden_size,
                    config.head_hidden_size,
                    len(taxonomy.time_bio_labels),
                    config.dropout,
                ),
                taxonomy.time_bio_labels,
                config.layers.time,
            ),
            TriggerTaskAdapter(
                TriggerBoundaryHead(
                    config.context.input_hidden_size,
                    config.head_hidden_size,
                    config.dropout,
                ),
                config.layers.trigger,
                training_config=config.trigger_training,
                decode_config=config.trigger_decode,
                loss_strategy=trigger_loss_strategy,
            ),
            SemanticTaskAdapter(
                SemanticSpanHead(
                    hidden_size=config.context.hidden_size,
                    labels=len(taxonomy.semantic_labels),
                    biaffine_size=config.semantic_biaffine_size,
                    max_span_width=config.context.max_span_width,
                    width_size=config.context.width_embedding_size,
                    dropout=config.dropout,
                    verifier=semantic_verifier,
                ),
                taxonomy.semantic_labels,
                config.layers.semantic,
                config.context.max_span_width,
            ),
            StatementTypeTaskAdapter(
                StatementTypeHead(
                    config.context.hidden_size,
                    len(taxonomy.statement_types),
                    config.dropout,
                ),
                taxonomy.statement_types,
            ),
            DirectedPairTaskAdapter(
                "assertor",
                AssertorHead(config.pairs.hidden_size, len(taxonomy.assertor_labels)),
                taxonomy.assertor_labels,
            ),
            DirectedPairTaskAdapter(
                "argument",
                ArgumentHead(config.pairs.hidden_size, len(taxonomy.argument_labels)),
                taxonomy.argument_labels,
            ),
            DirectedPairTaskAdapter(
                "relation",
                RelationHead(config.pairs.hidden_size, len(taxonomy.relation_labels)),
                taxonomy.relation_labels,
            ),
            CoreferenceTaskAdapter(
                "entity_coreference",
                EntityCoreferenceHead(
                    config.pairs, len(taxonomy.coreference_labels)
                ),
                taxonomy.coreference_labels,
                entity_coreference_loss,
            ),
            CoreferenceTaskAdapter(
                "event_coreference",
                EventCoreferenceHead(
                    config.pairs, len(taxonomy.coreference_labels)
                ),
                taxonomy.coreference_labels,
                event_coreference_loss,
            ),
        ]
        super().__init__(adapters)


def _token_ce(logits: torch.Tensor, target: torch.LongTensor) -> torch.Tensor:
    if not torch.any(target.ne(-100)):
        return logits.sum() * 0.0
    return F.cross_entropy(
        logits.reshape(-1, logits.shape[-1]), target.reshape(-1), ignore_index=-100
    )


def _masked_ce(logits, target, mask):
    active = mask & target.ne(-100)
    if not torch.any(active):
        return logits.sum() * 0.0
    return F.cross_entropy(logits[active], target[active])


def _masked_bce(logits, target, mask):
    if mask.shape != logits.shape:
        raise ValueError("BCE mask must match logits")
    if not torch.any(mask):
        return logits.sum() * 0.0
    return F.binary_cross_entropy_with_logits(
        logits[mask], target[mask].to(logits.dtype)
    )


def _boundary_loss(start_logits, end_logits, start_target, end_target, token_mask):
    mask = token_mask.unsqueeze(-1).expand_as(start_logits)
    return _masked_bce(start_logits, start_target, mask) + _masked_bce(
        end_logits, end_target, mask
    )
