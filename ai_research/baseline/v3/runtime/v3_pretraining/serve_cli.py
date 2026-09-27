"""Local Gold-free v3 diagnostic serving entry point; never writes a database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import torch

from runtime.v3_pretraining.serving import load_diagnostic_worker


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a stage-13 smoke checkpoint on raw article JSON")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--input", type=Path, help="Raw article JSON; stdin when omitted")
    parser.add_argument("--no-primary", action="store_true", help="Lifecycle regression probe")
    parser.add_argument("--public-only", action="store_true",
                        help="Emit the validated PUBLIC graph without diagnostic audit")
    args = parser.parse_args(argv)
    article = json.loads(args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read())
    allowed = {"article_id", "article_version_id", "title", "content", "published_at"}
    if not isinstance(article, dict) or set(article) - allowed or not {"article_id", "content"} <= set(article):
        raise ValueError("input requires raw article_id/content and only declared metadata")
    torch.set_num_threads(4)
    worker = load_diagnostic_worker(args.checkpoint)
    if args.public_only:
        payload = worker.analyze_public(**article, enable_primary=not args.no_primary)
    else:
        result = worker.analyze(**article, enable_primary=not args.no_primary)
        payload = {"public": result.public, "audit": result.audit}
    print(json.dumps(payload, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
