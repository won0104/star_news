"""Production relation ontology registry.

역사 checkpoint 재현을 위해 ``BaselineTaskRegistry``는 바꾸지 않는다. 이 registry는
non-relation adapter를 재사용하고 legacy 4-way Relation adapter만 세 독립 task family로
교체한다.
"""

from __future__ import annotations

from ..contracts import ModelConfig, PRODUCTION_RELATION_ONTOLOGY
from ..pairs.ontology import CausalHead, StatementAboutHead, SubeventHead
from .base import TaskRegistry
from .baseline import BaselineTaskRegistry, DirectedPairTaskAdapter


class ProductionTaskRegistry(TaskRegistry):
    """Legacy ``relation`` Head 없이 production_v1 task를 등록한다."""

    def __init__(self, config: ModelConfig) -> None:
        if config.relation_ontology_mode != PRODUCTION_RELATION_ONTOLOGY:
            raise ValueError("ProductionTaskRegistry requires production_v1 mode")
        taxonomy = config.taxonomy
        legacy = BaselineTaskRegistry(config)
        adapters = []
        for name, adapter in legacy.items():
            if name == "relation":
                adapters.extend(
                    (
                        DirectedPairTaskAdapter(
                            "causal",
                            CausalHead(config.pairs.hidden_size),
                            taxonomy.causal_labels,
                        ),
                        DirectedPairTaskAdapter(
                            "subevent",
                            SubeventHead(config.pairs.hidden_size),
                            taxonomy.subevent_labels,
                        ),
                        DirectedPairTaskAdapter(
                            "statement_about",
                            StatementAboutHead(config.pairs.hidden_size),
                            taxonomy.statement_about_labels,
                        ),
                    )
                )
                continue
            adapters.append(adapter)
        super().__init__(adapters)
