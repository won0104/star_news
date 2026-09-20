"""rc2의 pinned KF fast tokenizer를 task checkpoint 없이 로컬에서 검증해 연다."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
RC2_CONFIG = PROJECT / "runtime/configs/article-local-runtime-v22.json"


def local_snapshot() -> Path:
    payload = json.loads(RC2_CONFIG.read_text(encoding="utf-8"))["backbone"]
    model = str(payload["model_id"]).replace("/", "--")
    revision = str(payload["revision"])
    return PROJECT / "training/checkpoints/huggingface" / f"models--{model}" / "snapshots" / revision


def load_pinned_fast_tokenizer(snapshot: Path | None = None):
    """명시된 로컬 snapshot 파일의 SHA를 검사한다. 모델/legacy task weight는 열지 않는다."""
    from transformers import AutoTokenizer

    payload = json.loads(RC2_CONFIG.read_text(encoding="utf-8"))["backbone"]
    path = (snapshot or local_snapshot()).resolve()
    if path.name != payload["revision"]:
        raise ValueError("tokenizer snapshot revision differs from pinned backbone")
    for name in ("config.json", "special_tokens_map.json", "tokenizer.json",
                 "tokenizer_config.json", "vocab.txt"):
        file = path / name
        if not file.is_file() or sha256(file.read_bytes()).hexdigest() != payload["files_sha256"][name]:
            raise ValueError(f"pinned tokenizer file hash mismatch: {name}")
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, use_fast=True)
    if not tokenizer.is_fast:
        raise ValueError("pinned tokenizer must expose exact offset mapping")
    return tokenizer, payload["files_sha256"]["tokenizer.json"], payload["revision"]
