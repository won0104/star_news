"""KPF topic classifiers (big / small / region)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from starlight_ai.device import DeviceName
from starlight_ai.topic_map import topic_name_ko

TOKENIZER = ("jinmang2/kpfbert", "dc732cc2aaa998959a2721e06ed10f98f2c51a0f")
CLASSIFIERS = {
    "small": ("KPF/KPF-bert-cls1", "44fa9bc436d47738fe10d962d89967fdfa7a513e"),
    "big": ("KPF/KPF-bert-cls2", "5ebc5e8b04623f06f4688a9e3d0949d72b2ebc89"),
    "region": ("KPF/KPF-bert-cls3", "35595966d84913290a146eb64df21982c0653151"),
}

_DEFAULT_LABELS = Path(__file__).resolve().parent.parent / "data" / "labels.json"


class KPFClassifier:
    def __init__(
        self,
        *,
        device: DeviceName = "cpu",
        cache_dir: str | None = None,
        labels_path: Path | None = None,
        local_files_only: bool = True,
    ) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.device = device
        options: dict[str, Any] = {"local_files_only": local_files_only}
        if cache_dir:
            options["cache_dir"] = cache_dir

        self.tokenizer = AutoTokenizer.from_pretrained(
            TOKENIZER[0], revision=TOKENIZER[1], **options
        )
        path = labels_path or _DEFAULT_LABELS
        self.labels = json.loads(path.read_text(encoding="utf-8"))
        self.models: dict[str, Any] = {}
        dtype = torch.float32
        for task, (repo, revision) in CLASSIFIERS.items():
            model = AutoModelForSequenceClassification.from_pretrained(
                repo,
                revision=revision,
                torch_dtype=dtype,
                **options,
            )
            model.to(device).eval()
            if model.config.num_labels != len(self.labels[f"{task}_label"]):
                raise ValueError(f"Label count mismatch: {repo}")
            self.models[task] = model

    def predict(self, content: str) -> dict[str, Any]:
        encoded = self.tokenizer(
            content,
            max_length=512,
            truncation=True,
            stride=128,
            return_overflowing_tokens=True,
            padding=True,
            return_tensors="pt",
        )
        encoded.pop("overflow_to_sample_mapping", None)
        count = encoded["input_ids"].shape[0]
        predictions: dict[str, list[dict[str, Any]]] = {}
        with self.torch.inference_mode():
            for task, model in self.models.items():
                scores = self.torch.zeros(model.config.num_labels, device=self.device)
                for i in range(count):
                    batch = {k: v[i : i + 1].to(self.device) for k, v in encoded.items()}
                    scores += model(**batch).logits[0].softmax(dim=-1)
                scores /= count
                values, ids = scores.topk(1 if task == "region" else 3)
                predictions[task] = [
                    {
                        "label": self.labels[f"{task}_label"][idx],
                        "label_id": int(idx),
                        "score": float(score),
                    }
                    for score, idx in zip(values.tolist(), ids.tolist())
                ]
        big = predictions["big"][0]["label"]
        small = next(
            (
                row["label"]
                for row in predictions["small"]
                if row["label"] in self.labels["BS_label"][big]
            ),
            big + "일반",
        )
        return {
            "big_cls": big,
            "small_cls": small,
            "region_cls": predictions["region"][0]["label"],
            "topic": topic_name_ko(big),
            "top_predictions": predictions,
            "windows": count,
            "device": self.device,
        }
