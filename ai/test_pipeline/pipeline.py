"""One synthetic article -> CPU classification + KG -> readable result.json."""
import argparse
import gc
import json
import os
import re
import sys
import time
from pathlib import Path

# Set before importing torch / transformers / Hugging Face.
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
ROOT = Path(__file__).resolve().parent
CACHE = None


def require_cpu():
    import torch
    if torch.version.cuda is not None or torch.version.hip is not None:
        raise RuntimeError("Activate your CPU-only PyTorch environment.")
    torch.set_default_device("cpu")
    torch.set_num_threads(4)
    return torch

TOKENIZER = ('jinmang2/kpfbert', 'dc732cc2aaa998959a2721e06ed10f98f2c51a0f')
CLASSIFIERS = {'small': ('KPF/KPF-bert-cls1', '44fa9bc436d47738fe10d962d89967fdfa7a513e'), 'big': ('KPF/KPF-bert-cls2', '5ebc5e8b04623f06f4688a9e3d0949d72b2ebc89'), 'region': ('KPF/KPF-bert-cls3', '35595966d84913290a146eb64df21982c0653151')}

def preprocess_content(content: str, min_length: int = 10) -> list[str]:
    """Same line filtering as api_test.ipynb; output offsets use this cleaned text."""
    if not isinstance(content, str):
        raise ValueError("Article content must be a string.")
    paragraphs, seen = [], set()
    for paragraph in content.splitlines():
        paragraph = re.sub(r"\s+", " ", paragraph.strip())
        if not paragraph or len(paragraph) < min_length or "@" in paragraph:
            continue
        if not re.search(r'[.!?。？！]["\'”’)\]]*(?:\s*(?:\[[^\]]+\]|<[^>]+>))*$', paragraph):
            continue
        if paragraph not in seen:
            seen.add(paragraph)
            paragraphs.append(paragraph)
    return paragraphs

def cpu_modules(model):
    devices = {str(t.device) for t in list(model.parameters()) + list(model.buffers())}
    if devices - {"cpu"}:
        raise RuntimeError(f"Non-CPU model tensors found: {devices}")
    return sorted(devices)

class KPFClassifier:
    def __init__(self):
        self.torch = require_cpu()
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        options = {"cache_dir": CACHE, "local_files_only": True}
        self.tokenizer = AutoTokenizer.from_pretrained(TOKENIZER[0], revision=TOKENIZER[1], **options)
        self.labels = json.loads((ROOT / "labels.json").read_text(encoding="utf-8"))
        self.models = {}
        for task, (repo, revision) in CLASSIFIERS.items():
            model, info = AutoModelForSequenceClassification.from_pretrained(
                repo, revision=revision, torch_dtype=self.torch.float32,
                output_loading_info=True, **options,
            )
            if info.get("missing_keys") or info.get("mismatched_keys") or info.get("error_msgs"):
                raise RuntimeError(f"Incomplete classifier weights: {repo}: {info}")
            model.to("cpu").eval()
            cpu_modules(model)
            if model.config.num_labels != len(self.labels[f"{task}_label"]):
                raise ValueError(f"Label count mismatch: {repo}")
            if model.config.vocab_size != len(self.tokenizer):
                raise ValueError(f"Tokenizer vocabulary mismatch: {repo}")
            self.models[task] = model

    def predict(self, content):
        # Sliding windows keep long articles; process one window at a time on CPU.
        encoded = self.tokenizer(
            content, max_length=512, truncation=True, stride=128,
            return_overflowing_tokens=True, padding=True, return_tensors="pt",
        )
        encoded.pop("overflow_to_sample_mapping", None)
        count = encoded["input_ids"].shape[0]
        predictions = {}
        with self.torch.inference_mode():
            for task, model in self.models.items():
                scores = self.torch.zeros(model.config.num_labels, device="cpu")
                for i in range(count):
                    batch = {key: value[i:i + 1].to("cpu") for key, value in encoded.items()}
                    scores += model(**batch).logits[0].softmax(dim=-1)
                scores /= count
                values, ids = scores.topk(1 if task == "region" else 3)
                predictions[task] = [
                    {"label": self.labels[f"{task}_label"][idx], "label_id": idx, "score": score}
                    for score, idx in zip(values.tolist(), ids.tolist())
                ]
        big = predictions["big"][0]["label"]
        small = next((row["label"] for row in predictions["small"] if row["label"] in self.labels["BS_label"][big]), big + "일반")
        return {
            "big_cls": big, "small_cls": small,
            "region_cls": predictions["region"][0]["label"],
            "top_predictions": predictions, "windows": count,
            "aggregation": "mean_window_softmax", "device": "cpu",
            "model_revisions": CLASSIFIERS,
        }


