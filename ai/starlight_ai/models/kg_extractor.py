"""HF ArticleLocalKGPipeline wrapper."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from starlight_ai.device import DeviceName


class KGExtractor:
    def __init__(
        self,
        kg_dir: str | Path,
        *,
        device: DeviceName = "cpu",
        hf_cache: str | Path | None = None,
    ) -> None:
        import os

        self.bundle = Path(kg_dir).expanduser().resolve()
        config = self.bundle / "config" / "pipeline.json"
        if not config.is_file():
            raise FileNotFoundError(f"KG bundle missing config/pipeline.json: {self.bundle}")

        if hf_cache is not None:
            cache = str(Path(hf_cache).expanduser().resolve())
            os.environ["HF_HUB_CACHE"] = cache
            os.environ["ARTICLELOCAL_HF_CACHE"] = cache

        root = str(self.bundle)
        if root not in sys.path:
            sys.path.insert(0, root)

        from runtime import ArticleLocalKGPipeline

        self.device = device
        self._pipeline = ArticleLocalKGPipeline.from_config(
            config,
            repository_root=self.bundle,
            device=device,
        )

    def run(self, article: dict[str, Any]) -> dict[str, Any]:
        import torch

        with torch.inference_mode():
            result = self._pipeline.run(article)
        if hasattr(result, "to_dict"):
            return result.to_dict()
        if isinstance(result, dict):
            return result
        raise TypeError(f"Unexpected KG result type: {type(result)}")
