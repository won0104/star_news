"""Article-local inference entry points.

Training and experiment namespaces may produce checkpoints, but callers should use
this package for Gold-free runtime execution.
"""

from .eventframe import ArticleInput, ArticleLocalRuntime, ArticleLocalRuntimeResult
from .graph import (
    ArticleLocalKGAssembler, ArticleLocalKnowledgeGraphResult,
    CompactArticleLocalKGAssembler, CompactKnowledgeGraphResult,
    ResolvedGraphState,
)
from .pipeline import (
    ArticleLocalKGPipeline,
    GoldFreeKGPipelineConfig,
    load_goldfree_kg_pipeline_config,
)

__all__ = (
    "ArticleInput",
    "ArticleLocalRuntime",
    "ArticleLocalRuntimeResult",
    "ArticleLocalKGAssembler",
    "ArticleLocalKnowledgeGraphResult",
    "CompactArticleLocalKGAssembler",
    "CompactKnowledgeGraphResult",
    "ResolvedGraphState",
    "ArticleLocalKGPipeline",
    "GoldFreeKGPipelineConfig",
    "load_goldfree_kg_pipeline_config",
)
