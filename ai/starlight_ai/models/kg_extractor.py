"""HF KG bundle wrapper (v3 project release / v2.3 BoundedCandidate / ArticleLocalKGPipeline)."""

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
        if not self.bundle.is_dir():
            raise FileNotFoundError(f"KG bundle directory missing: {self.bundle}")

        if hf_cache is not None:
            cache = str(Path(hf_cache).expanduser().resolve())
            os.environ["HF_HUB_CACHE"] = cache
            os.environ["ARTICLELOCAL_HF_CACHE"] = cache

        root = str(self.bundle)
        if root not in sys.path:
            sys.path.insert(0, root)

        self.device = device
        self._v3 = False
        # v3 project release: manifest가 고정한 backbone snapshot으로 PUBLIC worker를 만든다.
        v3_release = self.bundle / "runtime" / "v3_pretraining" / "project_release.py"
        if v3_release.is_file():
            from runtime.v3_pretraining.project_release import load_project_release_worker

            snapshot = self._v3_backbone_snapshot(hf_cache)
            self._pipeline = load_project_release_worker(
                self.bundle, backbone_snapshot=snapshot, device=device
            )
            self._v3 = True
            return

        # v2.3 권장 엔트리(BoundedCandidate). 없으면 기존 pipeline.json 경로.
        bounded = (
            self.bundle / "runtime" / "candidate_routing" / "integrated.py"
        )
        if bounded.is_file():
            from runtime.candidate_routing.integrated import ArticleLocalBoundedCandidate

            candidate = ArticleLocalBoundedCandidate.load(device=device)
            candidate.eager_backbone()
            self._pipeline = candidate
            return

        config = self.bundle / "config" / "pipeline.json"
        if not config.is_file():
            raise FileNotFoundError(
                f"KG bundle missing config/pipeline.json: {self.bundle}"
            )

        from runtime import ArticleLocalKGPipeline

        self._pipeline = ArticleLocalKGPipeline.from_config(
            config,
            repository_root=self.bundle,
            device=device,
        )

    def _v3_backbone_snapshot(self, hf_cache: str | Path | None) -> Path:
        """release-manifest.json의 backbone model_id/revision을 HF cache snapshot 경로로 바꾼다."""
        import json
        import os

        manifest = json.loads((self.bundle / "release-manifest.json").read_text(encoding="utf-8"))
        backbone = manifest["backbone"]
        cache = Path(hf_cache or os.environ.get("HF_HUB_CACHE", "")).expanduser().resolve()
        repo_dir = "models--" + backbone["model_id"].replace("/", "--")
        snapshot = cache / repo_dir / "snapshots" / backbone["revision"]
        if not snapshot.is_dir():
            raise FileNotFoundError(f"KG v3 backbone snapshot missing: {snapshot}")
        return snapshot

    def run(self, article: dict[str, Any]) -> dict[str, Any]:
        import torch

        if self._v3:
            # v3 PUBLIC 입력은 허용 필드만 받으므로 서비스용 부가 필드(mysql_article_id 등)는 뺀다.
            kwargs: dict[str, Any] = {
                "article_id": str(article["article_id"]),
                "content": str(article["content"]),
            }
            for key in ("title", "article_version_id", "published_at"):
                if article.get(key):
                    kwargs[key] = str(article[key])
            # analyze_public은 자체 no_grad로 돈다. inference_mode 텐서는 v3 frozen feature
            # 검증("regular no_grad tensor")에서 거부되므로 감싸지 않는다.
            return self._pipeline.analyze_public(**kwargs)

        with torch.inference_mode():
            result = self._pipeline.run(article)
        if hasattr(result, "to_dict"):
            return result.to_dict()
        if isinstance(result, dict):
            return result
        raise TypeError(f"Unexpected KG result type: {type(result)}")
