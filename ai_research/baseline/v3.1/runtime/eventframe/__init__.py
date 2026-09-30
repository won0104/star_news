"""Canonical EventFrame-centered experimental runtime.

The public boundary is intentionally small: construct from one immutable config,
run one raw Article, and serialize the result without importing experiment helpers.
"""

from .contracts import ArticleInput, ArticleLocalRuntimeResult
from .runtime import ArticleLocalRuntime

__all__ = ("ArticleInput", "ArticleLocalRuntime", "ArticleLocalRuntimeResult")
