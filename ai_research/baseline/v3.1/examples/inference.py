"""Run one article through the frozen D2/E1 PUBLIC release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime.v3_pretraining.project_release import load_project_release_worker


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--backbone-snapshot", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    args = parser.parse_args()
    row = json.loads(args.input.read_text(encoding="utf-8"))
    allowed = {"article_id", "content", "title", "article_version_id", "published_at"}
    if (not isinstance(row, dict) or not {"article_id", "content"} <= set(row) or
            any(key not in allowed for key in row) or
            not isinstance(row["article_id"], str) or
            not isinstance(row["content"], str)):
        raise ValueError("input must contain article_id/content and only PUBLIC arguments")
    worker = load_project_release_worker(
        args.bundle, backbone_snapshot=args.backbone_snapshot, device=args.device)
    print(json.dumps(worker.analyze_public(**row), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
