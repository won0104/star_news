"""Single-article analysis orchestration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from starlight_ai.adapter.neo4j_schema import adapt_to_schema
from starlight_ai.device import DeviceName, resolve_device
from starlight_ai.models.event_embedder import DEFAULT_MODEL, EventEmbedder
from starlight_ai.models.kg_extractor import KGExtractor
from starlight_ai.models.kpf_classifier import KPFClassifier
from starlight_ai.preprocess import preprocess_content

# Server volume defaults (CPU). Local overrides via env / constructor.
DEFAULT_KG_DIR = os.environ.get("KG_MODEL_DIR", "/models/artifacts/kg-extractor")
DEFAULT_HF_CACHE = os.environ.get(
    "ARTICLELOCAL_HF_CACHE",
    os.environ.get("HF_HUB_CACHE", "/models/cache/hub"),
)


def _event_text(node: dict[str, Any]) -> str:
    props = node.get("properties") or {}
    for key in ("canonical_text", "text", "name", "title"):
        if props.get(key):
            return str(props[key])
    return ""


class ArticleAnalyzer:
    """Lazy-loads models once; reuse across articles (worker-friendly)."""

    def __init__(
        self,
        *,
        device: str | None = None,
        kg_dir: str | Path | None = None,
        hf_cache: str | Path | None = None,
        embedding_model: str = DEFAULT_MODEL,
        local_files_only: bool = True,
        include_classified_as_edge: bool = False,
        enable_classification: bool = True,
        enable_embedding: bool = True,
    ) -> None:
        self.device: DeviceName = resolve_device(device)
        self.kg_dir = Path(kg_dir or DEFAULT_KG_DIR).expanduser()
        self.hf_cache = Path(hf_cache or DEFAULT_HF_CACHE).expanduser()
        self.embedding_model = embedding_model
        self.local_files_only = local_files_only
        self.include_classified_as_edge = include_classified_as_edge
        self.enable_classification = enable_classification
        self.enable_embedding = enable_embedding

        self._classifier: KPFClassifier | None = None
        self._kg: KGExtractor | None = None
        self._embedder: EventEmbedder | None = None

    def _ensure_classifier(self) -> KPFClassifier:
        if self._classifier is None:
            self._classifier = KPFClassifier(
                device=self.device,
                cache_dir=str(self.hf_cache),
                local_files_only=self.local_files_only,
            )
        return self._classifier

    def _ensure_kg(self) -> KGExtractor:
        if self._kg is None:
            self._kg = KGExtractor(
                self.kg_dir,
                device=self.device,
                hf_cache=self.hf_cache,
            )
        return self._kg

    def _ensure_embedder(self) -> EventEmbedder:
        if self._embedder is None:
            self._embedder = EventEmbedder(
                self.embedding_model,
                device=self.device,
            )
        return self._embedder

    def process(self, article: dict[str, Any]) -> dict[str, Any]:
        if not article.get("article_id"):
            raise ValueError("article_id is required")
        content = article.get("content") or article.get("raw_text") or article.get("article")
        if not content or not str(content).strip():
            raise ValueError("content is required")

        cleaned = preprocess_content(str(content))
        if not cleaned:
            raise ValueError("No usable content after preprocessing")

        work = dict(article)
        work["content"] = cleaned

        classification = None
        if self.enable_classification:
            classification = self._ensure_classifier().predict(cleaned)

        kg = self._ensure_kg().run(work)

        event_embeddings: dict[str, list[float]] = {}
        emb_dim = 768
        emb_model = self.embedding_model
        if self.enable_embedding:
            events = [
                n
                for n in (kg.get("nodes") or [])
                if str(n.get("kind") or "").upper() in {"EVENT", "LOCAL_EVENT"}
            ]
            texts = [_event_text(n) for n in events]
            ids = [str(n.get("node_id") or n.get("id")) for n in events]
            embedder = self._ensure_embedder()
            emb_dim = embedder.dim
            emb_model = embedder.model_name
            if texts:
                vectors = embedder.encode(texts)
                for nid, vec in zip(ids, vectors):
                    event_embeddings[nid] = [float(x) for x in vec.tolist()]

        result = adapt_to_schema(
            article=work,
            kg=kg,
            classification=classification,
            event_embeddings=event_embeddings,
            embedding_model=emb_model,
            embedding_dim=emb_dim,
            include_classified_as_edge=self.include_classified_as_edge,
        )
        result["meta"] = {
            **(result.get("meta") or {}),
            "device": self.device,
        }
        return result


def process_article(
    article: dict[str, Any],
    *,
    analyzer: ArticleAnalyzer | None = None,
    **analyzer_kwargs: Any,
) -> dict[str, Any]:
    """Analyze one article. Pass a shared ``ArticleAnalyzer`` in workers."""
    active = analyzer or ArticleAnalyzer(**analyzer_kwargs)
    result = active.process(article)
    result["meta"] = {
        **(result.get("meta") or {}),
        "device": active.device,
    }
    return result
