"""Per-event sentence embeddings."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from starlight_ai.device import DeviceName

DEFAULT_MODEL = "jhgan/ko-sroberta-multitask"


class EventEmbedder:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        *,
        device: DeviceName = "cpu",
        batch_size: int = 32,
        normalize: bool = True,
        cache_folder: str | None = None,
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.normalize = normalize
        kwargs: dict = {"device": device}
        if cache_folder:
            kwargs["cache_folder"] = cache_folder
        self.model = SentenceTransformer(model_name, **kwargs)
        dim_fn = getattr(self.model, "get_embedding_dimension", None)
        if callable(dim_fn):
            self.dim = int(dim_fn() or 768)
        else:
            self.dim = int(self.model.get_sentence_embedding_dimension() or 768)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vectors = self.model.encode(
            list(texts),
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize,
        )
        return np.asarray(vectors, dtype=np.float32)
