"""Fixed Curated-RC StatementType inference over predicted Statement spans."""

from __future__ import annotations

import time
from typing import Any, Mapping

import torch

from .models import StatementTypeRuntimeModel
from .preprocessing import PreparedArticle


class FixedStatementTypeRuntime:
    """Classify canonical predicted Statements without changing their inventory."""

    def __init__(
        self,
        model: StatementTypeRuntimeModel,
        config: Mapping[str, Any],
        checkpoint_sha: str,
    ) -> None:
        self.model = model
        self.config = config
        self.checkpoint_sha = checkpoint_sha
        self.labels = tuple(config["labels"])

    @torch.inference_mode()
    def run(self, prepared: PreparedArticle, backbone, statements):
        started = time.perf_counter()
        if any(row.get("kind") != "STATEMENT" for row in statements):
            raise ValueError("StatementType consumes only canonical Statement mentions")
        if not statements:
            return {}, {
                "stage": "④ 속성 판정부",
                "component": "StatementType",
                "checkpoint_sha": self.checkpoint_sha,
                "input_count": 0,
                "candidate_count": 0,
                "output_count": 0,
                "drop_reason_counts": {},
                "warnings": [],
                "elapsed_seconds": 0.0,
            }
        runtime_statements = [
            {
                "statement_id": row["prediction_id"],
                "aligned": [row["sentence_index"], row["token_start"], row["token_end"]],
            }
            for row in statements
        ]
        batch = prepared.batch.to(next(self.model.parameters()).device)
        self.model.eval()
        output = self.model.forward_statements(batch, backbone, runtime_statements)
        probabilities = torch.softmax(output.logits[0], dim=-1)
        predicted = probabilities.argmax(dim=-1)
        rows = {}
        for index, statement in enumerate(runtime_statements):
            label_index = int(predicted[index])
            rows[statement["statement_id"]] = {
                "status": "EXECUTED",
                "value": self.labels[label_index],
                "score": float(probabilities[index, label_index]),
                "probabilities": {
                    label: float(probabilities[index, label_id])
                    for label_id, label in enumerate(self.labels)
                },
                "checkpoint_sha": self.checkpoint_sha,
                "source_statement_prediction_id": statement["statement_id"],
                "provenance": {
                    "source": "CURATED_RC_FIXED_CHECKPOINT_PREDICTION",
                    "gold_statement_injected": False,
                    "statement_inventory_modified": False,
                },
            }
        return rows, {
            "stage": "④ 속성 판정부",
            "component": "StatementType",
            "checkpoint_sha": self.checkpoint_sha,
            "input_count": len(runtime_statements),
            "candidate_count": len(runtime_statements),
            "output_count": len(rows),
            "drop_reason_counts": {},
            "warnings": [],
            "elapsed_seconds": time.perf_counter() - started,
        }
