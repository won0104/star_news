"""교체 가능한 ArticleLocal-KG KF-DeBERTa 기준 모델."""

from .contracts import (
    ModelConfig,
    TaxonomyConfig,
    TriggerDecodeConfig,
    TriggerTrainingConfig,
)
from .model import ArticleLocalKGModel

__all__ = [
    "ArticleLocalKGModel",
    "ModelConfig",
    "TaxonomyConfig",
    "TriggerDecodeConfig",
    "TriggerTrainingConfig",
]