# Server/container defaults: models live on the ai-cpu-models volume at /models.
DEFAULT_KG_DIR = "/models/artifacts/kg-extractor"
DEFAULT_HF_CACHE = "/models/cache/hub"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kg-dir",
        default=os.environ.get("KG_MODEL_DIR", DEFAULT_KG_DIR),
        help="KG bundle directory containing config/, runtime/, models/, weights/",
    )
    parser.add_argument(
        "--hf-cache",
        default=os.environ.get("ARTICLELOCAL_HF_CACHE", DEFAULT_HF_CACHE),
        help="Hugging Face hub cache directory (contains models--...)",
    )
    parser.add_argument("--input", type=Path, default=ROOT / "article.json")
    parser.add_argument("--output", type=Path, default=ROOT / "result.json")
    args = parser.parse_args()
    bundle = Path(args.kg_dir).expanduser().resolve()
    if not (bundle / "config" / "pipeline.json").is_file():
        parser.error(
            f"KG bundle must contain config/pipeline.json (looked in: {bundle})"
        )

    global CACHE
    CACHE = str(Path(args.hf_cache).expanduser().resolve())
    if not Path(CACHE).is_dir():
        parser.error(f"HF hub cache directory not found: {CACHE}")
    os.environ["HF_HUB_CACHE"] = CACHE
    os.environ["ARTICLELOCAL_HF_CACHE"] = CACHE

    torch = require_cpu()
    article = json.loads(args.input.read_text(encoding="utf-8-sig"))
    article["content"] = "\n".join(preprocess_content(article["content"]))
    if not article["content"]:
        raise ValueError("No usable content after preprocessing.")
    started = time.perf_counter()
    print("1/2 KPF classification on CPU...", flush=True)
    classifier = KPFClassifier()
    classification = classifier.predict(article["content"])
    del classifier
    gc.collect()

    print("2/2 KG extraction on CPU...", flush=True)
    sys.path.insert(0, str(bundle))
    from runtime import ArticleLocalKGPipeline
    pipeline = ArticleLocalKGPipeline.from_config(bundle / "config" / "pipeline.json", device="cpu")
    with torch.inference_mode():
        kg = pipeline.run(article).to_dict()
    passed = kg.get("validation", {}).get("status") == "PASS" and not kg.get("source_failures")
    nodes = []
    for node in kg["nodes"]:
        prop = node["properties"]
        label = next((prop[key] for key in ("canonical_name", "canonical_text", "text", "normalized_value", "title") if prop.get(key)), node["kind"])
        nodes.append({
            "id": node["node_id"], "kind": node["kind"], "text": label,
            **{key: prop[key] for key in ("entity_type", "statement_type") if key in prop},
        })
    names = {node["id"]: node["text"] for node in nodes}
    result = {
        "test_status": "PASSED" if passed else "FAILED",
        "device": "cpu",
        "article": article,
        "classification": {key: classification[key] for key in ("big_cls", "small_cls", "region_cls", "top_predictions")},
        "kg_status": kg["status"],
        "nodes": nodes,
        "edges": [{"type": e["edge_type"], "source": names[e["source_id"]], "target": names[e["target_id"]]} for e in kg["edges"]],
        "validation": kg["validation"]["status"],
        "source_failures": kg.get("source_failures", []),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{result['test_status']}: {len(nodes)} nodes, {len(kg['edges'])} edges -> {args.output}", flush=True)
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
